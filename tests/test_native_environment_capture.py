import copy
import json

import pytest

from scripts import capture_native_environment as environment
from test_native_gpu import observation as gpu_observation


VERSION = "156.0.8078.36"


def test_environment_reference_summary_binds_sources_without_admitting_generated_profiles():
    record = json.loads((environment.ROOT / "native/drafts/environment/stock156-capture-observations.json").read_bytes())
    assert record["passed"] is True and record["postguards_passed"] is True
    assert record["source_sha256"] == environment.source_inputs()
    assert record["capture_mode"] == "headless-automation-control" and record["viewport_emulation"] is False
    assert record["measured_hosts"] == 1
    assert [row["name"] for row in record["phases"]] == ["initial", "persistent-profile-restart"]
    for row in record["phases"]:
        assert row["passed"] is True
        assert row["coverage"] == {"webgl": 8, "webgl2": 8, "webgpu": 8,
                                   "http_hint_contexts": {"full": 3, "low_entropy": 2, "absent": 3}}
    assert len(record["failure_controls"]) == 3
    assert all(row["passed"] is True for row in record["failure_controls"])
    for key in ("profile_generation_admitted", "ordinary_user_identity_verified", "glint_runtime_verified",
                "privacy_admitted", "production_admitted"):
        assert record[key] is False


def test_published_manager_mode_findings_remain_failed_and_reproducible():
    record = json.loads((environment.ROOT / "native/drafts/environment/stock156-screen-consistency-observations.json").read_bytes())
    assert record["passed"] is False and record["measurement_completed"] is True
    assert record["postguards_passed"] is True and record["source_sha256"] == environment.source_inputs()
    assert [row["name"] for row in record["modes"]] == ["native-control", "manager-desktop", "manager-mobile-web"]
    for row in record["modes"]:
        native = row["name"] == "native-control"
        assert row["passed"] is native and row["restart_comparison_complete"] is native
        assert row["viewport_emulation"] is not native
        assert len(row["phases"]) == 2
        assert all(phase["passed"] is native for phase in row["phases"])
        if not native:
            assert row["configuration"] == environment.configuration_for_mode(row["name"]).environment_settings()
            assert all(phase["document"] != phase["cross_origin_frame"] for phase in row["phases"])
    for key in ("glint_runtime_verified", "screen_inheritance_fixed", "profile_generation_admitted", "production_admitted"):
        assert record[key] is False


