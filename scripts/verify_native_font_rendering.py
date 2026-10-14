"""Measure experimental Windows text modes; never admit fingerprint capabilities."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime
from app.core.native import canvas_fidelity
from scripts import native_canvas_formats, native_font_contexts, native_font_rendering
from scripts.verify_native_branding import measure_branding_resources
from scripts.verify_native_privacy_units import require_idle_builder
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core

MODES = ("off", "native", "aliased", "grayscale", "cleartype-rgb", "cleartype-bgr")
PATCH = ROOT / "native/patches/0062-native-windows-font-rasterization.patch"


@dataclass(frozen=True)
class RenderingConfiguration(NativeConfiguration):
    rasterization: str = "off"

    def validate(self) -> None:
        super().validate()
        if not isinstance(self.rasterization, str) or self.rasterization not in MODES:
            raise ValueError("Unknown experimental Windows font mode")

    def launch_arguments(self) -> list[str]:
        arguments = super().launch_arguments()
        if self.rasterization != "off":
            arguments.append("--glint-windows-font-rasterization=" + self.rasterization)
        return arguments


def compare(control: dict, candidate: dict) -> dict:
    if (not isinstance(control, dict) or not isinstance(candidate, dict)
            or set(control) != set(native_font_contexts.SCOPES) or set(candidate) != set(control)):
        raise ValueError("Font comparison requires all eight scopes")
    result = {}
    for scope in native_font_contexts.SCOPES:
        first, second = control[scope], candidate[scope]
        native_font_contexts.validate_scope(scope, first)
        native_font_contexts.validate_scope(scope, second)
        result[scope] = {
            "text": native_font_rendering.compare_control(first["text"], second["text"]),
            "fidelity": canvas_fidelity.compare_control(first["fidelity"], second["fidelity"]),
            "formats": native_canvas_formats.compare_control(first["formats"], second["formats"]),
            "consistency_changed": (native_font_rendering.consistency_observations(first["text"])
                                    != native_font_rendering.consistency_observations(second["text"])),
        }
    return result


def assess(runs: dict) -> dict:
    if (not isinstance(runs, dict) or set(runs) != set(MODES)
            or any(not isinstance(value, list) or len(value) != 2 for value in runs.values())):
        raise ValueError("Each font mode requires two complete profile starts")
    restarts = {mode: compare(values[0], values[1]) for mode, values in runs.items()}
    controls = {mode: compare(runs["off"][0], runs[mode][0]) for mode in MODES[1:]}
    failures = []
    for mode, rounds in runs.items():
        for round_index, scopes in enumerate(rounds):
            for scope, value in scopes.items():
                observations = native_font_rendering.consistency_observations(value["text"])
                if (any(item["operation"] in {"repeat", "pngRepeat"} for item in observations)
                        or any(row["repeat"]["changedChannels"] for row in value["fidelity"]["rows"])):
                    failures.append({"mode": mode, "round": round_index, "scope": scope,
                                     "reason": "repeated-read-or-export-is-unstable"})
    for mode, scopes in restarts.items():
        for scope, observed in scopes.items():
            if (observed["text"] or not observed["fidelity"]["matches_control"]
                    or observed["formats"] or observed["consistency_changed"]):
                failures.append({"mode": mode, "scope": scope, "reason": "restart-changed-observation"})
    for mode, scopes in controls.items():
        for scope, observed in scopes.items():
            if (not observed["fidelity"]["matches_control"] or observed["formats"]
                    or observed["consistency_changed"] or (mode == "native" and observed["text"])):
                failures.append({"mode": mode, "scope": scope, "reason": "control-compatibility-changed"})
    effect = any(
        first["hashes"]["pixels"] != second["hashes"]["pixels"]
        for scope in native_font_contexts.SCOPES
        for first, second in zip(runs["aliased"][0][scope]["text"]["rows"],
                                 runs["grayscale"][0][scope]["text"]["rows"], strict=True))
    if not effect:
        failures.append({"reason": "no-measured-aliased-versus-grayscale-pixel-effect"})
    return {"passed": not failures, "failures": failures, "restarts": restarts,
            "controls": controls, "aliased_grayscale_pixel_effect": effect}


async def verify(executable: Path, destination: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("Windows font rendering verification requires Windows")
    require_idle_builder()
    if executable != executable.resolve() or not executable.is_file() or executable.name != "chrome.exe":
        raise ValueError("An explicit canonical Chrome executable is required")
    if (destination != destination.resolve() or destination.exists() or not destination.parent.is_dir()
            or destination.is_relative_to(ROOT) or destination.is_relative_to(executable.parent)):
        raise ValueError("Fresh private evidence outside the repository/runtime is required")
    receipt_path = executable.parent / "camouflow-build.json"
    if (receipt_path != receipt_path.resolve() or not receipt_path.is_file()
            or receipt_path.stat().st_size > 1024 * 1024):
        raise ValueError("A bounded compiled receipt is required")
    receipt = receipt_path.read_bytes()
    record = json.loads(receipt.decode("utf-8-sig"))
    core = measure_runtime_core(executable)
    expected = {"name": PATCH.name, "sha256": hashlib.sha256(PATCH.read_bytes()).hexdigest()}
    if (not isinstance(record, dict) or record.get("platform") != "win32"
            or record.get("binary") != "chrome.exe" or record.get("runtime_core_sha256_measured") != core
            or not isinstance(record.get("patches"), list) or record["patches"].count(expected) != 1):
        raise ValueError("The exact compiled font policy and runtime core receipt are required")
    inputs = [PATCH, Path(__file__), ROOT / "scripts/native_font_contexts.py",
              ROOT / "scripts/native_font_rendering.py", ROOT / "scripts/native_canvas_formats.py",
              ROOT / "app/core/native/canvas_fidelity.py"]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    resources = measure_branding_resources(executable)
    destination.mkdir()
    report = {"passed": False, "scope": __doc__, "capability_admitted": False,
              "runtime_core_sha256_measured": core, "inputs_sha256": before,
              "resource_pack_sha256": resources, "runs": {}, "errors": []}
    server = None
    thread = None
    server_started = False
    try:
        server = FixtureServer(("127.0.0.1", 0), native_font_contexts.FontFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        server_started = True
        for mode in MODES:
            report["runs"][mode] = []
            for round_index in range(2):
                runtime = NativeRuntime(destination / "profiles" / mode, executable,
                                        RenderingConfiguration(rasterization=mode))
                try:
                    context = await runtime.start(headless=True)
                    page = await context.new_page()
                    measured = await native_font_contexts.collect(page, f"http://127.0.0.1:{server.server_address[1]}")
                    report["runs"][mode].append(measured)
                except Exception as error:
                    report["errors"].append({"mode": mode, "round": round_index,
                                              "error": type(error).__name__ + ": " + str(error)})
                finally:
                    try:
                        await runtime.close()
                    except Exception as error:
                        report["errors"].append({"mode": mode, "round": round_index,
                                                  "cleanup_error": type(error).__name__ + ": " + str(error)})
                    if runtime.has_resources:
                        raise RuntimeError("Font probe retains browser resources; remaining modes were not run")
                    (destination / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        if not report["errors"]:
            report["assessment"] = assess(report["runs"])
            report["passed"] = report["assessment"]["passed"]
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    finally:
        if server is not None:
            if server_started:
                server.shutdown()
            server.server_close()
        if server_started:
            thread.join(timeout=5)
        try:
            report["inputs_unchanged"] = (
                core == measure_runtime_core(executable) and receipt == receipt_path.read_bytes()
                and resources == measure_branding_resources(executable)
                and before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs})
        except (ValueError, OSError) as error:
            report["inputs_unchanged"] = False
            report["guard_error"] = type(error).__name__ + ": " + str(error)
        report["passed"] = report["passed"] and report["inputs_unchanged"]
        (destination / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        report = asyncio.run(verify(arguments.executable, arguments.output))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Font rendering verification failed: {error}\n")
    print(json.dumps({key: report.get(key) for key in ("passed", "errors", "error", "inputs_unchanged")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
