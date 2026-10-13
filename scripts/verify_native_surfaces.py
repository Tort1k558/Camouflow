"""Combined owned Canvas/OfflineAudio isolation gate; never anti-bot admission."""

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
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import Error as BrowserError

from app.core.native.runtime import NativeRuntime
from scripts.verify_native_audio import AUDIO_READ
from scripts.verify_native_audio import validate_observations as validate_audio
from scripts.verify_native_audio_quality import compare_quality, strip_quality
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
        parsed = urlsplit(self.path)
        if parsed.path not in {"/surface-startup", "/surface-executed"}:
            return super().do_GET()
        identifiers = parse_qs(parsed.query).get("id", [])
        if len(identifiers) != 1 or len(identifiers[0]) != 32 or any(
                character not in "0123456789abcdef" for character in identifiers[0]):
            self.send_error(400)
            return
        identifier = identifiers[0]
        execution = parsed.path == "/surface-executed"
        self.server.record(identifier, "executions" if execution else "requests")
        body = b"" if execution else (
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


def validate_combined(observed: dict, previous: dict | None = None, *, protected: bool) -> None:
    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError("Combined probe must observe every document and worker")
    if any(not isinstance(value, dict) or set(value) != {"canvas", "audio"}
           for value in observed.values()):
        raise ValueError("Combined surface observations are incomplete")
    canvas = {name: value["canvas"] for name, value in observed.items()}
    audio = strip_quality({name: value["audio"] for name, value in observed.items()})
    validate_canvas(canvas, require_context_equality=not protected)
    coverage = validate_audio(audio)
    if set(coverage["available"]) != DOCUMENT_CONTEXTS:
        raise ValueError("Offline Audio must be measured in all five document contexts")
    if protected:
        for surface, names, field in ((canvas, SAME_PARTITION, "pixels"),
                                      (audio, SAME_PARTITION & DOCUMENT_CONTEXTS, "signal")):
            reference = surface["document"][field]
            if any(surface[name][field] != reference for name in names):
                raise ValueError("Same-partition surface reads disagree")
            if surface["cross_origin_frame"][field] == reference:
                raise ValueError("Cross-origin partition did not isolate the surface")
    if previous is not None:
        validate_combined(previous, protected=protected)
        previous_canvas = {name: value["canvas"] for name, value in previous.items()}
        previous_audio = strip_quality({name: value["audio"] for name, value in previous.items()})
        if canvas != previous_canvas or audio != previous_audio:
            raise ValueError("Combined surface reads changed across profile restart")


def validate_isolation(baseline: dict, first: dict, second: dict) -> None:
    validate_combined(baseline, protected=False)
    validate_combined(first, protected=True)
    validate_combined(second, protected=True)
    for name in CONTEXTS:
        if len({row[name]["canvas"]["pixels"] for row in (baseline, first, second)}) != 3:
            raise ValueError("Canvas must change from baseline and isolate both profiles")
    for name in DOCUMENT_CONTEXTS:
        if len({row[name]["audio"]["signal"]["hash"] for row in (baseline, first, second)}) != 3:
            raise ValueError("Audio must change from baseline and isolate both profiles")
        if any(row[name]["audio"]["silence"]["hash"] != baseline[name]["audio"]["silence"]["hash"]
               for row in (first, second)):
            raise ValueError("Protected Audio changed silent samples or buffer semantics")


def probe_inputs() -> dict[str, str]:
    names = ("scripts/verify_native_surfaces.py", "scripts/verify_native_canvas.py",
             "scripts/verify_native_audio.py", "scripts/verify_native_worker_startup.py",
             "scripts/verify_native_audio_quality.py",
             "scripts/verify_native_runtime.py", "app/core/native/runtime.py",
             "app/core/native/configuration.py", "app/core/native/identity.py")
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


async def verify(executable: Path, owned: Path, server: SurfaceFixtureServer, report: dict,
                 runtimes: list[NativeRuntime]) -> None:
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
    configuration = SurfaceConfiguration(probe_mode="unavailable",
        disabled_features_argument=replacement, ignored_driver_argument=original)
    runtime = NativeRuntime(owned / "missing-policy", executable, configuration)
    runtimes.append(runtime)
    check = {"name": "missing-document-policy", "passed": False}
    report["checks"].append(check)
    try:
        context = await runtime.start(headless=True)
        identifier = uuid.uuid4().hex
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto(f"{origin}/surface-startup?id={identifier}", timeout=20000)
        except BrowserError as error:
            check["navigation_error"] = str(error)
            if "net::ERR_ABORTED" not in str(error):
                raise ValueError("Missing-policy navigation did not produce an explicit abort") from error
        else:
            raise ValueError("Missing-policy document committed")
        await asyncio.sleep(0.5)
        check["observed"] = server.counts(identifier)
        if check["observed"]["requests"] < 1 or check["observed"]["executions"] != 0:
            raise ValueError("Missing-policy rejection lacks a fetched fixture or executed script")
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
        parser.error("Refusing to overwrite surface evidence")
    report = {"schema": 1, "passed": False, "privacy_admitted": False, "checks": [],
              "platform": platform.platform(), "scope": "Combined Canvas/OfflineAudio isolation, restart, float32 error/SNR and missing-policy rejection; render durations measured, not a performance admission; no GPU or anti-bot admission"}
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
        asyncio.run(verify(executable, owned, server, report, runtimes))
        if (measure_runtime_core(executable) != core or validate_receipt(executable, core) != receipt
                or probe_inputs() != inputs):
            raise ValueError("Surface runtime, receipt or probe code changed during verification")
        expected = {f"{name}-{phase}" for name in ("baseline", "profile-a", "profile-b")
                    for phase in ("initial", "restart")}
        expected.add("missing-document-policy")
        if ({check["name"] for check in report["checks"]} != expected
                or len(report["checks"]) != len(expected)):
            raise ValueError("Combined surface phases are incomplete")
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
                if any(runtime.has_resources for runtime in runtimes):
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