def observed_environment():
    brands = [{"brand": "Chromium", "version": "156"}]
    high = {"brands": brands, "mobile": False, "platform": "Windows",
            "fullVersionList": [{"brand": "Chromium", "version": VERSION}],
            "architecture": "x86", "bitness": "64", "platformVersion": "19.0.0",
            "model": "", "wow64": False, "formFactors": ["Desktop"]}
    hints = {key: high[key] for key in ("brands", "mobile", "platform")}
    hardware = {"hardwareConcurrency": 8, "deviceMemory": 8, "platform": "Win32", "language": "en-US",
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HeadlessChrome/156.0.0.0 Safari/537.36"}
    headers = {"user-agent": hardware["userAgent"], "accept-language": "en-US,en;q=0.9",
               "sec-ch-ua": '"Chromium";v="156"', "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
               "sec-ch-ua-full-version-list": '"Chromium";v="' + VERSION + '"',
               "sec-ch-ua-arch": '"x86"', "sec-ch-ua-bitness": '"64"',
               "sec-ch-ua-platform-version": '"19.0.0"', "sec-ch-ua-model": '""',
               "sec-ch-ua-wow64": "?0", "sec-ch-ua-form-factors": '"Desktop"'}
    gpu = gpu_observation()
    observed = {}
    for name in environment.canvas.CONTEXTS:
        document = name in environment.NETWORK_DOCUMENTS | environment.INHERITED_DOCUMENTS
        present = {"user-agent", "accept-language"}
        if name in environment.NETWORK_DOCUMENTS:
            present = environment.HEADER_NAMES
        elif name in environment.INHERITED_DOCUMENTS:
            present |= environment.LOW_HINTS
        observed[name] = copy.deepcopy({
            "identity": {"userAgent": hardware["userAgent"], "language": "en-US", "userAgentData": hints,
                         "metadata": high, "headers": {key: value if key in present else None for key, value in headers.items()},
                         "getter": "function get userAgent() { [native code] }", "illegalInvocation": True,
                         "ownProperty": False, "plugins": ["PDF Viewer"] if document else None,
                         "chromeType": "object" if document else "undefined"},
            "hardware": hardware, "gpu": gpu[name], "languages": ["en-US"],
            "intl": {"locale": "en-US", "timezone": "UTC"},
            "viewport": ({"width": 800, "height": 600} if name == "document" else {"width": 300, "height": 150}) if document else None,
            "screen": {"width": 800, "height": 600, "availWidth": 800, "availHeight": 600,
                       "colorDepth": 24, "pixelDepth": 24, "dpr": 1, "touch": 0} if document else None,
        })
    return observed


def test_environment_records_native_scope_specific_headers_without_fabricating_worker_hints():
    observed = observed_environment()
    result = environment.validate_environment(observed, VERSION, previous=copy.deepcopy(observed))
    assert result == {"webgl": 8, "webgl2": 8, "webgpu": 8,
                      "http_hint_contexts": {"full": 3, "low_entropy": 2, "absent": 3}}
    assert observed["dedicated"]["identity"]["headers"]["sec-ch-ua"] is None
    assert observed["srcdoc_frame"]["identity"]["headers"]["sec-ch-ua-arch"] is None


@pytest.mark.parametrize("field,value", [
    ("hardwareConcurrency", True), ("hardwareConcurrency", 0), ("deviceMemory", float("nan")),
    ("platform", "MacIntel"), ("language", "ru-RU"), ("userAgent", "Chrome/148.0.0.0"),
])
def test_environment_rejects_invalid_or_contradictory_hardware(field, value):
    observed = observed_environment()
    observed["shared"]["hardware"][field] = value
    with pytest.raises(ValueError):
        environment.validate_environment(observed, VERSION)


@pytest.mark.parametrize("name", sorted(environment.canvas.CONTEXTS))
def test_environment_rejects_missing_realms(name):
    observed = observed_environment()
    observed.pop(name)
    with pytest.raises(ValueError):
        environment.validate_environment(observed, VERSION)


@pytest.mark.parametrize("name,header,value", [
    ("document", "sec-ch-ua-arch", None), ("cross_origin_frame", "sec-ch-ua-platform", '"macOS"'),
    ("same_origin_frame", "sec-ch-ua-bitness", '"32"'), ("document", "sec-ch-ua", '"Chromium";v="148"'),
    ("document", "accept-language", "ru-RU"), ("service", "user-agent", "Chrome/148.0.0.0"),
    ("dedicated", "sec-ch-ua", '"Chromium";v="156"'), ("shared", "sec-ch-ua-model", '""'),
    ("about_blank_frame", "sec-ch-ua-platform-version", '"19.0.0"'),
    ("srcdoc_frame", "sec-ch-ua-mobile", None),
])
def test_environment_requires_exact_pinned_header_availability_and_present_values(name, header, value):
    observed = observed_environment()
    observed[name]["identity"]["headers"][header] = value
    with pytest.raises(ValueError):
        environment.validate_environment(observed, VERSION)


@pytest.mark.parametrize("field,value", [
    ("width", True), ("availWidth", 801), ("touch", -1), ("dpr", float("nan")),
    ("dpr", float("inf")), ("pixelDepth", 0), ("height", 601),
])
def test_environment_rejects_invalid_or_cross_realm_screen_changes(field, value):
    observed = observed_environment()
    observed["cross_origin_frame"]["screen"][field] = value
    with pytest.raises(ValueError):
        environment.validate_environment(observed, VERSION)


@pytest.mark.parametrize("mutation", ["missing", "unknown", "plugins", "worker-screen", "worker-plugins", "chrome-type",
                                      "locale", "languages", "gpu-unavailable", "gpu-change", "gpu-readback"])
def test_environment_cannot_admit_incomplete_or_inconsistent_measurements(mutation):
    observed = observed_environment()
    if mutation == "missing":
        observed["document"].pop("hardware")
    elif mutation == "unknown":
        observed["document"]["invented"] = True
    elif mutation == "plugins":
        observed["document"]["identity"]["plugins"] = [True]
    elif mutation == "worker-screen":
        observed["service"]["screen"] = observed["document"]["screen"]
    elif mutation == "worker-plugins":
        observed["dedicated"]["identity"]["plugins"] = []
    elif mutation == "chrome-type":
        observed["shared"]["identity"]["chromeType"] = "object"
    elif mutation == "locale":
        observed["shared"]["intl"]["locale"] = "ru-RU"
    elif mutation == "languages":
        observed["service"]["languages"] = ["ru-RU"]
    elif mutation == "gpu-unavailable":
        observed["service"]["gpu"]["webgpu"] = {"available": False, "reason": "No adapter"}
    elif mutation == "gpu-change":
        observed["shared"]["gpu"]["webgl"]["webgl"]["renderer"] = "Different GPU"
    else:
        observed["document"]["gpu"]["webgpu"]["roundtrip"][0] = 0
    with pytest.raises(ValueError):
        environment.validate_environment(observed, VERSION)


def test_environment_does_not_discard_restart_changes():
    observed, previous = observed_environment(), observed_environment()
    previous["service"]["identity"]["getter"] = "function changed() { [native code] }"
    with pytest.raises(ValueError, match="restart"):
        environment.validate_environment(observed, VERSION, previous=previous)


def test_shader_translation_length_is_recorded_but_is_not_an_identity_parameter():
    observed, previous = observed_environment(), observed_environment()
    observed["about_blank_frame"]["gpu"]["webgl"]["webgl"]["translatedShaderLength"] += 17
    previous["document"]["gpu"]["webgl"]["webgl2"]["translatedShaderLength"] += 31
    environment.validate_environment(observed, VERSION, previous=previous)
    assert observed["about_blank_frame"]["gpu"]["webgl"]["webgl"]["translatedShaderLength"] == 273
    observed["about_blank_frame"]["gpu"]["webgl"]["webgl"]["translatedShaderLength"] = True
    with pytest.raises(ValueError):
        environment.validate_environment(observed, VERSION)


def test_fixture_delegates_hints_to_inherited_frames_and_never_invents_request_values():
    assert "if (allow) blank.allow = allow" in (environment.ROOT / "scripts/verify_native_canvas.py").read_text(encoding="utf-8-sig")
    assert "if (allow) srcdoc.allow = allow" in (environment.ROOT / "scripts/verify_native_canvas.py").read_text(encoding="utf-8-sig")
    assert environment.configuration_for_mode("native-control") is None
    assert environment.configuration_for_mode("manager-desktop").context_options()["screen"] == {"width": 1366, "height": 768}
    mobile = environment.configuration_for_mode("manager-mobile-web")
    assert mobile.environment == "mobile_web" and mobile.width == 390 and mobile.device_scale_factor == 3
    with pytest.raises(ValueError):
        environment.configuration_for_mode("automatic-fallback")


def test_manager_validation_never_silently_accepts_the_native_unemulated_control():
    observed = observed_environment()
    with pytest.raises(ValueError, match="Requested manager configuration"):
        environment.validate_requested_configuration(observed, environment.configuration_for_mode("manager-desktop"))
    observed["document"]["viewport"] = {"width": 1366, "height": 768}
    observed["document"]["screen"].update(width=1366, height=768, availWidth=1366, availHeight=768)
    environment.validate_requested_configuration(observed, environment.configuration_for_mode("manager-desktop"))


@pytest.mark.parametrize("mode", ["native-control", "manager-desktop", "manager-mobile-web"])
@pytest.mark.parametrize("failed_phases", [(), (0,), (1,), (0, 1)])
def test_capture_runs_both_explicit_phases_without_fallback_or_reusing_observed_driver_arguments(tmp_path, monkeypatch, mode, failed_phases):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    configuration = environment.configuration_for_mode(mode)
    launches = []
    measured = []

    class Driver:
        async def __aenter__(self):
            return SimpleNamespace(chromium=self)

        async def __aexit__(self, *args):
            pass

        async def launch_persistent_context(self, profile, **options):
            context = SimpleNamespace(browser=SimpleNamespace(version=VERSION), close=AsyncMock(), options=options)
            launches.append(context)
            return context

    async def arguments(context):
        return [*context.options["args"], "--driver-owned-switch"]

    async def observe(*args, **kwargs):
        values = observed_environment()
        if configuration is not None:
            for value in values.values():
                if value["screen"] is not None:
                    value["screen"].update(width=configuration.width, height=configuration.height,
                                           availWidth=configuration.width, availHeight=configuration.height,
                                           dpr=configuration.device_scale_factor,
                                           touch=1 if configuration.environment == "mobile_web" else 0)
            values["document"]["viewport"] = {"width": configuration.width, "height": configuration.height}
        if len(measured) in failed_phases:
            values["cross_origin_frame"]["screen"]["width"] += 1
        measured.append(values)
        return values

    monkeypatch.setattr(environment, "async_playwright", Driver)
    monkeypatch.setattr(environment.workers, "browser_arguments", arguments)
    monkeypatch.setattr(environment.canvas, "observe", observe)
    report = {"checks": []}
    task = environment.capture(tmp_path / "chrome.exe", tmp_path / "profile", "http://owned", report,
                               configuration=configuration)
    if failed_phases:
        with pytest.raises(ValueError):
            asyncio.run(task)
    else:
        asyncio.run(task)
    assert len(launches) == len(report["checks"]) == 2
    assert report["restart_comparison_complete"] is (not failed_phases)
    expected = [index not in failed_phases for index in range(2)]
    assert [row["passed"] for row in report["checks"]] == expected
    for context in launches:
        context.close.assert_awaited_once()
        assert "--driver-owned-switch" not in context.options["args"]
        if configuration is None:
            assert context.options["no_viewport"] is True
        else:
            assert "no_viewport" not in context.options
            assert context.options["screen"] == {"width": configuration.width, "height": configuration.height}
            assert context.options["args"] == ["--enable-automation", *configuration.launch_arguments()]
def test_glint67_screen_record_preserves_failed_manager_modes_without_false_admission():
    import hashlib
    import json

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/glint67-screen-consistency-observations.json").read_bytes())
    assert record["measurement_complete"] and record["postguards_passed"] and not record["passed"]
    checkpoint = root / "native/drafts/upstream-156" / record["required_manifest"]
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == record["candidate_manifest_sha256"]
    assert all(record[name] is False for name in ("screen_inheritance_fixed", "privacy_admitted", "production_admitted",
                                                "active_build_output_used", "installed_package_verified", "no_viewport_control_is_a_fix"))
    modes = record["modes"]
    assert [row["mode"] for row in modes] == ["manager-desktop", "manager-mobile-web", "native-control"]
    for row, expected in zip(modes, ((1366, 768, 1, False), (390, 844, 3, False), (800, 600, 1, True)), strict=True):
        width, height, dpr, passed = expected
        assert row["passed"] is passed
        assert [phase["name"] for phase in row["phases"]] == ["initial", "persistent-profile-restart"]
        for phase in row["phases"]:
            assert phase["passed"] is passed
            main, cross = phase["screen"]["document"], phase["screen"]["cross_origin_frame"]
            assert (main["width"], main["height"], main["dpr"]) == (width, height, dpr)
            assert (cross["width"], cross["height"], cross["dpr"]) == (800, 600, 1)
            assert (main == cross) is passed
            assert all(phase["screen"][name] is None for name in ("dedicated", "shared", "service"))


def test_screen69_source_package_does_not_claim_a_compiled_or_runtime_fix():
    import hashlib
    import re

    root = environment.ROOT
    directory = root / "native/drafts/environment"
    record = json.loads((directory / "screen-inheritance69-preparation.json").read_bytes())
    assert all(record[key] is False for key in (
        "selected", "cpp_compiled", "native_tests_executed", "runtime_verified",
        "screen_inheritance_fixed", "privacy_admitted", "production_admitted"))
    assert record["apply_check_passed"] and record["binding_generation_passed"]
    assert record["active_source_postguards_passed"] and record["active_browser_core_unchanged"]
    raw = (directory / record["patch"]).read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert hashlib.sha256(raw).hexdigest() == record["patch_sha256"]
    assert raw.count(b"diff --git ") == record["patch_files"] == 19
    added = "\n".join(line[1:] for line in raw.decode("utf-8").splitlines()
                      if line.startswith("+") and not line.startswith("+++"))
    cases = re.findall(r"TEST\(GlintLogicalScreenTest,\s*(\w+)\)", added)
    assert cases == record["prepared_native_cases"] and len(cases) == 9
    checkpoint = directory / record["base_manifest"]
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == record["base_manifest_sha256"]
    manifest = json.loads((root / "native/drafts/upstream-156/manifest.json").read_bytes())
    base = json.loads(checkpoint.read_bytes())
    assert len(base["patches"]) == 68
    assert manifest["patches"][:68] == base["patches"]


def test_queued_main_dpr_correction_preserves_incomplete_baseline_and_has_no_admission():
    import hashlib
    import re

    directory = environment.ROOT / "native/drafts/environment"
    baseline = json.loads((directory / "screen68-first-script-observations.json").read_bytes())
    assert not baseline["passed"] and not baseline["measurement_complete"] and baseline["postguards_passed"]
    assert len(baseline["phases"]) == 5 and baseline["error_type"] == "TimeoutError"
    for row in baseline["phases"][:4]:
        assert len(row["observations"]) == 6 and row["browser_connection_closed"]
        if row["mode"] == "manager-mobile-web":
            main = row["observations"]["main"]
            assert main["first"]["screen"]["dpr"] == 3 and main["settled"]["screen"]["dpr"] == 1
    record = json.loads((directory / "main-dpr70-preparation.json").read_bytes())
    assert all(record[key] is False for key in (
        "selected", "cpp_compiled", "native_tests_executed", "runtime_verified",
        "screen_inheritance_fixed", "privacy_admitted", "production_admitted"))
    assert record["apply_check_passed"] and record["active_source_postguards_passed"]
    patch = (directory / record["patch"]).read_bytes()
    assert hashlib.sha256(patch).hexdigest() == record["patch_sha256"]
    added = "\n".join(line[1:] for line in patch.decode("utf-8").splitlines()
                      if line.startswith("+") and not line.startswith("+++"))
    cases = re.findall(r"TEST_F\(WebFrameWidgetSimTest,\s*(Glint\w+)\)", added)
    assert cases == record["prepared_native_cases"] and len(cases) == 3


def test_complete_first_script_baseline_keeps_failed_manager_modes_and_passing_controls():
    import hashlib

    directory = environment.ROOT / "native/drafts/environment"
    record = json.loads((directory / "screen68-first-script-complete-observations.json").read_bytes())
    assert record["measurement_complete"] and record["postguards_passed"] and record["fixture_control_passed"]
    assert not record["passed"] and not record["screen_inheritance_fixed"] and not record["production_admitted"]
    assert [row["passed"] for row in record["phases"]] == [False, False, False, False, True, True]
    for name, expected in record["fixture_source_sha256"].items():
        assert hashlib.sha256((directory / "first-script" / name).read_bytes()).hexdigest() == expected
    for row in record["phases"]:
        assert len(row["observations"]) == 6 and row["browser_connection_closed"]
        for value in row["observations"].values():
            assert value["clicks"] == [{"trusted": True, "x": 52, "y": 38, "inside": True}]
        if row["mode"] == "native-control":
            main = row["observations"]["main"]["settled"]
            expected_size = [round(main["viewport"][axis] * main["screen"]["dpr"])
                             for axis in ("width", "height")]
        else:
            expected_size = {"manager-desktop": [1366, 768], "manager-mobile-web": [1170, 2532]}[row["mode"]]
        assert row["screenshot"]["size"] == expected_size
