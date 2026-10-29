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
from app.core.native.privacy import FONT_RASTERIZATION_MODES, TEXT_TUNING_ARGUMENTS
from app.core.native import canvas_fidelity
from scripts import native_build, native_canvas_formats, native_canvas_hdr, native_font_contexts, native_font_rendering, native_font_visuals
from scripts import native_font_workloads
from scripts.verify_native_branding import measure_branding_resources
from scripts.verify_native_privacy_units import require_idle_builder
from scripts.verify_native_runtime import FixtureServer, STORAGE, measure_runtime_core

MODES = ("off", *FONT_RASTERIZATION_MODES)
TEXT_TUNING_CASES = {"off" if name == "native" else name: arguments
                     for name, arguments in TEXT_TUNING_ARGUMENTS.items()}
PATCH = ROOT / "native/patches/0062-native-windows-font-rasterization.patch"


def series_modes(series: str) -> tuple[str, ...]:
    if series == "rasterization":
        return MODES
    if series == "text-tuning":
        return tuple(TEXT_TUNING_CASES)
    raise ValueError("Unknown rendering verification series")


@dataclass(frozen=True)
class RenderingConfiguration(NativeConfiguration):
    rasterization: str = "off"

    def validate(self) -> None:
        super().validate()
        if not isinstance(self.rasterization, str) or self.rasterization not in (*MODES, *TEXT_TUNING_CASES):
            raise ValueError("Unknown experimental Windows font mode")
        if self.rasterization != "off" and (self.privacy_policy.text_tuning != "native"
                                             or self.privacy_policy.font_rasterization != "native"):
            raise ValueError("Research rendering flags must not override an explicit profile rendering policy")

    def launch_arguments(self, *, admission=None) -> list[str]:
        arguments = super().launch_arguments(admission=admission)
        if self.rasterization in TEXT_TUNING_CASES:
            arguments.extend(TEXT_TUNING_CASES[self.rasterization])
        else:
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
            "hdr": native_canvas_hdr.compare_control(first["hdr"], second["hdr"]),
            "consistency_changed": (native_font_rendering.consistency_observations(first["text"])
                                    != native_font_rendering.consistency_observations(second["text"])),
        }
    return result


def assess(runs: dict, *, series: str = "rasterization") -> dict:
    modes = series_modes(series)
    if (not isinstance(runs, dict) or set(runs) != set(modes)
            or any(not isinstance(value, list) or len(value) != 2 for value in runs.values())):
        raise ValueError("Each font mode requires two complete profile starts")
    restarts = {mode: compare(values[0], values[1]) for mode, values in runs.items()}
    controls = {mode: compare(runs["off"][0], runs[mode][0]) for mode in modes[1:]}
    failures = []
    for mode, rounds in runs.items():
        for round_index, scopes in enumerate(rounds):
            for scope, value in scopes.items():
                observations = native_font_rendering.consistency_observations(value["text"])
                if (any(item["operation"] in {"repeat", "pngRepeat"} for item in observations)
                        or any(row["repeat"]["changedChannels"] for row in value["fidelity"]["rows"])):
                    failures.append({"mode": mode, "round": round_index, "scope": scope,
                                     "reason": "repeated-read-or-export-is-unstable"})
                if any(row[operation]["status"] != "ok" for row in value["formats"]["rows"]
                       for operation in ("read", "export")):
                    failures.append({"mode": mode, "round": round_index, "scope": scope,
                                     "reason": "colour-storage-api-unavailable"})
                if any(row[operation]["status"] != "ok" for row in value["hdr"]["rows"]
                       for operation in ("read", "repeat", "png")):
                    failures.append({"mode": mode, "round": round_index, "scope": scope,
                                     "reason": "hdr-api-operation-failed"})
                if any(not item["repeat_matches"] for item in native_canvas_hdr.observations(value["hdr"])):
                    failures.append({"mode": mode, "round": round_index, "scope": scope,
                                     "reason": "hdr-repeated-read-is-unstable"})
    for mode, scopes in restarts.items():
        for scope, observed in scopes.items():
            if (observed["text"] or not observed["fidelity"]["matches_control"]
                    or observed["formats"] or observed["hdr"] or observed["consistency_changed"]):
                failures.append({"mode": mode, "scope": scope, "reason": "restart-changed-observation"})
    for mode, scopes in controls.items():
        for scope, observed in scopes.items():
            if (not observed["fidelity"]["matches_control"] or observed["formats"] or observed["hdr"]
                    or observed["consistency_changed"] or (mode == "native" and observed["text"])):
                failures.append({"mode": mode, "scope": scope, "reason": "control-compatibility-changed"})
    def pixel_effects(first_mode, second_mode):
        return {scope: any(first["hashes"]["pixels"] != second["hashes"]["pixels"]
                          for first, second in zip(runs[first_mode][0][scope]["text"]["rows"],
                                                   runs[second_mode][0][scope]["text"]["rows"], strict=True))
                for scope in native_font_contexts.SCOPES}

    if series == "text-tuning":
        effects = {"gamma": pixel_effects("gamma-1400", "gamma-2200"),
                   "contrast": pixel_effects("contrast-300", "contrast-500")}
        for parameter, scopes in effects.items():
            if not all(scopes.values()):
                failures.append({"reason": "no-isolated-parameter-pixel-effect", "parameter": parameter,
                                 "scopes": [scope for scope, changed in scopes.items() if not changed]})
        return {"passed": not failures, "failures": failures, "restarts": restarts,
                "controls": controls, "independent_parameter_effects": effects}
    effects = pixel_effects("aliased", "grayscale")
    effect = all(effects.values())
    if not effect:
        failures.append({"reason": "no-measured-aliased-versus-grayscale-pixel-effect",
                         "scopes": [scope for scope, changed in effects.items() if not changed]})
    return {"passed": not failures, "failures": failures, "restarts": restarts,
            "controls": controls, "aliased_grayscale_pixel_effect": effect, "pixel_effects_by_scope": effects}


