"""Owned worker startup/denial probes; not Canvas or fingerprint admission."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import threading
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime
from scripts.native_build import load_candidate
from scripts.native_build import LOCK
from scripts.verify_native_runtime import (
    FixtureHandler,
    FixtureServer,
    measure_runtime_core,
)

CASES = tuple((kind, script_type) for kind in ("dedicated", "shared", "service")
              for script_type in ("classic", "module"))
FEATURE_ARGUMENT = "--enable-features=ThirdPartyStoragePartitioning"
BOOTSTRAP_ARGUMENT = "--glint-worker-canvas-bootstrap-test"
SURFACE_BOOTSTRAP_ARGUMENT = "--glint-worker-surface-bootstrap-test"
SURFACE_PATCH = "0031-native-worker-surface-policy.patch"
KEY_ARGUMENT = "--camouflow-native-privacy-key-service=1"
PHASES = {"baseline": ("initial", "restart"), "ready": ("initial", "restart"), "unavailable": ("initial",)}
NESTED_CASES = tuple((parent, child) for parent in ("classic", "module") for child in ("classic", "module"))

NESTED_PROBE = """async ({id, childId, parentType, childType}) => {
  let worker;
  try {
    return await new Promise(resolve => {
      const timer = setTimeout(() => resolve({status: 'timeout'}), 15000);
      const finish = value => { clearTimeout(timer); resolve(value); };
      const query = new URLSearchParams({id, childId, parentType, childType});
      worker = new Worker(`/startup-nested-parent.js?${query}`, {type: parentType});
      worker.onmessage = event => finish(event.data.status ? {status: event.data.status} :
        {status: 'reply', id: event.data.id});
      worker.onerror = event => { event.preventDefault(); finish({status: 'worker-error'}); };
      worker.postMessage('probe');
    });
  } finally { worker?.terminate(); }
}"""


def nested_worker_source(identifier: str, child_identifier: str, parent_type: str, child_type: str) -> str:
    if (parent_type, child_type) not in NESTED_CASES:
        raise ValueError("Unknown nested worker script types")
    if (not isinstance(identifier, str) or not isinstance(child_identifier, str)
            or not identifier or not child_identifier or identifier == child_identifier):
        raise ValueError("Nested workers require distinct nonempty execution identifiers")
    prefix = "import {moduleMarker} from '/startup-module.js';\n" if parent_type == "module" else ""
    child_url = "/startup-dedicated.js?" + urlencode({"id": child_identifier, "type": child_type})
    return prefix + f"""
