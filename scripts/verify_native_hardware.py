"""Verify native Chromium hardware bindings, not page-level JavaScript overrides."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import platform
import sys
import tempfile
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import Error as PlaywrightError, async_playwright  # noqa: E402
from scripts.verify_native_runtime import FixtureHandler, FixtureServer  # noqa: E402

READ = """() => ({
  hardwareConcurrency: navigator.hardwareConcurrency,
  deviceMemory: navigator.deviceMemory,
  userAgent: navigator.userAgent,
  platform: navigator.platform,
  language: navigator.language
})"""

WORKERS = """async () => {
  const request = (port, start) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Hardware worker probe timed out')), 10000);
    port.onmessage = event => { clearTimeout(timer); resolve(event.data); };
    port.onmessageerror = () => { clearTimeout(timer); reject(new Error('Invalid worker response')); };
    try { start(); } catch (error) { clearTimeout(timer); reject(error); }
  });
  const dedicated = new Worker('/hardware-dedicated.js');
  const shared = new SharedWorker('/hardware-shared.js');
  let registration;
  let channel;
  try {
    const dedicatedValues = await request(dedicated, () => dedicated.postMessage('read'));
    const sharedValues = await request(shared.port, () => {
      shared.port.start(); shared.port.postMessage('read');
    });
    registration = await navigator.serviceWorker.register('/hardware-service.js');
    const ready = await navigator.serviceWorker.ready;
    channel = new MessageChannel();
    const serviceValues = await request(channel.port1, () => {
      ready.active.postMessage('read', [channel.port2]);
    });
    return {dedicated: dedicatedValues, shared: sharedValues, service: serviceValues};
  } finally {
    dedicated.terminate(); shared.port.close();
    channel?.port1.close(); channel?.port2.close();
    if (registration) await registration.unregister();
  }
}"""


class HardwareFixtureHandler(FixtureHandler):
    def do_GET(self):
        bodies = {
            "/hardware-dedicated.js": f"self.onmessage = () => self.postMessage(({READ})());",
            "/hardware-shared.js": f"self.onconnect = event => {{ const port = event.ports[0]; port.onmessage = () => port.postMessage(({READ})()); port.start(); }};",
            "/hardware-service.js": (
                "self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));"
                "self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));"
                f"self.addEventListener('message', event => event.ports[0].postMessage(({READ})()));"
            ),
        }
        if self.path not in bodies:
            return super().do_GET()
        body = bodies[self.path].encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def validate_observations(observed: dict, baseline: dict | None = None,
                          concurrency: int | None = None, memory: float | None = None) -> None:
    expected_contexts = {"document", "same_origin_frame", "cross_origin_frame", "dedicated", "shared", "service"}
    if set(observed) != expected_contexts:
        raise ValueError("Hardware probe did not observe every document/worker context")
    document = observed["document"]
    cpu, ram = document.get("hardwareConcurrency"), document.get("deviceMemory")
    if type(cpu) is not int or cpu < 1 or type(ram) not in (int, float) or not math.isfinite(ram) or ram <= 0:
        raise ValueError("Native hardware APIs returned invalid values")
    for name, values in observed.items():
        if values != document:
            raise ValueError(f"Hardware/identity values disagree in {name}")
    if baseline is not None:
        for key in ("userAgent", "platform", "language"):
            if document[key] != baseline[key]:
                raise ValueError(f"Hardware privacy configuration changed {key}")
        expected_cpu = min(baseline["hardwareConcurrency"], concurrency) if concurrency is not None else baseline["hardwareConcurrency"]
        expected_ram = min(baseline["deviceMemory"], memory) if memory is not None else baseline["deviceMemory"]
        if cpu != expected_cpu or ram != expected_ram:
            raise ValueError(f"Native limits were ignored or inconsistent: expected {expected_cpu}/{expected_ram}, got {cpu}/{ram}")


async def observe(context, origin: str) -> dict:
    page = context.pages[0]
    await page.goto(origin, wait_until="load", timeout=30000)
    await page.evaluate("url => { const frame = document.createElement('iframe'); frame.id = 'cross-origin'; frame.src = url; document.body.append(frame); }",
                        origin.replace("127.0.0.1", "localhost") + "/cross-frame")
    await page.locator("#cross-origin").content_frame.locator("h1").wait_for(timeout=15000)
    observed = {"document": await page.evaluate(READ)}
    for name, frame_id in (("same_origin_frame", "owned-frame"), ("cross_origin_frame", "cross-origin")):
        frame = await page.locator("#" + frame_id).element_handle()
        observed[name] = await (await frame.content_frame()).evaluate(READ)
    observed.update(await asyncio.wait_for(page.evaluate(WORKERS), timeout=40))
    return observed


async def verify(executable: Path, profiles: Path, origin: str, report: dict) -> None:
    async with async_playwright() as driver:
        baseline = None
        for name, cpu, ram in (("native-baseline", None, None), ("privacy-ceilings", 1, 0.25),
                               ("concurrency-only", 1, None), ("memory-only", None, 0.25),
                               ("upper-limits-never-invent-hardware", 64, 16)):
            arguments = []
            if cpu is not None:
                arguments.append(f"--camouflow-hardware-concurrency={cpu}")
            if ram is not None:
                arguments.append(f"--camouflow-device-memory={ram:g}")
            context = await driver.chromium.launch_persistent_context(str(profiles / name), executable_path=str(executable),
                headless=True, chromium_sandbox=True, timeout=30000, args=arguments)
            try:
                report["browser_version"] = context.browser.version
                values = await observe(context, origin)
                check = {"name": name, "arguments": arguments, "observed": values, "passed": False}
                report["checks"].append(check)
                validate_observations(values, baseline, cpu, ram)
                check["passed"] = True
                if baseline is None:
                    baseline = values["document"]
                    if baseline["hardwareConcurrency"] == 1 and baseline["deviceMemory"] <= 0.25:
                        raise ValueError("Host values cannot distinguish ignored switches from functioning limits")
            finally:
                await context.close()
        for index, argument in enumerate(("--camouflow-hardware-concurrency=0", "--camouflow-hardware-concurrency=invalid",
                                           "--camouflow-device-memory=0.3", "--camouflow-device-memory=")):
            context = await driver.chromium.launch_persistent_context(str(profiles / f"invalid-{index}"),
                executable_path=str(executable), headless=True, chromium_sandbox=True, timeout=30000, args=[argument])
            try:
                page = context.pages[0]
                crashed = asyncio.Event()
                page.on("crash", lambda _: crashed.set())
                await page.goto(origin, timeout=30000)
                try:
                    await page.evaluate(READ)
                except PlaywrightError:
                    await asyncio.wait_for(crashed.wait(), timeout=10)
                else:
                    raise ValueError("Invalid native hardware configuration was silently accepted")
                report["checks"].append({"name": "invalid-configuration-fails-renderer", "argument": argument, "passed": True})
            finally:
                await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {"schema": 1, "platform": platform.platform(), "passed": False, "checks": []}
    server = None
    thread = None
    try:
        executable = args.executable.resolve(strict=True)
        if not executable.is_file():
            raise ValueError("An explicit Chromium executable is required")
        with executable.open("rb") as stream:
            report["binary_sha256_measured"] = hashlib.file_digest(stream, "sha256").hexdigest()
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), HardwareFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="native-hardware-owned-", dir=args.work_dir.resolve()) as owned:
            origin = f"http://127.0.0.1:{server.server_port}"
            asyncio.run(verify(executable, Path(owned), origin, report))
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
        report["traceback"] = traceback.format_exc()
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": len(report["checks"]), "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
