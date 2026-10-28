"""Measure native Canvas readback consistency; this is not a masking acceptance gate."""

from __future__ import annotations

import argparse
import asyncio
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
from scripts.verify_native_runtime import FixtureHandler, FixtureServer, measure_runtime_core


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
  let htmlBlob = null, htmlDataUrl = null, htmlCapture = null;
  if (typeof document !== 'undefined') {
    const html = document.createElement('canvas');
    html.width = width; html.height = height;
    const htmlContext = html.getContext('2d', {willReadFrequently: true});
    htmlContext.drawImage(canvas, 0, 0);
    const dataUrl = html.toDataURL('image/png');
    const pendingExport = new Promise((resolve, reject) => html.toBlob(
      value => value ? resolve(value) : reject(new Error('Canvas export returned null')), 'image/png'));
    htmlContext.fillStyle = '#000000'; htmlContext.fillRect(0, 0, width, height);
    htmlCapture = await hash(read(htmlContext)) !== pixels;
    const exported = await pendingExport;
    htmlBlob = await decode(exported);
    const response = await fetch(dataUrl);
    htmlDataUrl = await decode(await response.blob());
  }
  const equal = (left, right) => left.length === right.length && left.every((value, i) => value === right[i]);
  const full = read(context);
  const expected = new Uint8ClampedArray(8 * 7 * 4);
  for (let y = 0; y < 7; y++) {
    expected.set(full.subarray(((y + 5) * width + 3) * 4, ((y + 5) * width + 11) * 4), y * 8 * 4);
  }
  const partial = context.getImageData(3, 5, 8, 7).data;
  const negative = context.getImageData(11, 12, -8, -7).data;
  const outside = context.getImageData(-2, -3, 1, 1).data;
  const clipped = context.getImageData(-1, -1, 2, 2).data;
  const expectedClipped = new Uint8ClampedArray(16);
  expectedClipped.set(full.subarray(0, 4), 12);
  const transparent = new OffscreenCanvas(width, height);
  const transparentContext = transparent.getContext('2d', {willReadFrequently: true});
  transparentContext.fillStyle = 'rgba(255, 0, 0, 0.5)';
  transparentContext.fillRect(3, 5, 8, 7);
  const transparentPixels = await hash(read(transparentContext));
  const transparentData = read(transparentContext);
  const geometry = {
    partialMatchesFull: equal(partial, expected),
    negativeDimensionsMatch: equal(negative, expected),
    outsideRemainsTransparent: equal(outside, new Uint8ClampedArray(4)),
    clippedPaddingMatches: equal(clipped, expectedClipped),
    opaqueCornerRendered: equal(full.subarray((width * height - 1) * 4), new Uint8ClampedArray([52, 86, 120, 255])),
    transparentAlphaRendered: equal(transparentData.subarray((5 * width + 3) * 4, (5 * width + 3) * 4 + 4),
                                    new Uint8ClampedArray([255, 0, 0, 128])),
    transparentRepeat: transparentPixels === await hash(read(transparentContext)),
    transparentExport: transparentPixels === await decode(await transparent.convertToBlob({type: 'image/png'}))
  };
  const errorName = async action => {
    try { await action(); return 'no-error'; }
    catch (error) { return error instanceof DOMException ? error.name : 'non-DOM-exception'; }
  };
  const empty = new OffscreenCanvas(0, 1);
  empty.getContext('2d');
  const errors = {
    zeroWidthRead: await errorName(() => context.getImageData(0, 0, 0, 1)),
    zeroHeightRead: await errorName(() => context.getImageData(0, 0, 1, 0)),
    emptyOffscreenExport: await errorName(() => empty.convertToBlob({type: 'image/png'}))
  };
  return {pixels, repeat, blob, htmlBlob, htmlDataUrl, htmlCapture, geometry, errors};
}"""

CONTEXTS = {"document", "same_origin_frame", "cross_origin_frame", "about_blank_frame",
            "srcdoc_frame", "dedicated", "shared", "service"}
GEOMETRY_EXPECTED = {"partialMatchesFull": True, "negativeDimensionsMatch": True,
                     "outsideRemainsTransparent": True, "transparentRepeat": True,
                     "transparentExport": True, "clippedPaddingMatches": True,
                     "opaqueCornerRendered": True, "transparentAlphaRendered": True}

ERRORS_EXPECTED = {"zeroWidthRead": "IndexSizeError", "zeroHeightRead": "IndexSizeError",
                   "emptyOffscreenExport": "IndexSizeError"}

SECURITY_READ = """async () => {
  const failure = action => {
    try { action(); return 'no-error'; }
    catch (error) { return error instanceof DOMException ? error.name : 'non-DOM-exception'; }
  };
  const image = new Image();
  const url = new URL('/canvas-taint.svg', location.href);
  url.hostname = location.hostname === 'localhost' ? '127.0.0.1' : 'localhost';
  await new Promise((resolve, reject) => {
    image.onload = resolve; image.onerror = () => reject(new Error('Owned cross-origin image failed'));
    image.src = url.href;
  });
  const canvas = document.createElement('canvas'); canvas.width = 16; canvas.height = 16;
  const context = canvas.getContext('2d'); context.drawImage(image, 0, 0);
  const taintedRead = failure(() => context.getImageData(0, 0, 16, 16));
  const taintedDataUrl = failure(() => canvas.toDataURL());
  const taintedBlob = failure(() => canvas.toBlob(() => {}));
  const offscreen = new OffscreenCanvas(16, 16);
  const target = offscreen.getContext('2d'); target.drawImage(image, 0, 0);
  const taintedOffscreenRead = failure(() => target.getImageData(0, 0, 16, 16));
  let taintedOffscreenBlob = 'no-error';
  try { await offscreen.convertToBlob(); }
  catch (error) { taintedOffscreenBlob = error instanceof DOMException ? error.name : 'non-DOM-exception'; }
  const taintedZeroWidth = failure(() => context.getImageData(0, 0, 0, 1));
  const taintedOffscreenZeroWidth = failure(() => target.getImageData(0, 0, 0, 1));
  const propagated = {};
  for (const [name, source] of [['html', canvas], ['offscreen', offscreen]]) {
    const bitmap = await createImageBitmap(source);
    try {
      const copy = new OffscreenCanvas(16, 16);
      const copyContext = copy.getContext('2d'); copyContext.drawImage(bitmap, 0, 0);
      propagated[name] = failure(() => copyContext.getImageData(0, 0, 1, 1));
    } finally { bitmap.close(); }
  }
  context.clearRect(0, 0, 16, 16); target.clearRect(0, 0, 16, 16);
  const clearedTaint = failure(() => context.getImageData(0, 0, 1, 1));
  const clearedOffscreenTaint = failure(() => target.getImageData(0, 0, 1, 1));
  for (const active of [context, target]) {
    active.fillStyle = '#112233'; active.globalAlpha = 0.5; active.setTransform(2, 0, 0, 2, 1, 1);
  }
  canvas.width = canvas.width; offscreen.width = offscreen.width;
  const resetBlank = active => active.getImageData(0, 0, 16, 16).data.every(value => value === 0);
  const resetState = active => {
    const matrix = active.getTransform();
    return active.fillStyle === '#000000' && active.globalAlpha === 1
      && [matrix.a, matrix.b, matrix.c, matrix.d, matrix.e, matrix.f].every(
        (value, index) => value === [1, 0, 0, 1, 0, 0][index]);
  };
  const resetHtmlBlank = resetBlank(context), resetOffscreenBlank = resetBlank(target);
  const resetHtmlState = resetState(context), resetOffscreenState = resetState(target);
  const resetHtmlExport = await new Promise(resolve => canvas.toBlob(value => resolve(value?.type === 'image/png')));
  const resetOffscreenExport = (await offscreen.convertToBlob()).type === 'image/png';
  context.drawImage(image, 0, 0); target.drawImage(image, 0, 0);
  const retaintedRead = failure(() => context.getImageData(0, 0, 1, 1));
  const retaintedOffscreenRead = failure(() => target.getImageData(0, 0, 1, 1));
  const empty = document.createElement('canvas'); empty.width = 0;
  const zeroWidthRead = failure(() => empty.getContext('2d').getImageData(0, 0, 0, 1));
  const emptyDataUrl = empty.toDataURL();
  const emptyBlob = await new Promise(resolve => empty.toBlob(blob => resolve(blob === null)));
  return {taintedRead, taintedDataUrl, taintedBlob, taintedOffscreenRead,
          taintedOffscreenBlob, zeroWidthRead, emptyDataUrl, emptyBlob,
          taintedZeroWidth, taintedOffscreenZeroWidth,
          htmlBitmapTaint: propagated.html, offscreenBitmapTaint: propagated.offscreen,
          clearedTaint, clearedOffscreenTaint, resetHtmlBlank, resetOffscreenBlank,
          resetHtmlState, resetOffscreenState, resetHtmlExport, resetOffscreenExport,
          retaintedRead, retaintedOffscreenRead};
}"""

SECURITY_EXPECTED = {"taintedRead": "SecurityError", "taintedDataUrl": "SecurityError",
                     "taintedBlob": "SecurityError", "taintedOffscreenRead": "SecurityError",
                     "taintedOffscreenBlob": "SecurityError", "zeroWidthRead": "IndexSizeError",
                     "emptyDataUrl": "data:,", "emptyBlob": True,
                     # Pinned Chromium checks origin cleanliness before zero dimensions;
                     # this baseline is not a claim of current HTML exception-order conformance.
                     "taintedZeroWidth": "SecurityError", "taintedOffscreenZeroWidth": "SecurityError",
                     "htmlBitmapTaint": "SecurityError", "offscreenBitmapTaint": "SecurityError",
                     "clearedTaint": "SecurityError", "clearedOffscreenTaint": "SecurityError",
                     "resetHtmlBlank": True, "resetOffscreenBlank": True,
                     "resetHtmlState": True, "resetOffscreenState": True,
                     "resetHtmlExport": True, "resetOffscreenExport": True,
                     "retaintedRead": "SecurityError", "retaintedOffscreenRead": "SecurityError"}


class CanvasFixtureHandler(FixtureHandler):
    worker_read = READ

    def do_GET(self):
        if self.path == "/canvas-taint.svg":
            body = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="red"/></svg>'
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        bodies = {
            "/hardware-dedicated.js": f"self.onmessage = async () => self.postMessage(await ({self.worker_read})());",
            "/hardware-shared.js": f"self.onconnect = event => {{ const port = event.ports[0]; port.onmessage = async () => port.postMessage(await ({self.worker_read})()); port.start(); }};",
            "/hardware-service.js": (
                "self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));"
                "self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));"
                f"self.addEventListener('message', event => event.waitUntil(({self.worker_read})().then(value => event.ports[0].postMessage(value))));"
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


def validate_observations(observed: dict, previous: dict | None = None, *,
                          require_context_equality: bool = True) -> None:
    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError("Canvas probe must observe every document and worker context")
    if any(not isinstance(values, dict) or set(values) != {"pixels", "repeat", "blob", "htmlBlob", "htmlDataUrl", "htmlCapture", "geometry", "errors"}
           for values in observed.values()):
        raise ValueError("Canvas readback paths are missing")
    for name, values in observed.items():
        expected_capture = None if name in {"dedicated", "shared", "service"} else True
        if values["htmlCapture"] is not expected_capture:
            raise ValueError(f"Canvas HTML export mutation was not measured in {name}")
        if values["errors"] != ERRORS_EXPECTED:
            raise ValueError(f"Canvas zero-size API errors changed in {name}")
        if (not isinstance(values["geometry"], dict) or set(values["geometry"]) != set(GEOMETRY_EXPECTED)
                or any(value is not True for value in values["geometry"].values())):
            raise ValueError(f"Canvas partial or transparent readback disagrees in {name}")
        digest = values["pixels"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Canvas pixels were not measured")
        for key in ("repeat", "blob", "htmlBlob", "htmlDataUrl"):
            expected = None if name in {"dedicated", "shared", "service"} and key.startswith("html") else digest
            if values[key] != expected:
                raise ValueError(f"Canvas readback disagrees in {name}/{key}")
        if require_context_equality and digest != observed["document"]["pixels"]:
            raise ValueError(f"Unmodified drawing differs across native contexts: {name}")
    if previous is not None and observed != previous:
        raise ValueError("Canvas readback changed across an unmodified profile restart")


def validate_security(observed: dict) -> None:
    if (not isinstance(observed, dict) or set(observed) != {"document", "same_origin_frame", "cross_origin_frame"}
            or any(values != SECURITY_EXPECTED for values in observed.values())):
        raise ValueError("Native Canvas security or empty-image behavior changed")


async def read_owned_context(frame, read: str, name: str, *, timeout: float = 30):
    try:
        return await asyncio.wait_for(frame.evaluate(read), timeout=timeout)
    except TimeoutError as error:
        raise TimeoutError("Owned readback timed out in " + name) from error


async def observe(context, origin: str, read: str = READ) -> dict:
    page = context.pages[0]
    await page.goto(origin, wait_until="load", timeout=30000)
    await page.evaluate("url => { const frame = document.createElement('iframe'); frame.id = 'cross-origin'; frame.src = url; document.body.append(frame); }",
                        origin.replace("127.0.0.1", "localhost") + "/cross-frame")
    await page.locator("#cross-origin").content_frame.locator("h1").wait_for(timeout=15000)
    await page.evaluate("""() => {
      const blank = document.createElement('iframe');
      blank.id = 'owned-about-blank'; blank.src = 'about:blank';
      document.body.append(blank);
      const srcdoc = document.createElement('iframe');
      srcdoc.id = 'owned-srcdoc'; srcdoc.srcdoc = '<h1>Owned srcdoc context</h1>';
      document.body.append(srcdoc);
    }""")
    await page.locator("#owned-srcdoc").content_frame.locator("h1").wait_for(timeout=15000)
    observed = {"document": await read_owned_context(page, read, "document")}
    for name, frame_id in (("same_origin_frame", "owned-frame"), ("cross_origin_frame", "cross-origin"),
                           ("about_blank_frame", "owned-about-blank"), ("srcdoc_frame", "owned-srcdoc")):
        element = await page.locator("#" + frame_id).element_handle()
        if element is None:
            raise ValueError("Owned Canvas frame element is missing: " + name)
        frame = await element.content_frame()
        if frame is None:
            raise ValueError("Owned Canvas frame is missing: " + name)
        observed[name] = await read_owned_context(frame, read, name)
    observed.update(await read_owned_context(page, WORKERS, "workers", timeout=40))
    return observed


async def security_frames(page) -> dict:
    frames = {"document": page.main_frame}
    for name, frame_id in (("same_origin_frame", "owned-frame"), ("cross_origin_frame", "cross-origin")):
        element = await page.locator("#" + frame_id).element_handle()
        if element is None:
            raise ValueError("Owned security frame element is missing: " + name)
        frame = await element.content_frame()
        if frame is None:
            raise ValueError("Owned security frame is missing: " + name)
        frames[name] = frame
    return frames


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
                security = {}
                page = context.pages[0]
                for name, frame in (await security_frames(page)).items():
                    security[name] = await asyncio.wait_for(frame.evaluate(SECURITY_READ), timeout=20)
                check = {"name": phase + "-security-and-empty-images", "observed": security, "passed": False}
                report["checks"].append(check)
                validate_security(security)
                check["passed"] = True
            finally:
                await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--windows-library-directory", type=Path,
                        help="Canonical DLL directory inside a relocated Windows browser package")
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Refusing to overwrite existing Canvas evidence")
    report = {"schema": 1, "platform": platform.platform(), "passed": False, "checks": [],
              "readback_contexts": sorted(CONTEXTS),
              "scope": "Unmodified Canvas consistency baseline only; no masking or anti-bot claim"}
    server = None
    thread = None
    try:
        executable = args.executable.resolve(strict=True)
        if not executable.is_file():
            raise ValueError("An explicit Chromium executable is required")
        core = measure_runtime_core(executable, args.windows_library_directory)
        report["runtime_core_sha256_measured"] = core
        report["binary_sha256_measured"] = core[executable.name]
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), CanvasFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="native-canvas-owned-", dir=args.work_dir.resolve()) as owned:
            asyncio.run(verify(executable, Path(owned), f"http://127.0.0.1:{server.server_port}", report))
        if measure_runtime_core(executable, args.windows_library_directory) != core:
            raise ValueError("Chromium runtime core changed during Canvas verification")
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
        with args.report.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, indent=2))
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
