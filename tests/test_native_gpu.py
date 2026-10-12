from __future__ import annotations

import copy
import json
import sys

import pytest

from scripts.verify_native_gpu import (
    CONTEXTS,
    WEBGL_LIMITS,
    WEBGPU_LIMITS,
    validate_observations,
)


def observation(*, minimized=False, webgpu=True):
    gl = {"available": True, "extensions": ["EXT_color_buffer_float"], "debug": False,
          "vendor": None, "renderer": None, "unavailableParameter": {"value": None, "error": 1280},
          "pixels": [17, 34, 51, 255], "error": 0, "contextLost": False,
          "limits": dict.fromkeys(WEBGL_LIMITS, 16)}
    if not minimized:
        gl.update(extensions=["EXT_color_buffer_float", "WEBGL_debug_renderer_info"], debug=True,
                  vendor="Actual vendor", renderer="Actual renderer", unavailableParameter=None)
    info = {"vendor": "", "architecture": "", "device": "", "description": "",
            "subgroupMinSize": 4, "subgroupMaxSize": 32, "isFallbackAdapter": False}
    if not minimized:
        info.update(vendor="actual", architecture="actual", device="actual", description="actual")
    gpu = {"available": True, "info": info, "repeat": copy.deepcopy(info), "deviceInfo": copy.deepcopy(info),
           "features": ["depth-clip-control"], "limits": dict.fromkeys(WEBGPU_LIMITS, 256),
           "roundtrip": [17, 34, 51, 255], "compute": [18, 35, 52, 256], "validationError": None, "errors": []}
    if not webgpu:
        gpu = {"available": False, "reason": "No adapter"}
    return {name: {"webgl": {"webgl": copy.deepcopy(gl), "webgl2": copy.deepcopy(gl)},
                   "webgpu": copy.deepcopy(gpu)} for name in CONTEXTS}


def test_baseline_and_minimized_preserve_capabilities():
    baseline = observation()
    assert validate_observations(baseline) == {"webgl": 8, "webgl2": 8, "webgpu": 8}
    assert validate_observations(observation(minimized=True), minimized=True, baseline=baseline) == {
        "webgl": 8, "webgl2": 8, "webgpu": 8}


def test_unavailable_webgpu_is_not_counted_as_coverage():
    assert validate_observations(observation(webgpu=False))["webgpu"] == 0


@pytest.mark.parametrize("field,value", [
    ("pixels", [0, 0, 0, 0]), ("error", 1282), ("contextLost", True),
    ("available", 1), ("debug", 0), ("extensions", ["WEBGL_debug_renderer_info"]),
    ("unavailableParameter", {"value": None, "error": 0}), ("vendor", "leak"),
    ("limits", {}),
])
def test_rejects_invalid_webgl(field, value):
    observed = observation(minimized=True)
    observed["document"]["webgl"]["webgl"][field] = value
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True)


@pytest.mark.parametrize("field,value", [
    ("roundtrip", [0, 0, 0, 0]), ("compute", [0, 0, 0, 0]), ("validationError", "Validation failed"),
    ("errors", ["Device lost"]), ("available", 1), ("features", [1]),
    ("limits", {}), ("repeat", {}), ("deviceInfo", {}),
])
def test_rejects_invalid_webgpu(field, value):
    observed = observation(minimized=True)
    observed["document"]["webgpu"][field] = value
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True)


@pytest.mark.parametrize("api", ["webgl", "webgl2", "webgpu"])
def test_rejects_lost_baseline_capability(api):
    observed = observation(minimized=True)
    target = observed["document"]["webgpu"] if api == "webgpu" else observed["document"]["webgl"][api]
    target.update(available=False, reason="Unavailable")
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True, baseline=observation())


def test_minimized_rejects_ignored_feature_flag():
    with pytest.raises(ValueError):
        validate_observations(observation(), minimized=True)


def test_missing_context_and_all_unavailable_cannot_pass():
    observed = observation()
    del observed["document"]
    with pytest.raises(ValueError):
        validate_observations(observed)
    observed = observation()
    for value in observed.values():
        value["webgl"] = {api: {"available": False} for api in ("webgl", "webgl2")}
    with pytest.raises(ValueError):
        validate_observations(observed)


def test_changed_capability_is_not_accepted():
    observed = observation(minimized=True)
    observed["document"]["webgpu"]["limits"]["maxBufferSize"] += 1
    with pytest.raises(ValueError):
        validate_observations(observed, minimized=True, baseline=observation())


def test_gpu_cli_preserves_existing_evidence(tmp_path, monkeypatch):
    from scripts import verify_native_gpu as gpu

    report = tmp_path / "existing.json"
    report.write_text("existing evidence", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(tmp_path / "chrome.exe"),
                                     "--work-dir", str(tmp_path / "owned"), "--report", str(report)])
    with pytest.raises(SystemExit) as failure:
        gpu.main()
    assert failure.value.code == 2
    assert report.read_text(encoding="utf-8") == "existing evidence"


def test_gpu_cli_records_failure_without_admission(tmp_path, monkeypatch):
    from scripts import verify_native_gpu as gpu

    report = tmp_path / "failed.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(tmp_path / "missing.exe"),
                                     "--work-dir", str(tmp_path / "owned"), "--report", str(report)])
    assert gpu.main() == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["passed"] is False and evidence["privacy_admitted"] is False
    assert evidence["error"] and not evidence["checks"]
