import asyncio
from copy import deepcopy

import pytest

from app.core.native import canvas_fidelity
from scripts import native_canvas_formats, native_font_contexts, native_font_rendering


def observation(scope):
    return {
        "start": {"phase": "parser", "readyState": "loading", "requestsAtStart": 0}
        if scope in {"document", "iframe"} else
        {"phase": "worker-global", "readyState": None, "requestsAtStart": 0},
        "text": {"rows": [{"font": font, "opaque": opaque, "mime": "image/png", "pngBytes": 512,
                           "inkPixels": 256, "metrics": {name: 20 for name in native_font_rendering.METRICS},
                           "hashes": {name: "a" * 64 for name in native_font_rendering.HASHES}}
                          for font in native_font_rendering.FONTS for opaque in (True, False)]},
        "fidelity": {"width": canvas_fidelity.WIDTH, "height": canvas_fidelity.HEIGHT,
                     "rows": [{"name": name, **{operation: {"changedChannels": 0, "changedPixels": 0,
                                                         "alphaChanges": 0, "maximumError": 0}
                                               for operation in ("input", "repeat", "single", "export", "rewrite")}}
                              for name in canvas_fidelity.CASES]},
        "formats": {"rows": [{"colorSpace": colour, "pixelFormat": storage, "contextColorSpace": colour,
                              "contextColorType": "float16" if storage == "rgba-float16" else "unorm8",
                              "read": {"status": "ok", "colorSpace": colour, "pixelFormat": storage,
                                       "dataType": "Float16Array" if storage == "rgba-float16" else "Uint8ClampedArray",
                                       "length": 1024, "finite": True},
                              "export": {"status": "ok", "mime": "image/png", "bytes": 128}}
                             for colour, storage in native_canvas_formats.CASES]},
    }


@pytest.mark.parametrize("scope", native_font_contexts.SCOPES)
def test_scope_requires_complete_first_script_measurement(scope):
    native_font_contexts.validate_scope(scope, observation(scope))


@pytest.mark.parametrize("change", [{"phase": "late"}, {"readyState": "complete"},
                                    {"requestsAtStart": 1}, {"requestsAtStart": False}])
def test_late_or_ambiguous_start_rejects(change):
    value = observation("document")
    value["start"].update(change)
    with pytest.raises(ValueError, match="first script"):
        native_font_contexts.validate_scope("document", value)


@pytest.mark.parametrize("section", ["text", "fidelity", "formats"])
def test_missing_measurement_rejects(section):
    value = observation("document")
    value[section]["rows"].pop()
    with pytest.raises(ValueError):
        native_font_contexts.validate_scope("document", value)


@pytest.mark.parametrize("kind", ["dedicated", "shared", "service"])
def test_worker_probe_begins_before_message_handler(kind):
    source = native_font_contexts.worker_source(kind).decode("utf-8")
    assert source.index("const fontProbe") < source.index("requests++")
    assert "requestsAtStart: requests" in source


def test_unknown_worker_kind_rejects():
    with pytest.raises(ValueError):
        native_font_contexts.worker_source("other")


class Frame:
    async def evaluate(self, code):
        assert code == "window.fontProbe"
        return observation("iframe")


class Page:
    def __init__(self):
        self.workers = []

    async def goto(self, url, **kwargs):
        assert url == "http://127.0.0.1:1234/font-probe"

    async def evaluate(self, code, argument=None):
        if code == "window.fontProbe":
            return observation("document")
        if argument is not None:
            scope = argument["kind"] + "-" + argument["type"]
            self.workers.append(scope)
            return observation(scope)

    def frame(self, *, name):
        assert name == "font-child"
        return Frame()


def test_collector_retains_all_eight_scopes():
    page = Page()
    result = asyncio.run(native_font_contexts.collect(page, "http://127.0.0.1:1234"))
    assert tuple(result) == native_font_contexts.SCOPES
    assert page.workers == list(native_font_contexts.SCOPES[2:])


def test_missing_owned_iframe_rejects():
    page = Page()
    page.frame = lambda **kwargs: None
    with pytest.raises(ValueError, match="iframe"):
        asyncio.run(native_font_contexts.collect(page, "http://127.0.0.1:1234"))


def test_format_errors_are_retained_not_hidden_by_schema_validation():
    value = deepcopy(observation("document"))
    value["formats"]["rows"][1]["read"] = {"status": "error", "name": "NotReadableError"}
    native_font_contexts.validate_scope("document", value)
    assert native_canvas_formats.compare_control(observation("document")["formats"], value["formats"])
