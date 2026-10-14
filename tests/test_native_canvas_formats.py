from copy import deepcopy

import pytest

from scripts import native_canvas_formats as formats


def measurement():
    return {"rows": [{"colorSpace": colour, "pixelFormat": storage, "contextColorSpace": colour,
                      "contextColorType": "float16" if storage == "rgba-float16" else "unorm8",
                      "read": {"status": "ok", "colorSpace": colour, "pixelFormat": storage,
                               "dataType": "Uint8ClampedArray" if storage == "rgba-unorm8" else "Float16Array",
                               "length": 1024, "finite": True},
                      "export": {"status": "ok", "mime": "image/png", "bytes": 128}}
                     for colour, storage in formats.CASES]}


def test_supported_formats_match_control():
    assert formats.compare_control(measurement(), measurement()) == []


def test_png_size_difference_is_not_api_failure():
    candidate = measurement()
    candidate["rows"][0]["export"]["bytes"] = 256
    assert formats.compare_control(measurement(), candidate) == []


@pytest.mark.parametrize("operation", ["read", "export"])
def test_candidate_rejection_is_not_compatibility_pass(operation):
    candidate = measurement()
    candidate["rows"][1][operation] = {"status": "error", "name": "NotReadableError"}
    differences = formats.compare_control(measurement(), candidate)
    assert len(differences) == 1
    assert differences[0]["operation"] == operation
    assert differences[0]["candidate"]["name"] == "NotReadableError"


@pytest.mark.parametrize("key,value", [("colorSpace", "srgb"), ("pixelFormat", "rgba-unorm8"),
                                       ("dataType", "Uint8ClampedArray"), ("length", True),
                                       ("finite", 1), ("finite", False)])
def test_storage_cannot_silently_fall_back(key, value):
    candidate = measurement()
    candidate["rows"][3]["read"][key] = value
    with pytest.raises(ValueError):
        formats.validate_measurement(candidate)


def test_missing_case_rejects():
    candidate = measurement()
    candidate["rows"].pop()
    with pytest.raises(ValueError):
        formats.validate_measurement(candidate)


def test_context_colour_space_cannot_silently_fall_back():
    candidate = deepcopy(measurement())
    candidate["rows"][1]["contextColorSpace"] = "srgb"
    with pytest.raises(ValueError):
        formats.validate_measurement(candidate)


def test_float16_context_cannot_silently_fall_back():
    candidate = measurement()
    candidate["rows"][2]["contextColorType"] = "unorm8"
    with pytest.raises(ValueError):
        formats.validate_measurement(candidate)


def test_worker_probe_is_bounded_and_releases_resources():
    assert "30000" in formats.WORKER_READ
    assert "worker.onmessageerror" in formats.WORKER_READ
    assert "finally { clearTimeout(timer); worker?.terminate(); URL.revokeObjectURL(url); }" in formats.WORKER_READ
