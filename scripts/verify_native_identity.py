"""Verify native headless UA policy across HTTP, frames and workers, not CAPTCHA scores."""

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

from playwright.async_api import Error as PlaywrightError, async_playwright  # noqa: E402
from app.core.native.diagnostics import audit_observed_request_identity  # noqa: E402
from scripts.verify_native_hardware import WORKERS  # noqa: E402
from scripts.verify_native_runtime import FixtureHandler, FixtureServer, measure_runtime_core  # noqa: E402

FLAG = "--camouflow-native-user-agent"
HINTS = ("Sec-CH-UA", "Sec-CH-UA-Mobile", "Sec-CH-UA-Platform", "Sec-CH-UA-Arch",
         "Sec-CH-UA-Bitness", "Sec-CH-UA-Platform-Version", "Sec-CH-UA-Full-Version-List",
         "Sec-CH-UA-Model", "Sec-CH-UA-WoW64", "Sec-CH-UA-Form-Factors")
HINT_POLICY_FEATURES = tuple(name.lower().removeprefix("sec-") for name in HINTS)


def delegated_hint_policy(port: int) -> str:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Identity fixture requires an actual owned server port")
    return ", ".join(f'{feature}=(self "http://localhost:{port}")' for feature in HINT_POLICY_FEATURES)


READ = """async () => {
  const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(navigator), 'userAgent');
  let illegalInvocation = false;
  try { descriptor.get.call({}); } catch (error) { illegalInvocation = error instanceof TypeError; }
  return {
    userAgent: navigator.userAgent,
    language: navigator.language,
    userAgentData: navigator.userAgentData.toJSON(),
    metadata: await navigator.userAgentData.getHighEntropyValues([
      'architecture', 'bitness', 'platformVersion', 'fullVersionList', 'model', 'wow64', 'formFactors']),
    headers: await (await fetch('/identity-echo')).json(),
    getter: Function.prototype.toString.call(descriptor.get), illegalInvocation,
    ownProperty: Object.hasOwn(navigator, 'userAgent'),
    plugins: navigator.plugins ? Array.from(navigator.plugins, plugin => plugin.name) : null,
    chromeType: typeof globalThis.chrome
  };
}"""


class IdentityFixtureHandler(FixtureHandler):
    def do_GET(self):
        if self.path == "/identity-echo":
            body = json.dumps({name.lower(): self.headers.get(name)
                               for name in ("User-Agent", "Accept-Language", *HINTS)}).encode("utf-8")
            content_type = "application/json"
        elif self.path == "/hardware-dedicated.js":
            body = f"self.onmessage = async () => self.postMessage(await ({READ})());".encode("utf-8")
            content_type = "application/javascript"
        elif self.path == "/hardware-shared.js":
            body = ("self.onconnect = event => { const port = event.ports[0]; "
                    f"port.onmessage = async () => port.postMessage(await ({READ})()); port.start(); }}").encode("utf-8")
            content_type = "application/javascript"
        elif self.path == "/hardware-service.js":
            body = ("self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));"
                    "self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));"
                    f"self.addEventListener('message', event => event.waitUntil((async () => event.ports[0].postMessage(await ({READ})()))()));").encode("utf-8")
            content_type = "application/javascript"
        else:
            body = b"<!doctype html><title>Owned Native identity fixture</title><h1>Native identity</h1>"
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-CH", ", ".join(HINTS))
        if self.server.strict_client_hints:
            self.send_header("Permissions-Policy", delegated_hint_policy(self.server.server_port))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


def validate_observation(observed: dict, baseline: dict, *, protected: bool, worker: bool,
                         strict_client_hints: bool = False) -> None:
    if not worker:
        for values in (baseline, observed):
            headers = values.get("headers")
            names = ("user-agent", "accept-language", *(name.lower() for name in HINTS)) if strict_client_hints else (
                "user-agent", "accept-language", "sec-ch-ua-platform", "sec-ch-ua-mobile")
            identity_headers = ({name: headers.get(name) for name in names}
                if isinstance(headers, dict) else headers)
            issues = audit_observed_request_identity(identity_headers,
                {"document": {**values, "userAgentHighEntropy": values.get("metadata")}},
                strict_client_hints=strict_client_hints)
            if issues:
                raise ValueError("Native request/JS identity contradictions: " + "; ".join(issues))
    if baseline["userAgent"].count("HeadlessChrome/") != 1:
        raise ValueError("An actual headless UA leak is required as the baseline control")
    if not baseline["metadata"].get("fullVersionList"):
        raise ValueError("Genuine high-entropy browser versions are required as a control")
    expected = baseline["userAgent"].replace("HeadlessChrome/", "Chrome/") if protected else baseline["userAgent"]
    if observed["userAgent"] != expected or observed["headers"]["user-agent"] != expected:
        raise ValueError("Native UA policy does not agree across JavaScript and HTTP")
    if observed["metadata"] != baseline["metadata"]:
        raise ValueError("Native UA policy changed genuine Client Hints")
    for name in HINTS:
        if observed["headers"][name.lower()] != baseline["headers"][name.lower()]:
            raise ValueError("Native UA policy changed HTTP Client Hints: " + name)
    if observed["ownProperty"] or not observed["illegalInvocation"] or "[native code]" not in observed["getter"]:
        raise ValueError("Native userAgent getter shape was replaced")
    if worker:
        if observed["plugins"] is not None:
            raise ValueError("Unexpected plugin API on WorkerNavigator")
    elif observed["plugins"] != baseline["plugins"] or observed["chromeType"] != baseline["chromeType"]:
        raise ValueError("Native policy changed genuine plugins or window.chrome")


