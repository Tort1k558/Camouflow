"""Build native unit executables once, then collect every selected target result.

Windows source-build fixtures only, not browser/privacy/production admission.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts import verify_native_privacy_units as units
from scripts.package_native_windows import read_record, validate_build_receipt
from scripts.verify_native_runtime import measure_runtime_core

ARTIFACT_VOLUME = "D:"


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_inputs(candidate: dict) -> set[Path]:
    return (set((ROOT / "app").rglob("*.py"))
            | set((ROOT / "scripts").glob("verify_native_*.py"))
            | set((ROOT / "scripts").glob("native_*.py"))
            | {Path(__file__).resolve(), ROOT / "scripts/package_native_windows.py",
               ROOT / "native/build-lock.json", ROOT / "native/args.gn",
               candidate["directory"] / "manifest.json"}
            | {candidate["directory"] / "patches" / row["file"] for row in candidate["manifest"]["patches"]})


def verify(workspace: Path, report_dir: Path, targets: tuple[str, ...], *,
           candidate_name: str, jobs: int = 4, vs_installation: Path | None = None,
           git_ssl_backend: str = "openssl", local_toolchain: bool = False,
           timeout_seconds: int = 300) -> dict:
    if sys.platform != "win32":
        raise ValueError("Native unit batch verification currently supports Windows only")
    if (not isinstance(targets, (tuple, list)) or not targets
            or any(type(target) is not str or target not in units.SUPPORTED_TARGETS for target in targets)
            or len(targets) != len(set(targets))):
        raise ValueError("Select distinct, explicit supported native targets")
    if type(local_toolchain) is not bool:
        raise ValueError("Local toolchain selection must be an explicit boolean")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 900:
        raise ValueError("Native case deadline must be between 1 and 900 seconds")
    candidate = build.load_candidate(candidate_name)
    lock = candidate["lock"]
    if type(jobs) is not int or not 1 <= jobs <= min(4, lock["build_jobs"]):
        raise ValueError("Native unit batches require 1..4 jobs")
    build.preflight(workspace, lock=lock)
    build.candidate_workspace(workspace, candidate)
    source = workspace / "chromium/src"
    if source != source.resolve() or not source.is_dir():
        raise ValueError("A canonical pinned Chromium checkout is required")
    if (not report_dir.is_absolute() or report_dir.drive.upper() != ARTIFACT_VOLUME
            or report_dir != report_dir.resolve() or not report_dir.parent.is_dir()
            or report_dir.is_relative_to(source) or report_dir.is_relative_to(ROOT)
            or report_dir.exists() or report_dir.is_symlink()):
        raise ValueError("Select a fresh canonical report directory on D: outside both repositories")
    with build.workspace_lock(workspace):
        units.require_idle_builder(workspace)
        report_dir.mkdir(exist_ok=False)
        return _verify_locked(workspace, report_dir, tuple(targets), candidate=candidate, jobs=jobs,
                              vs_installation=vs_installation, git_ssl_backend=git_ssl_backend,
                              local_toolchain=local_toolchain, timeout_seconds=timeout_seconds)


def _verify_locked(workspace: Path, report_dir: Path, targets: tuple[str, ...], *, candidate: dict,
                   jobs: int, vs_installation: Path | None, git_ssl_backend: str,
                   local_toolchain: bool, timeout_seconds: int) -> dict:
    source = workspace / "chromium/src"
    output = source / "out/CamouFlowNative"
    report = {"schema": 1, "passed": False, "scope": __doc__, "platform": "win32",
              "candidate": candidate["name"], "candidate_manifest_sha256": candidate["manifest_sha256"],
              "source_chromium_revision": candidate["lock"]["chromium_revision"],
              "chromium_version": candidate["lock"]["chromium_version"],
              "requested_targets": list(targets), "jobs": jobs, "targets": [],
              "build_invocations": 0, "postguards_passed": False,
              "browser_runtime_verified": False, "privacy_admitted": False, "production_admitted": False}
    inputs = {}
    paths = set()
    initial = {}
    env = None

    def save():
        (report_dir / "batch.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")

    save()
    try:
        env = units.verification_environment(workspace, vs_installation, git_ssl_backend, local_toolchain)
        temporary = report_dir / "temp"
        temporary.mkdir(exist_ok=False)
        env.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
        report["temporary_directory"] = temporary.name
        patches = units.verified_source_chain(workspace, candidate, candidate["lock"], env)
        delivery = {target: units.require_target_sources(source, patches, target) for target in targets}
        paths = source_inputs(candidate)
        if any(path != path.resolve() or not path.is_file() for path in paths):
            raise ValueError("A batch verification input is missing or linked")
        inputs = {path: checksum(path) for path in paths}
        receipt_path, args_path = output / "camouflow-build.json", output / "args.gn"
        receipt_raw, args_raw = receipt_path.read_bytes(), args_path.read_bytes()
        receipt = read_record(receipt_path)
        validate_build_receipt(receipt, candidate["lock"], candidate=candidate)
        core = measure_runtime_core(output / "chrome.exe")
        if (receipt.get("runtime_core_sha256_measured") != core
                or receipt.get("binary_sha256_measured") != core["chrome.exe"]
                or receipt.get("args_sha256") != hashlib.sha256(args_raw).hexdigest()
                or args_raw.decode("utf-8-sig").replace("\r\n", "\n") != (ROOT / "native/args.gn").read_text(encoding="utf-8-sig")):
            raise ValueError("Compiled browser core/GN differs from its exact source-build receipt")
        if local_toolchain and receipt.get("local_windows_toolchain_sha256") != env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]:
            raise ValueError("Compiled receipt uses a different local Windows toolchain")
        initial = {"patches": patches, "delivery": delivery, "core": core,
                   "receipt_raw": receipt_raw, "args_raw": args_raw}
        binaries = sorted({units.unit_binary_target(target) for target in targets})
        report.update(build_targets=binaries, runtime_core_sha256_measured=core,
                      build_receipt_sha256=hashlib.sha256(receipt_raw).hexdigest(),
                      inputs_sha256={str(path): value for path, value in inputs.items()})
        if local_toolchain:
            report["local_windows_toolchain_sha256"] = env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]
        save()
        with (report_dir / "build.log").open("x", encoding="utf-8", newline="\n") as log:
            build.check_patch_dependencies(source, env)
            report["build_invocations"] = 1
            save()
            subprocess.run(build.depot_command("autoninja", workspace)
                           + ["-C", "out/CamouFlowNative", "-j", str(jobs), *binaries],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        binary_hashes = {name: checksum(output / (name + ".exe")) for name in binaries}
        initial["binary_hashes"] = binary_hashes
        for target in targets:
            required = units.required_tests(target)
            results = report_dir / (target + "-tests.json")
            name = units.unit_binary_target(target)
            row = {"target": target, "build_target": name, "native_cases_passed": False,
                   "test_binary_sha256": binary_hashes[name], "results": results.name}
            try:
                selected = ":".join(suite + "." + case for suite, cases in required.items() for case in sorted(cases))
                with (report_dir / (target + ".log")).open("x", encoding="utf-8", newline="\n") as log:
                    completed = subprocess.run([str(output / (name + ".exe")), "--gtest_filter=" + selected,
                                               "--single-process-tests", "--gtest_output=json:" + str(results)],
                                              cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT,
                                              timeout=timeout_seconds, check=False)
                row["returncode"] = completed.returncode
                if completed.returncode != 0:
                    raise ValueError("Native case process exited unsuccessfully")
                units.validate_results(read_record(results), target=target)
                row.update(native_cases_passed=True, tests=sum(map(len, required.values())),
                           result_sha256=checksum(results))
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                row.update(error_type=type(error).__name__, error=str(error))
            report["targets"].append(row)
            save()
        report["passed"] = len(report["targets"]) == len(targets) and all(row["native_cases_passed"] for row in report["targets"])
    except Exception as error:
        report.update(passed=False, error_type=type(error).__name__, error=str(error))
    finally:
        try:
            if not initial or source_inputs(candidate) != paths or any(checksum(path) != value for path, value in inputs.items()):
                raise ValueError("Batch source/tool inputs changed or preflight did not finish")
            if (measure_runtime_core(output / "chrome.exe") != initial["core"]
                    or (output / "camouflow-build.json").read_bytes() != initial["receipt_raw"]
                    or (output / "args.gn").read_bytes() != initial["args_raw"]
                    or units.verified_source_chain(workspace, candidate, candidate["lock"], env) != initial["patches"]):
                raise ValueError("Batch changed baseline browser, receipt, GN or ordered patch inputs")
            for target, before in initial["delivery"].items():
                if before is not None and units.snapshot_delivery_sources(source) != before:
                    raise ValueError("Delivery source inputs changed during the batch")
            if local_toolchain and build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"] != env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]:
                raise ValueError("Local Windows toolchain changed during the batch")
            for name, before in initial.get("binary_hashes", {}).items():
                if checksum(output / (name + ".exe")) != before:
                    raise ValueError("A unit executable changed during case execution")
            report["postguards_passed"] = True
        except Exception as error:
            report.update(postguards_passed=False, postguard_error=str(error))
        report["passed"] = report["passed"] and report["postguards_passed"]
        save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--targets", choices=units.SUPPORTED_TARGETS, nargs="+", required=True)
    parser.add_argument("--candidate", choices=("upstream-156",), required=True)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--vs-installation", type=Path)
    parser.add_argument("--git-ssl-backend", choices=("openssl", "schannel"), default="openssl")
    parser.add_argument("--local-windows-toolchain", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    try:
        result = verify(args.workspace, args.report_dir, tuple(args.targets), candidate_name=args.candidate,
                        jobs=args.jobs, vs_installation=args.vs_installation,
                        git_ssl_backend=args.git_ssl_backend, local_toolchain=args.local_windows_toolchain,
                        timeout_seconds=args.timeout_seconds)
    except Exception as error:
        print(f"Native batch verification failed ({type(error).__name__}): {error}", file=sys.stderr)
        return 1
    print(json.dumps({"passed": result["passed"], "report": str(args.report_dir / "batch.json")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
