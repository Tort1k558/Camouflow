import asyncio
from copy import deepcopy
import hashlib
import json

import pytest

from app.core.native import canvas_fidelity
from scripts import native_canvas_formats, native_canvas_hdr, native_font_contexts, native_font_rendering
from scripts import verify_native_font_rendering as verifier


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
        "hdr": {"rows": [{"colorSpace": colour, "alpha": alpha, "contextColorSpace": colour,
                          "contextColorType": "float16", "input": native_canvas_hdr.input_values(alpha),
                          **{operation: {"status": "ok", "colorSpace": colour, "pixelFormat": "rgba-float16",
                                         "dataType": "Float16Array", "values": native_canvas_hdr.input_values(alpha)}
                             for operation in ("read", "repeat")},
                          "png": {"status": "ok", "mime": "image/png", "bytes": 128,
                                  "width": native_canvas_hdr.WIDTH, "height": native_canvas_hdr.HEIGHT,
                                  "rgba8Sha256": "a" * 64, "pngSha256": "b" * 64}}
                         for colour, alpha in native_canvas_hdr.CASES]},
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


@pytest.mark.parametrize("section", ["text", "fidelity", "formats", "hdr"])
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


def mode_runs():
    result = {mode: [{scope: observation(scope) for scope in native_font_contexts.SCOPES}
                     for _ in range(2)] for mode in verifier.MODES}
    for scopes in result["aliased"]:
        for value in scopes.values():
            for row in value["text"]["rows"]:
                row["hashes"] = {name: "b" * 64 for name in native_font_rendering.HASHES}
    return result


def tuning_runs():
    result = {mode: [{scope: observation(scope) for scope in native_font_contexts.SCOPES}
                     for _ in range(2)] for mode in verifier.TEXT_TUNING_CASES}
    for mode, rounds in result.items():
        digest = hashlib.sha256(mode.encode()).hexdigest()
        for scopes in rounds:
            for value in scopes.values():
                for row in value["text"]["rows"]:
                    row["hashes"] = {name: digest for name in native_font_rendering.HASHES}
    return result


@pytest.mark.parametrize("failure", [None, "gamma", "contrast-worker", "raw", "format", "hdr",
                                   "restart", "unstable-export", "missing-case", "missing-scope"])
def test_text_tuning_requires_isolated_effects_and_full_compatible_factorial_matrix(failure):
    runs = tuning_runs()
    mode = "gamma-2200-contrast-500"
    if failure == "gamma":
        runs["gamma-2200"] = deepcopy(runs["gamma-1400"])
    elif failure == "contrast-worker":
        for phase in range(2):
            runs["contrast-500"][phase]["shared-module"] = deepcopy(runs["contrast-300"][phase]["shared-module"])
    elif failure == "raw":
        for scopes in runs[mode]:
            scopes["document"]["fidelity"]["rows"][0]["input"] = {
                "changedChannels": 1, "changedPixels": 1, "alphaChanges": 0, "maximumError": 1}
    elif failure in {"format", "hdr"}:
        section = "formats" if failure == "format" else "hdr"
        for scopes in runs[mode]:
            scopes["document"][section]["rows"][0]["read"] = {"status": "error", "name": "NotReadableError"}
    elif failure == "restart":
        runs[mode][1]["service-classic"]["text"]["rows"][0]["metrics"]["width"] += 1
    elif failure == "unstable-export":
        for scopes in runs[mode]:
            scopes["document"]["text"]["rows"][0]["hashes"]["pngRepeat"] = "c" * 64
    elif failure == "missing-case":
        del runs[mode]
    elif failure == "missing-scope":
        del runs[mode][0]["service-module"]
    if failure in {"missing-case", "missing-scope"}:
        with pytest.raises(ValueError):
            verifier.assess(runs, series="text-tuning")
        return
    result = verifier.assess(runs, series="text-tuning")
    assert result["passed"] is (failure is None)
    assert "aliased_grayscale_pixel_effect" not in result
    if failure == "gamma":
        assert not any(result["independent_parameter_effects"]["gamma"].values())
    elif failure == "contrast-worker":
        assert not result["independent_parameter_effects"]["contrast"]["shared-module"]
    elif failure is None:
        assert all(all(scopes.values()) for scopes in result["independent_parameter_effects"].values())


