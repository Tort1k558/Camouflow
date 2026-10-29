"""Owned Audio API compatibility checks; no device-cohort or privacy admission."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import sys
import threading

from scripts import native_build as build
from scripts.verify_native_surfaces import SurfaceConfiguration, validate_receipt
from scripts.verify_native_worker_startup import browser_arguments, partitioning_argument

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "native/fixtures/audio"
MODES = ("baseline", "legacy", "math")

PROBES = ("fidelity", "analyser", "worklet", "realtime")
RATES = (44100, 48000)
GRAPHS = ("identity", "half-gain", "compressor")
FIDELITY_GRAPHS = ("silence", "identity", "half-gain", "impulse", "stereo", "constant-positive",
                   "constant-negative", "oscillator", "compressor")
CHECKS = {
    "analyser": {"closed", "formatPreserved", "timeFinite", "timeRepeatedExact", "timeMatchesRenderedTail",
        "shortArrayPrefixExact", "longArrayPrefixExact", "longArrayTailUntouched", "byteTimeConversionExact",
        "frequencyValid", "frequencyRepeatedExact", "byteFrequencyRepeatedExact", "invalidFftRejected",
        "outputMutationDoesNotChangeAnalyser"},
    "worklet": {"closed", "formatPreserved", "allFramesCoveredExactlyOnce", "workletSampleRateExact",
        "workletTimelineCoherent", "workletDataFinite", "workletSignalNonzero", "workletMatchesRendered",
        "readApisAgree", "linearGraphExact", "sourceBufferUnchanged"},
    "realtime": {"trustedActivation", "realtimeAdvanced", "suspended", "signalFiniteAndNonzero",
        "suspendedReadsExact", "byteConversionExact", "frequencyValid", "compressorReductionFinite",
        "outputMuted", "nativeSampleRateValid", "closed"},
}


def validate_checks(checks: object, probe: str) -> None:
    if type(probe) is not str or probe not in CHECKS:
        raise ValueError("Unknown Audio check set")
    if not isinstance(checks, dict) or set(checks) != CHECKS[probe] or any(value is not True for value in checks.values()):
        raise ValueError("Incomplete or failed Audio checks: " + probe)


def validate_observation(observed: object, probe: str) -> dict:
    if type(probe) is not str or probe not in PROBES:
        raise ValueError("Unknown Audio compatibility probe")
    if (not isinstance(observed, dict) or type(observed.get("schema")) is not int
            or observed["schema"] != 1 or observed.get("passed") is not True):
        raise ValueError("Audio compatibility observation did not pass: " + probe)
    if probe == "realtime":
        rate = observed.get("sampleRate")
        try:
            valid_rate = type(rate) in (int, float) and math.isfinite(rate) and rate > 0
        except OverflowError:
            valid_rate = False
        if (not valid_rate
                or observed.get("errors") != []):
            raise ValueError("Invalid realtime Audio metadata or cleanup errors")
        validate_checks(observed.get("checks"), probe)
        return {"cases": 1, "checks_per_case": len(CHECKS[probe])}
    graphs = FIDELITY_GRAPHS if probe == "fidelity" else GRAPHS
    repetitions = range(3 if probe == "fidelity" else 2)
    expected = {(rate, graph, repetition) for rate in RATES for graph in graphs for repetition in repetitions}
    rows = observed.get("rows")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("Audio compatibility case coverage is incomplete: " + probe)
    seen = set()
    digests = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed Audio case")
        key = (row.get("rate"), row.get("kind" if probe == "fidelity" else "graph"), row.get("repetition"))
        if type(key[0]) is not int or type(key[1]) is not str or type(key[2]) is not int:
            raise ValueError("Malformed Audio case identity")
        if key not in expected or key in seen or row.get("passed") is not True:
            raise ValueError("Missing, duplicated, foreign or failed Audio case")
        seen.add(key)
        if probe != "fidelity":
            validate_checks(row.get("checks"), probe)
            if probe == "worklet" and (type(row.get("packetCount")) is not int or not 1 <= row["packetCount"] <= 2048):
                raise ValueError("Invalid AudioWorklet packet count")
            continue
        if (type(row.get("frames")) is not int or row["frames"] != 512
                or type(row.get("sampleRate")) is not int or row["sampleRate"] != key[0]
                or type(row.get("channelCount")) is not int or row["channelCount"] != 2
                or any(row.get(name) is not True for name in ("closed", "eventSameBuffer", "copyMutationExact"))):
            raise ValueError("Audio fidelity format or lifecycle changed")
        channels = row.get("channels")
        if not isinstance(channels, list) or len(channels) != 2:
            raise ValueError("Audio fidelity channel coverage is incomplete")
        for channel in channels:
            if (not isinstance(channel, dict) or type(channel.get("sha256")) is not str
                    or not re.fullmatch(r"[0-9a-f]{64}", channel["sha256"])
                    or any(channel.get(name) is not True for name in ("finite", "repeatedExact", "copiedExact", "segmentedExact"))
                    or channel.get("expectedExact") is not (None if key[1] in {"oscillator", "compressor"} else True)
                    or type(channel.get("nonzero")) is not bool
                    or (key[1] == "silence" and channel["nonzero"])
                    or (key[1] != "silence" and not channel["nonzero"])):
                raise ValueError("Audio fidelity signal or read APIs disagree")
        hashes = tuple(channel["sha256"] for channel in channels)
        if (hashes[0] == hashes[1]) != (key[1] != "stereo"):
            raise ValueError("Audio fidelity channel relationships changed")
        group = key[:2]
        if group in digests and digests[group] != hashes:
            raise ValueError("Audio fidelity changed across repeated renders")
        digests[group] = hashes
    if seen != expected or (probe == "fidelity" and observed.get("repeatStable") is not True):
        raise ValueError("Audio compatibility repetitions are incomplete or unstable")
    if probe == "fidelity":
        for rate in RATES:
            silent = digests[(rate, "silence")]
            if (any(digests[(rate, graph)] == silent for graph in graphs if graph != "silence")
                    or digests[(rate, "identity")] == digests[(rate, "half-gain")]
                    or digests[(rate, "constant-positive")] == digests[(rate, "constant-negative")]):
                raise ValueError("Audio fidelity hashes contradict the controlled input graphs")
    return {"cases": len(expected), "checks_per_case": None if probe == "fidelity" else len(CHECKS[probe])}


@dataclass(frozen=True)
class AudioConfiguration(SurfaceConfiguration):
    audio_mode: str = "baseline"

    def launch_arguments(self) -> list[str]:
        if self.audio_mode not in MODES:
            raise ValueError("Unknown Audio compatibility mode")
        if self.probe_mode != ("baseline" if self.audio_mode == "baseline" else "ready"):
            raise ValueError("Audio compatibility mode and policy configuration disagree")
        arguments = super().launch_arguments()
        if self.audio_mode == "math":
            indices = [index for index, value in enumerate(arguments) if value.startswith("--enable-features=")]
            if len(indices) != 1:
                raise ValueError("AudioMath requires one explicit feature list")
            arguments[indices[0]] += ",GlintAudioMathCandidate"
        return arguments


def fixture_sources() -> dict[str, str]:
    sources = {}
    for name in (*PROBES, "worklet-processor"):
        path = FIXTURES / (name + ".js")
        if path != path.resolve() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError("Audio fixtures must be canonical bounded source files")
        with path.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("Audio fixture exceeds its size bound")
        sources[name] = raw.decode("utf-8-sig")
    return sources


class AudioFixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, sources: dict[str, str]):
        self.sources = dict(sources)
        super().__init__(("127.0.0.1", 0), AudioFixtureHandler)

    @property
    def origin(self) -> str:
        return "http://127.0.0.1:" + str(self.server_port)


class AudioFixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/audio":
            body, kind = "<!doctype html><title>Owned Audio compatibility</title>", "text/html"
        elif self.path == "/glint-audio-worklet.js":
            body, kind = self.server.sources["worklet-processor"], "text/javascript"
        else:
            self.send_error(404)
            return
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)


async def measure(context, server: AudioFixtureServer) -> dict:
    result = {"passed": False, "probes": {}}

    async def route(request):
        if request.request.url.startswith(server.origin + "/"):
            await request.continue_()
        else:
            await request.abort("blockedbyclient")

    await context.route("**/*", route)
    try:
        page = context.pages[0] if context.pages else await context.new_page()
        for probe in PROBES:
            check = {"passed": False}
            result["probes"][probe] = check
            try:
                await page.goto(server.origin + "/audio", timeout=10000)
                source = server.sources[probe]
                if probe == "realtime":
                    await page.evaluate("() => { const probe = (" + source + ");"
                        "const button=document.createElement('button'); button.textContent='Run muted audio';"
                        "button.onclick=()=>{window.ownedAudioTask=probe();}; document.body.append(button); }")
                    await page.get_by_role("button", name="Run muted audio", exact=True).click(timeout=10000)
                    observed = await asyncio.wait_for(page.evaluate("() => window.ownedAudioTask"), timeout=90)
                else:
                    observed = await asyncio.wait_for(page.evaluate(source), timeout=90)
                check["observed"] = observed
                check["coverage"] = validate_observation(observed, probe)
                check["passed"] = True
            except Exception as error:
                check.update(error_type=type(error).__name__, error=str(error))
        result["passed"] = set(result["probes"]) == set(PROBES) and all(row["passed"] for row in result["probes"].values())
    finally:
        try:
            await context.unroute("**/*", route)
        except Exception as error:
            result.update(passed=False, cleanup_error_type=type(error).__name__, cleanup_error=str(error))
    return result


async def measure_modes(executable: Path, owned: Path, server: AudioFixtureServer, modes: tuple[str, ...], report: dict,
                        revision: str, version: str) -> None:
    from app.core.native.runtime import NativeRuntime

    async def start(configuration, profile):
        runtime = NativeRuntime(owned / profile, executable, configuration)
        try:
            context = await runtime.start(headless=True)
            session = await context.browser.new_browser_cdp_session()
            failure = None
            try:
                observed_version = await session.send("Browser.getVersion")
                if observed_version["revision"] != "@" + revision or observed_version["product"] != "Chrome/" + version:
                    raise ValueError("Audio compatibility requires the real selected Git revision stamp")
            except BaseException as error:
                failure = error
                raise
            finally:
                try:
                    await session.detach()
                except Exception as error:
                    if failure is None:
                        raise
                    failure.add_note("Audio CDP session cleanup failed: " + str(error))
            arguments = await browser_arguments(context)
            if any(value not in arguments for value in configuration.launch_arguments()):
                raise ValueError("Browser did not apply the requested Audio configuration")
            return runtime, context, arguments
        except BaseException as primary:
            try:
                await runtime.close()
            except Exception as error:
                primary.add_note("Owned startup cleanup failed: " + str(error))
            raise

    report["phase"] = "discovery"
    runtime, _, arguments = await start(AudioConfiguration(), "discovery")
    try:
        original = next(value for value in arguments if value.startswith("--disable-features="))
        replacement = partitioning_argument(arguments)
    finally:
        await runtime.close()
        if runtime.has_resources:
            raise RuntimeError("Owned Audio discovery runtime retained resources")
    for mode in modes:
        report["phase"] = mode
        report["modes"][mode] = {"passed": False}
        configuration = AudioConfiguration(audio_mode=mode, probe_mode="baseline" if mode == "baseline" else "ready",
            derivation_mode="profile-identity", disabled_features_argument=replacement, ignored_driver_argument=original)
        runtime, context, effective = await start(configuration, "baseline" if mode == "baseline" else "protected")
        primary = None
        try:
            if partitioning_argument(effective) != replacement:
                raise ValueError("Browser partitioning configuration changed")
            report["modes"][mode] = await measure(context, server)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                await runtime.close()
                if runtime.has_resources:
                    raise RuntimeError("Owned Audio runtime retained resources")
                report["modes"][mode]["resources_closed"] = True
            except Exception as error:
                report["cleanup_errors"].append({"mode": mode, "error_type": type(error).__name__, "error": str(error)})
                if primary is None:
                    raise
                primary.add_note("Owned runtime cleanup failed: " + str(error))
    report["phase"] = "completed"


def probe_paths(candidate: dict) -> set[Path]:
    from scripts.verify_native_privacy_batch import source_inputs

    return (source_inputs(candidate) | {Path(__file__).resolve(), *FIXTURES.glob("*.js")}
            | {ROOT / "app/core/native" / name for name in ("runtime.py", "configuration.py", "identity.py", "profile_version.py")})


def verify(workspace: Path, executable: Path, owned: Path, *, candidate_name: str, modes: tuple[str, ...]) -> dict:
    from scripts import verify_native_privacy_units as units

    if (not isinstance(modes, tuple) or not modes or any(type(mode) is not str or mode not in MODES for mode in modes)
            or len(set(modes)) != len(modes)):
        raise ValueError("Select distinct explicit Audio compatibility modes")
    if sys.platform != "win32" or candidate_name != "upstream-156":
        raise ValueError("Audio compatibility requires the explicit Windows upstream-156 candidate")
    if (not owned.is_absolute() or owned.drive.upper() != "D:" or owned != owned.resolve()
            or not owned.parent.is_dir() or owned.exists() or owned.is_relative_to(ROOT)
            or owned.is_relative_to(workspace / "chromium/src")):
        raise ValueError("Audio evidence requires a fresh canonical D: directory outside source checkouts")
    candidate = build.load_candidate(candidate_name)
    if not any(row["file"] == "0067-native-audio-math-context-candidate.patch" for row in candidate["manifest"]["patches"]):
        raise ValueError("Audio compatibility requires the selected AudioMath patch")
    if workspace.drive.upper() != "D:":
        raise ValueError("Audio candidate workspace must remain on D:")
    build.candidate_workspace(workspace, candidate)
    with build.workspace_lock(workspace):
        units.require_idle_builder(workspace)
        owned.mkdir()
        report = {"schema": 1, "passed": False, "candidate": candidate_name, "requested_modes": list(modes), "modes": {},
                  "candidate_manifest_sha256": candidate["manifest_sha256"], "cleanup_errors": [],
                  "scope": "Explicit Audio API compatibility modes; not device-cohort, broad audio quality, privacy or release admission",
                  "privacy_admitted": False, "production_admitted": False, "postguards_passed": False}
        server = thread = None
        core = receipt = files = inputs = None
        try:
            if executable != executable.resolve() or not executable.is_file():
                raise ValueError("Audio diagnostics require a canonical executable")
            core = build.measure_runtime_core(executable)
            receipt = validate_receipt(executable, core, derivation_mode="profile-identity", candidate_name=candidate_name)
            files = probe_paths(candidate)
            inputs = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            report.update(runtime_core_sha256_measured=core, receipt_sha256=hashlib.sha256(receipt).hexdigest(),
                          measured_inputs_sha256={str(path.relative_to(ROOT)): value for path, value in inputs.items()})
            server = AudioFixtureServer(fixture_sources())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            asyncio.run(measure_modes(executable, owned, server, modes, report,
                                     candidate["lock"]["chromium_revision"], candidate["lock"]["chromium_version"]))
            report["passed"] = set(report["modes"]) == set(modes) and all(row["passed"] for row in report["modes"].values())
        except Exception as error:
            report.update(passed=False, error_type=type(error).__name__, error=str(error))
        finally:
            try:
                if server is not None:
                    if thread is not None and thread.is_alive():
                        server.shutdown()
                    server.server_close()
                if thread is not None:
                    thread.join(timeout=5)
                    if thread.is_alive():
                        raise RuntimeError("Owned Audio fixture thread remains")
            except Exception as error:
                report["cleanup_errors"].append({"error_type": type(error).__name__, "error": str(error)})
            if inputs is not None:
                try:
                    if (build.measure_runtime_core(executable) != core
                            or validate_receipt(executable, core, derivation_mode="profile-identity", candidate_name=candidate_name) != receipt
                            or any(hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in inputs.items())
                            or probe_paths(candidate) != files):
                        raise ValueError("Audio runtime, receipt or diagnostic inputs changed")
                    report["postguards_passed"] = True
                except Exception as error:
                    report["postguard_error_type"] = type(error).__name__
                    report["postguard_error"] = str(error)
            report["passed"] = report["passed"] and report["postguards_passed"] and not report["cleanup_errors"]
            (owned / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--candidate", choices=("upstream-156",), required=True)
    parser.add_argument("--mode", choices=MODES, action="append", required=True)
    args = parser.parse_args()
    try:
        report = verify(args.workspace, args.executable, args.work_dir, candidate_name=args.candidate, modes=tuple(args.mode))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({key: report.get(key) for key in ("passed", "requested_modes", "postguards_passed", "error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
