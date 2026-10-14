import asyncio

import pytest

from scripts import native_font_visuals as visuals


def measurement():
    return {"rows": [{"font": font, "domWidth": 160.25, "domHeight": 24, "svgWidth": 160.25,
                      "canvasWidth": 160.25, "canvasPixelSha256": "a" * 64} for font in visuals.FONTS]}


def test_visual_scene_contains_actual_dom_svg_and_canvas():
    assert visuals.HTML.count('<section class="row"') == 3
    assert visuals.HTML.count("<canvas ") == 3
    assert visuals.HTML.count("<svg ") == 3
    visuals.validate_measurement(measurement())


@pytest.mark.parametrize("key,value", [("domWidth", 0), ("domHeight", True), ("svgWidth", float("nan")),
                                      ("canvasWidth", float("inf")), ("canvasPixelSha256", "invalid"),
                                      ("font", "unknown")])
def test_invalid_visual_observations_reject(key, value):
    candidate = measurement()
    candidate["rows"][0][key] = value
    with pytest.raises(ValueError):
        visuals.validate_measurement(candidate)


def test_visual_collector_uses_owned_scene_and_keeps_measurements():
    class Page:
        async def set_content(self, source, **kwargs):
            assert source == visuals.HTML

        async def evaluate(self, code):
            assert code == visuals.READ
            return measurement()

    assert asyncio.run(visuals.collect(Page())) == measurement()