@pytest.mark.parametrize("mode,flags", verifier.TEXT_TUNING_CASES.items())
def test_upstream_text_tuning_uses_only_explicit_existing_flags(mode, flags):
    arguments = verifier.RenderingConfiguration(rasterization=mode).launch_arguments()
    assert arguments == ["--lang=en-US", "--accept-lang=en-US", *flags]
    assert not any("readback" in flag or "rasterization=" in flag for flag in arguments)


@pytest.mark.parametrize("series", ["", "unknown", None, True])
def test_unknown_rendering_series_has_no_fallback(series):
    with pytest.raises(ValueError, match="Unknown rendering"):
        verifier.assess({}, series=series)


def test_all_modes_require_stable_compatible_observations_and_pixel_effect():
    result = verifier.assess(mode_runs())
    assert result["passed"] and result["aliased_grayscale_pixel_effect"]
    assert result["controls"]["aliased"]["document"]["text"]
    assert not result["controls"]["native"]["document"]["text"]


def test_effect_in_some_scopes_does_not_hide_ignored_worker_policy():
    runs = mode_runs()
    for index in range(2):
        runs["aliased"][index]["service-module"]["text"] = deepcopy(runs["grayscale"][index]["service-module"]["text"])
    result = verifier.assess(runs)
    assert not result["passed"]
    assert result["pixel_effects_by_scope"]["document"]
    assert not result["pixel_effects_by_scope"]["service-module"]


@pytest.mark.parametrize("mutation", ["restart", "native-change", "raw-change", "format-error", "unstable-export", "no-effect"])
def test_incompatible_or_ineffective_mode_is_not_a_pass(mutation):
    runs = mode_runs()
    if mutation == "restart":
        runs["aliased"][1]["document"]["text"]["rows"][0]["metrics"]["width"] += 1
    elif mutation == "native-change":
        for scopes in runs["native"]:
            scopes["document"]["text"]["rows"][0]["metrics"]["width"] += 1
    elif mutation == "raw-change":
        for scopes in runs["aliased"]:
            scopes["document"]["fidelity"]["rows"][0]["input"] = {
                "changedChannels": 1, "changedPixels": 1, "alphaChanges": 0, "maximumError": 1}
    elif mutation == "format-error":
        for scopes in runs["aliased"]:
            scopes["document"]["formats"]["rows"][1]["read"] = {"status": "error", "name": "NotReadableError"}
    elif mutation == "unstable-export":
        for scopes in runs["aliased"]:
            scopes["document"]["text"]["rows"][0]["hashes"]["pngRepeat"] = "c" * 64
    else:
        runs["aliased"] = deepcopy(runs["grayscale"])
    assert not verifier.assess(runs)["passed"]


@pytest.mark.parametrize("missing", ["mode", "restart", "scope"])
def test_incomplete_mode_matrix_rejects(missing):
    runs = mode_runs()
    if missing == "mode":
        runs.pop("native")
    elif missing == "restart":
        runs["native"].pop()
    else:
        runs["native"][0].pop("service-module")
    with pytest.raises(ValueError):
        verifier.assess(runs)


def test_unstable_control_does_not_make_equally_broken_modes_pass():
    runs = mode_runs()
    for rounds in runs.values():
        for scopes in rounds:
            scopes["document"]["text"]["rows"][0]["hashes"]["pngRepeat"] = "c" * 64
    result = verifier.assess(runs)
    assert not result["passed"]
    assert any(item["reason"] == "repeated-read-or-export-is-unstable" for item in result["failures"])


