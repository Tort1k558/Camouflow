from copy import deepcopy

import pytest

from scripts import native_canvas_hdr as hdr


def measurement():
    rows = []
    for colour, alpha in hdr.CASES:
        values = hdr.input_values(alpha)
        read = {"status": "ok", "colorSpace": colour, "pixelFormat": "rgba-float16",
                "dataType": "Float16Array", "values": values[:]}
        rows.append({"colorSpace": colour, "alpha": alpha, "contextColorSpace": colour,
                     "contextColorType": "float16", "input": values,
                     "read": read, "repeat": deepcopy(read),
                     "png": {"status": "ok", "mime": "image/png", "bytes": 128, "width": hdr.WIDTH,
                             "height": hdr.HEIGHT, "rgba8Sha256": "a" * 64, "pngSha256": "b" * 64}})
    return {"rows": rows}


def test_hdr_fixture_preserves_independent_known_inputs():
    value = measurement()
    hdr.validate_measurement(value)
    assert hdr.compare_control(value, deepcopy(value)) == []
    assert all(row["repeat_matches"] and row["rgb_above_one"] and row["rgb_below_zero"]
               for row in hdr.observations(value))
    assert all(row["changed_channels"] == 0 for row in hdr.observations(value))


def test_clipping_is_observed_not_assumed_to_be_correct_or_wrong():
    candidate = measurement()
    candidate["rows"][0]["read"]["values"][2] = 1
    observed = hdr.observations(candidate)[0]
    assert observed["changed_channels"] == 1 and observed["maximum_absolute_error"] == 1
    assert not observed["repeat_matches"]
    assert hdr.compare_control(measurement(), candidate)[0]["operation"] == "read"


def test_api_errors_are_retained_not_converted_to_success():
    candidate = measurement()
    candidate["rows"][1]["read"] = {"status": "error", "name": "NotReadableError"}
    assert hdr.observations(candidate)[1]["read_status"] == "error"
    assert hdr.compare_control(measurement(), candidate)


@pytest.mark.parametrize("field,value", [("contextColorType", "unorm8"), ("contextColorSpace", "display-p3"),
                                        ("colorSpace", "fake"), ("alpha", "fake")])
def test_context_cannot_silently_fall_back(field, value):
    candidate = measurement()
    candidate["rows"][0][field] = value
    with pytest.raises(ValueError):
        hdr.validate_measurement(candidate)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, 65505, "0.5"])
def test_invalid_typed_pixel_rejects(value):
    candidate = measurement()
    candidate["rows"][0]["read"]["values"][0] = value
    with pytest.raises(ValueError):
        hdr.validate_measurement(candidate)


def test_alpha_outside_unit_interval_rejects():
    candidate = measurement()
    candidate["rows"][0]["read"]["values"][3] = 2
    with pytest.raises(ValueError):
        hdr.validate_measurement(candidate)


@pytest.mark.parametrize("change", ["missing-case", "short-read", "wrong-input", "fake-hash", "boolean-width"])
def test_incomplete_or_forged_observation_rejects(change):
    candidate = measurement()
    if change == "missing-case":
        candidate["rows"].pop()
    elif change == "short-read":
        candidate["rows"][0]["read"]["values"].pop()
    elif change == "wrong-input":
        candidate["rows"][0]["input"][0] = 2
    elif change == "fake-hash":
        candidate["rows"][0]["png"]["pngSha256"] = "invalid"
    else:
        candidate["rows"][0]["png"]["width"] = True
    with pytest.raises(ValueError):
        hdr.validate_measurement(candidate)
