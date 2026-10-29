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


@pytest.mark.parametrize("mode", ["off", "gamma-1400", "grayscale"])
def test_developer_rendering_preserves_base_policy_admission_contract(monkeypatch, mode):
    admission = object()
    observed = []
    def base_arguments(self, *, admission=None):
        observed.append(admission)
        return ["--owned-reviewed-base"]
    monkeypatch.setattr(verifier.NativeConfiguration, "launch_arguments", base_arguments)
    arguments = verifier.RenderingConfiguration(rasterization=mode).launch_arguments(admission=admission)
    assert observed == [admission] and arguments[0] == "--owned-reviewed-base"


def test_developer_rendering_does_not_bypass_required_runtime_admission():
    from app.core.native.privacy import NativePrivacyPolicy

    configuration = verifier.RenderingConfiguration(privacy_policy=NativePrivacyPolicy(cpu_limit=2), rasterization="gamma-1400")
    with pytest.raises(ValueError, match="verified"):
        configuration.launch_arguments(admission=object())


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
@pytest.mark.parametrize("workload_mode", [False, True])
def test_mode_verifier_preserves_failure_and_guards_inputs(tmp_path, monkeypatch, failure, series, candidate_mode, workload_mode,
                                                         profile_concurrency=1):
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
                     "scripts/native_font_workloads.py",
                     "scripts/verify_native_runtime.py",
                     "app/core/native/canvas_fidelity.py", "app/core/native/configuration.py",
                     "app/core/native/privacy.py", "app/core/native/runtime.py", "app/core/native/identity.py"):
        path = public / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned probe")
    font_file = tmp_path / "owned-font.ttf"
    font_file.write_bytes(b"\x00\x01\x00\x00" + b"owned font" * 16)

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
    monkeypatch.setattr(verifier, "require_idle_builder", lambda *args: None)
    monkeypatch.setattr(verifier, "measure_runtime_core", core)
    monkeypatch.setattr(verifier, "measure_branding_resources",
                        lambda path: {"resources.pak": hashlib.sha256(pack.read_bytes()).hexdigest()})
    runs = mode_runs() if series == "rasterization" else tuning_runs()
    modes = verifier.series_modes(series)
    starts = []
    closed = []
    storage = {}
    storage_deadlines = []
    wait_for = asyncio.wait_for
    async def bounded_storage(awaitable, *, timeout):
        if getattr(awaitable, "cr_code", None) and awaitable.cr_code.co_name == "evaluate":
            storage_deadlines.append(timeout)
            if failure == "storage-timeout":
                timeout = .001
        return await wait_for(awaitable, timeout=timeout)
    monkeypatch.setattr(verifier.asyncio, "wait_for", bounded_storage)

    class Page:
        def __init__(self, mode):
            self.mode = mode

        async def screenshot(self, *, path):
            from pathlib import Path
            Path(path).write_bytes(b"owned screenshot")

        async def goto(self, *args, **kwargs):
            pass

        async def evaluate(self, script, value):
            assert script == verifier.STORAGE
            if failure == "storage-timeout":
                await asyncio.sleep(60)
            key = "shared" if failure == "storage-share" else self.mode
            if value is not None:
                storage[key] = value
            marker = storage.get(key)
            return {"cookie": "" if marker is None else "owned=" + marker, "local": marker,
                    "indexed": marker, "cached": marker, "workers": 0 if marker is None else 1}

    class Runtime:
        def __init__(self, profile, path, configuration):
            self.mode = configuration.rasterization
            self.has_resources = False
            if failure == "storage-loss":
                storage.pop(self.mode, None)

        async def start(self, **kwargs):
            self.has_resources = True
            starts.append(self.mode)
            if failure == "start" and self.mode == "off":
                raise RuntimeError("owned startup failure")
            return self

        async def new_page(self):
            return Page(self.mode)

        async def close(self):
            closed.append(self.mode)
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
            elif failure == "workload-font-change":
                font_file.write_bytes(b"changed font")
            elif failure == "workload-source-change":
                (public / "scripts/native_font_workloads.py").write_bytes(b"changed workload helper")
            elif failure == "workload-artifact-change":
                (tmp_path / "evidence/workload-off-0/note.txt").write_bytes(b"changed note")
        return deepcopy(runs[mode][0])

    async def workload_collect(page, base_url, artifacts, font_sha256):
        if failure == "workload-measurement":
            raise ValueError("owned editing failure")
        value = workload_observation(font_sha256)
        if failure == "workload-semantic-change" and page.mode == modes[-1]:
            for name in ("domWidth", "svgWidth", "canvasWidth"):
                value["font"][name] += 1
        if failure == "storage-after-workload":
            storage[page.mode] = "changed-by-workload"
        elif failure == "storage-peer-late" and page.mode == modes[1]:
            storage[modes[0]] = "changed-by-peer"
        artifacts.mkdir()
        for name, data in {"note.txt": value["download"]["text"].encode("utf-8"),
                           "workspace.png": b"owned workload screenshot", "print.pdf": b"%PDF-" + b"x" * 4091}.items():
            (artifacts / name).write_bytes(data)
            value["artifacts"][name] = hashlib.sha256(data).hexdigest()
        return value

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
    monkeypatch.setattr(verifier.native_font_workloads, "collect", workload_collect)
    monkeypatch.setattr(verifier, "FixtureServer", Server)
    destination = tmp_path / "evidence"
    selector = None if candidate is None else candidate["name"]
    report = asyncio.run(verifier.verify(executable, destination, series=series, candidate_name=selector,
                                        workload_font=font_file if workload_mode else None,
                                        profile_concurrency=profile_concurrency))
    assert report["passed"] is (failure is None)
    assert report["capability_admitted"] is False
    assert report["series"] == series
    if candidate_mode:
        assert report["candidate"] == selector and report["candidate_manifest_sha256"] == candidate["manifest_sha256"]
    else:
        assert "candidate" not in report
    assert json.loads((destination / "report.json").read_text(encoding="utf-8")) == report
    assert report["inputs_unchanged"] is (failure not in {
        "core-change", "pack-change", "pack-removed", "source-change", "policy-change", "receipt-change", "screenshot-change", "screenshot-removed",
        "workload-font-change", "workload-source-change", "workload-artifact-change"})
    if failure == "cleanup":
        assert starts == list(modes[:profile_concurrency])
        assert closed == starts
    elif failure != "bind":
        assert starts == [mode for offset in range(0, len(modes), profile_concurrency) for _ in range(2)
                          for mode in modes[offset:offset + profile_concurrency]]
        assert sorted(closed) == sorted(starts)
    if failure == "storage-peer-late":
        assert any(error.get("round") == 0 and error.get("phase") == "storage"
                   and "peer changed" in error.get("error", "") for error in report["errors"])
    if failure is None:
        assert report["peak_live_profiles"] == profile_concurrency
        assert all(len(values) == 2 for values in report["profile_storage"].values())
        assert storage_deadlines and set(storage_deadlines) == {30}
    with pytest.raises(ValueError, match="Fresh private evidence"):
        asyncio.run(verifier.verify(executable, destination, series=series, candidate_name=selector))


