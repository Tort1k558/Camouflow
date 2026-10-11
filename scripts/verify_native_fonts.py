"""Verify Windows native font selection using owned pages and genuine local fonts."""

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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright  # noqa: E402
from scripts.verify_native_hardware import WORKERS  # noqa: E402
from scripts.verify_native_runtime import FixtureHandler, FixtureServer  # noqa: E402

READ = """async postscript => {
  const text = 'mmmmmmmmiiiiWWW012345';
  const canvas = new OffscreenCanvas(480, 80);
  const context = canvas.getContext('2d', {willReadFrequently:true});
  const measure = async family => {
    context.clearRect(0, 0, 480, 80);
    context.font = '20px ' + family;
    const width = context.measureText(text).width;
    context.fillText(text, 0, 35);
    const pixels = context.getImageData(0, 0, 480, 80).data;
    const digest = await crypto.subtle.digest('SHA-256', pixels);
    const hash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2,'0')).join('');
    let cssWidth = null;
    if (typeof document !== 'undefined') {
      const span = document.createElement('span');
      span.style.cssText = 'position:absolute;white-space:pre;font:20px ' + family;
      span.textContent = text;
      document.body.append(span);
      try { cssWidth = span.getBoundingClientRect().width; }
      finally { span.remove(); }
    }
    return {width, hash, cssWidth};
  };
  const local = new FontFace('OwnedExcludedLocal', 'local("' + postscript + '")');
  let excludedLocalLoaded = false;
  try { await local.load(); excludedLocalLoaded = true; }
  catch (error) { if (!(error instanceof DOMException)) throw error; }
  const downloaded = new FontFace('OwnedDownloaded', 'url(/owned-font.ttf)');
  const fontSet = typeof document === 'undefined' ? self.fonts : document.fonts;
  try {
    await downloaded.load(); fontSet.add(downloaded);
    return {
      origin: self.location.origin,
      arial: await measure('Arial'),
      excluded: await measure('"Courier New", Arial'),
      downloaded: await measure('OwnedDownloaded'),
      excludedLocalLoaded
    };
  } finally { fontSet.delete(downloaded); }
}"""


