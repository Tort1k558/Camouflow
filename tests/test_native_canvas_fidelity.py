from copy import deepcopy

import pytest

from scripts import native_canvas_fidelity as fidelity


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
