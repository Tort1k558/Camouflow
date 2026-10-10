"""Real Native source-runtime gate; owned local fixtures only, no customer profiles."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import TCPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration  # noqa: E402
from app.core.native.runtime import NativeRuntime, NativeRuntimeError  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

STORAGE = """async value => {
  const db = await new Promise((resolve, reject) => {
    const request = indexedDB.open('owned-native', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('values');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  try {
    const cache = await caches.open('owned-native');
    if (value !== null) {
      document.cookie = 'owned=' + value + '; Max-Age=3600; Path=/';
      localStorage.setItem('owned', value);
      await new Promise((resolve, reject) => {
        const transaction = db.transaction('values', 'readwrite');
        transaction.objectStore('values').put(value, 'owned');
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
      await cache.put('/owned-value', new Response(value));
      await navigator.serviceWorker.register('/worker.js');
      await navigator.serviceWorker.ready;
    }
    const indexed = await new Promise((resolve, reject) => {
      const request = db.transaction('values').objectStore('values').get('owned');
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
    });
    const cached = await cache.match('/owned-value');
    const workers = await navigator.serviceWorker.getRegistrations();
    return {cookie: document.cookie, local: localStorage.getItem('owned'), indexed,
      cached: cached ? await cached.text() : null, workers: workers.length};
  } finally { db.close(); }
}"""


class FixtureServer(HTTPServer):
    authenticated_requests = 0
    challenges = 0
    proxy_mode = False

    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name, self.server_port = "localhost", self.server_address[1]


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.server.proxy_mode:
            expected = "Basic " + base64.b64encode(b"owned-user:owned-pass").decode("ascii")
            if self.headers.get("Proxy-Authorization") != expected:
                self.server.challenges += 1
                self.send_response(407)
                self.send_header("Proxy-Authenticate", 'Basic realm="Native owned fixture"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.server.authenticated_requests += 1
        if self.path == "/worker.js":
            body = b"self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));"
            content_type = "application/javascript"
        else:
            body = b'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Owned Native fixture</title><h1>Native runtime</h1><input aria-label="Value"><button onclick="document.querySelector(\'output\').textContent=document.querySelector(\'input\').value">Apply</button><output></output>'
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


async def resolve_executable(explicit: str) -> Path:
    if explicit:
        return Path(explicit).resolve()
    async with async_playwright() as driver:
        return Path(driver.chromium.executable_path).resolve()


async def verify(profile_root: Path, executable: Path, origin: str, proxy_server: FixtureServer) -> dict:
    desktop = NativeConfiguration()
    mobile = NativeConfiguration(environment="mobile_web", width=390, height=844, device_scale_factor=3)
    a = NativeRuntime(profile_root / "a", executable, desktop)
    b = NativeRuntime(profile_root / "b", executable, mobile)
    proxied = NativeRuntime(profile_root / "proxy", executable, desktop)
    checks = []
    try:
        context_a = await a.start(headless=True)
        context_b = await b.start(headless=True)
        page_a, page_b = context_a.pages[0], context_b.pages[0]
        await page_a.goto(origin)
        await page_b.goto(origin)
        blank = {"cookie": "", "local": None, "indexed": None, "cached": None, "workers": 0}
        assert await page_b.evaluate(STORAGE, None) == blank
        await page_a.evaluate(STORAGE, "alpha")
        assert await page_b.evaluate(STORAGE, None) == blank, "Profile storage leaked"
        await page_b.evaluate(STORAGE, "beta")
        assert await page_a.evaluate(STORAGE, None) == {"cookie": "owned=alpha", "local": "alpha", "indexed": "alpha", "cached": "alpha", "workers": 1}
        checks.append("concurrent-profile-isolation")
        child = await asyncio.to_thread(subprocess.run,
            [sys.executable, str(Path(__file__).resolve()), "--check-lock", str(a.profile_dir), "--executable", str(executable)],
            cwd=ROOT, capture_output=True, text=True, timeout=15)
        assert child.returncode == 0, "Separate process could own the same profile: " + child.stdout + child.stderr
        checks.append("cross-process-owner-exclusion")
        await page_a.get_by_label("Value", exact=True).fill("native automation")
        await page_a.get_by_role("button", name="Apply", exact=True).click()
        assert await page_a.locator("output").inner_text() == "native automation"
        tab = await context_a.new_page()
        await tab.goto(origin)
        await tab.close()
        await page_a.screenshot(path=str(profile_root / "automation.png"))
        checks.append("navigation-tabs-fill-click-extract-screenshot")
        observed = await page_b.evaluate("({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,touch:navigator.maxTouchPoints,webdriver:navigator.webdriver})")
        assert observed["width"] == 390 and observed["height"] == 844
        assert observed["dpr"] == 3 and observed["touch"] > 0
        checks.append("mobile-web-viewport-dpr-touch")
        version = context_a.browser.version
        await a.close()
        await b.close()
        for runtime, value in [(a, "alpha"), (b, "beta")]:
            context = await runtime.start(headless=True)
            page = context.pages[0]
            await page.goto(origin)
            assert await page.evaluate(STORAGE, None) == {"cookie": "owned=" + value, "local": value, "indexed": value, "cached": value, "workers": 1}
            await runtime.close()
        checks.append("cookie-localstorage-indexeddb-cache-serviceworker-restart")
        context = await proxied.start(headless=True, proxy={"server": f"http://127.0.0.1:{proxy_server.server_port}", "username": "owned-user", "password": "owned-pass"})
        response = await context.pages[0].goto("http://native-fixture.invalid/")
        assert response.status == 200
        assert await context.pages[0].title() == "Owned Native fixture"
        assert proxy_server.authenticated_requests > 0 and proxy_server.challenges > 0
        checks.append("authenticated-http-proxy-no-direct-dns-route")
        with executable.open("rb") as binary:
            checksum = hashlib.file_digest(binary, "sha256").hexdigest()
        return {"passed": True, "platform": platform.system(), "architecture": platform.machine(),
                "version": version, "binary_sha256_measured": checksum, "checks": checks,
                "mobile_observed": observed, "fingerprint_patched": False}
    finally:
        try:
            await proxied.close()
        finally:
            try:
                await a.close()
            finally:
                await b.close()


async def check_lock(profile: Path, executable: Path) -> int:
    runtime = NativeRuntime(profile.resolve(), executable, NativeConfiguration())
    try:
        await runtime.start(headless=True)
    except NativeRuntimeError as error:
        return 0 if "Another process owns" in str(error) else 1
    finally:
        await runtime.close()
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="")
    parser.add_argument("--work-dir", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--report", type=Path, default=ROOT / "outputs/native-runtime/source.json")
    parser.add_argument("--check-lock", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    executable = asyncio.run(resolve_executable(args.executable))
    if args.check_lock:
        return asyncio.run(check_lock(args.check_lock, executable))
    args.work_dir.mkdir(parents=True, exist_ok=True)
    server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
    proxy_server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
    proxy_server.proxy_mode = True
    threads = [threading.Thread(target=item.serve_forever, daemon=True) for item in (server, proxy_server)]
    for thread in threads:
        thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="native-owned-", dir=args.work_dir.resolve()) as owned:
            report = asyncio.run(verify(Path(owned).resolve(), executable, f"http://127.0.0.1:{server.server_port}", proxy_server))
    except Exception as error:
        report = {"passed": False, "platform": platform.system(), "error_type": type(error).__name__, "error": str(error)[:1000]}
    finally:
        for item in (server, proxy_server):
            item.shutdown()
            item.server_close()
        for thread in threads:
            thread.join()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