@pytest.mark.parametrize("failure", ["workload-measurement", "workload-font-change", "workload-source-change",
                                     "workload-artifact-change", "workload-semantic-change"])
@pytest.mark.parametrize("series", ["rasterization", "text-tuning"])
@pytest.mark.parametrize("candidate_mode", [False, True])
def test_workload_verifier_guards_fail_without_weakening_native_checks(tmp_path, monkeypatch, failure, series, candidate_mode):
    test_mode_verifier_preserves_failure_and_guards_inputs(tmp_path, monkeypatch, failure, series, candidate_mode, True)


@pytest.mark.parametrize("failure", [None, "start", "measurement", "cleanup", "source-change", "screenshot-change",
                                     "workload-font-change", "workload-artifact-change", "storage-share", "storage-loss",
                                     "storage-after-workload", "storage-peer-late", "storage-timeout"])
def test_concurrent_rendering_profiles_preserve_guards_and_close_every_owner(tmp_path, monkeypatch, failure):
    test_mode_verifier_preserves_failure_and_guards_inputs(tmp_path, monkeypatch, failure, "text-tuning", True, True, 2)


@pytest.mark.parametrize("concurrency", [0, 3, True, 1.0, None])
def test_rendering_concurrency_rejects_before_builder_access(tmp_path, monkeypatch, concurrency):
    monkeypatch.setattr(verifier.sys, "platform", "win32")
    monkeypatch.setattr(verifier, "require_idle_builder", lambda *args: pytest.fail("Invalid concurrency reached the builder"))
    with pytest.raises(ValueError, match="explicitly 1 or 2"):
        asyncio.run(verifier.verify(tmp_path / "chrome.exe", tmp_path / "output", profile_concurrency=concurrency))
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("modes", [(), ("off", "off"), ("unknown",), ["off"], (True,)])
def test_profile_collector_rejects_ambiguous_modes_before_start(tmp_path, monkeypatch, modes):
    monkeypatch.setattr(verifier, "NativeRuntime", lambda *args: pytest.fail("Ambiguous profile modes reached runtime"))
    with pytest.raises(ValueError, match="explicit, supported and unique"):
        asyncio.run(verifier.collect_profiles(tmp_path / "chrome.exe", tmp_path, "http://127.0.0.1:1234", modes, {}))


