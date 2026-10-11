"""Verify native WebRTC UDP privacy using owned loopback fixtures, never public STUN."""

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
from scripts.verify_native_runtime import FixtureHandler, FixtureServer  # noqa: E402


GATHER = """async port => {
    const connection = new RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.1:' + port}]});
    const candidates = [];
    connection.onicecandidate = event => {
        if (event.candidate) candidates.push({type:event.candidate.type, protocol:event.candidate.protocol});
    };
    try {
        connection.createDataChannel('owned-native-probe');
        await connection.setLocalDescription(await connection.createOffer());
        await new Promise(resolve => setTimeout(resolve, 5000));
        return {candidates, gathering:connection.iceGatheringState};
    } finally { connection.close(); }
}"""


class StunObserver(asyncio.DatagramProtocol):
    def __init__(self):
        self.requests = 0
        self.closed = asyncio.get_running_loop().create_future()

    def datagram_received(self, data, address):
        if len(data) >= 20 and data[:2] == b"\x00\x01" and data[4:8] == b"\x21\x12\xa4\x42":
            self.requests += 1

    def connection_lost(self, error):
        if not self.closed.done():
            self.closed.set_result(None)


def validate_probe(observed: dict, *, protected: bool) -> None:
    if not protected:
        if observed["loopback_stun_requests"] <= 0:
            raise ValueError("WebRTC positive control did not reach the owned STUN observer")
        return
    if observed["loopback_stun_requests"] or any(candidate["protocol"] == "udp" for candidate in observed["candidates"]):
        raise ValueError("Native WebRTC policy ignored or ineffective: direct UDP observed")
    if observed["gathering"] != "complete":
        raise ValueError("Protected WebRTC gathering did not complete; absence of packets is insufficient")


async def observe(frame) -> dict:
    probe = StunObserver()
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: probe, local_addr=("127.0.0.1", 0))
    try:
        observed = await frame.evaluate(GATHER, transport.get_extra_info("sockname")[1])
        return {**observed, "loopback_stun_requests": probe.requests}
    finally:
        transport.close()
        await asyncio.wait_for(probe.closed, timeout=5)


async def verify(executable: Path, root: Path, origin: str, checks: list) -> dict:
    async with async_playwright() as driver:
        version = ""
        for protected in (False, True):
            with tempfile.TemporaryDirectory(prefix="native-webrtc-owned-", dir=root) as directory:
                context = await driver.chromium.launch_persistent_context(directory,
                    executable_path=str(executable), headless=True, chromium_sandbox=True,
                    args=["--camouflow-webrtc-ip-handling-policy=disable_non_proxied_udp"] if protected else [])
                try:
                    version = context.browser.version
                    page = context.pages[0]
                    await page.goto(origin)
                    frames = [("document", page)]
                    if protected:
                        await page.evaluate("""async origin => {
                            for (const url of [origin, origin.replace('127.0.0.1', 'localhost')]) {
                                const frame = document.createElement('iframe');
                                const loaded = new Promise(resolve => frame.onload = resolve);
                                frame.src = url; document.body.append(frame); await loaded;
                            }
                        }""", origin)
                        frames.extend(zip(("same_origin_frame", "cross_origin_frame"), page.frames[1:]))
                        if len(frames) != 3:
                            raise ValueError("Both owned WebRTC frame contexts must be observed")
                    for name, frame in frames:
                        observed = await observe(frame)
                        check = {"context": name, "protected": protected, "observed": observed, "passed": False}
                        checks.append(check)
                        validate_probe(observed, protected=protected)
                        check["passed"] = True
                finally:
                    await context.close()
        for invalid in ("", "default", "DISABLE_NON_PROXIED_UDP"):
            with tempfile.TemporaryDirectory(prefix="native-webrtc-invalid-", dir=root) as directory:
                try:
                    context = await driver.chromium.launch_persistent_context(directory,
                        executable_path=str(executable), headless=True, chromium_sandbox=True,
                        args=["--camouflow-webrtc-ip-handling-policy=" + invalid], timeout=30000)
                except PlaywrightError as error:
                    if "Invalid CamouFlow WebRTC policy" not in str(error):
                        raise ValueError("Invalid-policy launch failed without the expected native CHECK") from error
                    checks.append({"invalid_policy": invalid, "passed": True})
                else:
                    await context.close()
                    raise ValueError("Native accepted an unsupported WebRTC policy")
    with executable.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"passed": True, "platform": platform.system(), "version": version,
            "binary_sha256_measured": checksum, "checks": checks,
            "scope": "Owned loopback STUN UDP and document/same-origin/cross-origin ICE candidates; not TURN or media connectivity"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    checks = []
    server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        report = asyncio.run(verify(args.executable.resolve(), args.work_dir,
                                   f"http://127.0.0.1:{server.server_port}", checks))
    except Exception as error:
        report = {"passed": False, "platform": platform.system(), "checks": checks,
                  "error_type": type(error).__name__, "error": str(error)}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