const execution = fetch('/startup-executed?id=' + encodeURIComponent({json.dumps(identifier)}));
const child = new Worker({json.dumps(child_url)}, {{type: {json.dumps(child_type)}}});
child.onmessage = async event => {{
  await execution;
  child.terminate();
  self.postMessage({{id: event.data.id}});
}};
child.onerror = event => {{
  event.preventDefault();
  child.terminate();
  self.postMessage({{status: 'nested-worker-error'}});
}};
self.onmessage = () => child.postMessage('probe');
"""

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

SHARED_CLIENT_PROBE = """async ({scriptType, id, reuse}) => {
  const worker = reuse ? window.ownedSharedWorker :
    new SharedWorker(`/startup-shared.js?id=${id}&type=${scriptType}`, {type: scriptType, name: id});
  window.ownedSharedWorker = worker;
  return await new Promise(resolve => {
    const timer = setTimeout(() => resolve({status: 'timeout'}), 15000);
    const finish = value => { clearTimeout(timer); resolve(value); };
    worker.onerror = () => finish({status: 'worker-error'});
    worker.port.onmessage = event => finish({status: 'reply', id: event.data.id});
    worker.port.start(); worker.port.postMessage('probe');
  });
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
        elif parsed.path == "/startup-nested-parent.js":
            try:
                identifier = query["id"][0]
                body = nested_worker_source(identifier, query["childId"][0], query["parentType"][0], query["childType"][0])
            except (KeyError, ValueError):
                self.send_error(400, "Invalid nested worker fixture request")
                return
            with self.server.execution_lock:
                self.server.script_requests[identifier] = self.server.script_requests.get(identifier, 0) + 1
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
    bootstrap_policy: str = "canvas"
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
        if self.bootstrap_policy not in {"canvas", "surfaces"}:
            raise ValueError("Unknown worker bootstrap policy")
        arguments = super().launch_arguments() + [FEATURE_ARGUMENT, "--enable-automation"]
        if self.disabled_features_argument is not None:
            if partitioning_argument([self.disabled_features_argument]) != self.disabled_features_argument:
                raise ValueError("Worker probe still disables storage partitioning")
            arguments.append(self.disabled_features_argument)
        if self.probe_mode != "baseline":
            arguments.append(SURFACE_BOOTSTRAP_ARGUMENT if self.bootstrap_policy == "surfaces" else BOOTSTRAP_ARGUMENT)
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


async def verify_shared_clients(context, origin: str, server: WorkerStartupServer,
                                mode: str, phase: str, report: dict) -> None:
    for script_type in ("classic", "module"):
        identifier = uuid.uuid4().hex
        check = {"name": f"{mode}-{phase}-shared-clients-{script_type}", "passed": False, "observed": []}
        report["checks"].append(check)
        pages = []
        try:
            for _ in range(2):
                page = await context.new_page()
                pages.append(page)
                await page.goto(origin, timeout=20000)
            arguments = {"scriptType": script_type, "id": identifier, "reuse": False}
            if mode == "unavailable":
                observations = await asyncio.wait_for(asyncio.gather(*[
                    page.evaluate(PROBE, {**arguments, "kind": "shared", "cached": False, "retain": False})
                    for page in pages]), timeout=25)
            else:
                observations = []
                for page in pages:
                    observations.append(await asyncio.wait_for(page.evaluate(SHARED_CLIENT_PROBE, arguments), timeout=25))
                await pages[0].close()
                observations.append(await asyncio.wait_for(
                    pages[1].evaluate(SHARED_CLIENT_PROBE, {**arguments, "reuse": True}), timeout=25))
            executions = server.count(identifier)
            for observed in observations:
                observed["executions"] = executions
            check.update(observed=observations, script_requests=server.script_count(identifier))
            for observed in observations:
                validate_observation(observed, mode=mode, kind="shared", identifier=identifier)
            if mode != "unavailable" and check["script_requests"] != 1:
                raise ValueError("Shared clients did not reuse one worker script instance")
            check["passed"] = True
        finally:
            for page in pages:
                await page.close()


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


def validate_nested_observation(observed: dict, *, mode: str, child_identifier: str) -> None:
    if (mode not in PHASES or not isinstance(observed, dict)
            or not isinstance(child_identifier, str) or not child_identifier):
        raise ValueError("Unknown or incomplete nested worker observation")
    for field in ("executions", "script_requests"):
        values = observed.get(field)
        if (not isinstance(values, dict) or set(values) != {"parent", "child"}
                or any(type(value) is not int or value < 0 for value in values.values())):
            raise ValueError("Nested worker execution/fetch counters are incomplete")
    if mode == "unavailable":
        if (set(observed) != {"status", "executions", "script_requests"}
                or observed["status"] != "worker-error"
                or observed["executions"] != {"parent": 0, "child": 0}
                or observed["script_requests"]["child"] != 0
                or observed["script_requests"]["parent"] not in {0, 1}):
            raise ValueError("Unavailable parent policy must reject without parent/child execution or child fetch")
    elif (set(observed) != {"status", "id", "executions", "script_requests"}
          or observed["status"] != "reply" or observed["id"] != child_identifier
          or observed["executions"] != {"parent": 1, "child": 1}
          or observed["script_requests"] != {"parent": 1, "child": 1}):
        raise ValueError("Nested workers must fetch and execute each body exactly once and return the child reply")


async def verify_nested_workers(page, server: WorkerStartupServer, mode: str, phase: str, report: dict) -> None:
    for parent_type, child_type in NESTED_CASES:
        identifier, child_identifier = uuid.uuid4().hex, uuid.uuid4().hex
        observed = await asyncio.wait_for(page.evaluate(NESTED_PROBE, {
            "id": identifier, "childId": child_identifier, "parentType": parent_type, "childType": child_type,
        }), timeout=25)
        observed["executions"] = {"parent": server.count(identifier), "child": server.count(child_identifier)}
        observed["script_requests"] = {"parent": server.script_count(identifier), "child": server.script_count(child_identifier)}
        check = {"name": f"{mode}-{phase}-nested-{parent_type}-{child_type}", "passed": False, "observed": observed}
        report["checks"].append(check)
        validate_nested_observation(observed, mode=mode, child_identifier=child_identifier)
        check["passed"] = True


def validate_receipt(executable: Path, core: dict, *, bootstrap_policy: str = "canvas", candidate_name: str | None = None) -> bytes:
    if bootstrap_policy not in {"canvas", "surfaces"}:
        raise ValueError("Unknown worker bootstrap policy")
    candidate = None if candidate_name is None else load_candidate(candidate_name)
    lock = LOCK if candidate is None else candidate["lock"]
    patch_directory = ROOT / "native/patches" if candidate is None else candidate["directory"] / "patches"
    path = executable.parent / "camouflow-build.json"
    if path != path.resolve() or path.is_symlink() or path.stat().st_size > 8 * 1024**2:
        raise ValueError("Worker startup requires a canonical local build receipt")
    with path.open("rb") as stream:
        raw = stream.read(8 * 1024**2 + 1)
    if len(raw) > 8 * 1024**2:
        raise ValueError("Worker receipt exceeds its size bound")
    receipt = json.loads(raw.decode("utf-8-sig"))
    if (not isinstance(receipt, dict) or not isinstance(receipt.get("patches"), list)
            or receipt.get("chromium_revision") != lock["chromium_revision"]
            or receipt.get("binary_sha256_measured") != core[executable.name]):
        raise ValueError("Worker startup receipt does not match the pinned executable")
    if candidate is not None:
        from scripts.package_native_windows import validate_build_receipt
        validate_build_receipt(receipt, lock, candidate=candidate)
        if (set(core) != {"chrome.exe", "chrome.dll", "chrome_elf.dll"}
                or receipt.get("runtime_core_sha256_measured") != core):
            raise ValueError("Candidate worker receipt must bind every Windows runtime core file")
        arguments_path = executable.parent / "args.gn"
        if arguments_path != arguments_path.resolve() or arguments_path.stat().st_size > 65536:
            raise ValueError("Candidate diagnostics require canonical bounded build arguments")
        with arguments_path.open("rb") as stream:
            arguments = stream.read(65537)
        if len(arguments) > 65536:
            raise ValueError("Candidate arguments exceed their size bound")
        if (hashlib.sha256(arguments).hexdigest() != receipt.get("args_sha256")
                or arguments.decode("utf-8-sig").replace("\r\n", "\n")
                != (ROOT / "native/args.gn").read_text(encoding="utf-8-sig")):
            raise ValueError("Candidate worker build arguments changed or differ from the selected recipe")
    for number in range(15, 28):
        candidates = list(patch_directory.glob(f"{number:04d}-*.patch"))
        if len(candidates) != 1:
            raise ValueError("Worker startup requires the exact registered source chain")
        patch = candidates[0]
        expected = {"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
        if expected not in receipt.get("patches", []):
            raise ValueError("Worker startup receipt lacks a required exact patch")
    if bootstrap_policy == "surfaces":
        patch = patch_directory / SURFACE_PATCH
        if not patch.is_file() or patch.is_symlink():
            raise ValueError("Surface worker runtime requires a registered source patch, not uncompiled drafts")
        expected = {"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
        if expected not in receipt["patches"]:
            raise ValueError("Worker runtime receipt lacks the exact compiled surface-policy patch")
    return raw


async def verify(executable: Path, owned: Path, server: WorkerStartupServer, report: dict,
                 runtimes: list[NativeRuntime], *, bootstrap_policy: str = "canvas", include_nested: bool = False) -> None:
    origin = f"http://127.0.0.1:{server.server_port}"
    discovery = NativeRuntime(profile_dir=owned / "driver-arguments", executable=executable,
                              configuration=StartupConfiguration())
    runtimes.append(discovery)
    try:
        context = await discovery.start(headless=True)
        original_arguments = await browser_arguments(context)
        disabled_features_argument = partitioning_argument(original_arguments)
        report["driver_disabled_features_original"] = next(
            argument for argument in original_arguments if argument.startswith("--disable-features="))
        report["probe_disabled_features_replacement"] = disabled_features_argument
    finally:
        await discovery.close()
    for mode, phases in PHASES.items():
        configuration = StartupConfiguration(probe_mode=mode, bootstrap_policy=bootstrap_policy,
                                             disabled_features_argument=disabled_features_argument,
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
                await verify_shared_clients(context, origin, server, mode, phase, report)
                if include_nested:
                    await verify_nested_workers(page, server, mode, phase, report)
            finally:
                await runtime.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--bootstrap-policy", choices=("canvas", "surfaces"), default="canvas")
    parser.add_argument("--include-nested", action="store_true", help="Add 20 classic/module nested dedicated-worker checks")
    parser.add_argument("--candidate", choices=("upstream-156",),
                        help="Bind owned diagnostics to the exact selected candidate receipt/patches; not admission")
    args = parser.parse_args()
    selection = {} if args.candidate is None else {"candidate_name": args.candidate}
    if args.report.exists() or args.report.is_symlink():
        parser.error("Refusing to overwrite worker startup evidence")
    report = {"schema": 1, "passed": False, "checks": [], "arguments": {}, "platform": platform.platform(),
              "bootstrap_policy": args.bootstrap_policy, "privacy_admitted": False,
              "scope": "Owned classic/module worker startup, restart, shared multi-page clients and unavailable-policy rejection; not Canvas, nested workers, early startup termination or admission"}
    report["include_nested"] = args.include_nested
    if args.include_nested:
        report["scope"] = "Owned worker startup/restart plus nested dedicated-worker body execution; unavailable parent prevents child creation; not independent child denial, early termination, Canvas or admission"
    server = thread = owned = None
    runtimes = []
    try:
        executable = args.executable.resolve(strict=True)
        if args.candidate is not None:
            report.update(candidate=args.candidate,
                          candidate_manifest_sha256=load_candidate(args.candidate)["manifest_sha256"])
        probe_checksum = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        report["probe_sha256"] = probe_checksum
        core = measure_runtime_core(executable)
        receipt = validate_receipt(executable, core, bootstrap_policy=args.bootstrap_policy, **selection)
        report.update(runtime_core_sha256_measured=core, binary_sha256_measured=core[executable.name],
                      receipt_sha256=hashlib.sha256(receipt).hexdigest())
        args.work_dir.mkdir(parents=True, exist_ok=True)
        if args.work_dir.resolve().is_relative_to(ROOT):
            raise ValueError("Worker profiles must stay outside the public checkout")
        server = WorkerStartupServer(("127.0.0.1", 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        owned = Path(tempfile.mkdtemp(prefix="glint-worker-startup-", dir=args.work_dir.resolve()))
        asyncio.run(verify(executable, owned, server, report, runtimes,
                           bootstrap_policy=args.bootstrap_policy, include_nested=args.include_nested))
        if (measure_runtime_core(executable) != core
                or validate_receipt(executable, core, bootstrap_policy=args.bootstrap_policy, **selection) != receipt
                or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != probe_checksum):
            raise ValueError("Worker runtime code, receipt or probe changed during verification")
        expected = {f"{mode}-{phase}-{kind}-{script_type}" for mode, phases in PHASES.items()
                    for phase in phases for kind, script_type in CASES}
        expected.update(f"{mode}-{phase}-shared-clients-{script_type}" for mode, phases in PHASES.items()
                        for phase in phases for script_type in ("classic", "module"))
        if args.include_nested:
            expected.update(f"{mode}-{phase}-nested-{parent}-{child}" for mode, phases in PHASES.items()
                            for phase in phases for parent, child in NESTED_CASES)
        if {check["name"] for check in report["checks"]} != expected or len(report["checks"]) != len(expected):
            raise ValueError("Worker startup phases are incomplete")
        report["passed"] = True
    except Exception as error:  # noqa: BLE001 - persist failed diagnostic evidence before exiting
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
