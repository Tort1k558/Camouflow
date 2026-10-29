"""Build Chromium's official Windows archive staging without replacing its receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import native_build as build
from scripts.package_native_windows import read_record
from scripts.verify_native_privacy_units import require_idle_builder

STAGING_RELATIVE = Path("gen/chrome/installer/mini_installer/mini_installer/temp_installer_archive/Chrome-bin")
TARGET = "chrome/installer/mini_installer:mini_installer_archive"


def stage(workspace: Path, report: Path, *, vs_installation: Path | None = None, jobs: int = 4,
          candidate_name: str | None = None, git_ssl_backend: str = "openssl", local_toolchain: bool = False) -> dict:
    if sys.platform != "win32":
        raise ValueError("Official Native staging currently supports Windows only")
    candidate = None if candidate_name is None else build.load_candidate(candidate_name)
    lock = build.LOCK if candidate is None else candidate["lock"]
    if type(local_toolchain) is not bool or (local_toolchain and candidate is None):
        raise ValueError("Local Windows toolchain staging requires an explicit candidate")
    if type(jobs) is not int or not 1 <= jobs <= min(4, lock["build_jobs"]):
        raise ValueError("Native staging requires 1..4 jobs")
    if candidate is None:
        build.preflight(workspace)
    else:
        build.preflight(workspace, lock=lock)
    build.candidate_workspace(workspace, candidate)
    with build.workspace_lock(workspace):
        return _stage_locked(workspace, report, vs_installation=vs_installation, jobs=jobs, candidate=candidate,
                             lock=lock, git_ssl_backend=git_ssl_backend, local_toolchain=local_toolchain)


def _stage_locked(workspace: Path, report: Path, *, vs_installation: Path | None, jobs: int,
                  candidate: dict | None, lock: dict, git_ssl_backend: str, local_toolchain: bool) -> dict:
    source = workspace / "chromium/src"
    output = source / "out/CamouFlowNative"
    staged = output / STAGING_RELATIVE
    if (source != source.resolve() or not source.is_dir() or output != output.resolve()
            or staged != staged.resolve() or not staged.is_relative_to(output)):
        raise ValueError("Official staging must stay inside the canonical owned build output")
    if (not report.is_absolute() or report != report.resolve() or not report.parent.is_dir()
            or report.is_relative_to(source) or report.is_relative_to(ROOT)):
        raise ValueError("A new canonical report outside both repositories is required")
    log_path = report.with_name(report.stem + "-build.log")
    if any(path.exists() or path.is_symlink() for path in (report, log_path)):
        raise ValueError("Refusing to overwrite Native staging evidence")
    require_idle_builder(workspace)
    env = (build.environment(workspace, git_ssl_backend=git_ssl_backend, local_toolchain=local_toolchain)
           if candidate is not None or git_ssl_backend != "openssl" else build.environment(workspace))
    env.update(GOMEMLIMIT="3GiB", PYTHONIOENCODING="utf-8")
    if vs_installation is not None:
        if vs_installation != vs_installation.resolve() or not vs_installation.is_dir():
            raise ValueError("Visual Studio installation must be canonical and installed")
        if local_toolchain and str(vs_installation) != env.get("vs2026_install"):
            raise ValueError("Visual Studio selection differs from the prepared local toolchain")
        env["vs2026_install"] = str(vs_installation)
    def source_state():
        build.candidate_workspace(workspace, candidate)
        if build.run(["git", "rev-parse", "HEAD"], source, env, capture=True) != lock["chromium_revision"]:
            raise ValueError("Chromium revision differs from the pinned build lock")
        for name in ("sync", "hooks"):
            if candidate is None:
                build.require_stage(workspace / "chromium", name)
            else:
                build.require_stage(workspace / "chromium", name, candidate)
        return (build.candidate_source_patches(source, env, candidate) if candidate is not None else
                build.source_patches(source, env) + build.v8_source_patches(source, env))
    receipt_path = output / "camouflow-build.json"
    receipt_bytes = receipt_path.read_bytes()
    receipt = read_record(receipt_path)
    arguments = (output / "args.gn").read_bytes()
    public_arguments = (ROOT / "native/args.gn").read_bytes()
    core = build.measure_runtime_core(output / "chrome.exe")
    patches = source_state()
    expected = {"schema": 1, "platform": "win32", "binary": "chrome.exe",
                "native_version": lock["native_version"],
                "chromium_revision": lock["chromium_revision"],
                "depot_tools_revision": lock["depot_tools_revision"],
                **({"candidate_manifest_sha256": candidate["manifest_sha256"]} if candidate is not None else {}),
                **({"local_windows_toolchain_sha256": env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]}
                   if local_toolchain else {})}
    if (any(type(receipt.get(key)) is not type(value) or receipt[key] != value for key, value in expected.items())
            or receipt.get("runtime_core_sha256_measured") != core
            or receipt.get("binary_sha256_measured") != core["chrome.exe"]
            or receipt.get("args_sha256") != hashlib.sha256(arguments).hexdigest()
            or arguments.decode("utf-8-sig").replace("\r\n", "\n") != public_arguments.decode("utf-8-sig").replace("\r\n", "\n")
            or receipt.get("patches") != patches):
        raise ValueError("A matching pinned build receipt/core/GN/patch chain is required before staging")
    proof = {"passed": False, "scope": "Official archive staging only; not relocated runtime or policy admission",
             "target": TARGET, "jobs": jobs, "staged": str(staged), "log": str(log_path),
             "runtime_core_sha256_measured": core,
             **({"candidate": candidate["name"], "candidate_manifest_sha256": candidate["manifest_sha256"]}
                if candidate is not None else {}),
             **({"local_windows_toolchain_sha256": env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]}
                if local_toolchain else {}),
             "build_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(), "patches": patches}
    with log_path.open("x", encoding="utf-8", newline="\n") as log:
        try:
            build.check_patch_dependencies(source, env)
            subprocess.run(build.depot_command("autoninja", workspace) +
                           ["-C", "out/CamouFlowNative", "-j", str(jobs), TARGET],
                           cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            version = lock["chromium_version"]
            staged_core = build.measure_runtime_core(staged / "chrome.exe", staged / version)
            if staged_core != core:
                raise ValueError("Official staging differs from the verified browser core")
            proof.update(passed=True, staged_runtime_core_sha256_measured=staged_core)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            proof["error"] = type(error).__name__ + ": " + str(error)
        finally:
            try:
                proof["inputs_unchanged"] = (
                    build.measure_runtime_core(output / "chrome.exe") == core
                    and receipt_path.read_bytes() == receipt_bytes
                    and (output / "args.gn").read_bytes() == arguments
                    and (ROOT / "native/args.gn").read_bytes() == public_arguments
                    and source_state() == patches
                    and (not local_toolchain or build.local_windows_toolchain(workspace)["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]
                         == env["GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256"]))
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                proof["inputs_unchanged"] = False
                proof["guard_error"] = type(error).__name__ + ": " + str(error)
            proof["passed"] = proof["passed"] and proof["inputs_unchanged"]
            with report.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(proof, stream, indent=2)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--vs-installation", type=Path)
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--candidate", choices=("upstream-156",))
    parser.add_argument("--git-ssl-backend", choices=("openssl", "schannel"), default="openssl")
    parser.add_argument("--local-windows-toolchain", action="store_true")
    args = parser.parse_args()
    try:
        proof = stage(args.workspace, args.report, vs_installation=args.vs_installation, jobs=args.jobs,
                      candidate_name=args.candidate, git_ssl_backend=args.git_ssl_backend,
                      local_toolchain=args.local_windows_toolchain)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Native staging failed: {error}\n")
    print(json.dumps({key: proof.get(key) for key in ("passed", "staged", "error", "inputs_unchanged")}))
    return 0 if proof["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
