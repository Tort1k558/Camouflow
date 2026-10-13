import copy
import hashlib
import json
import struct
import sys
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from scripts import verify_native_surfaces as surfaces
from scripts.verify_native_canvas import ERRORS_EXPECTED, GEOMETRY_EXPECTED


def observation(digest="a", cross=None):
    rows = {}
    for name in surfaces.CONTEXTS:
        value = (cross if name == "cross_origin_frame" and cross else digest) * 64
        worker = name not in surfaces.DOCUMENT_CONTEXTS
        canvas = {key: value for key in ("pixels", "repeat", "blob", "htmlBlob", "htmlDataUrl")}
        canvas.update(htmlCapture=None if worker else True, geometry=copy.deepcopy(GEOMETRY_EXPECTED),
                      errors=copy.deepcopy(ERRORS_EXPECTED))
        if worker:
            canvas.update(htmlBlob=None, htmlDataUrl=None)
            audio = {"available": False, "reason": "API unavailable"}
        else:
            samples = [0x3e800000 + int(value[0], 16) * 2] * 4096
            sample_hash = hashlib.sha256(struct.pack("<4096I", *samples)).hexdigest()
            silent_hash = hashlib.sha256(bytes(4096 * 4)).hexdigest()
            signal = {"hash": sample_hash, "copiedHash": sample_hash, "rightHash": sample_hash,
                "sampleBits": samples, "renderMilliseconds": 1.0,
                "finite": True, "silence": None, "signal": True, "eventSameBuffer": True,
                "liveMutation": True, "copyFromSeesMutation": True, "copyToSeesMutation": True,
                "invalidChannel": "IndexSizeError", "sampleRate": 44100, "channels": 2,
                "frames": 4096, "closed": True}
            silence = {**signal, "hash": silent_hash, "copiedHash": silent_hash,
                       "rightHash": silent_hash, "silence": True, "signal": None,
                       "sampleBits": [0] * 4096}
            audio = {"available": True, "completionMutationVisible": True,
                     "signal": signal, "repeat": copy.deepcopy(signal),
                     "silence": silence}
        rows[name] = {"canvas": canvas, "audio": audio}
    return rows


def test_combined_baseline_protected_restart_and_isolation():
    baseline, first, second = observation(), observation("b", "c"), observation("d", "e")
    surfaces.validate_combined(first, copy.deepcopy(first), protected=True)
    surfaces.validate_isolation(baseline, first, second)


@pytest.mark.parametrize("context", sorted(surfaces.CONTEXTS))
def test_missing_context_cannot_pass(context):
    observed = observation("b", "c")
    del observed[context]
    with pytest.raises(ValueError):
        surfaces.validate_combined(observed, protected=True)


@pytest.mark.parametrize("surface", ["canvas", "audio"])
def test_same_partition_disagreement_cannot_pass(surface):
    observed = observation("b", "c")
    observed["same_origin_frame"][surface] = observation("d", "e")["document"][surface]
    with pytest.raises(ValueError, match="Same-partition"):
        surfaces.validate_combined(observed, protected=True)


def test_cross_origin_without_isolation_cannot_pass():
    with pytest.raises(ValueError, match="Cross-origin"):
        surfaces.validate_combined(observation(), protected=True)


def test_restart_drift_and_reused_profile_cannot_pass():
    first = observation("b", "c")
    with pytest.raises(ValueError, match="restart"):
        surfaces.validate_combined(first, observation("d", "e"), protected=True)
    with pytest.raises(ValueError, match="both profiles"):
        surfaces.validate_isolation(observation(), first, first)


def test_restart_durations_are_measured_not_fingerprint_identity():
    previous = observation("b", "c")
    observed = copy.deepcopy(previous)
    observed["document"]["audio"]["signal"]["renderMilliseconds"] = 2.5
    surfaces.validate_combined(observed, previous, protected=True)


def test_unavailable_document_audio_cannot_pass():
    observed = observation("b", "c")
    observed["srcdoc_frame"]["audio"] = {"available": False, "reason": "API unavailable"}
    with pytest.raises(ValueError, match="all five"):
        surfaces.validate_combined(observed, protected=True)


def test_prelaunch_failure_creates_no_profile_and_no_admission(tmp_path, monkeypatch):
    executable = tmp_path / "chrome.exe"
    executable.touch()
    report = tmp_path / "failed.json"
    owned = tmp_path / "owned"
    monkeypatch.setattr(surfaces, "measure_runtime_core", lambda path: {"chrome.exe": "a" * 64})

    def reject(*args, **kwargs):
        raise ValueError("Uncompiled source")

    monkeypatch.setattr(surfaces, "validate_receipt", reject)
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(executable),
                                      "--work-dir", str(owned), "--report", str(report)])
    assert surfaces.main() == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["error"] == "Uncompiled source"
    assert evidence["privacy_admitted"] is False and evidence["passed"] is False
    assert evidence["checks"] == [] and not owned.exists()


def test_receipt_requires_dll_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(surfaces, "validate_worker_receipt", lambda *args, **kwargs:
                        json.dumps({"patches": []}).encode())
    with pytest.raises(ValueError, match="every runtime core file"):
        surfaces.validate_receipt(tmp_path / "chrome.exe", {"chrome.exe": "a", "chrome.dll": "b"})


def test_surface_flags_do_not_enable_protection_in_baseline():
    assert surfaces.DOCUMENT_ARGUMENT not in surfaces.SurfaceConfiguration().launch_arguments()
    assert surfaces.DOCUMENT_ARGUMENT in surfaces.SurfaceConfiguration(probe_mode="ready").launch_arguments()


def test_owned_denial_fixture_counts_requests_and_execution_separately():
    server = surfaces.SurfaceFixtureServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    identifier = "a" * 32
    try:
        with urlopen(f"{origin}/surface-startup?id={identifier}", timeout=5) as response:
            assert b"surface-executed" in response.read()
        assert server.counts(identifier) == {"requests": 1, "executions": 0}
        with urlopen(f"{origin}/surface-executed?id={identifier}", timeout=5) as response:
            assert response.status == 204
        assert server.counts(identifier) == {"requests": 1, "executions": 1}
        with pytest.raises(HTTPError) as failure:
            urlopen(f"{origin}/surface-startup?id=invalid", timeout=5)
        assert failure.value.code == 400
        assert server.counts("invalid") == {"requests": 0, "executions": 0}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