async def collect_profiles(executable: Path, destination: Path, origin: str, modes: tuple[str, ...], report: dict,
                           *, profile_concurrency: int = 1, workload_font_sha256: str | None = None) -> None:
    if (not isinstance(modes, tuple) or not modes
            or any(not isinstance(mode, str) or mode not in (*MODES, *TEXT_TUNING_CASES) for mode in modes)
            or len(set(modes)) != len(modes)):
        raise ValueError("Rendering profile modes must be explicit, supported and unique")
    if type(profile_concurrency) is not int or not 1 <= profile_concurrency <= min(2, len(modes)):
        raise ValueError("Rendering profile concurrency must be explicitly 1 or 2")

    async def observe_storage(page, value):
        return await asyncio.wait_for(page.evaluate(STORAGE, value), timeout=30)

    report["profile_concurrency"] = profile_concurrency
    report["peak_live_profiles"] = 0
    report["profile_storage"] = {mode: [] for mode in modes}
    for mode in modes:
        report["runs"][mode] = []
        report["visuals"][mode] = []
        if workload_font_sha256 is not None:
            report["workloads"][mode] = []
    for offset in range(0, len(modes), profile_concurrency):
        batch = modes[offset:offset + profile_concurrency]
        for round_index in range(2):
            runtimes, pages, stored = {}, {}, {}
            try:
                for mode in batch:
                    runtime = NativeRuntime(destination / "profiles" / mode, executable,
                                            RenderingConfiguration(rasterization=mode))
                    runtimes[mode] = runtime
                    try:
                        context = await runtime.start(headless=True)
                        pages[mode] = await context.new_page()
                    except Exception as error:
                        report["errors"].append({"mode": mode, "round": round_index, "phase": "start",
                                                  "error": type(error).__name__ + ": " + str(error)})
                report["peak_live_profiles"] = max(report["peak_live_profiles"], len(pages))
                for mode, page in pages.items():
                    await page.goto(origin, wait_until="domcontentloaded", timeout=30000)
                    before = await observe_storage(page, None)
                    populated = {"cookie": "owned=" + mode, "local": mode, "indexed": mode, "cached": mode, "workers": 1}
                    expected = ({"cookie": "", "local": None, "indexed": None, "cached": None, "workers": 0}
                                if round_index == 0 else populated)
                    if before != expected:
                        raise ValueError("Rendering profile storage was shared or lost before measurement: " + mode)
                    after = await observe_storage(page, mode)
                    if after != populated:
                        raise ValueError("Rendering profile did not persist its owned storage marker: " + mode)
                    stored[mode] = {"before": before, "after": after}
                for mode, page in pages.items():
                    try:
                        if await observe_storage(page, None) != stored[mode]["after"]:
                            raise ValueError("Another rendering profile overwrote owned storage: " + mode)
                        measured = await native_font_contexts.collect(page, origin)
                        report["runs"][mode].append(measured)
                        visible = await native_font_visuals.collect(page)
                        screenshot = f"font-{mode}-{round_index}.png"
                        await page.screenshot(path=str(destination / screenshot))
                        report["screenshots_sha256"][screenshot] = hashlib.sha256((destination / screenshot).read_bytes()).hexdigest()
                        report["visuals"][mode].append(visible)
                        if workload_font_sha256 is not None:
                            workload = await native_font_workloads.collect(
                                page, origin, destination / f"workload-{mode}-{round_index}", workload_font_sha256)
                            report["workloads"][mode].append(workload)
                        if await observe_storage(page, None) != stored[mode]["after"]:
                            raise ValueError("Rendering workload changed owned profile storage: " + mode)
                        report["profile_storage"][mode].append(stored[mode])
                    except Exception as error:
                        report["errors"].append({"mode": mode, "round": round_index, "phase": "measure",
                                                  "error": type(error).__name__ + ": " + str(error)})
                for mode, page in pages.items():
                    if await observe_storage(page, None) != stored[mode]["after"]:
                        raise ValueError("A rendering peer changed another profile's storage: " + mode)
            except Exception as error:
                report["errors"].append({"batch": list(batch), "round": round_index, "phase": "storage",
                                          "error": type(error).__name__ + ": " + str(error)})
            finally:
                for mode, runtime in runtimes.items():
                    try:
                        await runtime.close()
                    except Exception as error:
                        report["errors"].append({"mode": mode, "round": round_index,
                                                  "cleanup_error": type(error).__name__ + ": " + str(error)})
                (destination / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
                if any(runtime.has_resources for runtime in runtimes.values()):
                    raise RuntimeError("Font probe retains browser resources; remaining modes were not run")


async def verify(executable: Path, destination: Path, *, series: str = "rasterization",
                 candidate_name: str | None = None, workload_font: Path | None = None,
                 profile_concurrency: int = 1) -> dict:
    modes = series_modes(series)
    candidate = None if candidate_name is None else native_build.load_candidate(candidate_name)
    policy_patch = PATCH if candidate is None else candidate["directory"] / "patches" / PATCH.name
    if sys.platform != "win32":
        raise ValueError("Windows font rendering verification requires Windows")
    if type(profile_concurrency) is not int or profile_concurrency not in (1, 2):
        raise ValueError("Rendering profile concurrency must be explicitly 1 or 2")
    if workload_font is not None and (not isinstance(workload_font, Path) or not workload_font.is_absolute()
            or workload_font != workload_font.resolve() or not workload_font.is_file()
            or not 64 <= workload_font.stat().st_size <= 2 * 1024**2):
        raise ValueError("Workloads require a bounded canonical explicit TrueType/OpenType font")
    require_idle_builder(executable.parent)
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
    expected = {"name": policy_patch.name, "sha256": hashlib.sha256(policy_patch.read_bytes()).hexdigest()}
    if (not isinstance(record, dict) or record.get("platform") != "win32"
            or record.get("binary") != "chrome.exe" or record.get("runtime_core_sha256_measured") != core
            or not isinstance(record.get("patches"), list) or record["patches"].count(expected) != 1):
        raise ValueError("The exact compiled font policy and runtime core receipt are required")
    if candidate is None:
        if "candidate_manifest_sha256" in record:
            raise ValueError("Candidate rendering verification requires explicit --candidate selection")
    else:
        manifest = candidate["manifest"]
        expected_patches = [
            {"name": row["file"], "sha256": row["sha256"],
             **({"repository": "v8", "revision": manifest["dependencies"]["v8"]["revision"]}
                if directory == "v8" else {})}
            for directory in (".", "v8") for row in manifest["patches"] if row.get("directory", ".") == directory]
        if (record.get("candidate_manifest_sha256") != candidate["manifest_sha256"]
                or record.get("chromium_revision") != candidate["lock"]["chromium_revision"]
                or record.get("depot_tools_revision") != candidate["lock"]["depot_tools_revision"]
                or record["patches"] != expected_patches):
            raise ValueError("Candidate rendering receipt differs from its complete pinned source/patch manifest")
    inputs = [policy_patch, Path(__file__), ROOT / "scripts/native_font_contexts.py",
              ROOT / "scripts/native_font_rendering.py", ROOT / "scripts/native_canvas_formats.py",
              ROOT / "scripts/native_canvas_hdr.py",
              ROOT / "scripts/native_font_visuals.py",
              ROOT / "scripts/verify_native_runtime.py",
              ROOT / "app/core/native/canvas_fidelity.py"]
    inputs.extend(ROOT / "app/core/native" / name for name in ("configuration.py", "privacy.py", "runtime.py", "identity.py"))
    if candidate is not None:
        inputs.extend([candidate["directory"] / "manifest.json", Path(native_build.__file__)])
        inputs.extend(candidate["directory"] / "patches" / row["file"] for row in candidate["manifest"]["patches"])
    if workload_font is not None:
        inputs.extend([ROOT / "scripts/native_font_workloads.py", workload_font])
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    if workload_font is not None:
        font_bytes = workload_font.read_bytes()
        if (hashlib.sha256(font_bytes).hexdigest() != before[str(workload_font)]
                or font_bytes[:4] not in (b"\x00\x01\x00\x00", b"OTTO")):
            raise ValueError("Workload font changed or is not a supported explicit TrueType/OpenType input")
    resources = measure_branding_resources(executable)
    destination.mkdir()
    report = {"passed": False, "scope": __doc__, "series": series, "capability_admitted": False,
              **({"candidate": candidate_name, "candidate_manifest_sha256": candidate["manifest_sha256"]}
                 if candidate is not None else {}),
              "runtime_core_sha256_measured": core, "inputs_sha256": before,
              "resource_pack_sha256": resources, "runs": {}, "visuals": {}, "screenshots_sha256": {}, "errors": []}
    server = None
    thread = None
    server_started = False
    try:
        handler = native_font_contexts.FontFixtureHandler if workload_font is None else native_font_workloads.WorkloadFixtureHandler
        server = FixtureServer(("127.0.0.1", 0), handler)
        if workload_font is not None:
            server.workload_font_bytes = font_bytes
            report["workloads"] = {}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        server_started = True
        await collect_profiles(executable, destination, f"http://127.0.0.1:{server.server_address[1]}", modes, report,
                               profile_concurrency=profile_concurrency,
                               workload_font_sha256=before[str(workload_font)] if workload_font is not None else None)
        if not report["errors"]:
            report["assessment"] = assess(report["runs"], series=series)
            report["visual_restarts"] = {mode: native_font_visuals.compare_control(values[0], values[1])
                                          for mode, values in report["visuals"].items()}
            report["visual_controls"] = {mode: native_font_visuals.compare_control(report["visuals"]["off"][0], values[0])
                                          for mode, values in report["visuals"].items() if mode != "off"}
            report["passed"] = (report["peak_live_profiles"] == profile_concurrency
                                and report["assessment"]["passed"] and not any(report["visual_restarts"].values())
                                and (series == "text-tuning" or not report["visual_controls"]["native"]))
            if workload_font is not None:
                report["workload_assessment"] = native_font_workloads.assess(report["workloads"], modes)
                report["passed"] = report["passed"] and report["workload_assessment"]["passed"]
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
                and before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
                and (candidate is None or native_build.load_candidate(candidate_name) == candidate)
                and (workload_font is None or all(
                    native_font_workloads.artifacts_unchanged(destination / f"workload-{mode}-{index}", value)
                    for mode, rounds in report.get("workloads", {}).items() for index, value in enumerate(rounds)))
                and all(value == hashlib.sha256((destination / name).read_bytes()).hexdigest()
                        for name, value in report["screenshots_sha256"].items()))
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
    parser.add_argument("--series", choices=("rasterization", "text-tuning"), default="rasterization")
    parser.add_argument("--candidate", choices=("upstream-156",), help="Bind the complete candidate build receipt; not capability admission")
    parser.add_argument("--workload-font", type=Path, help="Explicit real TTF/OTF for editing, web-font and export workloads")
    parser.add_argument("--profile-concurrency", type=int, choices=(1, 2), default=1,
                        help="Explicit maximum simultaneously live private profiles; default sequential")
    arguments = parser.parse_args()
    try:
        report = asyncio.run(verify(arguments.executable, arguments.output, series=arguments.series,
                                    candidate_name=arguments.candidate, workload_font=arguments.workload_font,
                                    profile_concurrency=arguments.profile_concurrency))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Font rendering verification failed: {error}\n")
    summary = {key: report.get(key) for key in ("passed", "errors", "error", "inputs_unchanged")}
    summary.update(report=str(arguments.output / "report.json"),
                   assessment_failures=len(report.get("assessment", {}).get("failures", [])),
                   visual_restart_differences=sum(map(len, report.get("visual_restarts", {}).values())),
                   native_visual_differences=len(report.get("visual_controls", {}).get("native", [])))
    print(json.dumps(summary, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