class FontFixtureHandler(FixtureHandler):
    def do_GET(self):
        if self.path == "/owned-font.ttf":
            body = getattr(self.server, "font_bytes", b"")
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "font/ttf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        name = json.dumps(getattr(self.server, "font_postscript", ""))
        read = f"const read = ({READ});"
        bodies = {
            "/hardware-dedicated.js": read + f"self.onmessage = async () => self.postMessage(await read({name}));",
            "/hardware-shared.js": read + f"self.onconnect = event => {{ const port = event.ports[0]; port.onmessage = async () => port.postMessage(await read({name})); port.start(); }};",
            "/hardware-service.js": read + (
                "self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));"
                "self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));"
                f"self.addEventListener('message', event => event.waitUntil(read({name}).then(values => event.ports[0].postMessage(values))));"
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


def validate_font_probe(observed: dict, baseline: dict | None, protected: bool) -> None:
    if protected and baseline is None:
        raise ValueError("Native font policy requires an observed unrestricted positive control")
    for name in ("arial", "excluded", "downloaded"):
        measured = observed.get(name, {})
        width = measured.get("width")
        if type(width) not in (int, float) or not math.isfinite(width) or width <= 0:
            raise ValueError("Font probe returned invalid genuine text metrics")
        digest = measured.get("hash", "")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Font probe did not measure canvas pixels")
        css = measured.get("cssWidth")
        if css is not None and (type(css) not in (int, float) or not math.isfinite(css) or abs(css - width) > 0.03125):
            raise ValueError("CSS and canvas disagree about native font metrics")
    if observed.get("excludedLocalLoaded") is not (not protected):
        raise ValueError("Native collection policy ignored or CSS local() bypassed it")
    if baseline is None:
        if abs(observed["arial"]["width"] - observed["excluded"]["width"]) < 1:
            raise ValueError("Positive control cannot distinguish the selected and excluded real fonts")
        return
    for name in ("arial", "downloaded", "excluded"):
        expected = baseline["arial" if protected and name == "excluded" else name]
        if any(observed[name][key] != expected[key] for key in ("width", "hash")):
            raise ValueError("Native font selection changed genuine rendering or leaked an excluded font")


def validate_enumeration(fonts: list, protected: bool) -> None:
    if not fonts or any(not isinstance(font, dict) or not isinstance(font.get("family"), str) for font in fonts):
        raise ValueError("Local Font Access did not enumerate genuine fonts")
    families = {font["family"].lower() for font in fonts}
    if protected and families != {"arial"}:
        raise ValueError("Local Font Access leaked families outside the native selection")
    if not protected and not {"arial", "courier new"}.issubset(families):
        raise ValueError("Windows font positive controls are unavailable")


async def verify(executable: Path, root: Path, server, checks: list) -> dict:
    origin = f"http://127.0.0.1:{server.server_port}"
    baseline = None
    expected_styles = None
    async with async_playwright() as driver:
        for name, protected, legacy in (
            ("native-default", False, False), ("native-legacy", False, True),
            ("selected-default", True, False), ("selected-legacy", True, True),
        ):
            with tempfile.TemporaryDirectory(prefix="native-fonts-owned-", dir=root) as profile:
                arguments = ["--camouflow-font-families=Arial"] if protected else []
                if legacy:
                    arguments.append("--disable-features=FontDataServiceAllWebContents")
                for restart in range(2 if protected else 1):
                    context = await driver.chromium.launch_persistent_context(
                        profile, executable_path=str(executable), chromium_sandbox=True,
                        headless=True, args=arguments, permissions=["local-fonts"], timeout=30000)
                    try:
                        version = context.browser.version
                        page = context.pages[0]
                        await page.goto(origin, wait_until="load", timeout=30000)
                        fonts = await page.evaluate("async () => (await queryLocalFonts()).map(font => ({family:font.family, postscriptName:font.postscriptName, style:font.style}))")
                        styles = sorted((font["postscriptName"], font["style"]) for font in fonts if font["family"] == "Arial")
                        check = {"mode": name, "restart": restart, "context": "local_font_access",
                                 "families": sorted({f["family"] for f in fonts}), "font_count": len(fonts),
                                 "arial_styles": styles, "passed": False}
                        checks.append(check)
                        validate_enumeration(fonts, protected)
                        if expected_styles is None:
                            expected_styles = styles
                        elif styles != expected_styles:
                            raise ValueError("Native selection lost or altered genuine Arial font styles")
                        check["passed"] = True
                        if baseline is None:
                            selected = next((font for font in fonts if font["family"] == "Courier New" and font["style"].lower() == "regular"), None)
                            if selected is None:
                                raise ValueError("A genuine regular Courier New font is required for the control")
                            server.font_postscript = selected["postscriptName"]
                            contents = await page.evaluate("async name => { const font = (await queryLocalFonts()).find(font => font.postscriptName === name); return Array.from(new Uint8Array(await (await font.blob()).arrayBuffer())); }", server.font_postscript)
                            if not 0 < len(contents) <= 8 * 1024 * 1024:
                                raise ValueError("Owned font fixture exceeds its bounded memory limit")
                            server.font_bytes = bytes(contents)
                        await page.evaluate("""async origin => {
                          const frame = document.createElement('iframe');
                          const loaded = new Promise(resolve => frame.onload = resolve);
                          frame.src = origin.replace('127.0.0.1', 'localhost') + '/cross-frame';
                          document.body.append(frame); await loaded;
                        }""", origin)
                        if len(page.frames) != 3:
                            raise ValueError("Exactly two owned font frame contexts must be observed")
                        frames = [("document", page), *zip(("same_origin_frame", "cross_origin_frame"), page.frames[1:])]
                        observations = {scope: await frame.evaluate(READ, server.font_postscript) for scope, frame in frames}
                        observations.update(await asyncio.wait_for(page.evaluate(WORKERS), timeout=40))
                        if set(observations) != {"document", "same_origin_frame", "cross_origin_frame", "dedicated", "shared", "service"}:
                            raise ValueError("All six document/worker font contexts must be observed")
                        for scope, observed in observations.items():
                            check = {"mode": name, "restart": restart, "context": scope,
                                     "observed": observed, "passed": False}
                            checks.append(check)
                            expected_origin = origin.replace("127.0.0.1", "localhost") if scope == "cross_origin_frame" else origin
                            if observed.get("origin") != expected_origin:
                                raise ValueError("Font probe did not execute in its intended document/worker origin")
                            validate_font_probe(observed, baseline, protected)
                            check["passed"] = True
                            if baseline is None:
                                baseline = observed
                    finally:
                        await context.close()
    with executable.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"passed": True, "platform": platform.system(), "version": version,
            "binary_sha256_measured": checksum, "checks": checks,
            "scope": "Windows font collections, CSS/local(), genuine canvas metrics/pixels, workers, downloaded font, enumeration and restart; not arbitrary font-file/TTC byte isolation"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    checks = []
    server = FixtureServer(("127.0.0.1", 0), FontFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if sys.platform != "win32":
            raise ValueError("This gate verifies the Windows-only font collection patch")
        args.work_dir.mkdir(parents=True, exist_ok=True)
        report = asyncio.run(verify(args.executable.resolve(), args.work_dir, server, checks))
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