@pytest.mark.parametrize("section", ["formats", "hdr"])
def test_equally_unsupported_control_and_modes_are_not_compatible_pass(section):
    runs = mode_runs()
    for rounds in runs.values():
        for scopes in rounds:
            scopes["document"][section]["rows"][0]["read"] = {"status": "error", "name": "NotReadableError"}
    assert not verifier.assess(runs)["passed"]


def test_changed_hdr_values_fail_even_with_stable_restarts():
    runs = mode_runs()
    for scopes in runs["aliased"]:
        for operation in ("read", "repeat"):
            scopes["document"]["hdr"]["rows"][0][operation]["values"][2] = 1
    result = verifier.assess(runs)
    assert not result["passed"]
    assert result["controls"]["aliased"]["document"]["hdr"]


@pytest.mark.parametrize("mode", verifier.MODES)
def test_mode_arguments_are_explicit_without_readback_flags(mode):
    args = verifier.RenderingConfiguration(rasterization=mode).launch_arguments()
    expected = "--glint-windows-font-rasterization=" + mode
    assert (expected in args) is (mode != "off")
    assert all("readback" not in argument.lower() for argument in args)


@pytest.mark.parametrize("mode", ["Native", "rgb", "", None, True])
def test_unknown_modes_have_no_fallback(mode):
    with pytest.raises(ValueError):
        verifier.RenderingConfiguration(rasterization=mode).context_options()


@pytest.mark.parametrize("failure", [None, "restart", "one-scope-no-effect", "missing-mode"])
def test_admitted_rendering_requires_restart_stability_and_effect_in_every_scope(failure):
    from scripts.verify_native_admitted_policy import validate_rendering

    runs = mode_runs()
    measured = {"native": deepcopy(runs["native"]), "grayscale": deepcopy(runs["aliased"])}
    if failure == "restart":
        measured["native"][1]["document"]["text"]["rows"][0]["hashes"]["pixels"] = "f" * 64
    elif failure == "one-scope-no-effect":
        for index in range(2):
            measured["grayscale"][index]["service-module"] = deepcopy(measured["native"][index]["service-module"])
    elif failure == "missing-mode":
        del measured["native"]
    if failure is None:
        validate_rendering(measured)
    else:
        with pytest.raises(ValueError):
            validate_rendering(measured)


