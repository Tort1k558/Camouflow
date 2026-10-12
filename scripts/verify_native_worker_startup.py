"""Owned worker startup/denial probes; not Canvas or fingerprint admission."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import threading
import traceback
from urllib.parse import parse_qs, urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime
from scripts.native_build import LOCK
from scripts.verify_native_runtime import FixtureHandler, FixtureServer, measure_runtime_core

CASES = tuple((kind, script_type) for kind in ("dedicated", "shared", "service")
              for script_type in ("classic", "module"))
FEATURE_ARGUMENT = "--enable-features=ThirdPartyStoragePartitioning"
BOOTSTRAP_ARGUMENT = "--glint-worker-canvas-bootstrap-test"
KEY_ARGUMENT = "--camouflow-native-privacy-key-service=1"
PHASES = {"baseline": ("initial", "restart"), "ready": ("initial", "restart"), "unavailable": ("initial",)}

PROBE = """async ({kind, scriptType, id, cached, retain}) => {
  let worker, registration, channel;
  const url = `/startup-${kind}.js?id=${id}&type=${scriptType}`;
  try {
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => resolve({status: 'timeout'}), 15000);
      const finish = value => { clearTimeout(timer); resolve(value); };
      const message = event => finish({status: 'reply', id: event.data.id});
      const error = () => finish({status: 'worker-error'});
      if (kind === 'dedicated') {
        worker = new Worker(url, {type: scriptType});
        worker.onmessage = message; worker.onerror = error;
        worker.postMessage('probe');
      } else if (kind === 'shared') {
        worker = new SharedWorker(url, {type: scriptType, name: id});
        worker.onerror = error; worker.port.onmessage = message;
        worker.port.start(); worker.port.postMessage('probe');
      } else {
        const scope = `/startup/${id}/`;
        const registrationRequest = cached ? navigator.serviceWorker.getRegistration(scope) :
          navigator.serviceWorker.register(url, {type: scriptType, scope});
        registrationRequest
          .then(value => {
            if (!value) { finish({status: 'registration-error'}); return; }
            registration = value;
            const active = value.installing || value.waiting || value.active;
            if (!active) { finish({status: 'registration-error'}); return; }
            const send = () => {
              if (active.state === 'redundant') { finish({status: 'registration-error'}); return; }
              if (active.state !== 'activated' || channel) return;
              channel = new MessageChannel(); channel.port1.onmessage = message;
              active.postMessage('probe', [channel.port2]);
            };
            active.addEventListener('statechange', send); send();
          }, () => finish({status: 'registration-error'}));
      }
    });
  } finally {
    if (kind === 'dedicated') worker?.terminate();
    if (kind === 'shared') worker?.port.close();
    channel?.port1.close(); channel?.port2.close();
    if (registration && !retain) await registration.unregister();
  }
}"""


class WorkerStartupServer(FixtureServer):
    def __init__(self, address):
        self.execution_lock = threading.Lock()
        self.executions: dict[str, int] = {}
        self.script_requests: dict[str, int] = {}
        super().__init__(address, WorkerStartupHandler)

    def count(self, identifier: str) -> int:
        with self.execution_lock:
            return self.executions.get(identifier, 0)

    def script_count(self, identifier: str) -> int:
        with self.execution_lock:
            return self.script_requests.get(identifier, 0)


class WorkerStartupHandler(FixtureHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/startup-module.js":
            body = "export const moduleMarker = true;"
        elif parsed.path == "/startup-executed":
            identifier = query.get("id", [""])[0]
            with self.server.execution_lock:
                self.server.executions[identifier] = self.server.executions.get(identifier, 0) + 1
            body = ""
        elif parsed.path in {f"/startup-{kind}.js" for kind, _ in CASES}:
            identifier = query.get("id", [""])[0]
            with self.server.execution_lock:
                self.server.script_requests[identifier] = self.server.script_requests.get(identifier, 0) + 1
            kind = parsed.path.removeprefix("/startup-").removesuffix(".js")
            prefix = "import {moduleMarker} from '/startup-module.js';\n" if query.get("type") == ["module"] else ""
            # This beacon is issued by the worker body, not the script fetch.
            prefix += f"const execution = fetch('/startup-executed?id=' + {json.dumps(identifier)});\n"
            reply = f"const value = {{id: {json.dumps(identifier)}}};\n"
            bodies = {
                "dedicated": "self.onmessage = () => execution.then(() => self.postMessage(value));",
                "shared": "self.onconnect = event => { const port = event.ports[0]; port.onmessage = () => execution.then(() => port.postMessage(value)); port.start(); };",
                "service": "self.addEventListener('install', event => event.waitUntil(execution.then(() => self.skipWaiting()))); self.addEventListener('activate', event => event.waitUntil(self.clients.claim())); self.addEventListener('message', event => event.waitUntil(execution.then(() => event.ports[0].postMessage(value))));",
            }
            body = prefix + reply + bodies[kind]
        else:
            return super().do_GET()
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if parsed.path == "/startup-service.js":
            self.send_header("Service-Worker-Allowed", "/")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


@dataclass(frozen=True)
class StartupConfiguration(NativeConfiguration):
    probe_mode: str = "baseline"
    disabled_features_argument: str | None = None
    ignored_driver_argument: str | None = None

    def context_options(self) -> dict:
        options = super().context_options()
        if self.disabled_features_argument is not None:
            if (self.ignored_driver_argument is None
                    or partitioning_argument([self.ignored_driver_argument]) != self.disabled_features_argument):
                raise ValueError("Worker probe requires the exact measured driver exclusion")
            options["ignore_default_args"] = [self.ignored_driver_argument]
        elif self.ignored_driver_argument is not None:
            raise ValueError("Worker probe cannot discard feature exclusions without replacement")
        return options

    def launch_arguments(self) -> list[str]:
        if self.probe_mode not in PHASES:
            raise ValueError("Unknown worker startup probe mode")
        arguments = super().launch_arguments() + [FEATURE_ARGUMENT, "--enable-automation"]
        if self.disabled_features_argument is not None:
            if partitioning_argument([self.disabled_features_argument]) != self.disabled_features_argument:
                raise ValueError("Worker probe still disables storage partitioning")
            arguments.append(self.disabled_features_argument)
        if self.probe_mode != "baseline":
            arguments.append(BOOTSTRAP_ARGUMENT)
        if self.probe_mode == "ready":
            arguments.append(KEY_ARGUMENT)
        return arguments


def partitioning_argument(arguments: list[str]) -> str:
    if not isinstance(arguments, list) or any(not isinstance(argument, str) for argument in arguments):
        raise ValueError("Browser launch arguments are missing")
    disabled = [argument for argument in arguments if argument.startswith("--disable-features=")]
    if len(disabled) != 1:
        raise ValueError("Worker probe requires one measured disabled-feature argument")
    features = disabled[0].partition("=")[2].split(",")
    if any(not feature for feature in features):
        raise ValueError("Browser disabled-feature argument is malformed")
    retained = [feature for feature in features
                if feature.split("<", 1)[0].split(":", 1)[0] != "ThirdPartyStoragePartitioning"]
    if not retained:
        raise ValueError("Worker probe requires unrelated Playwright feature exclusions")
    return "--disable-features=" + ",".join(retained)


async def browser_arguments(context) -> list[str]:
    page = context.pages[0] if context.pages else await context.new_page()
    session = await context.new_cdp_session(page)
    try:
        result = await session.send("Browser.getBrowserCommandLine")
        return result["arguments"]
    finally:
        await session.detach()


def validate_observation(observed: dict, *, mode: str, kind: str, identifier: str) -> None:
    if mode not in PHASES or kind not in {item[0] for item in CASES} or not isinstance(observed, dict):
        raise ValueError("Unknown or incomplete worker observation")
    count = observed.get("executions")
    if type(count) is not int or count < 0:
        raise ValueError("Worker body execution evidence is missing")
    if mode == "unavailable":
        expected = "registration-error" if kind == "service" else "worker-error"
        if set(observed) != {"status", "executions"} or observed["status"] != expected or count != 0:
            raise ValueError("Unavailable policy must reject before worker body execution; timeout is inconclusive")
    elif set(observed) != {"status", "id", "executions"} or observed["status"] != "reply" or observed["id"] != identifier or count != 1:
        raise ValueError("Worker startup did not produce the owned response and exactly one execution beacon")


def validate_receipt(executable: Path, core: dict) -> bytes:
    path = executable.parent / "camouflow-build.json"
    if path != path.resolve() or path.is_symlink():
        raise ValueError("Worker startup requires a canonical local build receipt")
    raw = path.read_bytes()
    receipt = json.loads(raw.decode("utf-8-sig"))
    if (not isinstance(receipt, dict) or not isinstance(receipt.get("patches"), list)
            or receipt.get("chromium_revision") != LOCK["chromium_revision"]
            or receipt.get("binary_sha256_measured") != core[executable.name]):
        raise ValueError("Worker startup receipt does not match the pinned executable")
    for number in range(15, 28):
        candidates = list((ROOT / "native/patches").glob(f"{number:04d}-*.patch"))
        if len(candidates) != 1:
            raise ValueError("Worker startup requires the exact registered source chain")
        patch = candidates[0]
        expected = {"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
        if expected not in receipt.get("patches", []):
            raise ValueError("Worker startup receipt lacks a required exact patch")
    return raw


async def verify(executable: Path, owned: Path, server: WorkerStartupServer, report: dict,
                 runtimes: list[NativeRuntime]) -> None:
    origin = f"http://127.0.0.1:{server.server_port}"
    discovery = NativeRuntime(profile_dir=owned / "driver-arguments", executable=executable,
                              configuration=StartupConfiguration())
    runtimes.append(discovery)
    try:
        context = await discovery.start(headless=True)
        original_arguments = await browser_arguments(context)
        disabled_features_argument = partitioning_argument(original_arguments)
        report["driver_disabled_features_original"] = [argument for argument in original_arguments
                                                        if argument.startswith("--disable-features=")][0]
        report["probe_disabled_features_replacement"] = disabled_features_argument
    finally:
        await discovery.close()
    for mode, phases in PHASES.items():
        configuration = StartupConfiguration(probe_mode=mode, disabled_features_argument=disabled_features_argument,
                                             ignored_driver_argument=report["driver_disabled_features_original"])
        report["arguments"][mode] = configuration.launch_arguments()
        runtime = NativeRuntime(profile_dir=owned / mode, executable=executable, configuration=configuration)
        runtimes.append(runtime)
        installed_services = {}
        for phase in phases:
            try:
                context = await runtime.start(headless=True)
                effective = await browser_arguments(context)
                if (partitioning_argument(effective) != disabled_features_argument
                        or disabled_features_argument not in effective or FEATURE_ARGUMENT not in effective):
                    raise ValueError("Effective browser arguments still conflict with worker partitioning")
                report.setdefault("effective_partitioning_arguments", {})[f"{mode}-{phase}"] = [
                    argument for argument in effective
                    if argument.startswith(("--disable-features=", "--enable-features="))]
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(origin, timeout=20000)
                for kind, script_type in CASES:
                    cached = mode == "ready" and phase == "restart" and kind == "service"
                    identifier = installed_services[script_type] if cached else uuid.uuid4().hex
                    if mode == "ready" and phase == "initial" and kind == "service":
                        installed_services[script_type] = identifier
                    execution_before = server.count(identifier)
                    requests_before = server.script_count(identifier)
                    observed = await asyncio.wait_for(page.evaluate(PROBE, {
                        "kind": kind, "scriptType": script_type, "id": identifier,
                        "cached": cached, "retain": mode == "ready" and phase == "initial" and kind == "service",
                    }), timeout=25)
                    observed["executions"] = server.count(identifier) - execution_before
                    check = {"name": f"{mode}-{phase}-{kind}-{script_type}", "passed": False, "observed": observed,
                             "installed_service_restart": cached,
                             "script_requests": server.script_count(identifier) - requests_before}
                    report["checks"].append(check)
                    validate_observation(observed, mode=mode, kind=kind, identifier=identifier)
                    if cached and check["script_requests"] != 0:
                        raise ValueError("Installed service-worker restart fetched the main script instead of using retained installation")
                    check["passed"] = True
            finally:
                await runtime.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Refusing to overwrite worker startup evidence")
    report = {"schema": 1, "passed": False, "checks": [], "arguments": {}, "platform": platform.platform(),
              "scope": "Owned classic/module worker startup, restart and unavailable-policy rejection; not Canvas, nested workers, early termination or admission"}
    server = thread = owned = None
    runtimes = []
    try:
        executable = args.executable.resolve(strict=True)
        core = measure_runtime_core(executable)
        receipt = validate_receipt(executable, core)
        report.update(runtime_core_sha256_measured=core, binary_sha256_measured=core[executable.name],
                      receipt_sha256=hashlib.sha256(receipt).hexdigest())
        args.work_dir.mkdir(parents=True, exist_ok=True)
        if args.work_dir.resolve().is_relative_to(ROOT):
            raise ValueError("Worker profiles must stay outside the public checkout")
        server = WorkerStartupServer(("127.0.0.1", 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        owned = Path(tempfile.mkdtemp(prefix="glint-worker-startup-", dir=args.work_dir.resolve()))
        asyncio.run(verify(executable, owned, server, report, runtimes))
        if measure_runtime_core(executable) != core or validate_receipt(executable, core) != receipt:
            raise ValueError("Worker runtime code or receipt changed during verification")
        expected = {f"{mode}-{phase}-{kind}-{script_type}" for mode, phases in PHASES.items()
                    for phase in phases for kind, script_type in CASES}
        if {check["name"] for check in report["checks"]} != expected or len(report["checks"]) != len(expected):
            raise ValueError("Worker startup phases are incomplete")
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
        if owned is not None:
            try:
                if any(runtime.has_resources for runtime in runtimes):
                    raise ValueError("Worker probe resources remain; owned profiles retained")
                if owned != owned.resolve() or not owned.is_relative_to(args.work_dir.resolve()):
                    raise ValueError("Refusing cleanup outside the owned workspace")
                shutil.rmtree(owned)
            except (OSError, ValueError) as error:
                report.update(passed=False, cleanup_error=str(error), retained_profile_directory=str(owned))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    print(json.dumps({"passed": report["passed"], "report": str(args.report)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
