# Copyright 2026 CamouFlow contributors.
# SPDX-License-Identifier: MIT
"""Windows native-off/CfT/native-off exact-bit gate; no privacy admission."""

import argparse
import asyncio
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import runpy
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
DRAFT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_version(observed: dict, version: str, revision: str, *, dummy: bool) -> None:
    expected = "0" * 40 if dummy else revision
    if (not isinstance(observed, dict) or observed.get("product") != "Chrome/" + version
            or observed.get("revision") != "@" + expected):
        raise ValueError("Browser version/revision differs from the explicitly selected control mode")


def decode_capture(observed: dict, case: dict) -> bytes:
    if (not isinstance(observed, dict) or observed.get("id") != case["id"]
            or observed.get("frames") != case["frames"] or observed.get("sampleRate") != case["rate"]
            or observed.get("channelCount") != 2 or observed.get("eventSameBuffer") is not True
            or observed.get("closed") is not True):
        raise ValueError("Audio capture shape or completion lifecycle differs from the fixture")
    encoded = observed.get("samplesBase64")
    expected_bytes = case["frames"] * 4
    if (not isinstance(encoded, list) or len(encoded) != 2
            or any(not isinstance(value, str) or len(value) != 4 * ((expected_bytes + 2) // 3) for value in encoded)):
        raise ValueError("Audio capture channel encoding exceeds or differs from its bound")
    channels = [base64.b64decode(value, validate=True) for value in encoded]
    if any(len(value) != expected_bytes for value in channels):
        raise ValueError("Audio channel length differs from its fixture")
    raw = b"".join(channels)
    if any(not math.isfinite(value[0]) for value in struct.iter_unpack("<f", raw)):
        raise ValueError("Finite-signal Audio fixture produced a non-finite sample")
    return raw


def compare(before: bytes, stock: bytes, after: bytes) -> dict:
    if not before or len(before) % 4 or len(before) != len(stock) or len(before) != len(after):
        raise ValueError("Audio comparisons require equal, nonempty float32 buffers")
    return {"native_repeat_exact": before == after, "native_and_stock_exact": before == stock == after,
            "native_sha256": hashlib.sha256(before).hexdigest(),
            "stock_sha256": hashlib.sha256(stock).hexdigest(),
            "native_after_sha256": hashlib.sha256(after).hexdigest(),
            "mismatched_channel_samples": sum(before[i:i + 4] != stock[i:i + 4] for i in range(0, len(before), 4)),
            "native_repeat_mismatched_channel_samples": sum(before[i:i + 4] != after[i:i + 4] for i in range(0, len(before), 4))}


def inside_compiled_checkout(output: Path, executable: Path) -> bool:
    build_root = executable.parent.parent
    return build_root.name.casefold() == "out" and output.is_relative_to(build_root.parent)


def verify(args: argparse.Namespace) -> dict:
    output = args.output
    if (os.name != "nt" or not output.is_absolute() or output.drive.upper() != "D:"
            or output != output.resolve() or not output.parent.is_dir()
            or output.is_relative_to(ROOT)
            or any(output.is_relative_to(path.parent) or inside_compiled_checkout(output, path)
                   for path in (args.native_executable, args.stock_executable))):
        raise ValueError("Use a fresh, absolute, unlinked output directory on D: outside the code/binaries")
    output.mkdir(exist_ok=False)
    report = {"schema": 1, "passed": False, "scope": __doc__, "self_pid": os.getpid(),
              "preflight_completed": False, "measurement_complete": False,
              "native_policy_enabled": False, "audio_math_included": False,
              "same_build_flags_verified": False, "variant_device_cohort_verified": False,
              "privacy_admitted": False, "production_admitted": False,
              "native_dummy_revision_acknowledged": args.allow_native_dummy_revision,
              "phases": [], "comparisons": []}
    inputs = {}
    reviewed_project_paths = None

    def project_paths():
        return (set((ROOT / "app").rglob("*.py")) | set((ROOT / "scripts").glob("verify_native_*.py"))
                | set((ROOT / "scripts").glob("native_*.py")) | {ROOT / "scripts/package_native_windows.py"})

    previous_data = os.environ.get("CAMOUFLOW_DATA_DIR")
    os.environ["CAMOUFLOW_DATA_DIR"] = str(output / "workspace")

    def save():
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")

    save()
    try:
        from app.core.native.configuration import NativeConfiguration
        from app.core.native.runtime import NativeRuntime
        from scripts.native_build import load_candidate
        from scripts.package_native_windows import read_record, validate_build_receipt
        from scripts.verify_native_privacy_units import require_idle_builder
        from scripts.verify_native_runtime import measure_runtime_core

        for executable in (args.native_executable, args.stock_executable):
            if not executable.is_absolute() or executable != executable.resolve() or not executable.is_file() or executable.name != "chrome.exe":
                raise ValueError("Select explicit, installed and unlinked chrome.exe binaries")
        require_idle_builder(args.native_executable.parent)
        candidate = load_candidate("upstream-156")
        stock_path = DRAFT.parent / "upstream-156/stock-control-observations.json"
        stock_control = read_record(stock_path)
        published_path = DRAFT / "matched-stock-observations.json"
        published = read_record(published_path)
        receipt_path = args.native_executable.parent / "camouflow-build.json"
        args_path = args.native_executable.parent / "args.gn"
        receipt = read_record(receipt_path)
        validate_build_receipt(receipt, candidate["lock"], candidate=candidate)
        native_core = measure_runtime_core(args.native_executable)
        stock_core = measure_runtime_core(args.stock_executable)
        if native_core != receipt.get("runtime_core_sha256_measured") or stock_core != stock_control.get("stock_core_sha256"):
            raise ValueError("A selected executable/DLL differs from its source-bound receipt/control")
        if receipt.get("binary_sha256_measured") != native_core["chrome.exe"] or receipt.get("args_sha256") != checksum(args_path):
            raise ValueError("Native executable or GN arguments differ from their compiled receipt")
        if (stock_control.get("passed") is not True or stock_control.get("exact_stock_runtime_source_verified") is not True
                or stock_control.get("target_revision") != candidate["lock"]["chromium_revision"]
                or stock_control.get("target_version") != candidate["lock"]["chromium_version"]):
            raise ValueError("Official stock control does not match the candidate upstream base")
        if args.allow_native_dummy_revision and (checksum(receipt_path) != published["candidate_build_receipt_sha256"]
                                                or native_core != published["native_core_sha256"]):
            raise ValueError("Dummy revision acknowledgement is restricted to the published, inspected native checkpoint")
        case_raw, cases = runpy.run_path(str(DRAFT / "matrix.py"))["load_cases"](DRAFT / "cases.json")
        probe_path = DRAFT / "compressor-matrix-control.js"
        probe_raw = probe_path.read_bytes()
        if (hashlib.sha256(case_raw).hexdigest() != published["cases_sha256"]
                or hashlib.sha256(probe_raw).hexdigest() != published["probe_sha256"]):
            raise ValueError("Published Audio fixture bytes changed; review and rebind before comparison")
        reviewed_project_paths = project_paths()
        paths = (reviewed_project_paths
                 | {Path(__file__).resolve(), DRAFT / "matrix.py",
                    DRAFT / "cases.json", probe_path, stock_path, published_path,
                    candidate["directory"] / "manifest.json", receipt_path, args_path}
                 | {candidate["directory"] / "patches" / row["file"] for row in candidate["manifest"]["patches"]}
                 | {args.native_executable.parent / name for name in native_core}
                 | {args.stock_executable.parent / name for name in stock_core})
        if any(path != path.resolve() or not path.is_file() for path in paths):
            raise ValueError("A measurement input is missing or linked")
        inputs = {path: checksum(path) for path in paths}
        expected_cores = ({args.native_executable.parent / name: digest for name, digest in native_core.items()}
                          | {args.stock_executable.parent / name: digest for name, digest in stock_core.items()})
        if (any(inputs[path] != digest for path, digest in expected_cores.items())
                or inputs[args_path] != receipt["args_sha256"]
                or inputs[candidate["directory"] / "manifest.json"] != candidate["manifest_sha256"]):
            raise ValueError("A compiled core/GN/manifest input changed during preflight")
        report.update(preflight_completed=True, native_core_sha256=native_core, stock_core_sha256=stock_core,
                      native_receipt_sha256=checksum(receipt_path), candidate_manifest_sha256=candidate["manifest_sha256"],
                      stock_control_sha256=checksum(stock_path), cases_sha256=hashlib.sha256(case_raw).hexdigest(),
                      probe_sha256=hashlib.sha256(probe_raw).hexdigest(), measured_input_count=len(inputs),
                      project_input_sha256={path.relative_to(ROOT).as_posix(): digest for path, digest in sorted(inputs.items())
                                            if path.is_relative_to(ROOT)})
        save()
        buffers = {}

        async def phase(label, executable):
            folder = output / label
            folder.mkdir()
            measured = {"label": label, "passed": False, "captures": []}
            report["phases"].append(measured)
            runtime = NativeRuntime(folder / "owned-profile", executable, NativeConfiguration())
            failure = None
            try:
                context = await runtime.start(headless=True)
                session = await asyncio.wait_for(context.browser.new_browser_cdp_session(), timeout=10)
                version_failure = None
                try:
                    observed_version = await asyncio.wait_for(session.send("Browser.getVersion"), timeout=10)
                    measured["browser_get_version"] = {key: observed_version.get(key) for key in ("product", "revision")}
                    save()
                    validate_version(observed_version, candidate["lock"]["chromium_version"],
                                     candidate["lock"]["chromium_revision"],
                                     dummy=args.allow_native_dummy_revision and label != "stock")
                except BaseException as error:
                    version_failure = error
                    raise
                finally:
                    try:
                        await asyncio.wait_for(session.detach(), timeout=5)
                    except Exception as error:
                        if version_failure is None:
                            raise
                        version_failure.add_note("CDP cleanup failed: " + str(error))

                async def respond(route):
                    if route.request.url == "http://127.0.0.1/glint-audio-matrix":
                        await route.fulfill(content_type="text/html", body="<!doctype html><title>Owned Audio A/B/A</title>")
                    else:
                        await route.abort("blockedbyclient")
                await context.route("**/*", respond)
                page = context.pages[0]
                await page.goto("http://127.0.0.1/glint-audio-matrix", timeout=10000)
                for case in cases:
                    owned = folder / case["id"]
                    owned.mkdir()
                    repeated = []
                    for iteration in range(3):
                        observed = await asyncio.wait_for(page.evaluate(probe_raw.decode("utf-8"), case), timeout=20)
                        try:
                            raw = decode_capture(observed, case)
                        except Exception:
                            (owned / (str(iteration) + ".error.json")).write_text(json.dumps(observed, indent=2), encoding="utf-8")
                            raise
                        (owned / (str(iteration) + ".f32")).write_bytes(raw)
                        measured["captures"].append({"id": case["id"], "iteration": iteration,
                                                     "raw_sha256": hashlib.sha256(raw).hexdigest()})
                        repeated.append(raw)
                        save()
                    if repeated[0] != repeated[1] or repeated[0] != repeated[2]:
                        raise ValueError(f"Within-phase Audio output is nondeterministic at {label}/{case['id']}; no retry performed")
                    buffers[label, case["id"]] = repeated[0]
                measured["passed"] = True
            except BaseException as error:
                failure = error
                raise
            finally:
                try:
                    await runtime.close()
                except Exception as error:
                    measured["cleanup_error"] = str(error)[:1000]
                    if failure is None:
                        raise
                    failure.add_note("Runtime cleanup failed: " + str(error))
                finally:
                    measured["resources_closed"] = not runtime.has_resources
                    save()

        async def collect():
            for label, executable in (("native-before", args.native_executable), ("stock", args.stock_executable), ("native-after", args.native_executable)):
                await asyncio.wait_for(phase(label, executable), timeout=240)
        asyncio.run(collect())
        report["comparisons"] = [{"id": case["id"], **compare(*(buffers[label, case["id"]]
            for label in ("native-before", "stock", "native-after")))} for case in cases]
        report["measurement_complete"] = True
        report["capture_count"] = sum(len(phase["captures"]) for phase in report["phases"])
        report["native_matches_stock_all_cases"] = all(row["native_and_stock_exact"] for row in report["comparisons"])
        report["native_repeat_stable_all_cases"] = all(row["native_repeat_exact"] for row in report["comparisons"])
        report["passed"] = (report["capture_count"] == len(cases) * 9
            and report["native_matches_stock_all_cases"] and report["native_repeat_stable_all_cases"]
            and all(row["resources_closed"] and "cleanup_error" not in row for row in report["phases"]))
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error)[:1000],
                      error_notes=[note[:1000] for note in getattr(error, "__notes__", [])])
    finally:
        try:
            report["postguards_passed"] = (bool(inputs) and project_paths() == reviewed_project_paths
                                           and all(checksum(path) == digest for path, digest in inputs.items()))
        except Exception as error:
            report.update(postguards_passed=False, postguard_error=str(error)[:1000])
        report["passed"] = report["passed"] and report["postguards_passed"]
        if previous_data is None:
            os.environ.pop("CAMOUFLOW_DATA_DIR", None)
        else:
            os.environ["CAMOUFLOW_DATA_DIR"] = previous_data
        save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-executable", required=True, type=Path)
    parser.add_argument("--stock-executable", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Fresh owned output directory on D:")
    parser.add_argument("--allow-native-dummy-revision", action="store_true",
                        help="Explicitly acknowledge the published non-official native checkpoint's dummy CDP stamp")
    args = parser.parse_args()
    try:
        report = verify(args)
    except Exception as error:
        print(f"Audio browser matrix failed ({type(error).__name__}): {error}", file=sys.stderr)
        return 1
    print(json.dumps({key: value for key, value in report.items() if key not in ("phases", "comparisons", "project_input_sha256")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
