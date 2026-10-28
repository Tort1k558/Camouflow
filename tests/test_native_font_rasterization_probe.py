from copy import deepcopy

import pytest

from scripts import native_font_rendering as rendering


def measurement():
    return {"rows": [{"font": font, "opaque": opaque, "mime": "image/png", "pngBytes": 512,
                      "inkPixels": 256, "metrics": {name: 20 for name in rendering.METRICS},
                      "hashes": {name: "a" * 64 for name in rendering.HASHES}}
                     for font in rendering.FONTS for opaque in (True, False)]}


def test_unchanged_control_has_no_observed_differences():
    assert rendering.compare_control(measurement(), measurement()) == []
    assert rendering.consistency_observations(measurement()) == []


def test_changed_pixels_are_observations_not_acceptance():
    candidate = measurement()
    candidate["rows"][0]["hashes"]["pixels"] = "b" * 64
    assert rendering.compare_control(measurement(), candidate) == [
        {"font": rendering.FONTS[0], "opaque": True, "fields": ["hashes"]}]
    assert len(rendering.consistency_observations(candidate)) == 3


def test_png_byte_length_is_not_rendering_acceptance():
    candidate = measurement()
    candidate["rows"][0]["pngBytes"] += 1
    assert rendering.compare_control(measurement(), candidate) == []


@pytest.mark.parametrize("mode", ["native", "grayscale", "gamma-1400", "contrast-500"])
@pytest.mark.parametrize("policy", [{"text_tuning": "gamma-2200"}, {"font_rasterization": "grayscale"}])
def test_research_configuration_never_overrides_explicit_profile_rendering(mode, policy):
    from scripts.verify_native_font_rendering import RenderingConfiguration
    from app.core.native.privacy import NativePrivacyPolicy

    requested = NativePrivacyPolicy.from_dict(policy)
    with pytest.raises(ValueError, match="must not override"):
        RenderingConfiguration(rasterization=mode, privacy_policy=requested).validate()
    RenderingConfiguration(rasterization="off", privacy_policy=requested).validate()


@pytest.mark.parametrize("field,value", [("opaque", 1), ("inkPixels", 0), ("inkPixels", True),
                                        ("pngBytes", 0), ("font", "fake"), ("mime", "image/jpeg")])
def test_invalid_observation_rejects(field, value):
    candidate = measurement()
    candidate["rows"][0][field] = value
    with pytest.raises(ValueError):
        rendering.validate_measurement(candidate)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "20", -1025])
def test_invalid_metrics_reject(value):
    candidate = measurement()
    candidate["rows"][0]["metrics"]["width"] = value
    with pytest.raises(ValueError):
        rendering.validate_measurement(candidate)


@pytest.mark.parametrize("mutation", ["missing-case", "reordered", "missing-metric", "bad-hash"])
def test_incomplete_observations_reject(mutation):
    candidate = deepcopy(measurement())
    if mutation == "missing-case":
        candidate["rows"].pop()
    elif mutation == "reordered":
        candidate["rows"].reverse()
    elif mutation == "missing-metric":
        candidate["rows"][0]["metrics"].pop("width")
    else:
        candidate["rows"][0]["hashes"]["pixels"] = "not-a-digest"
    with pytest.raises(ValueError):
        rendering.validate_measurement(candidate)
