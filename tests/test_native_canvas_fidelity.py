from copy import deepcopy

import pytest

from scripts import native_canvas_fidelity as fidelity
from app.core.native.diagnostics import audit_observed_canvas, compare_observed, OBSERVE
from app.core.native.configuration import NativeConfiguration


def measurement():
    zero = {"changedChannels": 0, "changedPixels": 0, "alphaChanges": 0, "maximumError": 0}
    return {"width": fidelity.WIDTH, "height": fidelity.HEIGHT,
            "rows": [{"name": name, **{key: deepcopy(zero) for key in
                      ("input", "repeat", "single", "export", "rewrite")}} for name in fidelity.CASES]}


def test_matching_control_is_not_anti_bot_acceptance():
    result = fidelity.compare_control(measurement(), measurement())
    assert result["matches_control"] is True
    assert result["differences"] == []
    assert "do not prove" in result["scope"]


def test_actual_pixel_mutation_is_retained():
    current = measurement()
    current["rows"][0]["input"] = {
        "changedChannels": 900, "changedPixels": 600, "alphaChanges": 0, "maximumError": 1}
    result = fidelity.compare_control(measurement(), current)
    assert result["matches_control"] is False
    assert result["differences"] == [{"case": "opaque-palette", "operation": "input",
                                      "control": measurement()["rows"][0]["input"],
                                      "candidate": current["rows"][0]["input"]}]


@pytest.mark.parametrize("operation", ["input", "repeat", "single", "export", "rewrite"])
@pytest.mark.parametrize("metrics", [
    {"changedChannels": True, "changedPixels": 1, "alphaChanges": 0, "maximumError": 1},
    {"changedChannels": 1, "changedPixels": 0, "alphaChanges": 0, "maximumError": 1},
    {"changedChannels": 1, "changedPixels": 1, "alphaChanges": 2, "maximumError": 1},
    {"changedChannels": 1, "changedPixels": 1, "alphaChanges": 0, "maximumError": 0},
    {"changedChannels": 1, "changedPixels": 1, "alphaChanges": 0, "maximumError": 256},
])
def test_invalid_metrics_reject(operation, metrics):
    current = measurement()
    current["rows"][0][operation] = metrics
    with pytest.raises(ValueError, match="Invalid Canvas fidelity"):
        fidelity.validate_measurement(current)


def test_single_pixel_cannot_report_multiple_pixels():
    current = measurement()
    current["rows"][0]["single"] = {
        "changedChannels": 2, "changedPixels": 2, "alphaChanges": 0, "maximumError": 1}
    with pytest.raises(ValueError):
        fidelity.validate_measurement(current)


def test_missing_case_rejects():
    current = measurement()
    current["rows"].pop()
    with pytest.raises(ValueError):
        fidelity.validate_measurement(current)


def test_product_probe_contains_shared_measurement_in_worker_function():
    assert "__GLINT_CANVAS_FIDELITY__" not in OBSERVE
    assert fidelity.READ in OBSERVE
    assert "canvasValues.toString()" in OBSERVE


def test_canvas_audit_preserves_stock_transparent_rounding():
    current = measurement()
    current["rows"][2]["input"] = {
        "changedChannels": 1344, "changedPixels": 768, "alphaChanges": 0, "maximumError": 1}
    assert audit_observed_canvas({"document": {"canvas": {"available": True, "fidelity": current}}}) == []


def test_canvas_audit_reports_explicit_opaque_pixel_mutation():
    current = measurement()
    current["rows"][0]["input"] = {
        "changedChannels": 1056, "changedPixels": 720, "alphaChanges": 0, "maximumError": 1}
    issues = audit_observed_canvas({"worker": {"canvas": {"available": True, "fidelity": current}}})
    assert issues == ["Worker Canvas opaque-palette changes explicitly supplied opaque pixels"]


@pytest.mark.parametrize("operation", ["repeat", "single", "export", "rewrite"])
def test_canvas_audit_reports_inconsistent_read(operation):
    current = measurement()
    current["rows"][0][operation] = {
        "changedChannels": 1, "changedPixels": 1, "alphaChanges": 0, "maximumError": 1}
    issues = audit_observed_canvas({"document": {"canvas": {"available": True, "fidelity": current}}})
    assert issues == [f"Document Canvas opaque-palette {operation} disagrees with its first read"]


@pytest.mark.parametrize("canvas", [None, [], {"available": 1}, {"available": True},
                                     {"available": True, "fidelity": {}}, {"available": False}])
def test_canvas_audit_rejects_unobserved_or_invalid_measurement(canvas):
    assert len(audit_observed_canvas({"document": {"canvas": canvas}})) == 1


def test_canvas_comparison_does_not_crash_on_malformed_rows():
    configuration = NativeConfiguration()
    values = {"width": configuration.width, "height": configuration.height,
              "dpr": configuration.device_scale_factor, "language": configuration.locale,
              "timezone": configuration.timezone, "canvas": None}
    issues = compare_observed(configuration, {"document": values, "worker": values})
    assert issues == ["Canvas observations could not be compared"]
