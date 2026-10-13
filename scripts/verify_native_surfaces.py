"""Combined owned Canvas/OfflineAudio isolation gate; never anti-bot admission."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import threading
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from app.core.native.runtime import NativeRuntime
from scripts.verify_native_audio import AUDIO_READ
from scripts.verify_native_audio import validate_observations as validate_audio
from scripts.verify_native_audio_quality import compare_quality, strip_quality
from scripts import verify_native_nested_canvas as nested_canvas
from scripts.verify_native_canvas import (
    CONTEXTS,
    READ,
    SECURITY_READ,
    CanvasFixtureHandler,
    observe,
    security_frames,
    validate_security,
)
from scripts.verify_native_canvas import (
    validate_observations as validate_canvas,
)
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core
from scripts.verify_native_worker_startup import (
    FEATURE_ARGUMENT,
    KEY_ARGUMENT,
    StartupConfiguration,
    browser_arguments,
    partitioning_argument,
)
from scripts.verify_native_worker_startup import (
    validate_receipt as validate_worker_receipt,
)

DOCUMENT_ARGUMENT = "--glint-document-surface-bootstrap-test"
REQUIRED_PATCHES = (
    "0032-native-document-surface-policy.patch",
    "0033-native-surface-readback.patch",
)
COMBINED_READ = f"async () => ({{canvas: await ({READ})(), audio: await ({AUDIO_READ})(true)}})"
DOCUMENT_CONTEXTS = CONTEXTS - {"dedicated", "shared", "service"}
SAME_PARTITION = CONTEXTS - {"cross_origin_frame"}


def validate_denial_navigation(observed: dict, *, denied: bool) -> None:
    expected = {"requests": 1, "executions": 0 if denied else 1}
    if (observed["counts"] != expected
            or any(type(value) is not int for value in observed["counts"].values())):
        raise ValueError("Denial probe requires one fetched fixture and calibrated script execution")
    if any(event["method"] == "overflow" for event in observed["events"]):
        raise ValueError("Owned navigation event evidence exceeded its bounded budget")
    before, after = observed["before_frame"], observed["after_frame"]
    if before["id"] != after["id"]:
        raise ValueError("Denial probe lost its owned frame")
    if not denied:
        if after["url"] != observed["url"]:
            raise ValueError("Control document did not commit")
        return
    if (before["url"] != after["url"] or before["loaderId"] != after["loaderId"]
            or observed["before_history"] != observed["after_history"]):
        raise ValueError("Denied document changed the committed frame or navigation history")
    requests = {event["requestId"] for event in observed["events"]
                if event["method"] == "Network.requestWillBeSent" and event["type"] == "Document"
                and event["url"] == observed["url"] and event["frameId"] == before["id"]}
    aborted = {event["requestId"] for event in observed["events"]
               if event["method"] == "Network.loadingFailed" and event["type"] == "Document"
               and event["errorText"] == "net::ERR_ABORTED" and event["canceled"] is True}
    if len(requests) != 1 or not requests.issubset(aborted):
        raise ValueError("Denied owned document lacks an exact correlated ERR_ABORTED event")
    if any(event["method"] == "Page.frameNavigated" and event["url"] == observed["url"]
           for event in observed["events"]):
        raise ValueError("Denied document emitted a commit event")


async def verify_document_denial(executable: Path, owned: Path, server: SurfaceFixtureServer,
                                original: str, replacement: str, check: dict) -> None:
    # A denied initial about:blank cannot satisfy a persistent driver's page wait.
    # Browser-level CDP observes the original profile without requiring that commit.
    temporary = owned / "denial-driver-temp"
    temporary.mkdir()
    marker = owned / "denial-driver-live"
    marker.write_text("owned diagnostic driver", encoding="utf-8")
    saved = {name: os.environ.get(name) for name in ("TEMP", "TMP", "TMPDIR")}
    try:
        for name in saved:
            os.environ[name] = str(temporary)
        driver = await async_playwright().start()
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    observations = check.setdefault("observations", {})
    try:
        for mode in ("baseline", "unavailable"):
            configuration = SurfaceConfiguration(probe_mode=mode,
                disabled_features_argument=replacement, ignored_driver_argument=original)
            browser = await driver.chromium.launch(executable_path=str(executable), headless=True,
                args=configuration.launch_arguments(), ignore_default_args=[original])
            try:
                cdp = await browser.new_browser_cdp_session()
                arguments = (await cdp.send("Browser.getBrowserCommandLine"))["arguments"]
                check.setdefault("effective_arguments", {})[mode] = arguments
                if (KEY_ARGUMENT in arguments or partitioning_argument(arguments) != replacement
                        or FEATURE_ARGUMENT not in arguments
                        or (DOCUMENT_ARGUMENT in arguments) != (mode == "unavailable")):
                    raise ValueError("Denial browser arguments do not match the owned missing-key mode")
                target = await cdp.send("Target.createTarget", {"url": "about:blank"})
                session = (await cdp.send("Target.attachToTarget", {
                    "targetId": target["targetId"], "flatten": False}))["sessionId"]
                pending, events = {}, []

                def received(event):
                    if event.get("sessionId") != session:
                        return
                    message = json.loads(event["message"])
                    future = pending.pop(message.get("id"), None)
                    if future is not None and not future.done():
                        future.set_result(message)
                    method, params = message.get("method"), message.get("params", {})
                    if len(events) >= 512:
                        if events[-1]["method"] != "overflow":
                            events.append({"method": "overflow"})
                        return
                    if method == "Network.requestWillBeSent" and params.get("type") == "Document":
                        events.append({"method": method, "requestId": params["requestId"],
                            "type": params["type"], "frameId": params["frameId"],
                            "url": params["request"]["url"]})
                    elif method == "Network.loadingFailed" and params.get("type") == "Document":
                        events.append({"method": method, "requestId": params["requestId"],
                            "type": params["type"], "errorText": params["errorText"],
                            "canceled": params.get("canceled", False)})
                    elif method == "Page.frameNavigated":
                        events.append({"method": method, "url": params["frame"]["url"]})

                cdp.on("Target.receivedMessageFromTarget", received)

                async def send(index, method, params):
                    future = asyncio.get_running_loop().create_future()
                    pending[index] = future
                    try:
                        await cdp.send("Target.sendMessageToTarget", {"sessionId": session,
                            "message": json.dumps({"id": index, "method": method, "params": params})})
                        message = await asyncio.wait_for(future, 15)
                        if "error" in message or not isinstance(message.get("result"), dict):
                            raise ValueError(f"Owned CDP command failed: {method}")
                        return message["result"]
                    finally:
                        pending.pop(index, None)

                await send(1, "Page.enable", {})
                await send(2, "Network.enable", {})
                before = await send(3, "Page.getFrameTree", {})
                history = await send(4, "Page.getNavigationHistory", {})
                identifier = uuid.uuid4().hex
                url = f"http://127.0.0.1:{server.server_port}/surface-startup?id={identifier}"
                navigation = await send(5, "Page.navigate", {"url": url})
                deadline = asyncio.get_running_loop().time() + 10
                while asyncio.get_running_loop().time() < deadline:
                    counts = server.counts(identifier)
                    if ((mode == "baseline" and counts["executions"] == 1)
                            or (mode == "unavailable" and any(event["method"] == "Network.loadingFailed"
                                and event["type"] == "Document" for event in events))):
                        break
                    await asyncio.sleep(0.05)
                await asyncio.sleep(0.5)
                after = await send(6, "Page.getFrameTree", {})
                observed = {"url": url, "counts": server.counts(identifier), "navigation": navigation,
                    "before_frame": before["frameTree"]["frame"], "after_frame": after["frameTree"]["frame"],
                    "before_history": history, "after_history": await send(7, "Page.getNavigationHistory", {}),
                    "events": list(events), "browser_live": await cdp.send("Browser.getVersion")}
                observations[mode] = observed
                validate_denial_navigation(observed, denied=mode == "unavailable")
            finally:
                await asyncio.wait_for(browser.close(), 15)
    finally:
        await asyncio.wait_for(driver.stop(), 15)
    marker.unlink()


class SurfaceFixtureServer(FixtureServer):
    def __init__(self, address):
        super().__init__(address, SurfaceFixtureHandler)
        self._lock = threading.Lock()
        self._counts: dict[str, dict[str, int]] = {}

    def record(self, identifier: str, kind: str) -> None:
        with self._lock:
            counts = self._counts.setdefault(identifier, {"requests": 0, "executions": 0})
            counts[kind] += 1

    def counts(self, identifier: str) -> dict[str, int]:
        with self._lock:
            return dict(self._counts.get(identifier, {"requests": 0, "executions": 0}))


class SurfaceFixtureHandler(CanvasFixtureHandler):
    worker_read = COMBINED_READ

    def do_GET(self) -> None:
        if nested_canvas.serve_fixture(self):
            return
        parsed = urlsplit(self.path)
        if parsed.path not in {"/surface-startup", "/surface-first-script", "/surface-executed"}:
            return super().do_GET()
        identifiers = parse_qs(parsed.query).get("id", [])
        if len(identifiers) != 1 or len(identifiers[0]) != 32 or any(
                character not in "0123456789abcdef" for character in identifiers[0]):
            self.send_error(400)
            return
        identifier = identifiers[0]
        execution = parsed.path == "/surface-executed"
        self.server.record(identifier, "executions" if execution else "requests")
        if execution:
            body = b""
        elif parsed.path == "/surface-first-script":
            body = (
                "<!doctype html><script>"
                "const glintParserState = document.readyState;"
                f"const glintParserRead = ({COMBINED_READ})();"
                "const glintFirstChild = document.createElement('iframe');"
                "document.documentElement.appendChild(glintFirstChild);"
                "const glintInitialChildURL = glintFirstChild.contentWindow.location.href;"
                f"const glintChildRead = glintFirstChild.contentWindow.eval('(' + {json.dumps(COMBINED_READ)} + ')()');"
                "window.__glintFirstSurfaceRead = Promise.all([glintParserRead, glintChildRead])"
                ".then(async ([observed, initialChild]) => {"
                f"const response = await fetch('/surface-executed?id={identifier}');"
                "if (!response.ok) throw new Error('First-script execution beacon failed');"
                "return {parserState: glintParserState, observed, initialChild,"
                "initialChildURL: glintInitialChildURL};});"
                "</script>"
            ).encode()
        else:
            body = (
                f"<!doctype html><script>fetch('/surface-executed?id={identifier}');</script>"
            ).encode()
        self.send_response(204 if execution else 200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


@dataclass(frozen=True)
class SurfaceConfiguration(StartupConfiguration):
    bootstrap_policy: str = "surfaces"

    def launch_arguments(self) -> list[str]:
        arguments = super().launch_arguments()
        if self.probe_mode != "baseline":
            arguments.append(DOCUMENT_ARGUMENT)
        return arguments


def validate_receipt(executable: Path, core: dict) -> bytes:
    raw = validate_worker_receipt(executable, core, bootstrap_policy="surfaces")
    receipt = json.loads(raw.decode("utf-8-sig"))
    # An EXE hash alone does not bind Blink code in chrome.dll on Windows.
    if receipt.get("runtime_core_sha256_measured") != core:
        raise ValueError("Combined surface gate requires a receipt binding every runtime core file")
    for name in REQUIRED_PATCHES:
        patch = ROOT / "native/patches" / name
        if not patch.is_file() or patch.is_symlink():
            raise ValueError("Combined surfaces require registered patches, not uncompiled drafts")
        expected = {"name": name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
        if expected not in receipt["patches"]:
            raise ValueError("Combined receipt lacks an exact compiled surface patch")
    return raw


def validate_combined(observed: dict, previous: dict | None = None, *, protected: bool,
                      derivation_mode: str = "partitioned-privacy") -> None:
    if not isinstance(derivation_mode, str) or derivation_mode not in {
            "partitioned-privacy", "profile-identity"}:
        raise ValueError("Unknown combined surface derivation mode")
    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError("Combined probe must observe every document and worker")
    if any(not isinstance(value, dict) or set(value) != {"canvas", "audio"}
           for value in observed.values()):
        raise ValueError("Combined surface observations are incomplete")
    canvas = {name: value["canvas"] for name, value in observed.items()}
    audio = strip_quality({name: value["audio"] for name, value in observed.items()})
    stable_identity = derivation_mode == "profile-identity"
    validate_canvas(canvas, require_context_equality=not protected or stable_identity)
    coverage = validate_audio(audio)
    if set(coverage["available"]) != DOCUMENT_CONTEXTS:
        raise ValueError("Offline Audio must be measured in all five document contexts")
    if protected:
        names = CONTEXTS if stable_identity else SAME_PARTITION
        for surface, contexts, field in ((canvas, names, "pixels"),
                                         (audio, names & DOCUMENT_CONTEXTS, "signal")):
            reference = surface["document"][field]
            if any(surface[name][field] != reference for name in contexts):
                raise ValueError("Profile identity surface reads disagree" if stable_identity
                                 else "Same-partition surface reads disagree")
            if not stable_identity and surface["cross_origin_frame"][field] == reference:
                raise ValueError("Cross-origin partition did not isolate the surface")
    if previous is not None:
        validate_combined(previous, protected=protected, derivation_mode=derivation_mode)
        previous_canvas = {name: value["canvas"] for name, value in previous.items()}
        previous_audio = strip_quality({name: value["audio"] for name, value in previous.items()})
        if canvas != previous_canvas or audio != previous_audio:
            raise ValueError("Combined surface reads changed across profile restart")


def validate_isolation(baseline: dict, first: dict, second: dict, *,
                       derivation_mode: str = "partitioned-privacy") -> None:
    validate_combined(baseline, protected=False, derivation_mode=derivation_mode)
    validate_combined(first, protected=True, derivation_mode=derivation_mode)
    validate_combined(second, protected=True, derivation_mode=derivation_mode)
    for name in CONTEXTS:
        if len({row[name]["canvas"]["pixels"] for row in (baseline, first, second)}) != 3:
            raise ValueError("Canvas must change from baseline and isolate both profiles")
    for name in DOCUMENT_CONTEXTS:
        if len({row[name]["audio"]["signal"]["hash"] for row in (baseline, first, second)}) != 3:
            raise ValueError("Audio must change from baseline and isolate both profiles")
        if any(row[name]["audio"]["silence"]["hash"] != baseline[name]["audio"]["silence"]["hash"]
               for row in (first, second)):
            raise ValueError("Protected Audio changed silent samples or buffer semantics")


def validate_first_script(result: dict, document: dict, counts: dict) -> None:
    if (not isinstance(result, dict)
            or set(result) != {"parserState", "observed", "initialChild", "initialChildURL"}
            or result["parserState"] != "loading"):
        raise ValueError("Surface measurement did not start in the first parser script")
    if result["initialChildURL"] != "about:blank":
        raise ValueError("Initial child surface measurement was taken after navigation")
    if counts != {"requests": 1, "executions": 1}:
        raise ValueError("First-script fixture lacks one fetched document and completed execution")
    settled_audio = strip_quality({"document": document["audio"]})
    for context in ("observed", "initialChild"):
        observed = result[context]
        if not isinstance(observed, dict) or set(observed) != {"canvas", "audio"}:
            raise ValueError("First-script surface observations are incomplete: " + context)
        if observed["canvas"] != document["canvas"]:
            raise ValueError("Canvas policy changed between the first script and settled document: " + context)
        first_audio = strip_quality({"document": observed["audio"]})
        if first_audio != settled_audio:
            raise ValueError("Audio policy changed between the first script and settled document: " + context)


def probe_inputs() -> dict[str, str]:
    names = ("scripts/verify_native_surfaces.py", "scripts/verify_native_canvas.py",
             "scripts/verify_native_audio.py", "scripts/verify_native_worker_startup.py",
             "scripts/verify_native_audio_quality.py",
             "scripts/verify_native_nested_canvas.py",
             "scripts/verify_native_runtime.py", "app/core/native/runtime.py",
             "app/core/native/configuration.py", "app/core/native/identity.py")
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


async def verify(executable: Path, owned: Path, server: SurfaceFixtureServer, report: dict,
                 runtimes: list[NativeRuntime], *, include_nested_canvas: bool = False) -> None:
    origin = f"http://127.0.0.1:{server.server_port}"
    discovery = NativeRuntime(owned / "driver-arguments", executable, SurfaceConfiguration())
    runtimes.append(discovery)
    try:
        context = await discovery.start(headless=True)
        arguments = await browser_arguments(context)
        replacement = partitioning_argument(arguments)
        original = next(arg for arg in arguments if arg.startswith("--disable-features="))
        report["driver_disabled_features_original"] = original
        report["probe_disabled_features_replacement"] = replacement
    finally:
        await discovery.close()
    results = {}
    for name in ("baseline", "profile-a", "profile-b"):
        mode = "baseline" if name == "baseline" else "ready"
        configuration = SurfaceConfiguration(probe_mode=mode,
            disabled_features_argument=replacement, ignored_driver_argument=original)
        runtime = NativeRuntime(owned / name, executable, configuration)
        runtimes.append(runtime)
        previous = None
        previous_nested = None
        for phase in ("initial", "restart"):
            try:
                context = await runtime.start(headless=True)
                effective = await browser_arguments(context)
                if (partitioning_argument(effective) != replacement or replacement not in effective
                        or FEATURE_ARGUMENT not in effective):
                    raise ValueError("Effective arguments disable storage partitioning")
                if mode == "ready" and DOCUMENT_ARGUMENT not in effective:
                    raise ValueError("Document surface policy was not requested")
                check = {"name": f"{name}-{phase}", "passed": False}
                report["checks"].append(check)
                observed = await observe(context, origin, read=COMBINED_READ)
                check["observed"] = observed
                validate_combined(observed, previous, protected=mode == "ready")
                security = {}
                for frame_name, frame in (await security_frames(context.pages[0])).items():
                    security[frame_name] = await asyncio.wait_for(frame.evaluate(SECURITY_READ), timeout=20)
                check["security"] = security
                validate_security(security)
                identifier = uuid.uuid4().hex
                page = context.pages[0]
                await page.goto(f"{origin}/surface-first-script?id={identifier}", timeout=20000)
                first_script = await asyncio.wait_for(
                    page.evaluate("() => window.__glintFirstSurfaceRead"), timeout=30)
                counts = server.counts(identifier)
                check["first_script"] = first_script
                check["first_script_counts"] = counts
                validate_first_script(first_script, observed["document"], counts)
                if include_nested_canvas:
                    check["nested_canvas_evidence"] = {}
                    check["nested_canvas"] = await nested_canvas.observe(
                        page, server, observed["dedicated"]["canvas"], check["nested_canvas_evidence"])
                    if previous_nested is not None and check["nested_canvas"] != previous_nested:
                        raise ValueError("Nested worker Canvas changed across profile restart")
                    previous_nested = check["nested_canvas"]
                check["passed"] = True
                previous = observed
                results[name] = observed
            finally:
                await runtime.close()
    validate_isolation(results["baseline"], results["profile-a"], results["profile-b"])
    report["cross_profile_isolation_passed"] = True
    report["audio_quality"] = {
        name: compare_quality({context: row["audio"] for context, row in results["baseline"].items()},
                              {context: row["audio"] for context, row in results[name].items()})
        for name in ("profile-a", "profile-b")}
    check = {"name": "missing-document-policy", "passed": False}
    report["checks"].append(check)
    await verify_document_denial(executable, owned, server, original, replacement, check)
    check["passed"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--include-nested-canvas", action="store_true",
                        help="Also check first-script/repeated Canvas in classic/module parent/child workers")
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        parser.error("Refusing to overwrite surface evidence")
    report = {"schema": 1, "passed": False, "privacy_admitted": False, "checks": [],
              "platform": platform.platform(), "scope": "Combined Canvas/OfflineAudio isolation, first-parser-script consistency, restart, float32 error/SNR and missing-policy rejection; render durations measured, not a performance admission; no GPU or anti-bot admission"}
    report["include_nested_canvas"] = args.include_nested_canvas
    if args.include_nested_canvas:
        report["scope"] += "; nested classic/module dedicated-worker first-script/repeated Canvas and restart; not independent child-policy denial or nested Audio"
    server = thread = owned = None
    runtimes = []
    try:
        executable = args.executable.resolve(strict=True)
        core = measure_runtime_core(executable)
        receipt = validate_receipt(executable, core)
        inputs = probe_inputs()
        report.update(runtime_core_sha256_measured=core, probe_inputs_sha256=inputs,
                      receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                      javascript_sha256=hashlib.sha256(COMBINED_READ.encode("utf-8")).hexdigest())
        if args.work_dir.resolve().is_relative_to(ROOT):
            raise ValueError("Surface profiles must remain outside the public checkout")
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = SurfaceFixtureServer(("127.0.0.1", 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        owned = Path(tempfile.mkdtemp(prefix="glint-surfaces-", dir=args.work_dir.resolve()))
        asyncio.run(verify(executable, owned, server, report, runtimes,
                           include_nested_canvas=args.include_nested_canvas))
        if (measure_runtime_core(executable) != core or validate_receipt(executable, core) != receipt
                or probe_inputs() != inputs):
            raise ValueError("Surface runtime, receipt or probe code changed during verification")
        expected = {f"{name}-{phase}" for name in ("baseline", "profile-a", "profile-b")
                    for phase in ("initial", "restart")}
        expected.add("missing-document-policy")
        if ({check["name"] for check in report["checks"]} != expected
                or len(report["checks"]) != len(expected)):
            raise ValueError("Combined surface phases are incomplete")
        if args.include_nested_canvas:
            cases = {f"{parent}-{child}" for parent, child in nested_canvas.NESTED_CASES}
            nested_checks = [check for check in report["checks"] if check["name"] != "missing-document-policy"]
            if any(set(check.get("nested_canvas", {})) != cases
                   or set(check.get("nested_canvas_evidence", {})) != cases
                   or any(entry.get("passed") is not True for entry in check["nested_canvas_evidence"].values())
                   for check in nested_checks):
                raise ValueError("Nested Canvas phase coverage is incomplete")
            report["nested_canvas_case_count"] = sum(len(check["nested_canvas"]) for check in nested_checks)
        report["passed"] = True
    except Exception as error:  # noqa: BLE001 - retain failed evidence
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
                if any(runtime.has_resources for runtime in runtimes) or (owned / "denial-driver-live").exists():
                    raise ValueError("Live resources remain; owned profiles retained")
                if owned != owned.resolve() or not owned.is_relative_to(args.work_dir.resolve()):
                    raise ValueError("Refusing cleanup outside the owned workspace")
                shutil.rmtree(owned)
            except (OSError, ValueError) as error:
                report.update(passed=False, cleanup_error=str(error), retained_profile_directory=str(owned))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
