"""Verify Native webdriver exposure in owned pages; not general bot resistance."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright  # noqa: E402
from scripts.verify_native_hardware import WORKERS  # noqa: E402
from scripts.verify_native_runtime import FixtureHandler, FixtureServer  # noqa: E402

FEATURE = "CamouFlowAutomationConcealed"
READ = """() => {
  const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
  let illegalInvocation = false;
  try { Reflect.apply(descriptor.get, {}, []); }
  catch (error) { illegalInvocation = error instanceof TypeError; }
  return {
    value: navigator.webdriver,
    firstScriptValue: window.__automationFirst,
    ownProperty: Object.hasOwn(navigator, 'webdriver'),
    descriptor: {
      getter: Function.prototype.toString.call(descriptor.get),
      setter: descriptor.set === undefined,
      enumerable: descriptor.enumerable,
      configurable: descriptor.configurable,
      illegalInvocation
    }
  };
}"""
WORKER_READ = """() => ({
  present: 'webdriver' in navigator,
  ownProperty: Object.hasOwn(navigator, 'webdriver')
})"""


class AutomationFixtureHandler(FixtureHandler):
    def do_GET(self):
        bodies = {
            "/hardware-dedicated.js": f"self.onmessage = () => self.postMessage(({WORKER_READ})());",
            "/hardware-shared.js": f"self.onconnect = event => {{ const port = event.ports[0]; port.onmessage = () => port.postMessage(({WORKER_READ})()); port.start(); }};",
            "/hardware-service.js": (
                "self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));"
                "self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));"
                f"self.addEventListener('message', event => event.ports[0].postMessage(({WORKER_READ})()));"
            ),
        }
        javascript = self.path in bodies
        body = bodies.get(self.path, "<!doctype html><script>window.__automationFirst = navigator.webdriver;</script><h1>Owned automation fixture</h1>").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript" if javascript else "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def validate_observation(observed: dict, baseline: dict, expected: bool, *, first: bool | None = None) -> None:
    if type(observed.get("value")) is not bool or observed["value"] is not expected:
        raise ValueError("Native webdriver exposure was ignored or changed unexpectedly")
    if first is not None and observed.get("firstScriptValue") is not first:
        raise ValueError("Webdriver exposure was inconsistent before the first page script")
    descriptor = observed.get("descriptor", {})
    if observed.get("ownProperty") is not False or descriptor != baseline.get("descriptor"):
        raise ValueError("Webdriver getter shape changed instead of preserving the native binding")
    if "[native code]" not in descriptor.get("getter", "") or descriptor.get("illegalInvocation") is not True:
        raise ValueError("Webdriver native getter or illegal invocation behavior was not observed")


async def verify(executable: Path, root: Path, origin: str, checks: list) -> dict:
    baseline = None
    async with async_playwright() as driver:
        for name, switches, concealed, automation_controlled in (
            ("native-default", [], False, True),
            ("native-cdp-control", ["--disable-blink-features=AutomationControlled"], False, False),
            ("concealed", ["--enable-blink-features=" + FEATURE], True, True),
            ("concealed-cdp-control", ["--enable-blink-features=" + FEATURE,
                                       "--disable-blink-features=AutomationControlled"], True, False),
            ("explicitly-disabled", ["--disable-blink-features=" + FEATURE], False, True),
        ):
            with tempfile.TemporaryDirectory(prefix="native-automation-owned-", dir=root) as profile:
                arguments = ["--enable-automation", *switches]
                context = await driver.chromium.launch_persistent_context(
                    profile, executable_path=str(executable), chromium_sandbox=True,
                    headless=True, args=arguments, timeout=30000)
                try:
                    version = context.browser.version
                    page = context.pages[0]
                    await page.goto(origin, wait_until="load", timeout=30000)
                    await page.evaluate("""async origin => {
                      for (const url of [origin, origin.replace('127.0.0.1', 'localhost')]) {
                        const frame = document.createElement('iframe');
                        const loaded = new Promise(resolve => frame.onload = resolve);
                        frame.src = url; document.body.append(frame);
                        await loaded;
                      }
                    }""", origin)
                    if len(page.frames) != 3:
                        raise ValueError("Both owned automation frame contexts must be observed")
                    frames = [("document", page), *zip(("same_origin_frame", "cross_origin_frame"), page.frames[1:])]
                    popup = await context.new_page()
                    await popup.goto(origin, wait_until="load", timeout=30000)
                    frames.append(("new_target", popup))
                    for scope, frame in frames:
                        observed = await frame.evaluate(READ)
                        if baseline is None:
                            baseline = observed
                        check = {"mode": name, "context": scope, "observed": observed, "passed": False}
                        checks.append(check)
                        expected = automation_controlled and not concealed
                        validate_observation(observed, baseline, expected, first=expected)
                        check["passed"] = True
                    workers = await asyncio.wait_for(page.evaluate(WORKERS), timeout=40)
                    if set(workers) != {"dedicated", "shared", "service"}:
                        raise ValueError("All three worker types must be observed")
                    for scope, observed in workers.items():
                        check = {"mode": name, "context": scope, "observed": observed, "passed": False}
                        checks.append(check)
                        if observed != {"present": False, "ownProperty": False}:
                            raise ValueError("Native policy added a nonstandard webdriver property to WorkerNavigator")
                        check["passed"] = True
                    for target_name, target in (("document", page), ("new_target", popup)):
                        session = await context.new_cdp_session(target)
                        try:
                            for enabled in (False, True):
                                await session.send("Emulation.setAutomationOverride", {"enabled": enabled})
                                observed = await target.evaluate(READ)
                                check = {"mode": name, "context": target_name, "cdp_override": enabled,
                                         "observed": observed, "passed": False}
                                checks.append(check)
                                expected = False if concealed else automation_controlled or enabled
                                validate_observation(observed, baseline, expected)
                                check["passed"] = True
                        finally:
                            await session.detach()
                finally:
                    await context.close()
    with executable.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"passed": True, "platform": platform.system(), "version": version,
            "binary_sha256_measured": checksum, "checks": checks,
            "scope": "Native webdriver getter, first script, frames, new target, workers and CDP override; not CDP invisibility or general bot resistance"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    checks = []
    server = FixtureServer(("127.0.0.1", 0), AutomationFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        report = asyncio.run(verify(args.executable.resolve(), args.work_dir,
                                   f"http://127.0.0.1:{server.server_port}", checks))
    except Exception as error:
        report = {"passed": False, "platform": platform.system(), "checks": checks,
                  "error_type": type(error).__name__, "error": str(error)}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
