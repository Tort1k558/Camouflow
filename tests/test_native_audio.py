from __future__ import annotations

import copy
import json
import sys

import pytest

from scripts.verify_native_audio import CONTEXTS, validate_observations


def observation():
    signal = {"hash": "a" * 64, "copiedHash": "a" * 64, "rightHash": "a" * 64,
              "finite": True, "silence": None, "signal": True, "eventSameBuffer": True,
              "liveMutation": True, "copyFromSeesMutation": True, "copyToSeesMutation": True,
              "invalidChannel": "IndexSizeError", "sampleRate": 44100, "channels": 2,
              "frames": 4096, "closed": True}
    silence = {**signal, "silence": True, "signal": None}
    return {name: {"available": True, "signal": copy.deepcopy(signal),
                   "repeat": copy.deepcopy(signal), "silence": copy.deepcopy(silence)}
            for name in CONTEXTS}


def test_offline_baseline_and_restart():
    observed = observation()
    assert validate_observations(observed, copy.deepcopy(observed)) == {
        "available": sorted(CONTEXTS), "unavailable": []}


@pytest.mark.parametrize("field,value", [
    ("hash", "x" * 64), ("copiedHash", "b" * 64), ("rightHash", "b" * 64),
    ("finite", False), ("eventSameBuffer", False), ("liveMutation", False),
    ("copyFromSeesMutation", False), ("copyToSeesMutation", False),
    ("closed", 1), ("invalidChannel", "TypeError"), ("sampleRate", 48000),
    ("channels", 1), ("frames", 2048), ("signal", False), ("silence", False),
])
def test_bad_audio_semantics_are_rejected(field, value):
    observed = observation()
    observed["document"]["signal"][field] = value
    with pytest.raises(ValueError):
        validate_observations(observed)


def test_worker_api_unavailable_is_not_audio_coverage():
    observed = observation()
    for name in ("dedicated", "shared", "service"):
        observed[name] = {"available": False, "reason": "API unavailable"}
    coverage = validate_observations(observed)
    assert len(coverage["available"]) == 5
    assert len(coverage["unavailable"]) == 3


def test_missing_and_unavailable_contexts_cannot_pass():
    observed = observation()
    del observed["document"]
    with pytest.raises(ValueError):
        validate_observations(observed)
    observed = {name: {"available": False, "reason": "API unavailable"} for name in CONTEXTS}
    with pytest.raises(ValueError):
        validate_observations(observed)


def test_lost_capability_and_restart_drift_are_rejected():
    observed = observation()
    observed["document"] = {"available": False, "reason": "API unavailable"}
    with pytest.raises(ValueError):
        validate_observations(observed, observation())
    observed = observation()
    for phase in ("signal", "repeat"):
        for key in ("hash", "copiedHash", "rightHash"):
            observed["document"][phase][key] = "b" * 64
    with pytest.raises(ValueError):
        validate_observations(observed, observation())


def test_nonsilent_silence_is_rejected():
    observed = observation()
    observed["document"]["silence"]["silence"] = False
    with pytest.raises(ValueError):
        validate_observations(observed)


def test_audio_cli_preserves_existing_evidence(tmp_path, monkeypatch):
    from scripts import verify_native_audio as audio

    report = tmp_path / "existing.json"
    report.write_text("existing evidence", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(tmp_path / "chrome.exe"),
                                     "--work-dir", str(tmp_path / "owned"), "--report", str(report)])
    with pytest.raises(SystemExit) as failure:
        audio.main()
    assert failure.value.code == 2
    assert report.read_text(encoding="utf-8") == "existing evidence"


def test_audio_cli_records_failure_without_admission(tmp_path, monkeypatch):
    from scripts import verify_native_audio as audio

    report = tmp_path / "failed.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(tmp_path / "missing.exe"),
                                     "--work-dir", str(tmp_path / "owned"), "--report", str(report)])
    assert audio.main() == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["passed"] is False and evidence["privacy_admitted"] is False
    assert evidence["error"] and not evidence["checks"]