def workload_observation(font_sha256="b" * 64):
    from scripts import native_font_workloads as workloads

    text = workloads.NOTE + "\n" + workloads.APPROVED
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"note": {"value": workloads.NOTE, "undo": workloads.NOTE,
                     "events": ["deleteContentBackward", "historyUndo", "insertText"], "trusted": True},
            "editor": {"value": workloads.APPROVED, "undo": workloads.DRAFT,
                       "events": ["historyRedo", "historyUndo", "insertText"], "trusted": True},
            "selection": {"text": "Glint", "noteRange": [0, len(workloads.NOTE)]},
            "font": {"loaded": True, "domWidth": 120, "svgWidth": 120, "canvasWidth": 120, "fallbackWidth": 72,
                     "pixels": "a" * 64, "inkPixels": 1200, "pngBytes": 512, "roundTripMatches": True,
                     "networkSha256": font_sha256},
            "download": {"text": text, "sha256": digest},
            "pdf": {"headerValid": True, "bytes": 4096, "screenMediaRestored": True},
            "artifacts": {"workspace.png": "a" * 64, "print.pdf": "c" * 64, "note.txt": digest}}


@pytest.mark.parametrize("section,field,value", [
    ("note", "undo", "lost text"), ("note", "trusted", False), ("editor", "events", ["insertText"]),
    ("editor", "value", "changed content"), ("selection", "text", "wrong word"),
    ("selection", "noteRange", [False, 15]), ("font", "loaded", False), ("font", "roundTripMatches", False),
    ("font", "networkSha256", "bad"), ("font", "pixels", "bad"), ("font", "domWidth", 121),
    ("font", "fallbackWidth", 120), ("font", "canvasWidth", float("nan")), ("font", "inkPixels", 0),
    ("font", "inkPixels", 1.5), ("font", "pngBytes", True), ("pdf", "screenMediaRestored", False), ("pdf", "bytes", 0),
    ("download", "text", "lost Unicode"), ("artifacts", "note.txt", "a" * 64),
])
def test_text_workloads_reject_broken_editing_fonts_selection_and_exports(section, field, value):
    from scripts import native_font_workloads as workloads

    sample = workload_observation()
    workloads.validate(sample)
    sample[section][field] = value
    with pytest.raises(ValueError):
        workloads.validate(sample)