async def verify(executable: Path, work_dir: Path, origin: str, checks: list, *, strict_client_hints: bool = False) -> dict:
    core = measure_runtime_core(executable)
    baselines = {}
    async with async_playwright() as driver:
        for name, args in (("native-default", []), ("native-identity", [FLAG])):
            with tempfile.TemporaryDirectory(prefix="native-identity-", dir=work_dir) as owned:
                context = await driver.chromium.launch_persistent_context(
                    owned, executable_path=str(executable), headless=True, chromium_sandbox=True, args=args)
                try:
                    version = context.browser.version
                    page = context.pages[0]
                    await page.goto(origin)
                    await page.evaluate("""async ({origin, allow}) => {
                      for (const url of [origin, origin.replace('127.0.0.1', 'localhost')]) {
                        const frame = document.createElement('iframe');
                        if (allow) frame.allow = allow;
                        const loaded = new Promise(resolve => frame.onload = resolve);
                        frame.src = url; document.body.append(frame); await loaded;
                      }
                    }""", {"origin": origin, "allow": "; ".join(HINT_POLICY_FEATURES) if strict_client_hints else ""})
                    if len(page.frames) != 3:
                        raise ValueError("Both owned identity frames must be observed")
                    popup = await context.new_page()
                    await popup.goto(origin)
                    frames = [("document", page), *zip(("same_origin", "cross_origin"), page.frames[1:]), ("new_target", popup)]
                    values = {scope: await frame.evaluate(READ) for scope, frame in frames}
                    workers = await asyncio.wait_for(page.evaluate(WORKERS), timeout=40)
                    if set(workers) != {"dedicated", "shared", "service"}:
                        raise ValueError("All three identity workers must be observed")
                    values.update(workers)
                    for scope, observed in values.items():
                        baseline = baselines.setdefault(scope, observed)
                        if not any(brand["brand"] == "Chromium" and brand["version"] == version
                                   for brand in observed["metadata"].get("fullVersionList", [])):
                            raise ValueError("Client Hints do not report the actual Chromium browser version")
                        if observed["metadata"] != baselines["document"]["metadata"]:
                            raise ValueError("Native Client Hints disagree across document and worker/frame contexts")
                        check = {"mode": name, "context": scope, "observed": observed, "passed": False}
                        checks.append(check)
                        validate_observation(observed, baseline, protected=name == "native-identity", worker=scope in workers,
                                             strict_client_hints=strict_client_hints)
                        check["passed"] = True
                finally:
                    await context.close()
        for value in ("false", "true", "Chrome/152.0.0.0", "\u0442\u0435\u0441\u0442"):
            with tempfile.TemporaryDirectory(prefix="native-identity-invalid-", dir=work_dir) as owned:
                check = {"mode": "invalid-value", "value": value, "passed": False}
                checks.append(check)
                try:
                    context = await driver.chromium.launch_persistent_context(
                        owned, executable_path=str(executable), headless=True,
                        chromium_sandbox=True, args=[FLAG + "=" + value])
                except PlaywrightError as error:
                    if not any(message in str(error) for message in (
                            "Invalid CamouFlow Native browser identity flag", "Invalid Glint browser identity flag")):
                        raise ValueError("Invalid identity flag did not fail with its native CHECK") from error
                else:
                    await context.close()
                    raise ValueError("Native identity flag silently accepted a value")
                check["passed"] = True
    with executable.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    if measure_runtime_core(executable) != core:
        raise ValueError("Native identity browser core changed during verification")
    return {"passed": True, "platform": platform.system(), "version": version,
            "strict_client_hints": strict_client_hints,
            "runtime_core_sha256_measured": core,
            "binary_sha256_measured": checksum, "checks": checks,
            "scope": "Native UA HTTP/JavaScript coherence and preserved Client Hints/plugins; not CAPTCHA, TLS or CDP invisibility"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--strict-client-hints", action="store_true",
                        help="Compare document/frame low/high-entropy HTTP hints with JS after owned Accept-CH")
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Refusing to overwrite native identity evidence")
    checks = []
    server = FixtureServer(("127.0.0.1", 0), IdentityFixtureHandler)
    server.strict_client_hints = args.strict_client_hints
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        report = asyncio.run(verify(args.executable.resolve(), args.work_dir, f"http://127.0.0.1:{server.server_port}", checks,
                                   strict_client_hints=args.strict_client_hints))
    except Exception as error:
        report = {"passed": False, "platform": platform.system(), "checks": checks,
                  "error_type": type(error).__name__, "error": str(error)}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
