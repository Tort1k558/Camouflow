"""Isolated integration audit through CamouFlow's real launchers."""
import argparse
import asyncio
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["CAMOUFLOW_DATA_DIR"] = tempfile.mkdtemp(prefix="camouflow-engine-audit-")
from app.core.browser_interface import BrowserInterface
from app.storage import db

OUT = Path(__file__).resolve().parents[1] / ".local/browser-audit"
OUT.mkdir(parents=True, exist_ok=True)
OBSERVE = """async () => {
 const gl = document.createElement('canvas').getContext('webgl');
 const debug = gl && gl.getExtension('WEBGL_debug_renderer_info');
 const canvas = document.createElement('canvas');
 const ctx = canvas.getContext('2d'); ctx.fillText('CamouFlow audit', 5, 20);
 let canvasHash = 0; for (const c of canvas.toDataURL()) canvasHash = (canvasHash * 31 + c.charCodeAt(0)) | 0;
 return {ua:navigator.userAgent, platform:navigator.platform, languages:navigator.languages,
 language:navigator.language, timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,
 cores:navigator.hardwareConcurrency, memory:navigator.deviceMemory, webdriver:navigator.webdriver,
 screen:[screen.width,screen.height], inner:[innerWidth,innerHeight], outer:[outerWidth,outerHeight],
 webgl:debug?[gl.getParameter(debug.UNMASKED_VENDOR_WEBGL),gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)]:null,
 webrtc:typeof RTCPeerConnection, dark:matchMedia('(prefers-color-scheme: dark)').matches,
 canvasHash, jsRan:document.body.dataset.ran === 'yes', cspRan:document.body.dataset.ran === 'yes',
 cookies:document.cookie, storage:localStorage.getItem('audit'),
 permission:await navigator.permissions.query({name:'geolocation'}).then(p=>p.state).catch(()=>null)};
}"""


class Handler(BaseHTTPRequestHandler):
    requests: ClassVar[list] = []

    def do_GET(self):
        self.requests.append({"path": self.path, "headers": {key: self.headers.get(key) for key in ("Accept-Language", "X-Audit")}})
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        if self.path == "/csp":
            self.send_header("Content-Security-Policy", "script-src 'none'")
        self.end_headers()
        self.wfile.write(b'<input id="field"><button id="button">Check</button><script>document.body.dataset.ran="yes"</script><img src="/image">')

    def log_message(self, *args):
        pass


async def run_case(engine, name, settings, url, public=False):
    browser = BrowserInterface("audit-" + engine + "-" + name, browser_engine=engine, browser_settings=settings)
    result = {"engine": engine, "case": name, "settings": settings}
    try:
        await browser.start()
        result["browser_version"] = browser.browser.version if browser.browser else ""
        await browser.page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(.2)
        result["observed"] = await browser.page.evaluate(OBSERVE)
        result["viewport"] = browser.page.viewport_size
        try:
            await browser._human_type(browser.page.locator("#field"), "audit")
            result["typing"] = await browser.page.locator("#field").input_value()
        except Exception as exc:  # noqa: BLE001 - collect failures without losing other engine results
            result["typing_error"] = str(exc)
        await browser.page.goto(url + "csp", wait_until="domcontentloaded")
        result["csp"] = (await browser.page.evaluate(OBSERVE))["cspRan"]
        await browser.page.goto(url, wait_until="domcontentloaded")
        await browser.page.evaluate("document.cookie='audit=kept;path=/';localStorage.setItem('audit','kept')")
        await browser.close(force=True)
        await browser.start()
        await browser.page.goto(url, wait_until="domcontentloaded")
        result["restart"] = await browser.page.evaluate(OBSERVE)
        if public:
            result["sites"] = []
            for label, target in [("sannysoft", "https://bot.sannysoft.com/"),
                                  ("browserleaks", "https://browserleaks.com/javascript"),
                                  ("creepjs", "https://abrahamjuliot.github.io/creepjs/")]:
                site = {"site": label, "url": target}
                try:
                    response = await browser.page.goto(target, wait_until="domcontentloaded", timeout=45000)
                    await asyncio.sleep(8)
                    site.update(http_status=response.status if response else None,
                                observed=await browser.page.evaluate(OBSERVE))
                    site["text_file"] = f"{engine}-{label}.txt"
                    (OUT / site["text_file"]).write_text(await browser.page.locator("body").inner_text(timeout=5000), encoding="utf-8")
                    await browser.page.screenshot(path=str(OUT / f"{engine}-{label}.png"), full_page=True)
                except Exception as exc:  # noqa: BLE001 - retain site/network failures in the report
                    site["error"] = str(exc)
                result["sites"].append(site)
    except Exception as exc:  # noqa: BLE001 - retain launch failures in the report
        result["error"] = str(exc)
    finally:
        await browser.close(force=True)
    return result


