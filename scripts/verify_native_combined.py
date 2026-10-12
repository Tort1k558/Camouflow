"""Exercise Native hardware, fonts, WebRTC, automation and UA policies together."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
import sys
import tempfile
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright  # noqa: E402
from scripts import verify_native_canvas as canvas, verify_native_webrtc as webrtc  # noqa: E402
from scripts.verify_native_automation import FEATURE  # noqa: E402
from scripts.verify_native_hardware import close_context  # noqa: E402
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core  # noqa: E402

ARGUMENTS = ["--camouflow-hardware-concurrency=1", "--camouflow-device-memory=0.25",
             "--camouflow-font-families=Arial",
             "--camouflow-webrtc-ip-handling-policy=disable_non_proxied_udp",
             "--camouflow-native-user-agent",
             "--enable-automation", "--enable-blink-features=" + FEATURE]
REQUIRED_CHECKS = frozenset({"owned-stun-positive-control", "initial-profile-a", "initial-profile-b",
                             "restart-profile-a", "restart-profile-b"})

READ = """async () => {
  const canvas = await (""" + canvas.READ + """)();
  const context = new OffscreenCanvas(400, 80).getContext('2d');
  context.font = '20px Arial';
  const arial = context.measureText('mmmmmmmmiiiiWWW012345').width;
  context.font = '20px "Courier New", Arial';
  const restricted = context.measureText('mmmmmmmmiiiiWWW012345').width;
  const response = await fetch('/combined-identity');
  if (!response.ok) throw new Error('Owned combined identity request failed');
  const headers = await response.json();
  return {canvas, native: {cpu: navigator.hardwareConcurrency, memory: navigator.deviceMemory,
    webdriver: typeof document === 'undefined' ? null : navigator.webdriver, arial, restricted,
    userAgent: navigator.userAgent, userAgentHeader: headers.userAgent}};
}"""


class CombinedFixtureHandler(canvas.CanvasFixtureHandler):
    worker_read = READ

    def do_GET(self):
        if self.path != "/combined-identity":
            return super().do_GET()
        body = json.dumps({"userAgent": self.headers.get("User-Agent", "")}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def validate_observations(observed: dict, previous: dict | None = None, *, browser_version: str) -> None:
    if not isinstance(browser_version, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", browser_version) is None:
        raise ValueError("Combined probe requires the measured browser version")
    if not isinstance(observed, dict) or set(observed) != canvas.CONTEXTS:
        raise ValueError("Combined probe requires all document and worker contexts")
    for name, value in observed.items():
        if not isinstance(value, dict) or set(value) != {"canvas", "native"}:
            raise ValueError("Combined probe is missing native observations")
        native = value["native"]
        if (not isinstance(native, dict) or set(native) != {"cpu", "memory", "webdriver", "arial", "restricted", "userAgent", "userAgentHeader"}
                or type(native["cpu"]) is not int or native["cpu"] != 1
                or type(native["memory"]) not in {int, float} or native["memory"] != 0.25
                or native["webdriver"] is not (None if name in {"dedicated", "shared", "service"} else False)
                or type(native["arial"]) not in {int, float} or not 0 < native["arial"] < 400
                or type(native["restricted"]) not in {int, float}
                or native["restricted"] != native["arial"]):
            raise ValueError("Combined native policies disagree in " + name)
        agent = native["userAgent"]
        product = re.search(r" Chrome/([0-9]+)\.", agent) if isinstance(agent, str) else None
        if (product is None or product.group(1) != browser_version.split(".")[0]
                or "HeadlessChrome/" in agent or native["userAgentHeader"] != agent):
            raise ValueError("Combined UA differs from native version or HTTP in " + name)
    canvas.validate_observations({name: value["canvas"] for name, value in observed.items()},
                                None if previous is None else {name: value["canvas"] for name, value in previous.items()})
    if previous is not None and observed != previous:
        raise ValueError("Combined observations changed after profile restart")


async def verify(executable: Path, root: Path, origin: str, report: dict, library_directory: Path | None = None) -> None:
    async with async_playwright() as driver:
        control = await driver.chromium.launch_persistent_context(str(root / "control"),
            executable_path=str(executable), chromium_sandbox=True, headless=True, timeout=30000)
        try:
            if (library_directory is not None and library_directory != executable.parent
                    and library_directory.name != control.browser.version):
                raise ValueError("Combined DLL directory does not match the running browser")
            await control.pages[0].goto(origin, timeout=30000)
            measured = await asyncio.wait_for(webrtc.observe(control.pages[0]), timeout=15)
            check = {"name": "owned-stun-positive-control", "observed": measured, "passed": False}
            report["checks"].append(check)
            webrtc.validate_probe(measured, protected=False)
            check["passed"] = True
        finally:
            await close_context(control)
        previous = {}
        for phase in ("initial", "restart"):
            for profile in ("a", "b"):
                context = await driver.chromium.launch_persistent_context(str(root / profile),
                    executable_path=str(executable), chromium_sandbox=True, headless=True,
                    timeout=30000, args=ARGUMENTS)
                try:
                    report["version"] = context.browser.version
                    observed = await canvas.observe(context, origin, READ)
                    check = {"name": phase + "-profile-" + profile, "observed": observed,
                             "webrtc": {}, "security": {}, "passed": False}
                    report["checks"].append(check)
                    validate_observations(observed, previous.get(profile), browser_version=report["version"])
                    previous[profile] = observed
                    page = context.pages[0]
                    stored = await page.evaluate("() => localStorage.getItem('combined-profile')")
                    if stored != (None if phase == "initial" else profile):
                        raise ValueError("Combined profiles lost or shared their persistent marker")
                    await page.evaluate("value => localStorage.setItem('combined-profile', value)", profile)
                    for name, frame in (await canvas.security_frames(page)).items():
                        measured = await asyncio.wait_for(webrtc.observe(frame), timeout=15)
                        check["webrtc"][name] = measured
                        webrtc.validate_probe(measured, protected=True)
                        check["security"][name] = await asyncio.wait_for(frame.evaluate(canvas.SECURITY_READ), timeout=20)
                    if set(check["webrtc"]) != {"document", "same_origin_frame", "cross_origin_frame"}:
                        raise ValueError("Combined WebRTC frame coverage is incomplete")
                    canvas.validate_security(check["security"])
                    check["passed"] = True
                finally:
                    await close_context(context)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--windows-library-directory", type=Path,
                        help="Explicit package-owned DLL directory for a versioned Chrome-bin layout")
    args = parser.parse_args()
    report = {"schema": 1, "passed": False, "checks": [], "arguments": ARGUMENTS,
              "readback_contexts": sorted(canvas.CONTEXTS),
              "scope": "Combined hardware/fonts/WebRTC/automation/UA; Canvas compatibility baseline, not Canvas protection or release admission"}
    server = None
    thread = None
    try:
        if sys.platform != "win32":
            raise ValueError("Combined Native policy verification currently supports Windows only")
        executable = args.executable.resolve(strict=True)
        core = measure_runtime_core(executable, args.windows_library_directory)
        report.update(runtime_core_sha256_measured=core, binary_sha256_measured=core[executable.name])
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), CombinedFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="native-combined-owned-", dir=args.work_dir.resolve()) as owned:
            asyncio.run(verify(executable, Path(owned), f"http://127.0.0.1:{server.server_port}", report, args.windows_library_directory))
        if measure_runtime_core(executable, args.windows_library_directory) != core:
            raise ValueError("Native runtime code changed during combined verification")
        report["passed"] = True
    except Exception as error:
        report.update(error=str(error), traceback=traceback.format_exc())
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
