"""Capture one measured stock156 environment; never generate or apply an identity."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from app.core.native.diagnostics import audit_observed_identity, audit_observed_request_identity
from scripts import verify_native_canvas as canvas
from scripts import verify_native_gpu as gpu
from scripts import verify_native_identity as identity
from scripts import verify_native_worker_startup as workers
from scripts.verify_native_hardware import READ as HARDWARE_READ
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core

NETWORK_DOCUMENTS = {"document", "same_origin_frame", "cross_origin_frame"}
INHERITED_DOCUMENTS = {"about_blank_frame", "srcdoc_frame"}
LOW_HINTS = {"sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"}
HEADER_NAMES = {"user-agent", "accept-language", *(name.lower() for name in identity.HINTS)}


READ = """async () => {
  const identity = await (__IDENTITY__)();
  const hardware = (__HARDWARE__)();
  const format = new Intl.DateTimeFormat().resolvedOptions();
  return {identity, hardware, gpu: await (__GPU__)(),
    languages: Array.from(navigator.languages),
    intl: {locale: format.locale, timezone: format.timeZone},
    screen: typeof screen === 'undefined' ? null : {
      width: screen.width, height: screen.height,
      availWidth: screen.availWidth, availHeight: screen.availHeight,
      colorDepth: screen.colorDepth, pixelDepth: screen.pixelDepth,
      dpr: devicePixelRatio, touch: navigator.maxTouchPoints
    }};
}""".replace("__IDENTITY__", identity.READ).replace("__HARDWARE__", HARDWARE_READ).replace("__GPU__", gpu.GPU_READ)


class EnvironmentHandler(canvas.CanvasFixtureHandler):
    worker_read = READ

    def do_GET(self):
        if self.path != "/identity-echo":
            return super().do_GET()
        body = json.dumps({name.lower(): self.headers.get(name)
                           for name in ("User-Agent", "Accept-Language", *identity.HINTS)}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Accept-CH", ", ".join(identity.HINTS))
        self.send_header("Permissions-Policy", identity.delegated_hint_policy(self.server.server_port))
        super().end_headers()


def source_inputs() -> dict[str, str]:
    names = {
        "scripts/capture_native_environment.py", "scripts/verify_native_identity.py",
        "scripts/verify_native_gpu.py", "scripts/verify_native_canvas.py",
        "scripts/verify_native_hardware.py", "scripts/verify_native_runtime.py",
        "scripts/verify_native_worker_startup.py", "app/core/native/diagnostics.py",
        "app/core/native/configuration.py", "app/core/native/canvas_fidelity.py",
        "app/core/native/privacy.py", "native/drafts/upstream-156/stock-control-observations.json",
    }
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(names)}


def gpu_identity(value: dict) -> dict:
    """Select identity/capabilities, not diagnostic shader translation lengths."""
    return {
        "webgl": {kind: {key: values[key] for key in (
            "available", "extensions", "limits", "debug", "vendor", "renderer", "debugShaders")}
            if values["available"] else {"available": False}
            for kind, values in value["webgl"].items()},
        "webgpu": {key: value["webgpu"][key] for key in ("available", "info", "features", "limits")},
    }


def validate_environment(observed: dict, version: str, *, previous: dict | None = None) -> dict:
    if not isinstance(observed, dict) or set(observed) != canvas.CONTEXTS:
        raise ValueError("Environment requires all eight measured document/worker contexts")
    if previous is not None:
        validate_environment(previous, version)
    if any(not isinstance(value, dict) or "gpu" not in value for value in observed.values()):
        raise ValueError("Measured GPU observations are missing")
    graphics = {name: value["gpu"] for name, value in observed.items()}
    coverage = gpu.validate_observations(graphics)
    gpu.require_webgpu_coverage(graphics)
    baseline = observed["document"]
    if not isinstance(baseline, dict):
        raise ValueError("Measured document environment is missing")
    identity_keys = {"userAgent", "language", "userAgentData", "metadata", "headers", "getter",
                     "illegalInvocation", "ownProperty", "plugins", "chromeType"}
    hardware_keys = {"hardwareConcurrency", "deviceMemory", "userAgent", "platform", "language"}
    document_names = canvas.CONTEXTS - {"dedicated", "shared", "service"}
    for name in ("document", *sorted(canvas.CONTEXTS - {"document"})):
        value = observed[name]
        if (not isinstance(value, dict) or set(value) != {"identity", "hardware", "gpu", "languages", "intl", "screen"}
                or not isinstance(value["identity"], dict) or set(value["identity"]) != identity_keys
                or not isinstance(value["hardware"], dict) or set(value["hardware"]) != hardware_keys
                or not isinstance(value["intl"], dict) or set(value["intl"]) != {"locale", "timezone"}):
            raise ValueError("Malformed measured environment: " + name)
        details, hardware = value["identity"], value["hardware"]
        navigator = {**hardware, "languages": value["languages"], "timezone": value["intl"]["timezone"],
                     "intlLocale": value["intl"]["locale"], "userAgentData": details["userAgentData"],
                     "userAgentHighEntropy": details["metadata"]}
        issues = audit_observed_identity({"document": navigator, "worker": navigator}, version)
        headers = details["headers"]
        expected_headers = {"user-agent", "accept-language"}
        if name in NETWORK_DOCUMENTS:
            expected_headers = HEADER_NAMES
        elif name in INHERITED_DOCUMENTS:
            expected_headers |= LOW_HINTS
        if (not isinstance(headers, dict) or set(headers) != HEADER_NAMES
                or any(not isinstance(headers[key], str) for key in expected_headers)
                or any(headers[key] is not None for key in HEADER_NAMES - expected_headers)):
            raise ValueError("Pinned stock156 request-header availability changed: " + name)
        if name in NETWORK_DOCUMENTS | INHERITED_DOCUMENTS:
            issues += audit_observed_request_identity(
                {key: headers[key] for key in expected_headers}, {"document": navigator},
                strict_client_hints=name in NETWORK_DOCUMENTS)
        if any(headers[key] != baseline["identity"]["headers"][key] for key in expected_headers):
            issues.append("Emitted request headers disagree with document identity")
        if (details["userAgent"] != hardware["userAgent"] or details["language"] != hardware["language"]
                or details["ownProperty"] is not False or details["illegalInvocation"] is not True
                or not isinstance(details["getter"], str) or "[native code]" not in details["getter"]):
            issues.append("Native identity surfaces disagree")
        if issues:
            raise ValueError(name + ": " + "; ".join(issues))
        for key in ("hardware", "languages", "intl"):
            if value[key] != baseline[key]:
                raise ValueError(name + " disagrees with document " + key)
        if gpu_identity(value["gpu"]) != gpu_identity(baseline["gpu"]):
            raise ValueError(name + " disagrees with document GPU identity/capabilities")
        for key in ("userAgent", "language", "userAgentData", "metadata"):
            if details[key] != baseline["identity"][key]:
                raise ValueError(name + " disagrees with document identity " + key)
        screen = value["screen"]
        if name not in document_names:
            if screen is not None or details["plugins"] is not None or details["chromeType"] != "undefined":
                raise ValueError("Worker claimed document-only APIs: " + name)
        else:
            if (not isinstance(screen, dict) or set(screen) != {"width", "height", "availWidth", "availHeight",
                    "colorDepth", "pixelDepth", "dpr", "touch"}
                    or any(type(screen[key]) is not int or screen[key] <= 0
                           for key in ("width", "height", "availWidth", "availHeight", "colorDepth", "pixelDepth"))
                    or type(screen["touch"]) is not int or screen["touch"] < 0
                    or type(screen["dpr"]) not in (int, float) or not 0 < screen["dpr"] <= 8
                    or screen["availWidth"] > screen["width"] or screen["availHeight"] > screen["height"]
                    or not isinstance(details["plugins"], list)
                    or any(not isinstance(plugin, str) or not plugin for plugin in details["plugins"])
                    or details["chromeType"] != "object"
                    or screen != baseline["screen"] or details["plugins"] != baseline["identity"]["plugins"]
                    or details["chromeType"] != baseline["identity"]["chromeType"]):
                raise ValueError("Document screen/plugins observation is invalid: " + name)
        if previous is not None and (
                {**value, "gpu": gpu_identity(value["gpu"])}
                != {**previous[name], "gpu": gpu_identity(previous[name]["gpu"])}):
            raise ValueError("Environment changed across persistent-profile restart: " + name)
    return {**coverage, "http_hint_contexts": {"full": 3, "low_entropy": 2, "absent": 3}}


async def capture(executable: Path, profile: Path, origin: str, report: dict) -> None:
    async with async_playwright() as driver:
        previous = None
        for name in ("initial", "persistent-profile-restart"):
            context = await driver.chromium.launch_persistent_context(
                str(profile), executable_path=str(executable), headless=True,
                chromium_sandbox=True, timeout=30000, no_viewport=True,
                args=["--enable-automation"])
            primary = None
            try:
                arguments = await workers.browser_arguments(context)
                if any(value.startswith(("--user-agent=", "--camouflow-", "--glint-")) for value in arguments):
                    raise ValueError("Reference capture must not apply identity policies")
                if "--enable-automation" not in arguments:
                    raise ValueError("Reference command-line verification requires explicit automation mode")
                if report.get("browser_arguments") is not None:
                    if arguments != report["browser_arguments"]:
                        raise ValueError("Reference launch arguments changed across restart")
                else:
                    report["browser_arguments"] = arguments
                version = context.browser.version
                report["browser_version"] = version
                if version != "156.0.8078.36":
                    raise ValueError("Reference browser version differs from pinned stock156")
                observed = await canvas.observe(context, origin, READ,
                                                frame_allow="; ".join(identity.HINT_POLICY_FEATURES))
                check = {"name": name, "passed": False, "observed": observed}
                report["checks"].append(check)
                check["coverage"] = validate_environment(observed, version, previous=previous)
                check["passed"] = True
                previous = observed
            except BaseException as error:
                primary = error
                raise
            finally:
                try:
                    await context.close()
                except Exception as error:
                    if primary is None:
                        raise
                    primary.add_note("Reference context cleanup failed: " + str(error))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    owned = args.work_dir
    if (not owned.is_absolute() or owned.drive.upper() != "D:" or owned != owned.resolve()
            or owned.exists() or owned.is_relative_to(ROOT)
            or any((parent / ".git").exists() for parent in owned.parents)):
        parser.error("Select a new canonical D: evidence directory outside the checkout")
    executable = args.executable.resolve(strict=True)
    stock = json.loads((ROOT / "native/drafts/upstream-156/stock-control-observations.json").read_bytes())
    core = measure_runtime_core(executable)
    if core != stock["stock_core_sha256"]:
        parser.error("This capture requires the explicit pinned official stock156 control")
    inputs = source_inputs()
    owned.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, "passed": False, "checks": [], "capture_mode": "headless-automation-control",
              "viewport_emulation": False,
              "scope": "One measured stock156 host environment, not a general hardware cohort or generated identity",
              "host_platform": platform.platform(), "runtime_core_sha256_measured": core,
              "source_sha256": inputs, "profile_generation_admitted": False,
              "glint_runtime_verified": False, "privacy_admitted": False, "production_admitted": False}
    server = None
    thread = None
    profile = owned / "profile"
    try:
        server = FixtureServer(("127.0.0.1", 0), EnvironmentHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        asyncio.run(capture(executable, profile, f"http://127.0.0.1:{server.server_port}", report))
        if [row["name"] for row in report["checks"]] != ["initial", "persistent-profile-restart"]:
            raise ValueError("Reference capture phases are incomplete")
        report["passed"] = all(row["passed"] is True for row in report["checks"])
    except Exception as error:
        report.update(passed=False, error=str(error), traceback=traceback.format_exc())
    finally:
        try:
            if thread is not None and thread.is_alive():
                server.shutdown()
            if server is not None:
                server.server_close()
            if thread is not None and thread.ident is not None:
                thread.join(timeout=5)
                if thread.is_alive():
                    raise RuntimeError("Reference fixture server remains alive")
        except Exception as error:
            report.update(passed=False, server_cleanup_error=str(error))
        try:
            report["postguards_passed"] = measure_runtime_core(executable) == core and source_inputs() == inputs
        except Exception as error:
            report.update(postguards_passed=False, postguard_error=str(error))
        report["passed"] = report["passed"] and report["postguards_passed"]
        if report["passed"]:
            try:
                if profile != profile.resolve() or profile.parent != owned or not profile.is_dir():
                    raise ValueError("Reference cleanup escaped its owned profile")
                shutil.rmtree(profile)
            except Exception as error:
                report.update(passed=False, cleanup_error=str(error))
        with (owned / "report.json").open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(owned / "report.json"), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