async def main(args):
    db.init_db()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"
    results = []
    try:
        for engine in ("camoufox", "cloakbrowser"):
            for name, settings in [
                ("auto", {"headless": True, "locale": "en-US", "timezone": "America/New_York"}),
                ("custom", {"headless": not args.headed, "locale": "de-DE", "timezone": "Europe/Berlin", "window_width": 1100,
                            "window_height": 700, "screen_width": 1920, "screen_height": 1080, "os": ["windows"],
                            "platform": "windows", "hardware_concurrency": 4, "device_memory": 8, "color_scheme": "dark",
                            "navigator_overrides": {"hardwareConcurrency": 4},
                            "permissions": ["geolocation"], "extra_http_headers": {"X-Audit": "profile"}, "bypass_csp": True}),
                ("ephemeral", {"headless": True, "humanize": False, "persistent_context": False, "locale": "fr-FR",
                               "timezone": "Europe/Paris", "window_width": 1000, "window_height": 650}),
                ("blocked", {"headless": True, "humanize": False, "block_webrtc": True, "block_webgl": True,
                             "block_images": True, "java_script_enabled": False}),
            ]:
                result = await run_case(engine, name, settings, url, public=args.public_sites and name == "custom")
                observed, restart = result.get("observed", {}), result.get("restart", {})
                checks = {
                    "launch": "error" not in result,
                    "typing": result.get("typing") == "audit",
                    "javascript": observed.get("jsRan") == (name != "blocked"),
                    "csp": result.get("csp") == (name == "custom"),
                    "session": restart.get("storage") == (None if name == "ephemeral" else "kept"),
                    "stable_ua": bool(observed.get("ua")) and observed.get("ua") == restart.get("ua"),
                    "stable_gpu": observed.get("webgl") == restart.get("webgl"),
                }
                if name in {"auto", "custom", "ephemeral"}:
                    checks["locale"] = observed.get("language") == settings["locale"]
                    checks["timezone"] = observed.get("timezone") == settings["timezone"]
                if name == "custom":
                    checks["screen"] = observed.get("screen") == [1920, 1080]
                    checks["window"] = observed.get("outer") == [1100, 700] if engine == "camoufox" else observed.get("inner") == [1100, 700]
                    checks["cores"] = observed.get("cores") == 4
                if name == "blocked" and engine == "camoufox":
                    checks["webrtc_blocked"] = observed.get("webrtc") == "undefined"
                    checks["webgl_blocked"] = observed.get("webgl") is None
                canvas_stable = observed.get("canvasHash") == restart.get("canvasHash")
                result["canvas_stable"] = canvas_stable
                result["warnings"] = []
                if engine == "cloakbrowser":
                    checks["stable_canvas"] = canvas_stable
                elif not canvas_stable:
                    result["warnings"].append("Camoufox Canvas export changed after restart; per-session protection is not covered by the saved profile identity (upstream issue #721). Noise was not disabled.")
                result["checks"] = checks
                results.append(result)
                (OUT / "report.json").write_text(json.dumps({"passed": all(all(row["checks"].values()) for row in results), "data_root": str(db.DATA_ROOT), "cases": results,
                    "requests": Handler.requests}, indent=2), encoding="utf-8")
                print(engine, name, "passed" if all(checks.values()) else checks, flush=True)
    finally:
        server.shutdown()
        server.server_close()
    if not all(all(row["checks"].values()) for row in results):
        raise SystemExit("Browser settings verification failed; see " + str(OUT / "report.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-sites", action="store_true", help="Visit Sannysoft, BrowserLeaks and CreepJS; their content is stored locally")
    parser.add_argument("--headed", action="store_true", help="Show the browsers for the custom-settings case")
    asyncio.run(main(parser.parse_args()))
