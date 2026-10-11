"""Measure native Canvas readback consistency; this is not a masking acceptance gate."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import tempfile
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright
from scripts.verify_native_hardware import WORKERS
from scripts.verify_native_runtime import FixtureHandler, FixtureServer


READ = """async () => {
  const width = 96, height = 64;
  const canvas = new OffscreenCanvas(width, height);
  const context = canvas.getContext('2d', {willReadFrequently: true});
  context.fillStyle = '#345678'; context.fillRect(0, 0, width, height);
  const gradient = context.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, '#abcdef'); gradient.addColorStop(1, '#123456');
  context.fillStyle = gradient; context.fillRect(3, 5, 70, 40);
  context.font = '16px Arial'; context.fillStyle = '#ffeedd';
  context.fillText('Native 0123', 1, 28);
  const hash = async pixels => Array.from(new Uint8Array(
    await crypto.subtle.digest('SHA-256', pixels)), b => b.toString(16).padStart(2, '0')).join('');
  const read = target => target.getImageData(0, 0, width, height).data;
  const decode = async blob => {
    const image = await createImageBitmap(blob);
    try {
      const copy = new OffscreenCanvas(width, height);
      const target = copy.getContext('2d', {willReadFrequently: true});
      target.drawImage(image, 0, 0);
      return await hash(read(target));
    } finally { image.close(); }
  };
  const pixels = await hash(read(context));
  const repeat = await hash(read(context));
  const blob = await decode(await canvas.convertToBlob({type: 'image/png'}));
  let htmlBlob = null, htmlDataUrl = null;
  if (typeof document !== 'undefined') {
    const html = document.createElement('canvas');
    html.width = width; html.height = height;
    html.getContext('2d').drawImage(canvas, 0, 0);
    const exported = await new Promise((resolve, reject) => html.toBlob(
      value => value ? resolve(value) : reject(new Error('Canvas export returned null')), 'image/png'));
    htmlBlob = await decode(exported);
    const response = await fetch(html.toDataURL('image/png'));
    htmlDataUrl = await decode(await response.blob());
  }
  return {pixels, repeat, blob, htmlBlob, htmlDataUrl};
}"""

CONTEXTS = {"document", "same_origin_frame", "cross_origin_frame", "dedicated", "shared", "service"}


class CanvasFixtureHandler(FixtureHandler):
    def do_GET(self):
        bodies = {
            "/hardware-dedicated.js": f"self.onmessage = async () => self.postMessage(await ({READ})());",
            "/hardware-shared.js": f"self.onconnect = event => {{ const port = event.ports[0]; port.onmessage = async () => port.postMessage(await ({READ})()); port.start(); }};",
            "/hardware-service.js": (
                "self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));"
                "self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));"
                f"self.addEventListener('message', event => event.waitUntil(({READ})().then(value => event.ports[0].postMessage(value))));"
            ),
        }
        if self.path not in bodies:
            return super().do_GET()
        body = bodies[self.path].encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def validate_observations(observed: dict, previous: dict | None = None) -> None:
    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError("Canvas probe must observe every document and worker context")
    if any(not isinstance(values, dict) or set(values) != {"pixels", "repeat", "blob", "htmlBlob", "htmlDataUrl"}
           for values in observed.values()):
        raise ValueError("Canvas readback paths are missing")
    for name, values in observed.items():
        digest = values["pixels"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Canvas pixels were not measured")
        for key in ("repeat", "blob", "htmlBlob", "htmlDataUrl"):
            expected = None if name in {"dedicated", "shared", "service"} and key.startswith("html") else digest
            if values[key] != expected:
                raise ValueError(f"Canvas readback disagrees in {name}/{key}")
        if digest != observed["document"]["pixels"]:
            raise ValueError(f"Unmodified drawing differs across native contexts: {name}")
    if previous is not None and observed != previous:
        raise ValueError("Canvas readback changed across an unmodified profile restart")


async def observe(context, origin: str) -> dict:
    page = context.pages[0]
    await page.goto(origin, wait_until="load", timeout=30000)
    await page.evaluate("url => { const frame = document.createElement('iframe'); frame.id = 'cross-origin'; frame.src = url; document.body.append(frame); }",
                        origin.replace("127.0.0.1", "localhost") + "/cross-frame")
    await page.locator("#cross-origin").content_frame.locator("h1").wait_for(timeout=15000)
    observed = {"document": await page.evaluate(READ)}
    for name, frame_id in (("same_origin_frame", "owned-frame"), ("cross_origin_frame", "cross-origin")):
        element = await page.locator("#" + frame_id).element_handle()
        observed[name] = await (await element.content_frame()).evaluate(READ)
    observed.update(await asyncio.wait_for(page.evaluate(WORKERS), timeout=40))
    return observed


async def verify(executable: Path, profile: Path, origin: str, report: dict) -> None:
    previous = None
    async with async_playwright() as driver:
        for phase in ("initial", "persistent-profile-restart"):
            context = await driver.chromium.launch_persistent_context(
                str(profile), executable_path=str(executable), headless=True,
                chromium_sandbox=True, timeout=30000)
            try:
                report["browser_version"] = context.browser.version
                observed = await observe(context, origin)
                check = {"name": phase, "observed": observed, "passed": False}
                report["checks"].append(check)
                validate_observations(observed, previous)
                check["passed"] = True
                previous = observed
            finally:
                await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = {"schema": 1, "platform": platform.platform(), "passed": False, "checks": [],
              "scope": "Unmodified Canvas consistency baseline only; no masking or anti-bot claim"}
    server = None
    thread = None
    try:
        executable = args.executable.resolve(strict=True)
        if not executable.is_file():
            raise ValueError("An explicit Chromium executable is required")
        with executable.open("rb") as stream:
            report["binary_sha256_measured"] = hashlib.file_digest(stream, "sha256").hexdigest()
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), CanvasFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="native-canvas-owned-", dir=args.work_dir.resolve()) as owned:
            asyncio.run(verify(executable, Path(owned), f"http://127.0.0.1:{server.server_port}", report))
        with executable.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != report["binary_sha256_measured"]:
                raise ValueError("Chromium executable changed during Canvas verification")
        report["passed"] = True
    except Exception as error:
        report.update(error=str(error), traceback=traceback.format_exc())
    finally:
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
