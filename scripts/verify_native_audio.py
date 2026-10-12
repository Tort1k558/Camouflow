"""Measure offline AudioBuffer semantics; this is not an audio privacy gate."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import tempfile
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from scripts.verify_native_canvas import CONTEXTS, CanvasFixtureHandler, observe
from scripts.verify_native_runtime import FixtureServer, measure_runtime_core

AUDIO_READ = """async () => {
  if (typeof OfflineAudioContext === 'undefined') return {available: false, reason: 'API unavailable'};
  const hash = async values => Array.from(new Uint8Array(await crypto.subtle.digest(
    'SHA-256', values)), value => value.toString(16).padStart(2, '0')).join('');
  const render = async silent => {
    const context = new OfflineAudioContext(2, 4096, 44100);
    const source = context.createBufferSource();
    const input = context.createBuffer(2, 4096, 44100);
    for (let channel = 0; channel < 2; channel++) {
      const values = input.getChannelData(channel);
      for (let i = 0; i < values.length; i++) {
        values[i] = silent ? 0 : Math.sin(i * Math.PI * 2 * 440 / 44100) * 0.5;
      }
    }
    source.buffer = input;
    const compressor = context.createDynamicsCompressor();
    source.connect(compressor); compressor.connect(context.destination); source.start();
    let eventBuffer = null;
    context.oncomplete = event => { eventBuffer = event.renderedBuffer; };
    const result = await context.startRendering();
    const left = result.getChannelData(0), right = result.getChannelData(1);
    const digest = await hash(left);
    const copied = new Float32Array(left.length);
    result.copyFromChannel(copied, 0);
    const before = left[0]; left[0] = 0.375;
    const liveMutation = result.getChannelData(0)[0] === 0.375;
    const copyAfter = new Float32Array(1); result.copyFromChannel(copyAfter, 0);
    const copyFromSeesMutation = copyAfter[0] === 0.375;
    result.copyToChannel(new Float32Array([-0.25]), 0, 1);
    const copyToSeesMutation = left[1] === -0.25;
    left[0] = before;
    let invalidChannel = null;
    try { result.getChannelData(2); } catch (error) { invalidChannel = error.name; }
    return {hash: digest, copiedHash: await hash(copied), rightHash: await hash(right),
      finite: copied.every(Number.isFinite), silence: silent ? copied.every(value => value === 0) : null,
      signal: silent ? null : copied.some(value => value !== 0),
      eventSameBuffer: eventBuffer === result, liveMutation, copyFromSeesMutation, copyToSeesMutation,
      invalidChannel, sampleRate: result.sampleRate, channels: result.numberOfChannels,
      frames: result.length, closed: context.state === 'closed'};
  };
  return {available: true, signal: await render(false), repeat: await render(false), silence: await render(true)};
}"""


class AudioFixtureHandler(CanvasFixtureHandler):
    worker_read = AUDIO_READ


def probe_inputs() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "scripts/verify_native_audio.py", "scripts/verify_native_canvas.py",
        "scripts/verify_native_hardware.py", "scripts/verify_native_runtime.py")}


def validate_observations(observed: dict, previous: dict | None = None) -> dict:
    if not isinstance(observed, dict) or set(observed) != CONTEXTS:
        raise ValueError("Audio probe must observe every document and worker context")
    if previous is not None:
        validate_observations(previous)
    coverage = {"available": [], "unavailable": []}
    for name, values in observed.items():
        if not isinstance(values, dict) or type(values.get("available")) is not bool:
            raise ValueError(f"Missing Audio availability: {name}")
        if not values["available"]:
            if not isinstance(values.get("reason"), str) or not values["reason"]:
                raise ValueError(f"Missing Audio unavailability reason: {name}")
            if previous is not None and previous[name]["available"]:
                raise ValueError(f"Audio capability disappeared: {name}")
            coverage["unavailable"].append(name)
            continue
        coverage["available"].append(name)
        if set(values) != {"available", "signal", "repeat", "silence"}:
            raise ValueError(f"Missing Audio render phases: {name}")
        for phase in ("signal", "repeat", "silence"):
            result = values[phase]
            if not isinstance(result, dict):
                raise TypeError(f"Invalid Audio result: {name}/{phase}")
            digest = result.get("hash")
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(character not in "0123456789abcdef" for character in digest)
                    or result.get("copiedHash") != digest or result.get("rightHash") != digest):
                raise ValueError(f"Inconsistent Audio channel/copy reads: {name}/{phase}")
            if any(result.get(key) is not True for key in ("finite", "eventSameBuffer", "liveMutation",
                    "copyFromSeesMutation", "copyToSeesMutation", "closed")):
                raise ValueError(f"Audio buffer semantics failed: {name}/{phase}")
            if (result.get("invalidChannel") != "IndexSizeError" or result.get("sampleRate") != 44100
                    or result.get("channels") != 2 or result.get("frames") != 4096):
                raise ValueError(f"Audio format/error semantics failed: {name}/{phase}")
            if phase == "silence":
                if result.get("silence") is not True or result.get("signal") is not None:
                    raise ValueError(f"Offline silence changed: {name}")
            elif result.get("signal") is not True or result.get("silence") is not None:
                raise ValueError(f"Offline signal disappeared: {name}/{phase}")
        if values["signal"] != values["repeat"]:
            raise ValueError(f"Repeated offline rendering changed: {name}")
        if previous is not None and previous[name] != values:
            raise ValueError(f"Offline Audio changed across restart: {name}")
    if not coverage["available"]:
        raise ValueError("No available OfflineAudioContext; cannot pass diagnostics")
    return {key: sorted(value) for key, value in coverage.items()}


async def verify(executable: Path, profile: Path, origin: str, report: dict) -> None:
    previous = None
    async with async_playwright() as driver:
        for phase in ("initial", "persistent-profile-restart"):
            context = await driver.chromium.launch_persistent_context(
                str(profile), executable_path=str(executable), headless=True,
                chromium_sandbox=True, timeout=30000)
            try:
                report["browser_version"] = context.browser.version
                observed = await observe(context, origin, read=AUDIO_READ)
                check = {"name": phase, "observed": observed, "passed": False}
                report["checks"].append(check)
                check["coverage"] = validate_observations(observed, previous)
                check["passed"] = True
                previous = observed
            finally:
                await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--windows-library-directory", type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Refusing to overwrite existing Audio evidence")
    report = {"schema": 1, "platform": platform.platform(), "passed": False, "checks": [],
              "privacy_admitted": False, "contexts": sorted(CONTEXTS),
              "scope": "Unprotected offline AudioBuffer semantics baseline; no masking or anti-bot claim"}
    server = None
    thread = None
    try:
        executable = args.executable.resolve(strict=True)
        if not executable.is_file():
            raise ValueError("An explicit Chromium executable is required")
        core = measure_runtime_core(executable, args.windows_library_directory)
        report["runtime_core_sha256_measured"] = core
        inputs = probe_inputs()
        report["probe_inputs_sha256"] = inputs
        report["javascript_sha256"] = hashlib.sha256(AUDIO_READ.encode("utf-8")).hexdigest()
        args.work_dir.mkdir(parents=True, exist_ok=True)
        server = FixtureServer(("127.0.0.1", 0), AudioFixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix="glint-audio-owned-", dir=args.work_dir.resolve()) as owned:
            asyncio.run(verify(executable, Path(owned), f"http://127.0.0.1:{server.server_port}", report))
        if measure_runtime_core(executable, args.windows_library_directory) != core:
            raise ValueError("Chromium runtime core changed during Audio verification")
        if probe_inputs() != inputs:
            raise ValueError("Audio probe inputs changed during verification")
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
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, indent=2))
    print(json.dumps({"passed": report["passed"], "report": str(args.report), "error": report.get("error")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