@pytest.mark.parametrize("mutation", [None, "metric", "missing-mode", "missing-restart", "bad-control", "pixels"])
def test_workload_matrix_requires_stable_semantics_not_identical_rasterization(mutation):
    from scripts import native_font_workloads as workloads

    modes = ("off", "gamma-1400")
    runs = {mode: [workload_observation(), workload_observation()] for mode in modes}
    if mutation == "metric":
        for field in ("domWidth", "svgWidth", "canvasWidth"):
            runs["gamma-1400"][0]["font"][field] += 1
    elif mutation == "missing-mode":
        del runs["gamma-1400"]
    elif mutation == "missing-restart":
        runs["gamma-1400"].pop()
    elif mutation == "bad-control":
        runs["off"][0]["editor"]["trusted"] = False
    elif mutation == "pixels":
        runs["gamma-1400"][0]["font"].update(pixels="d" * 64, inkPixels=1000, pngBytes=600)
        runs["gamma-1400"][0]["pdf"]["bytes"] = 8192
    if mutation in ("missing-mode", "missing-restart", "bad-control"):
        with pytest.raises(ValueError):
            workloads.assess(runs, modes)
    else:
        assert workloads.assess(runs, modes)["passed"] is (mutation != "metric")


@pytest.mark.parametrize("kind", ["missing", "directory", "relative", "small", "large", "boolean"])
def test_invalid_workload_font_rejects_before_builder_or_browser_access(tmp_path, monkeypatch, kind):
    from pathlib import Path

    font = tmp_path / "font.ttf"
    if kind == "directory":
        font.mkdir()
    elif kind == "relative":
        font = Path("font.ttf")
    elif kind == "small":
        font.write_bytes(b"bad")
    elif kind == "large":
        with font.open("wb") as stream:
            stream.truncate(2 * 1024**2 + 1)
    elif kind == "boolean":
        font = True
    monkeypatch.setattr(verifier.sys, "platform", "win32")
    monkeypatch.setattr(verifier, "require_idle_builder", lambda *args: pytest.fail("Invalid font reached builder access"))
    destination = tmp_path / "evidence"
    with pytest.raises(ValueError, match="bounded canonical"):
        asyncio.run(verifier.verify(tmp_path / "chrome.exe", destination, workload_font=font))
    assert not destination.exists()


@pytest.mark.parametrize("change", [None, "changed", "missing"])
def test_workload_artifact_guard_measures_actual_exports(tmp_path, change):
    from scripts import native_font_workloads as workloads

    value = workload_observation()
    for name in workloads.ARTIFACTS:
        data = value["download"]["text"].encode("utf-8") if name == "note.txt" else name.encode("ascii")
        (tmp_path / name).write_bytes(data)
        value["artifacts"][name] = hashlib.sha256(data).hexdigest()
    if change == "changed":
        (tmp_path / "note.txt").write_bytes(b"changed artifact")
    elif change == "missing":
        (tmp_path / "workspace.png").unlink()
    if change == "missing":
        with pytest.raises(FileNotFoundError):
            workloads.artifacts_unchanged(tmp_path, value)
    else:
        assert workloads.artifacts_unchanged(tmp_path, value) is (change is None)


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
    monkeypatch.setattr(verifier, "require_idle_builder", lambda *args: None)
    monkeypatch.setattr(verifier, "measure_runtime_core", lambda path: core)
    monkeypatch.setattr(verifier, "NativeRuntime", lambda *args: pytest.fail("Invalid candidate reached launch"))
    monkeypatch.setattr(verifier, "PATCH", candidate["directory"] / "patches" / verifier.PATCH.name)
    selector = None if mutation == "implicit" else "unknown" if mutation == "unknown" else candidate["name"]
    expected = "explicit --candidate" if mutation == "implicit" else "Unknown Native" if mutation == "unknown" else "complete pinned"
    destination = tmp_path / "evidence"
    with pytest.raises(ValueError, match=expected):
        asyncio.run(verifier.verify(executable, destination, candidate_name=selector))
    assert not destination.exists()
