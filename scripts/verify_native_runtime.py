"""Real Native source-runtime gate; owned local fixtures only, no customer profiles."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import threading
import traceback
from contextlib import AsyncExitStack
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration  # noqa: E402
from app.core.native.diagnostics import inspect_native_profile  # noqa: E402
from app.core.native.runtime import NativeRuntime, NativeRuntimeError  # noqa: E402
from playwright.async_api import Error as PlaywrightError, async_playwright  # noqa: E402
from scripts.native_build import measure_runtime_core as measure_build_core  # noqa: E402

def measure_runtime_core(executable: Path, library_directory: Path | None = None) -> dict[str, str]:
    """Bind Windows evidence to executable code in DLLs, not only the launcher."""
    if not executable.is_file():
        raise NativeRuntimeError("Native browser is not installed")
    return measure_build_core(executable, library_directory)


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


PERMISSION_STATES = """async () => Object.fromEntries(await Promise.all(
  ['geolocation', 'notifications'].map(async name =>
    [name, (await navigator.permissions.query({name})).state])))"""


class FixtureServer(ThreadingHTTPServer):
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
            if self.path == "/":
                body += b'<iframe id="owned-frame" src="/frame"></iframe>'
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *args):
        pass


async def resolve_executable(explicit: str) -> Path:
    if explicit:
        return Path(explicit).resolve()
    async with async_playwright() as driver:
        return Path(driver.chromium.executable_path).resolve()


def linux_process_snapshot(root: Path = Path("/proc")) -> dict:
    rows = {}
    for entry in root.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8")
            name, tail = stat.split("(", 1)[1].rsplit(")", 1)
            fields = tail.split()
            if fields[0] in {"Z", "X"}:
                continue
            row = {"parent": int(fields[1]), "started": fields[19], "name": name, "executable": None}
            try:
                row["executable"] = (entry / "exe").readlink().name
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass
            rows[int(entry.name)] = row
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return rows


def process_snapshot() -> dict:
    if sys.platform == "linux":
        return linux_process_snapshot()
    if sys.platform == "win32":
        command = ("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
                   "Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId,Name,CreationDate "
                   "-OperationTimeoutSec 30 | Select-Object ProcessId,ParentProcessId,Name,CreationDate "
                   "| ConvertTo-Json -Compress")
        output = subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", command],
                                         encoding="utf-8", errors="replace", timeout=60)
        rows = json.loads(output) if output.strip() else []
        if isinstance(rows, dict):
            rows = [rows]
        return {row["ProcessId"]: {"parent": row["ParentProcessId"], "name": row["Name"],
                                  "started": row["CreationDate"]} for row in rows}
    output = subprocess.check_output(["ps", "-ww", "-axo", "pid=,ppid=,lstart=,comm="],
                                     encoding="utf-8", errors="replace", timeout=15,
                                     env={**os.environ, "LC_ALL": "C"})
    rows = {}
    for line in output.splitlines():
        fields = line.split(None, 7)
        if len(fields) != 8:
            raise ValueError("Unsupported process snapshot format")
        rows[int(fields[0])] = {"parent": int(fields[1]), "started": " ".join(fields[2:7]),
                                "name": Path(fields[7]).name}
    return rows


def same_process(left: dict | None, right: dict | None) -> bool:
    return bool(left is not None and right is not None
                and left["started"] == right["started"])


def executable_name(row: dict) -> str | None:
    return row["executable"] if "executable" in row else row["name"]


def controller_descendants(before: dict, current: dict, controller_pid: int) -> dict:
    owned = {controller_pid}
    while True:
        children = {pid for pid, row in current.items()
                    if row["parent"] in owned and not same_process(before.get(pid), row)}
        if children <= owned:
            return {pid: current[pid] for pid in owned if pid != controller_pid}
        owned.update(children)


async def controller_child(profile: Path, executable: Path, origin: str) -> None:
    parsed = urlsplit(origin)
    if (profile != profile.resolve() or profile.name != "controller-crash"
            or not profile.parent.name.startswith("native-owned-")
            or parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username is not None or parsed.path not in {"", "/"}
            or not parsed.port or parsed.query or parsed.fragment):
        raise ValueError("Controller crash helper requires an owned profile and loopback fixture")
    runtime = NativeRuntime(profile, executable, NativeConfiguration())
    try:
        context = await runtime.start(headless=True)
        page = context.pages[0]
        await page.goto(origin)
        await page.evaluate(STORAGE, "controller")
        assert (await page.evaluate(STORAGE, None))["cached"] == "controller"
        print(json.dumps({"ready": True, "pid": os.getpid()}), flush=True)
        await asyncio.to_thread(sys.stdin.read, 1)
    finally:
        await runtime.close()


async def verify_controller_crash(profile_root: Path, executable: Path, origin: str) -> int:
    before = await asyncio.to_thread(process_snapshot)
    profile = profile_root / "controller-crash"
    env = {**os.environ, "PYTHONPATH": sysconfig.get_path("purelib") + os.pathsep + os.environ.get("PYTHONPATH", "")}
    stderr_path = profile_root / "controller-stderr.log"
    with stderr_path.open("w", encoding="utf-8") as errors:
        controller = subprocess.Popen([sys._base_executable, str(Path(__file__).resolve()),
                                       "--controller-child", str(profile), "--fixture-origin", origin,
                                       "--executable", str(executable)], cwd=ROOT, env=env,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True)
    try:
        line = await asyncio.wait_for(asyncio.to_thread(controller.stdout.readline), timeout=40)
        if not line:
            raise RuntimeError("Controller child did not start: " + stderr_path.read_text(encoding="utf-8-sig", errors="replace")[-2000:])
        ready = json.loads(line)
        assert ready.get("ready") is True and ready.get("pid") == controller.pid, "Must kill the actual interpreter, not a venv launcher"
        assert controller.poll() is None
        owned = controller_descendants(before, await asyncio.to_thread(process_snapshot), controller.pid)
        assert all(row["started"] is not None for row in owned.values()), "Owned process identity is unavailable"
        assert any((executable_name(row) or "").lower() in {"node", "node.exe"} for row in owned.values()), "Owned driver was not observed"
        assert any((executable_name(row) or "").lower() == executable.name.lower() for row in owned.values()), "Owned Chromium was not observed"
        controller.kill()
        await asyncio.to_thread(controller.wait, timeout=10)
        deadline = asyncio.get_running_loop().time() + 30
        while True:
            current = await asyncio.to_thread(process_snapshot)
            remaining = [pid for pid, row in owned.items() if same_process(current.get(pid), row)]
            if not remaining:
                break
            assert asyncio.get_running_loop().time() < deadline, f"Owned processes survived controller kill: {remaining}"
            await asyncio.sleep(.5)
        runtime = NativeRuntime(profile, executable, NativeConfiguration())
        try:
            context = await runtime.start(headless=True)
            page = context.pages[0]
            await page.goto(origin)
            assert await page.evaluate(STORAGE, None) == {"cookie": "owned=controller", "local": "controller",
                "indexed": "controller", "cached": "controller", "workers": 1}
        finally:
            await runtime.close()
        return len(owned)
    finally:
        if controller.poll() is None:
            controller.kill()
        controller.wait(timeout=10)
        for stream in (controller.stdin, controller.stdout):
            stream.close()


async def _close_restart_profile(runtime, *, round_number: int, profile_slot: int, phase: str) -> None:
    started = asyncio.get_running_loop().time()
    try:
        await runtime.close()
    except Exception as error:
        elapsed = asyncio.get_running_loop().time() - started
        error.add_note(f"Native restart gate: round={round_number}, profile_slot={profile_slot}, "
                       f"phase={phase}, close_elapsed_seconds={elapsed:.3f}")
        raise


async def verify_multi_profile_restarts(profile_root: Path, executable: Path, origin: str,
                                       *, rounds: int = 3, profiles: int = 3,
                                       configuration: NativeConfiguration | None = None) -> list[dict]:
    if type(rounds) is not int or not 1 <= rounds <= 100 or type(profiles) is not int or not 2 <= profiles <= 4:
        raise ValueError("Native restart gate requires 1..100 rounds and 2..4 profiles")
    def expected(value):
        return {"cookie": "owned=" + value, "local": value, "indexed": value,
                "cached": value, "workers": 1}
    blank = {"cookie": "", "local": None, "indexed": None, "cached": None, "workers": 0}
    observations = []
    async def inspect_policy(runtime, page):
        if configuration is None:
            return
        required = configuration.privacy_policy.required_capabilities()
        if runtime.native_policy_capabilities != required:
            raise ValueError("Restart gate lost the admitted runtime policy")
        observed = await inspect_native_profile(page, configuration, runtime.context.browser.version)
        if observed["mismatches"]:
            raise ValueError("Restart gate observed inconsistent policy: " + str(observed["mismatches"]))

    for iteration in range(rounds):
        before = await asyncio.to_thread(process_snapshot)
        owned = {}
        runtimes = []
        pages = []
        async with AsyncExitStack() as cleanup:
            for index in range(profiles):
                runtime = NativeRuntime(profile_root / f"restart-{index}", executable, configuration or NativeConfiguration())
                cleanup.push_async_callback(_close_restart_profile, runtime, round_number=iteration + 1,
                                            profile_slot=index, phase="round-finalizer")
                context = await runtime.start(headless=True)
                runtimes.append(runtime)
                pages.append(context.pages[0])
            await asyncio.gather(*(page.goto(origin) for page in pages))
            for runtime, page in zip(runtimes, pages, strict=True):
                await inspect_policy(runtime, page)
            initial = await asyncio.gather(*(page.evaluate(STORAGE, None) for page in pages))
            assert initial == ([blank] * profiles if iteration == 0 else
                               [expected(f"round-{iteration - 1}-profile-{index}") for index in range(profiles)]), initial
            await asyncio.gather(*(page.evaluate(STORAGE, f"round-{iteration}-profile-{index}")
                                   for index, page in enumerate(pages)))
            values = [expected(f"round-{iteration}-profile-{index}") for index in range(profiles)]
            assert await asyncio.gather(*(page.evaluate(STORAGE, None) for page in pages)) == values
            owned = controller_descendants(before, await asyncio.to_thread(process_snapshot), os.getpid())
            assert all(row["started"] is not None and executable_name(row) is not None for row in owned.values()), "Owned process identity is unavailable"
            drivers = sum(executable_name(row).lower() in {"node", "node.exe"} for row in owned.values())
            assert drivers == profiles, f"Expected {profiles} independent drivers, observed {drivers}"
            assert any(executable_name(row).lower() == executable.name.lower() for row in owned.values()), "Owned Chromium was not observed"
            victim = iteration % profiles
            await _close_restart_profile(runtimes[victim], round_number=iteration + 1,
                                         profile_slot=victim, phase="checkpoint-before-crash")
            checkpoint = await runtimes[victim].start(headless=True)
            pages[victim] = checkpoint.pages[0]
            await pages[victim].goto(origin)
            persisted = await pages[victim].evaluate(STORAGE, None)
            assert persisted == values[victim], f"Graceful checkpoint lost stores: {persisted}"
            owned.update(controller_descendants(before, await asyncio.to_thread(process_snapshot), os.getpid()))
            browser = checkpoint.browser
            disconnected = asyncio.Event()
            browser.on("disconnected", disconnected.set)
            session = await browser.new_browser_cdp_session()
            try:
                await asyncio.wait_for(session.send("Browser.crash"), timeout=10)
            except (PlaywrightError, TimeoutError):
                pass
            await asyncio.wait_for(disconnected.wait(), timeout=10)
            assert not browser.is_connected(), "Crash target remained connected"
            survivors = [index for index in range(profiles) if index != victim]
            assert await asyncio.gather(*(pages[index].evaluate(STORAGE, None) for index in survivors)) == [values[index] for index in survivors], "One browser crash affected another profile"
            await _close_restart_profile(runtimes[victim], round_number=iteration + 1,
                                         profile_slot=victim, phase="crashed-profile-cleanup")
            recovered = await runtimes[victim].start(headless=True)
            pages[victim] = recovered.pages[0]
            await pages[victim].goto(origin)
            await inspect_policy(runtimes[victim], pages[victim])
            restored = await pages[victim].evaluate(STORAGE, None)
            assert restored == values[victim], f"Crash restore lost stores: {restored}; expected {values[victim]}"
            owned.update(controller_descendants(before, await asyncio.to_thread(process_snapshot), os.getpid()))
        deadline = asyncio.get_running_loop().time() + 30
        while True:
            current = await asyncio.to_thread(process_snapshot)
            remaining = [pid for pid, row in owned.items() if same_process(current.get(pid), row)]
            if not remaining:
                break
            assert asyncio.get_running_loop().time() < deadline, f"Owned processes survived restart round: {remaining}"
            await asyncio.sleep(.5)
        assert all(not runtime.has_resources for runtime in runtimes)
        observations.append({"round": iteration + 1, "concurrent_profiles": profiles,
                             "independent_drivers": drivers, "crashed_profile": victim,
                             "checkpoint_before_crash": True,
                             "policy_capabilities": (configuration.privacy_policy.required_capabilities()
                                                     if configuration is not None else []),
                             "processes_observed": len(owned), "remaining_owned_processes": 0})
    return observations


async def verify(profile_root: Path, executable: Path, origin: str, proxy_server: FixtureServer,
                 *, checks: list[str] | None = None, library_directory: Path | None = None,
                 release_store: Path | None = None, release_digest: str = "") -> dict:
    if bool(release_store) != bool(release_digest):
        raise ValueError("Native runtime release verification requires both store and checksum")
    runtime_core = measure_runtime_core(executable, library_directory)
    release = None
    if release_store is not None:
        from app.core.native.distribution import NativeBinaryStore

        store = NativeBinaryStore(release_store)
        release = store.inspect(release_digest)
        if (release.get("platform") != "win32" or release.get("build_kind") != "chromium-fork"
                or Path(release["executable_path"]) != executable
                or library_directory != executable.parent / release["chromium_version"]):
            raise ValueError("Runtime release identity or DLL layout differs from the installed package")
    desktop = NativeConfiguration()
    mobile = NativeConfiguration(environment="mobile_web", width=390, height=844, device_scale_factor=3,
                                 locale="de-DE", timezone="Europe/Berlin",
                                 permissions=("geolocation", "notifications"))
    a = NativeRuntime(profile_root / "a", executable, desktop)
    b = NativeRuntime(profile_root / "b", executable, mobile)
    proxied = NativeRuntime(profile_root / "proxy", executable, desktop)
    checks = [] if checks is None else checks
    try:
        context_a = await a.start(headless=True)
        context_b = await b.start(headless=True)
        page_a, page_b = context_a.pages[0], context_b.pages[0]
        await page_a.goto(origin)
        await page_b.goto(origin)
        default_permissions = await page_a.evaluate(PERMISSION_STATES)
        granted_permissions = {name: "granted" for name in default_permissions}
        assert default_permissions == {name: "denied" for name in default_permissions}, default_permissions
        assert await page_b.evaluate(PERMISSION_STATES) == granted_permissions
        await context_b.clear_permissions()
        revoked_permissions = await page_b.evaluate(PERMISSION_STATES)
        assert revoked_permissions == {name: "prompt" for name in default_permissions}, revoked_permissions
        await context_b.grant_permissions(list(mobile.permissions), origin=origin)
        assert await page_b.evaluate(PERMISSION_STATES) == granted_permissions
        assert await page_a.evaluate(PERMISSION_STATES) == default_permissions
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
        diagnostics = await inspect_native_profile(page_b, mobile, context_b.browser.version)
        assert diagnostics["mismatches"] == [], json.dumps(diagnostics)
        for scope in ("document", "worker"):
            hints = diagnostics["observed"][scope]["userAgentHighEntropy"]
            assert isinstance(hints, dict) and hints.get("fullVersionList"), json.dumps(diagnostics)
            assert "architecture" in hints and "platformVersion" in hints, json.dumps(diagnostics)
            canvas = diagnostics["observed"][scope]["canvas"]
            assert canvas["available"] and canvas["textWidth"] > 0, json.dumps(diagnostics)
            assert isinstance(canvas["pixelSha256"], str) and len(canvas["pixelSha256"]) == 64, json.dumps(diagnostics)
        audio = diagnostics["observed"]["document"]["audio"]
        assert audio["available"] and audio["frames"] == 4096 and audio["channels"] == 1, json.dumps(diagnostics)
        assert audio["probeSampleRate"] == 44100 and audio["absoluteSum"] > 0, json.dumps(diagnostics)
        checks.append("native-document-worker-configuration-diagnostics")
        version = context_a.browser.version
        if library_directory is not None and library_directory != executable.parent and library_directory.name != version:
            raise ValueError("Versioned runtime DLL directory does not match the running browser")
        await a.close()
        await b.close()
        for runtime, value in [(a, "alpha"), (b, "beta")]:
            context = await runtime.start(headless=True)
            page = context.pages[0]
            await page.goto(origin)
            assert await page.evaluate(PERMISSION_STATES) == (
                granted_permissions if runtime is b else default_permissions)
            assert await page.evaluate(STORAGE, None) == {"cookie": "owned=" + value, "local": value, "indexed": value, "cached": value, "workers": 1}
            await runtime.close()
        checks.append("cookie-localstorage-indexeddb-cache-serviceworker-restart")
        checks.append("configured-permissions-isolation-revocation-and-restart")
        abandoned = await asyncio.to_thread(subprocess.run,
            [sys.executable, str(Path(__file__).resolve()), "--abandon-lock", str(a.profile_dir),
             "--executable", str(executable)], cwd=ROOT, capture_output=True, text=True, timeout=15)
        assert abandoned.returncode == 0 and (a.profile_dir / "native-runtime.lock").is_file()
        context = await a.start(headless=True)
        page = context.pages[0]
        await page.goto(origin)
        checks.append("dead-owner-profile-lock-recovery")
        disconnected = asyncio.Event()
        context.browser.on("disconnected", disconnected.set)
        session = await context.browser.new_browser_cdp_session()
        try:
            await asyncio.wait_for(session.send("Browser.crash"), timeout=10)
        except (PlaywrightError, TimeoutError):
            pass
        await asyncio.wait_for(disconnected.wait(), timeout=10)
        assert not context.browser.is_connected()
        await a.close()
        context = await a.start(headless=True)
        page = context.pages[0]
        await page.goto(origin)
        assert await page.evaluate(STORAGE, None) == {"cookie": "owned=alpha", "local": "alpha",
            "indexed": "alpha", "cached": "alpha", "workers": 1}
        await a.close()
        checks.append("browser-crash-restart-preserves-committed-storage")
        context = await proxied.start(headless=True, proxy={"server": f"http://127.0.0.1:{proxy_server.server_port}", "username": "owned-user", "password": "owned-pass"})
        response = await context.pages[0].goto("http://native-fixture.invalid/")
        assert response.status == 200
        assert await context.pages[0].title() == "Owned Native fixture"
        assert proxy_server.authenticated_requests > 0 and proxy_server.challenges > 0
        checks.append("authenticated-http-proxy-no-direct-dns-route")
        from app.services.scenario_engine import ScenarioExecutor
        from app.services.scenario_recorder import ScenarioRecorder
        from app.services.profile_backup import export_profile, restore_profile
        from app.storage import db

        db.init_db()
        if db.DATA_ROOT.resolve() != (profile_root / "workspace").resolve():
            raise ValueError("Native runtime fixture database is outside its owned workspace")
        account = {"name": "Native core fixture", "browser_engine": "native", "native_settings": {
            "executable_path": str(executable), "headless": True, "humanize": False,
        }}
        db.db_add_account(account)
        scenario = db.Scenario("Native core compatibility", [
            {"action": "start"}, {"action": "goto", "value": origin},
            {"action": "type", "selector": "input", "value": "existing scenario"},
            {"action": "click", "selector": "button"},
            {"action": "wait_element", "selector": "output", "state": "visible"},
            {"action": "extract_text", "selector": "output", "to_var": "result"},
        ], "Owned Native source check")
        runner = ScenarioExecutor(account, "", scenario, keep_browser_open=False)
        try:
            await runner.start()
            assert runner.browser_engine == "native"
            assert runner.user_data_dir.relative_to(runner.profile_root.resolve()) == Path("native")
            assert await runner.run()
            assert runner.variables["result"] == "existing scenario"
            recorder = ScenarioRecorder()
            try:
                await recorder.attach(runner.page)
                await runner.page.goto(origin)
                await runner.page.get_by_label("Value", exact=True).fill("recorded native")
                await runner.page.get_by_role("button", name="Apply", exact=True).click()
                frame = runner.page.frame_locator("#owned-frame")
                await frame.get_by_label("Value", exact=True).fill("frame native")
                await frame.get_by_role("button", name="Apply", exact=True).click()
            finally:
                await recorder.stop()
            recorded_steps, recording_warnings = recorder.snapshot()
            assert not recording_warnings, recording_warnings
            assert [step["action"] for step in recorded_steps] == ["start", "goto", "type", "click", "type", "click"]
            assert recorded_steps[-1]["frame_selector"] == ['iframe[id="owned-frame"]']
        finally:
            await runner.close(force=True)
        checks.append("existing-browser-interface-and-scenario-executor")
        replay = ScenarioExecutor(account, "", db.Scenario("Native recorded replay", recorded_steps + [
            {"action": "wait_element", "selector": "output", "state": "visible"},
            {"action": "extract_text", "selector": "output", "to_var": "recorded_result"},
            {"action": "extract_text", "selector": "output", "frame_selector": recorded_steps[-1]["frame_selector"],
             "to_var": "recorded_frame_result"},
        ], "Owned Native recording"), keep_browser_open=False)
        try:
            await replay.start()
            assert await replay.run()
            assert replay.variables["recorded_result"] == "recorded native"
            assert replay.variables["recorded_frame_result"] == "frame native"
            await replay.page.evaluate(STORAGE, "backup")
        finally:
            await replay.close(force=True)
        checks.append("existing-recorder-capture-and-replay")
        backup = profile_root / "native-profile.zip"
        export_profile(account["name"], backup, sessions=True, secrets=True)
        restored_root = restore_profile(backup, "Native restored fixture")
        restored_account = next(item for item in db.db_get_accounts() if item["name"] == "Native restored fixture")
        assert restored_account["browser_engine"] == "native"
        assert not (restored_root / "native/native-runtime.lock").exists()
        restored = ScenarioExecutor(restored_account, "", db.Scenario("Native restored storage", [
            {"action": "start"}, {"action": "goto", "value": origin},
        ], "Owned Native backup check"), keep_browser_open=False)
        try:
            await restored.start()
            assert restored.browser_engine == "native"
            assert await restored.run()
            assert await restored.page.evaluate(STORAGE, None) == {"cookie": "owned=backup", "local": "backup",
                "indexed": "backup", "cached": "backup", "workers": 1}
            await restored.page.evaluate(STORAGE, "restored")
        finally:
            await restored.close(force=True)
        source = ScenarioExecutor(account, "", db.Scenario("Native original storage", [
            {"action": "start"}, {"action": "goto", "value": origin},
        ], "Owned Native backup isolation"), keep_browser_open=False)
        try:
            await source.start()
            assert await source.run()
            assert await source.page.evaluate(STORAGE, None) == {"cookie": "owned=backup", "local": "backup",
                "indexed": "backup", "cached": "backup", "workers": 1}
        finally:
            await source.close(force=True)
        checks.append("native-profile-backup-restore-storage-and-engine-isolation")
        from app.core.native.health import probe_native_binary

        health_work = profile_root / "binary-health"
        assert await probe_native_binary(executable, desktop, health_work) == version
        assert not list(health_work.iterdir())
        checks.append("native-binary-headless-health-and-disposable-profile-cleanup")
        cancelled = NativeRuntime(profile_root / "cancelled-close", executable, desktop)
        closing = None
        try:
            await cancelled.start(headless=True)
            closing = asyncio.create_task(cancelled.close())
            deadline = asyncio.get_running_loop().time() + cancelled.CLOSE_TIMEOUT_SECONDS
            while cancelled._driver_stop_task is None:
                assert not closing.done(), "Close finished before its stop operation could be observed"
                assert asyncio.get_running_loop().time() < deadline, "Driver stop was not reached"
                await asyncio.sleep(0)
            stop = cancelled._driver_stop_task
            closing.cancel()
            try:
                await closing
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("Cancelled close unexpectedly completed")
            assert cancelled._driver_stop_task is stop and not stop.cancelled()
            assert cancelled._profile_lock is not None
            child = await asyncio.to_thread(subprocess.run,
                [sys.executable, str(Path(__file__).resolve()), "--check-lock", str(cancelled.profile_dir),
                 "--executable", str(executable)], cwd=ROOT, capture_output=True, text=True, timeout=15)
            assert child.returncode == 0, "Interrupted teardown lost its profile owner: " + child.stdout + child.stderr
            await cancelled.close()
            assert cancelled.playwright is None and cancelled._driver_stop_task is None
            assert cancelled._profile_lock is None
        finally:
            if closing is not None and not closing.done():
                closing.cancel()
                try:
                    await closing
                except asyncio.CancelledError:
                    pass
            await cancelled.close()
        checks.append("cancelled-teardown-preserves-driver-stop-and-cross-process-profile-owner")
        controller_processes = await verify_controller_crash(profile_root, executable, origin)
        checks.append("controller-kill-exits-observed-process-tree-and-restores-five-stores")
        cancelled_start = NativeRuntime(profile_root / "cancelled-start", executable, desktop)
        starting = None
        try:
            before = await asyncio.to_thread(process_snapshot)
            starting = asyncio.create_task(cancelled_start.start(headless=True))
            while cancelled_start._driver_start_task is None:
                assert not starting.done(), "Driver start finished before cancellation could be observed"
                await asyncio.sleep(0)
            startup = cancelled_start._driver_start_task
            starting.cancel()
            try:
                await starting
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("Cancelled driver start unexpectedly completed")
            assert not startup.cancelled()
            assert cancelled_start.playwright is None and cancelled_start._driver_start_task is None
            assert cancelled_start._profile_lock is None
            descendants = controller_descendants(before, await asyncio.to_thread(process_snapshot), os.getpid())
            assert all(executable_name(row) is not None for row in descendants.values()), "Startup cleanup executable identity is unavailable"
            leaked = [pid for pid, row in descendants.items()
                      if (executable_name(row) or "").lower() in {"node", "node.exe", executable.name.lower()}]
            assert not leaked, f"Cancelled startup left owned browser/driver processes: {leaked}"
            context = await cancelled_start.start(headless=True)
            await context.pages[0].goto(origin)
            assert await context.pages[0].title() == "Owned Native fixture"
        finally:
            if starting is not None and not starting.done():
                starting.cancel()
                try:
                    await starting
                except asyncio.CancelledError:
                    pass
            await cancelled_start.close()
        checks.append("cancelled-driver-start-cleans-pending-operation-and-restarts-profile")
        await proxied.close()
        await a.close()
        await b.close()
        restart_rounds = await verify_multi_profile_restarts(profile_root, executable, origin)
        checks.append("three-profile-restarts-isolate-crashes-five-stores-and-exit-owned-processes")
        if measure_runtime_core(executable, library_directory) != runtime_core:
            raise ValueError("Native runtime core changed during verification")
        if release is not None and store.inspect(release_digest) != release:
            raise ValueError("Installed Native payload changed during runtime verification")
        checksum = runtime_core[executable.name]
        return {"passed": True, "platform": platform.system(), "architecture": platform.machine(),
                "version": version, "binary_sha256_measured": checksum, "checks": checks,
                "runtime_core_sha256_measured": runtime_core,
                "release_sha256_measured": release_digest if release is not None else None,
                "payload_files_sha256_measured": release["files_sha256"] if release is not None else None,
                "mobile_observed": observed, "diagnostics": diagnostics, "fingerprint_patched": False,
                "permission_states": {"configured_empty": default_permissions,
                                      "configured_grants": granted_permissions,
                                      "after_clear": revoked_permissions},
                "controller_descendants_observed": controller_processes,
                "multi_profile_restart_rounds": restart_rounds}
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


def close_owned_log_handlers(root: Path) -> None:
    root = root.resolve()
    loggers = [logging.getLogger(), *logging.Logger.manager.loggerDict.values()]
    for logger in loggers:
        if not isinstance(logger, logging.Logger):
            continue
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).resolve().is_relative_to(root):
                handler.close()
                logger.removeHandler(handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="")
    parser.add_argument("--work-dir", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--report", type=Path, default=ROOT / "outputs/native-runtime/source.json")
    parser.add_argument("--windows-library-directory", type=Path,
                        help="Explicit DLL directory for a versioned official Chrome-bin package; no automatic search")
    parser.add_argument("--release-store", type=Path, help="Verify every file of an installed immutable Native release")
    parser.add_argument("--release-sha256", default="", help="Expected installed release archive checksum")
    parser.add_argument("--check-lock", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--abandon-lock", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--controller-child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--fixture-origin", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if bool(args.release_store) != bool(args.release_sha256):
        parser.error("--release-store and --release-sha256 must be supplied together")
    if args.abandon_lock:
        from PyQt6.QtCore import QLockFile
        profile = args.abandon_lock
        marker = profile / "camouflow-native.json"
        if (not profile.is_absolute() or profile != profile.resolve()
                or not profile.parent.name.startswith("native-owned-") or marker.is_symlink()
                or (profile / "native-runtime.lock").is_symlink()
                or not marker.is_file()
                or json.loads(marker.read_text(encoding="utf-8-sig")) != {"engine": "camouflow-native", "schema": 1}):
            parser.error("Lock abandonment requires an owned Native test profile")
        lock = QLockFile(str(profile / "native-runtime.lock"))
        lock.setStaleLockTime(0)
        os._exit(0 if lock.tryLock(0) else 1)
    executable = asyncio.run(resolve_executable(args.executable))
    if args.controller_child:
        asyncio.run(controller_child(args.controller_child, executable, args.fixture_origin))
        return 0
    if args.check_lock:
        return asyncio.run(check_lock(args.check_lock, executable))
    args.work_dir.mkdir(parents=True, exist_ok=True)
    server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
    proxy_server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
    proxy_server.proxy_mode = True
    threads = [threading.Thread(target=item.serve_forever, daemon=True) for item in (server, proxy_server)]
    for thread in threads:
        thread.start()
    checks = []
    owned = None
    report = {"passed": False}
    try:
        owned = Path(tempfile.mkdtemp(prefix="native-owned-", dir=args.work_dir.resolve()))
        previous_data_dir = os.environ.get("CAMOUFLOW_DATA_DIR")
        os.environ["CAMOUFLOW_DATA_DIR"] = str(owned / "workspace")
        try:
            report = asyncio.run(verify(owned, executable, f"http://127.0.0.1:{server.server_port}", proxy_server,
                                        checks=checks, library_directory=args.windows_library_directory,
                                        release_store=args.release_store, release_digest=args.release_sha256))
        finally:
            try:
                close_owned_log_handlers(owned)
            except Exception as error:
                report.update(passed=False, log_cleanup_error=str(error)[:1000])
            finally:
                if previous_data_dir is None:
                    os.environ.pop("CAMOUFLOW_DATA_DIR", None)
                else:
                    os.environ["CAMOUFLOW_DATA_DIR"] = previous_data_dir
    except Exception as error:
        report.update(passed=False, platform=platform.system(), completed_checks=checks, error_type=type(error).__name__,
                      error=str(error)[:1000], traceback=traceback.format_exc()[-6000:],
                      error_notes=[note[:1000] for note in getattr(error, "__notes__", [])[-8:]])
    finally:
        for item in (server, proxy_server):
            item.shutdown()
            item.server_close()
        for thread in threads:
            thread.join()
        if owned is not None:
            if not report["passed"]:
                report["retained_profile_directory"] = str(owned)
            else:
                try:
                    if owned != owned.resolve() or not owned.is_relative_to(args.work_dir.resolve()):
                        raise ValueError("Refusing cleanup outside owned runtime workspace")
                    shutil.rmtree(owned)
                except (OSError, ValueError) as error:
                    report.update(passed=False, cleanup_error=str(error)[:1000], retained_profile_directory=str(owned))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
