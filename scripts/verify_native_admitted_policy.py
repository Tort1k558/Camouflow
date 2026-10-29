"""Exercise reviewed managed policies through NativeRuntime, not raw launch flags."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.admission import verify_runtime_policy
from app.core.native.configuration import NativeConfiguration
from app.core.native.health import probe_native_profile
from app.core.native.privacy import NativePrivacyPolicy
from app.core.native.runtime import NativeRuntime
from scripts import native_font_contexts, verify_native_canvas as canvas, verify_native_combined as combined
from scripts import native_font_rendering, native_canvas_hdr
from scripts import verify_native_font_rendering as rendering, verify_native_webrtc as webrtc
from scripts.verify_native_privacy_units import require_idle_builder
from scripts.verify_native_runtime import FixtureServer, FixtureHandler, verify_multi_profile_restarts

POLICY = NativePrivacyPolicy(cpu_limit=1, memory_limit=.25, fonts=("Arial",),
                            restrict_webrtc=True, conceal_automation=True, native_user_agent=True)


class PolicyFixtureHandler(native_font_contexts.FontFixtureHandler, combined.CombinedFixtureHandler):
    pass


def validate_rendering(rounds: dict) -> None:
    if (not isinstance(rounds, dict) or set(rounds) != {"native", "grayscale"}
            or any(not isinstance(value, list) or len(value) != 2 for value in rounds.values())):
        raise ValueError("Both admitted font modes require two starts")
    for mode, values in rounds.items():
        if values[0] != values[1]:
            raise ValueError("Admitted rendering changed after restart: " + mode)
        for scopes in values:
            for scope, measured in scopes.items():
                native_font_contexts.validate_scope(scope, measured)
                unstable = native_font_rendering.consistency_observations(measured["text"])
                if (any(value["operation"] in {"repeat", "pngRepeat"} for value in unstable)
                        or any(row["repeat"]["changedChannels"] for row in measured["fidelity"]["rows"])
                        or any(not row["repeat_matches"] for row in native_canvas_hdr.observations(measured["hdr"]))):
                    raise ValueError("Admitted repeated reads/exports are unstable in " + scope)
                if (any(row[operation]["status"] != "ok" for row in measured["formats"]["rows"] for operation in ("read", "export"))
                        or any(row[operation]["status"] != "ok" for row in measured["hdr"]["rows"] for operation in ("read", "repeat", "png"))):
                    raise ValueError("Admitted colour/HDR operations are unavailable in " + scope)
    controls = rendering.compare(rounds["native"][0], rounds["grayscale"][0])
    for scope, value in controls.items():
        if (not value["fidelity"]["matches_control"] or value["formats"] or value["hdr"]
                or value["consistency_changed"]):
            raise ValueError("Admitted font mode changed image/API compatibility in " + scope)
        first = rounds["native"][0][scope]["text"]["rows"]
        second = rounds["grayscale"][0][scope]["text"]["rows"]
        if not any(a["hashes"]["pixels"] != b["hashes"]["pixels"] for a, b in zip(first, second, strict=True)):
            raise ValueError("No measured admitted font effect in " + scope)


async def verify(executable: Path, destination: Path) -> dict:
    if (not destination.is_absolute() or destination != destination.resolve() or not destination.parent.is_dir()
            or destination.is_relative_to(executable.parent.parent.parent) or destination.is_relative_to(ROOT)):
        raise ValueError("New owned evidence must stay outside the application and binary store")
    require_idle_builder(executable.parent)
    admission = await asyncio.to_thread(verify_runtime_policy, executable, POLICY)
    inputs = [Path(__file__), *(ROOT / "app/core/native").glob("*.py"),
              *[ROOT / "scripts" / name for name in (
                  "native_font_contexts.py", "native_font_rendering.py", "native_canvas_formats.py", "native_canvas_hdr.py",
                  "verify_native_canvas.py", "verify_native_combined.py", "verify_native_webrtc.py", "verify_native_font_rendering.py",
                  "verify_native_runtime.py")]]
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    destination.mkdir(exist_ok=False)
    report = {"passed": False, "scope": "Experimental managed policies on owned fixtures; not CAPTCHA or device realism",
              "release_sha256_measured": admission.release_sha256, "inputs_sha256": hashes,
              "checks": [], "rendering": {"native": [], "grayscale": []}, "errors": []}
    server = None
    thread = None
    server_started = False
    runtimes = {}
    control = NativeRuntime(destination / "control", executable, NativeConfiguration())
    try:
        server = FixtureServer(("127.0.0.1", 0), PolicyFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        server_started = True
        origin = f"http://127.0.0.1:{server.server_port}"
        context = await control.start(headless=True)
        await context.pages[0].goto(origin)
        measured = await webrtc.observe(context.pages[0])
        webrtc.validate_probe(measured, protected=False)
        report["positive_control"] = measured
        await control.close()
        previous = {}
        for mode in report["rendering"]:
            configuration = NativeConfiguration(privacy_policy=replace(POLICY, font_rasterization=mode))
            runtimes[mode] = NativeRuntime(destination / ("profile-" + mode), executable, configuration)
        for phase in ("initial", "restart"):
            try:
                for runtime in runtimes.values():
                    await runtime.start(headless=True)
                for mode, runtime in runtimes.items():
                    context = runtime.context
                    check = {"phase": phase, "mode": mode, "passed": False}
                    report["checks"].append(check)
                    if runtime.native_policy_capabilities != runtime.configuration.privacy_policy.required_capabilities():
                        raise ValueError("Runtime admission differs from the selected policy")
                    observed = await canvas.observe(context, origin, combined.READ)
                    combined.validate_observations(observed, previous.get(mode), browser_version=context.browser.version)
                    previous[mode] = observed
                    page = context.pages[0]
                    marker = await page.evaluate("localStorage.getItem('admitted-profile')")
                    if marker != (None if phase == "initial" else mode):
                        raise ValueError("Admitted profiles lost or shared persistent storage")
                    await page.evaluate("value => localStorage.setItem('admitted-profile', value)", mode)
                    protected = await webrtc.observe(page)
                    webrtc.validate_probe(protected, protected=True)
                    security = {name: await frame.evaluate(canvas.SECURITY_READ)
                                for name, frame in (await canvas.security_frames(page)).items()}
                    canvas.validate_security(security)
                    measured = await native_font_contexts.collect(page, origin)
                    report["rendering"][mode].append(measured)
                    check.update(passed=True, capabilities=runtime.native_policy_capabilities,
                                 observed=observed, webrtc=protected, security=security)
            finally:
                for runtime in runtimes.values():
                    await runtime.close()
            (destination / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        validate_rendering(report["rendering"])
        with FixtureServer(("127.0.0.1", 0), FixtureHandler) as recovery_server:
            recovery_thread = threading.Thread(target=recovery_server.serve_forever, daemon=True)
            recovery_thread.start()
            try:
                report["recovery"] = await verify_multi_profile_restarts(
                    destination / "recovery", executable, f"http://127.0.0.1:{recovery_server.server_port}",
                    configuration=runtimes["grayscale"].configuration)
            finally:
                recovery_server.shutdown()
                recovery_thread.join(timeout=5)
        diagnostics = await probe_native_profile(executable, runtimes["grayscale"].configuration, destination / "health")
        if (diagnostics["mismatches"] or diagnostics["native_patch_capabilities"]
                != runtimes["grayscale"].configuration.privacy_policy.required_capabilities()):
            raise ValueError("Manager health diagnostics did not confirm the admitted policy")
        report.update(passed=True, diagnostics=diagnostics)
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    finally:
        for runtime in (control, *runtimes.values()):
            try:
                await runtime.close()
                if runtime.has_resources:
                    raise RuntimeError("Admitted runtime retained resources")
            except Exception as error:
                report["errors"].append(type(error).__name__ + ": " + str(error))
        if server is not None:
            if server_started:
                server.shutdown()
            server.server_close()
        if server_started:
            thread.join(timeout=5)
        try:
            verified = await asyncio.to_thread(verify_runtime_policy, executable, POLICY)
            report["inputs_unchanged"] = (verified == admission and hashes == {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs})
        except (OSError, ValueError) as error:
            report["inputs_unchanged"] = False
            report["guard_error"] = str(error)
        report["passed"] = report["passed"] and not report["errors"] and report["inputs_unchanged"]
        (destination / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(verify(args.executable, args.output))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Native policy verification failed: {error}\n")
    print(json.dumps({key: report.get(key) for key in ("passed", "error", "errors", "inputs_unchanged")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