@pytest.mark.parametrize("failure", [None, "measurement", "core-change", "pack-change", "pack-removed", "source-change", "policy-change", "receipt-change", "screenshot-change", "screenshot-removed", "visual-restart", "cleanup", "bind"])
@pytest.mark.parametrize("series", ["rasterization", "text-tuning"])
@pytest.mark.parametrize("candidate_mode", [False, True])
def test_mode_verifier_preserves_failure_and_guards_inputs(tmp_path, monkeypatch, failure, series, candidate_mode):
    public = tmp_path / "public"
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    executable = runtime_dir / "chrome.exe"
    executable.write_bytes(b"owned executable")
    pack = runtime_dir / "resources.pak"
    pack.write_bytes(b"owned resources")
    patch = public / "native/patches/0062-native-windows-font-rasterization.patch"
    patch.parent.mkdir(parents=True)
    patch.write_bytes(b"owned policy")
    for relative in ("scripts/native_font_contexts.py", "scripts/native_font_rendering.py",
                     "scripts/native_canvas_formats.py", "scripts/native_canvas_hdr.py", "scripts/native_font_visuals.py",
                     "app/core/native/canvas_fidelity.py", "app/core/native/configuration.py",
                     "app/core/native/privacy.py", "app/core/native/runtime.py", "app/core/native/identity.py"):
        path = public / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned probe")

    def core(path):
        return {"chrome.exe": hashlib.sha256(path.read_bytes()).hexdigest(),
                "chrome.dll": "d" * 64, "chrome_elf.dll": "e" * 64}

    candidate = verifier.native_build.load_candidate("upstream-156") if candidate_mode else None
    binding = {} if candidate is None else {
        "candidate_manifest_sha256": candidate["manifest_sha256"],
        "chromium_revision": candidate["lock"]["chromium_revision"],
        "depot_tools_revision": candidate["lock"]["depot_tools_revision"],
    }
    patches = ([{"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}]
               if candidate is None else candidate_receipt_patches(candidate))
    (runtime_dir / "camouflow-build.json").write_text(json.dumps({
        "platform": "win32", "binary": "chrome.exe", "runtime_core_sha256_measured": core(executable),
        "patches": patches, **binding,
    }), encoding="utf-8")
    monkeypatch.setattr(verifier, "ROOT", public)
    monkeypatch.setattr(verifier, "PATCH", patch)
    monkeypatch.setattr(verifier.sys, "platform", "win32")
    monkeypatch.setattr(verifier, "require_idle_builder", lambda: None)
    monkeypatch.setattr(verifier, "measure_runtime_core", core)
    monkeypatch.setattr(verifier, "measure_branding_resources",
                        lambda path: {"resources.pak": hashlib.sha256(pack.read_bytes()).hexdigest()})
    runs = mode_runs() if series == "rasterization" else tuning_runs()
    modes = verifier.series_modes(series)
    starts = []

    class Page:
        def __init__(self, mode):
            self.mode = mode

        async def screenshot(self, *, path):
            from pathlib import Path
            Path(path).write_bytes(b"owned screenshot")

    class Runtime:
        def __init__(self, profile, path, configuration):
            self.mode = configuration.rasterization
            self.has_resources = False

        async def start(self, **kwargs):
            self.has_resources = True
            starts.append(self.mode)
            return self

        async def new_page(self):
            return Page(self.mode)

        async def close(self):
            if failure == "cleanup":
                raise RuntimeError("owned cleanup failure")
            self.has_resources = False

    async def collect(page, url):
        mode = page.mode
        if failure == "measurement" and mode == "off":
            raise ValueError("owned measurement failure")
        if mode == modes[-1]:
            if failure == "core-change":
                executable.write_bytes(b"changed executable")
            elif failure == "pack-change":
                pack.write_bytes(b"changed resources")
            elif failure == "pack-removed":
                pack.unlink(missing_ok=True)
            elif failure == "source-change":
                (public / "scripts/native_font_contexts.py").write_bytes(b"changed probe")
            elif failure == "policy-change":
                (public / "app/core/native/privacy.py").write_bytes(b"changed policy")
            elif failure == "receipt-change":
                (runtime_dir / "camouflow-build.json").write_bytes(b"changed receipt")
            elif failure == "screenshot-change":
                (tmp_path / "evidence/font-off-0.png").write_bytes(b"changed screenshot")
            elif failure == "screenshot-removed":
                (tmp_path / "evidence/font-off-0.png").unlink(missing_ok=True)
        return deepcopy(runs[mode][0])

    async def visual_collect(page):
        value = {"rows": [{"font": font, "domWidth": 160, "domHeight": 24, "svgWidth": 160,
                           "canvasWidth": 160, "canvasPixelSha256": "a" * 64}
                          for font in verifier.native_font_visuals.FONTS]}
        visual_mode = "native" if series == "rasterization" else "gamma-1400"
        if failure == "visual-restart" and page.mode == visual_mode and starts.count(visual_mode) == 2:
            value["rows"][0]["domWidth"] += 1
        return value

    class Server:
        server_address = ("127.0.0.1", 1234)

        def __init__(self, *args):
            if failure == "bind":
                raise OSError("owned bind failure")

        def serve_forever(self):
            pass

        def shutdown(self):
            pass

        def server_close(self):
            pass

    monkeypatch.setattr(verifier, "NativeRuntime", Runtime)
    monkeypatch.setattr(verifier.native_font_contexts, "collect", collect)
    monkeypatch.setattr(verifier.native_font_visuals, "collect", visual_collect)
    monkeypatch.setattr(verifier, "FixtureServer", Server)
    destination = tmp_path / "evidence"
    selector = None if candidate is None else candidate["name"]
    report = asyncio.run(verifier.verify(executable, destination, series=series, candidate_name=selector))
    assert report["passed"] is (failure is None)
    assert report["capability_admitted"] is False
    assert report["series"] == series
    if candidate_mode:
        assert report["candidate"] == selector and report["candidate_manifest_sha256"] == candidate["manifest_sha256"]
    else:
        assert "candidate" not in report
    assert json.loads((destination / "report.json").read_text(encoding="utf-8")) == report
    assert report["inputs_unchanged"] is (failure not in {
        "core-change", "pack-change", "pack-removed", "source-change", "policy-change", "receipt-change", "screenshot-change", "screenshot-removed"})
    if failure == "cleanup":
        assert starts == ["off"]
    elif failure != "bind":
        assert starts == [mode for mode in modes for _ in range(2)]
    with pytest.raises(ValueError, match="Fresh private evidence"):
        asyncio.run(verifier.verify(executable, destination, series=series, candidate_name=selector))


def candidate_receipt_patches(candidate):
    manifest = candidate["manifest"]
    return [{"name": row["file"], "sha256": row["sha256"],
             **({"repository": "v8", "revision": manifest["dependencies"]["v8"]["revision"]}
                if directory == "v8" else {})}
            for directory in (".", "v8") for row in manifest["patches"] if row.get("directory", ".") == directory]


@pytest.mark.parametrize("mutation", ["implicit", "revision", "manifest", "missing-patch", "duplicate", "order", "v8", "unknown"])
def test_rendering_candidate_rejects_wrong_or_incomplete_receipt_before_launch(tmp_path, monkeypatch, mutation):
    candidate = verifier.native_build.load_candidate("upstream-156")
    executable = tmp_path / "runtime" / "chrome.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"owned candidate")
    core = {"chrome.exe": "a" * 64, "chrome.dll": "b" * 64, "chrome_elf.dll": "c" * 64}
    record = {"platform": "win32", "binary": "chrome.exe", "runtime_core_sha256_measured": core,
              "candidate_manifest_sha256": candidate["manifest_sha256"],
              "chromium_revision": candidate["lock"]["chromium_revision"],
              "depot_tools_revision": candidate["lock"]["depot_tools_revision"],
              "patches": candidate_receipt_patches(candidate)}
    if mutation == "revision":
        record["chromium_revision"] = "f" * 40
    elif mutation == "manifest":
        record["candidate_manifest_sha256"] = "f" * 64
    elif mutation == "missing-patch":
        record["patches"].pop(0)
    elif mutation == "duplicate":
        record["patches"].append(dict(record["patches"][0]))
    elif mutation == "order":
        record["patches"][0], record["patches"][1] = record["patches"][1], record["patches"][0]
    elif mutation == "v8":
        record["patches"][-1]["revision"] = "f" * 40
    (executable.parent / "camouflow-build.json").write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(verifier.sys, "platform", "win32")
    monkeypatch.setattr(verifier, "require_idle_builder", lambda: None)
    monkeypatch.setattr(verifier, "measure_runtime_core", lambda path: core)
    monkeypatch.setattr(verifier, "NativeRuntime", lambda *args: pytest.fail("Invalid candidate reached launch"))
    monkeypatch.setattr(verifier, "PATCH", candidate["directory"] / "patches" / verifier.PATCH.name)
    selector = None if mutation == "implicit" else "unknown" if mutation == "unknown" else candidate["name"]
    expected = "explicit --candidate" if mutation == "implicit" else "Unknown Native" if mutation == "unknown" else "complete pinned"
    destination = tmp_path / "evidence"
    with pytest.raises(ValueError, match=expected):
        asyncio.run(verifier.verify(executable, destination, candidate_name=selector))
    assert not destination.exists()
