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


@pytest.fixture
def first_script_verifier():
    import runpy

    return runpy.run_path(str(environment.ROOT / "native/drafts/environment/first-script/verify.py"))


@pytest.mark.parametrize("index", range(6))
def test_public_first_script_validator_matches_all_actual_baseline_phases(first_script_verifier, index):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    row = record["phases"][index]
    configuration = environment.configuration_for_mode(row["mode"])
    errors = first_script_verifier["validate_phase"](row["observations"], row["screenshot"]["size"], configuration, None)
    assert errors == row["errors"]
    assert (not errors) is row["passed"]


@pytest.mark.parametrize("bad_dpr", [0, -1, True, float("nan"), float("inf"), 10 ** 400])
def test_first_script_snapshot_rejects_invalid_dpr(first_script_verifier, bad_dpr):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    value = copy.deepcopy(record["phases"][-1]["observations"]["main"]["first"])
    value["screen"]["dpr"] = bad_dpr
    with pytest.raises(ValueError, match="DPR"):
        first_script_verifier["validate_snapshot"](value)


@pytest.mark.parametrize("mutation", ["media-empty", "media-not-bool", "viewport-empty", "orientation-not-string"])
def test_first_script_snapshot_rejects_incomplete_observations(first_script_verifier, mutation):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    value = copy.deepcopy(record["phases"][-1]["observations"]["main"]["first"])
    if mutation == "media-empty":
        value["media"] = {}
    elif mutation == "media-not-bool":
        value["media"]["width"] = 1
    elif mutation == "viewport-empty":
        value["viewport"] = {}
    else:
        value["screen"]["orientation"]["type"] = []
    with pytest.raises(ValueError):
        first_script_verifier["validate_snapshot"](value)


@pytest.mark.parametrize("mutation", ["missing-role", "untrusted", "numeric-trusted", "media-false", "screenshot", "restart"])
def test_first_script_phase_keeps_failed_contracts(first_script_verifier, mutation):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    row = copy.deepcopy(record["phases"][-1])
    previous = None
    if mutation == "missing-role":
        del row["observations"]["nested-return"]
        with pytest.raises(ValueError, match="six"):
            first_script_verifier["validate_phase"](row["observations"], row["screenshot"]["size"], None, None)
        return
    if mutation == "untrusted":
        row["observations"]["cross"]["clicks"][0]["trusted"] = False
    elif mutation == "numeric-trusted":
        row["observations"]["cross"]["clicks"][0]["trusted"] = 1
    elif mutation == "media-false":
        row["observations"]["cross"]["first"]["media"]["resolution"] = False
    elif mutation == "screenshot":
        row["screenshot"]["size"][0] += 1
    else:
        previous = copy.deepcopy(row["observations"]["main"]["first"]["screen"])
        previous["width"] += 1
    assert first_script_verifier["validate_phase"](row["observations"], row["screenshot"]["size"], None, previous)


def test_first_script_consistency_does_not_admit_unapplied_manager_settings(first_script_verifier):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    row = record["phases"][-1]
    configuration = environment.configuration_for_mode("manager-desktop")
    errors = first_script_verifier["validate_phase"](row["observations"], [1366, 768], configuration, None)
    assert errors == ["Main first script differs from requested manager screen/DPR"]


@pytest.mark.parametrize("phase,role,allowed", [("first", "cross", True), ("settled", "cross", False),
                                              ("first", "main", False)])
def test_first_script_child_pre_layout_zero_is_retained_not_replaced(first_script_verifier, phase, role, allowed):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    row = copy.deepcopy(record["phases"][-1])
    row["observations"][role][phase]["viewport"] = {"width": 0, "height": 0}
    if allowed:
        assert not first_script_verifier["validate_phase"](row["observations"], row["screenshot"]["size"], None, None)
        assert row["observations"][role][phase]["viewport"] == {"width": 0, "height": 0}
    else:
        with pytest.raises(ValueError, match="viewport"):
            first_script_verifier["validate_phase"](row["observations"], row["screenshot"]["size"], None, None)


@pytest.mark.parametrize("checkpoint", ["../001-069", "001-069.json", "", "001-69"])
def test_first_script_verifier_rejects_noncanonical_checkpoint_before_creating_evidence(first_script_verifier, tmp_path, checkpoint):
    with pytest.raises(ValueError, match="checkpoint"):
        first_script_verifier["verify"](tmp_path / "chrome.exe", tmp_path / "report", checkpoint)
    assert not (tmp_path / "report").exists()


def test_first_script_observers_accept_playwright_page_events_and_keep_phase_ownership(first_script_verifier):
    from collections import Counter
    from types import SimpleNamespace

    registered = []
    rows = []
    counters = []
    for _ in range(2):
        callbacks = {}
        page = SimpleNamespace(on=lambda name, callback: callbacks.__setitem__(name, callback))
        row = {"page_errors": [], "lifecycle_events": []}
        pending = Counter()
        first_script_verifier["install_observers"](page, row, pending)
        registered.append((page, callbacks))
        rows.append(row)
        counters.append(pending)
    for index, (page, callbacks) in enumerate(registered):
        callbacks["domcontentloaded"](page)
        callbacks["load"](page)
        callbacks["pageerror"](RuntimeError("Owned error " + str(index)))
        request = SimpleNamespace(url="http://owned/" + str(index))
        callbacks["request"](request)
        callbacks["request"](request)
        callbacks["requestfinished"](request)
        assert counters[index][request.url] == 1
        callbacks["requestfailed"](request)
        assert counters[index][request.url] == 0
    assert rows == [{"page_errors": ["Owned error " + str(index)],
                     "lifecycle_events": ["domcontentloaded", "load"]} for index in range(2)]


def test_public_first_script_execution_binds_current_sources_and_retains_incomplete_attempts():
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/public-first-script-cli-observations.json").read_bytes())
    assert record["public_cli_executed"] and record["baseline_findings_reproduced"]
    assert record["measurement_complete"] and record["postguards_passed"]
    assert not record["passed"] and not record["screen_inheritance_fixed"]
    assert record["final_owned_chrome_processes_remaining"] == 0
    assert all("\\" not in name for name in record["source_sha256"])
    for name, expected in record["source_sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    assert [row["passed"] for row in record["phases"]] == [False, False, False, False, True, True]
    assert all(row["document_contexts"] == 6 and row["browser_connection_closed"] and not row["page_errors"]
               for row in record["phases"])
    assert len(record["prior_incomplete_attempts"]) == 3
    assert all(not row["passed"] and not row["measurement_complete"] for row in record["prior_incomplete_attempts"])


@pytest.fixture
def screen_lifecycle_collector():
    import runpy

    return runpy.run_path(str(environment.ROOT / "native/drafts/environment/first-script/lifecycle.py"))


@pytest.mark.parametrize("state,expected", [
    (None, False), ({}, False), ({"registered": False, "events": [True]}, False),
    ({"registered": True, "events": None}, False), ({"registered": True, "events": []}, False),
    ({"registered": True, "events": [False]}, False), ({"registered": True, "events": ["true"]}, False),
    ({"registered": 1, "events": [True]}, False), ({"registered": True, "events": [True]}, True),
    ({"registered": True, "events": [False, True]}, True),
])
def test_screen_lifecycle_requires_retained_pageshow_persisted_evidence(screen_lifecycle_collector, state, expected):
    assert screen_lifecycle_collector["history_restored"](state) is expected


def test_screen_lifecycle_metrics_and_clear_do_not_mutate_original_baseline(screen_lifecycle_collector):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    original = record["phases"][-1]["observations"]["main"]["settled"]["screen"]
    before = copy.deepcopy(original)
    settings = {"width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True}
    params = screen_lifecycle_collector["metrics_parameters"](settings)
    assert params == {**settings, "screenWidth": 390, "screenHeight": 844,
                      "screenOrientation": {"type": "portraitPrimary", "angle": 0}}
    requested = screen_lifecycle_collector["expected_screen"](original, settings)
    assert (requested["width"], requested["height"], requested["dpr"]) == (390, 844, 3)
    assert requested["orientation"] == {"type": "portrait-primary", "angle": 0}
    assert screen_lifecycle_collector["expected_screen"](original, None) == before
    assert original == before


def test_screen_lifecycle_validation_keeps_child_geometry_separate(screen_lifecycle_collector):
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    values = {role: {"snapshot": copy.deepcopy(row["settled"]),
                     "embedding_size": copy.deepcopy(row["settled"]["viewport"])}
              for role, row in record["phases"][-1]["observations"].items()}
    expected = values["main"]["snapshot"]["screen"]
    assert not screen_lifecycle_collector["validate_page"](values, expected)
    values["cross"]["embedding_size"]["width"] += 1
    assert screen_lifecycle_collector["validate_page"](values, expected) == [
        "cross: child viewport differs from its own embedding box"]
    values.pop("nested-return")
    with pytest.raises(ValueError, match="six"):
        screen_lifecycle_collector["validate_page"](values, expected)


def test_screen_lifecycle_bfcache_fixture_uses_explicit_cacheable_response(screen_lifecycle_collector):
    import http.client
    import threading

    server = screen_lifecycle_collector["create_server"]()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request("GET", "/screen?role=main")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Cache-Control") == "public, max-age=60"
        assert b"glintFirstScreen" in response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert not thread.is_alive()


def restored_screen_state():
    record = json.loads((environment.ROOT / "native/drafts/environment/screen68-first-script-complete-observations.json").read_bytes())
    rows = record["phases"][-1]["observations"]
    parents = {role: "main" for role in rows}
    parents.update({"main": None, "nested-return": "cross"})
    snapshots = {role: {"snapshot": copy.deepcopy(row["settled"]), "persisted": True,
                         "parent": parents[role], "children_sizes": {}}
                 for role, row in rows.items()}
    for role, parent in parents.items():
        if parent is not None:
            snapshots[parent]["children_sizes"][role] = dict(rows[role]["settled"]["viewport"])
    return {"registered": True, "events": [True], "snapshots": snapshots,
            "timedOut": False, "protocolErrors": []}


def test_screen_lifecycle_restore_covers_six_persisted_documents_without_rewriting_raw_state(screen_lifecycle_collector):
    state = restored_screen_state()
    original = copy.deepcopy(state)
    observed = screen_lifecycle_collector["restored_observations"](state)
    assert state == original
    assert len(observed) == 6 and all(row["persisted"] for row in observed.values())
    assert not screen_lifecycle_collector["validate_page"](observed, observed["main"]["snapshot"]["screen"])


@pytest.mark.parametrize("mutation", ["timeout", "protocol", "missing", "not-persisted", "parent", "embedding", "mixed-events"])
def test_screen_lifecycle_rejects_incomplete_or_untrusted_restore_evidence(screen_lifecycle_collector, mutation):
    state = restored_screen_state()
    if mutation == "timeout":
        state["timedOut"] = True
    elif mutation == "protocol":
        state["protocolErrors"] = ["Duplicate document response"]
    elif mutation == "missing":
        state["snapshots"].pop("nested-return")
    elif mutation == "not-persisted":
        state["snapshots"]["cross"]["persisted"] = False
    elif mutation == "parent":
        state["snapshots"]["cross"]["parent"] = "missing"
    elif mutation == "embedding":
        state["snapshots"]["main"]["children_sizes"].pop("cross")
    else:
        state["events"] = [True, "true"]
    with pytest.raises(ValueError):
        screen_lifecycle_collector["restored_observations"](state)


@pytest.mark.parametrize("cache_restored", [False, True])
def test_screen_lifecycle_history_uses_cdp_not_unsupported_playwright_back(screen_lifecycle_collector, cache_restored):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    root = SimpleNamespace(name="", parent_frame=None, evaluate=AsyncMock())
    cross = SimpleNamespace(name="cross", parent_frame=root, evaluate=AsyncMock())
    frames = [root, cross, *[SimpleNamespace(name=name, parent_frame=cross if name == "nested-return" else root,
                                            evaluate=AsyncMock())
                            for name in ("same", "srcdoc", "about-blank", "nested-return")]]
    page = SimpleNamespace(frames=frames, goto=AsyncMock(), go_back=AsyncMock(side_effect=AssertionError("Unsupported API")))
    state = restored_screen_state() if cache_restored else {"registered": False, "events": None, "snapshots": {}}
    callbacks = {}
    calls = []

    async def send(name, arguments=None):
        calls.append((name, arguments))
        if name == "Page.getNavigationHistory":
            return {"currentIndex": 0, "entries": [{"id": 7, "url": "http://localhost:1234/screen?role=main"}]}
        if name == "Page.navigateToHistoryEntry":
            callbacks["Page.frameNavigated"]({"frame": {"id": "root", "url": "http://localhost:1234/screen?role=main"},
                                               "type": "BackForwardCacheRestore" if cache_restored else "Navigation"})
            return {}
        assert name == "Runtime.evaluate" and arguments["awaitPromise"] and arguments["returnByValue"]
        assert "owned-glint-history-request" in arguments["expression"]
        return {"result": {"value": state}}

    session = SimpleNamespace(send=send, on=lambda name, callback: callbacks.__setitem__(name, callback),
                              remove_listener=lambda name, callback: callbacks.pop(name))
    expected = {frame.name or "main": {"origin": "http://localhost:1234"} for frame in frames}
    report = {"fixture_port": 1234}
    result = asyncio.run(screen_lifecycle_collector["restore_history"](page, session, expected, report))
    assert result == state and not callbacks
    page.go_back.assert_not_awaited()
    assert [name for name, _ in calls] == ["Page.getNavigationHistory", "Page.navigateToHistoryEntry", "Runtime.evaluate"]
    assert all(frame.evaluate.await_count == 1 for frame in frames)
    assert report["history_navigation"]["type"] == ("BackForwardCacheRestore" if cache_restored else "Navigation")


def test_screen_lifecycle_calibration_matches_stock_without_false_manager_or_native_admission():
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/screen-lifecycle68-calibration-observations.json").read_bytes())
    assert not record["passed"] and record["paired_calibration_passed"] and record["measurement_complete"]
    assert record["same_screen_viewport_css"] and record["compared_document_snapshots"] == 78
    assert record["bfcache_restored_glint"] and record["bfcache_restored_stock"]
    assert record["bfcache_restored_documents_glint"] == record["bfcache_restored_documents_stock"] == 6
    assert all(record[key] is False for key in ("supported_manager_path_verified", "process_swap_verified",
                                               "native_0069_verified", "privacy_admitted", "production_admitted",
                                               "history_uses_playwright_navigation"))
    assert record["source_core_receipt_postguards_passed"] and record["final_owned_chrome_processes_remaining"] == 0
    assert len(record["stages"]) == 7
    assert sum(page["document_contexts"] for row in record["stages"] for page in row["pages"].values()) == 78
    for name, expected in record["source_sha256"].items():
        assert "\\" not in name and hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    assert record["prior_incomplete_attempt"]["measurement_complete"] is False


@pytest.fixture
def manager_screen_collector():
    import runpy

    return runpy.run_path(str(environment.ROOT / "native/drafts/environment/first-script/manager.py"))


def test_manager_screen_validator_uses_context_identity_and_actual_child_embedding(manager_screen_collector):
    from types import SimpleNamespace

    observed = manager_screen_collector["LIFECYCLE"]["restored_observations"](restored_screen_state())
    original = copy.deepcopy(observed)
    root = observed["main"]["snapshot"]
    configuration = SimpleNamespace(width=root["screen"]["width"], height=root["screen"]["height"],
                                    device_scale_factor=root["screen"]["dpr"])
    assert not manager_screen_collector["validate_capture"](observed, configuration, root["viewport"], root["screen"])
    assert observed == original


@pytest.mark.parametrize("mutation", ["viewport", "configuration", "child-screen", "child-embedding", "css", "coverage"])
def test_manager_screen_validator_rejects_inconsistent_supported_path(manager_screen_collector, mutation):
    from types import SimpleNamespace

    observed = manager_screen_collector["LIFECYCLE"]["restored_observations"](restored_screen_state())
    root = observed["main"]["snapshot"]
    viewport = dict(root["viewport"])
    baseline = dict(root["screen"])
    configuration = SimpleNamespace(width=baseline["width"], height=baseline["height"],
                                    device_scale_factor=baseline["dpr"])
    if mutation == "viewport":
        viewport["width"] += 1
    elif mutation == "configuration":
        configuration.device_scale_factor += 1
    elif mutation == "child-screen":
        observed["cross"]["snapshot"]["screen"]["width"] += 1
    elif mutation == "child-embedding":
        observed["cross"]["embedding_size"]["width"] += 1
    elif mutation == "css":
        observed["same"]["snapshot"]["media"]["resolution"] = False
    else:
        observed.pop("about-blank")
        with pytest.raises(ValueError, match="six"):
            manager_screen_collector["validate_capture"](observed, configuration, viewport, baseline)
        return
    assert manager_screen_collector["validate_capture"](observed, configuration, viewport, baseline)


def test_manager_screen_calibration_binds_sources_and_retains_failed_identity_contract():
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/manager-screen68-calibration-observations.json").read_bytes())
    assert record["measurement_complete"] and record["paired_calibration_complete"] and record["postguards_passed"]
    assert record["same_screen_viewport_css"] and record["compared_document_snapshots"] == 216
    assert not record["passed"] and not record["glint_screen_consistency_passed"] and not record["stock_screen_consistency_passed"]
    assert all(record[name] is False for name in ("extra_page_cdp_sessions", "full_native_runtime_lifecycle_verified",
        "bfcache_verified", "process_swap_verified", "native_0069_verified", "privacy_admitted", "production_admitted"))
    assert len(record["stages"]) == 20
    assert {(row["mode"], row["phase"]) for row in record["stages"]} == {
        (mode, phase) for mode in ("manager-desktop", "manager-mobile-web") for phase in ("initial", "restart")}
    assert sum(page["document_contexts"] for row in record["stages"] for page in row["pages"].values()) == 216
    for row in record["stages"]:
        for page in row["pages"].values():
            assert page["same_screen_viewport_css"]
            assert page["glint_screenshot_size"] == page["stock_screenshot_size"]
            for kind in ("glint", "stock"):
                assert (page[kind + "_touch_points"] > 0) == (row["mode"] == "manager-mobile-web")
                assert set(page[kind + "_trusted_last_clicks"]) == {
                    "main", "same", "cross", "nested-return", "srcdoc", "about-blank"}
                assert all(click == {"trusted": True, "x": 52, "y": 38, "inside": True}
                           for click in page[kind + "_trusted_last_clicks"].values())
    for name, value in record["source_sha256"].items():
        assert "\\" not in name and hashlib.sha256((root / name).read_bytes()).hexdigest() == value


def test_queued_native_lifecycle_cases_bind_to_dpr70_without_claiming_execution():
    import hashlib
    import re

    directory = environment.ROOT / "native/drafts/environment"
    record = json.loads((directory / "screen-lifecycle-native-tests-preparation.json").read_bytes())
    assert all(record[name] is False for name in ("selected", "cpp_compiled", "native_tests_executed",
        "runtime_verified", "screen_inheritance_fixed", "privacy_admitted", "production_admitted"))
    assert record["apply_check_passed"] and record["active_source_postguards_passed"]
    assert record["prepared_target"] == "blink_unittests"
    assert record["fixture_available_rectangle_valid"]
    assert hashlib.sha256((directory / record["base_patch"]).read_bytes()).hexdigest() == record["base_patch_sha256"]
    patch = (directory / record["patch"]).read_bytes()
    assert hashlib.sha256(patch).hexdigest() == record["patch_sha256"]
    added = "\n".join(line[1:] for line in patch.decode("utf-8").splitlines()
                       if line.startswith("+") and not line.startswith("+++"))
    assert re.findall(r"TEST_F\([^,]+,\s*(Glint\w+)\)", added) == record["prepared_cases"]
    assert len(record["prepared_cases"]) == 4
    assert "GlintLogicalRootDevicePixelRatio" in added and "glint_logical_screen_infos.reset()" in added
    assert "GetScreenInfo().device_scale_factor, 1" in added
    assert "SetInspectorDeviceScaleFactorOverride" in added and "SetCssZoomFactor" in added


@pytest.mark.parametrize("name", ["A", "B"])
def test_runtime_storage_control_accepts_only_its_owned_values(name):
    import runpy

    collector = runpy.run_path(str(environment.ROOT / "native/drafts/environment/first-script/runtime.py"))
    value = {"local": "owned-" + name, "cookie": "glint-owned=owned-" + name}
    assert collector["validate_storage"](value, name) is None


@pytest.mark.parametrize("value", [
    {"local": "owned-B", "cookie": "glint-owned=owned-B"},
    {"local": "owned-A", "cookie": ""},
    {"local": None, "cookie": "glint-owned=owned-A"},
    {"local": "owned-A", "cookie": "glint-owned=owned-A; glint-owned=owned-B"},
    {"local": "owned-A", "cookie": "glint-owned=owned-A", "extra": True},
])
def test_runtime_storage_control_rejects_cross_profile_missing_or_duplicate_values(value):
    import runpy

    collector = runpy.run_path(str(environment.ROOT / "native/drafts/environment/first-script/runtime.py"))
    with pytest.raises(ValueError, match="storage"):
        collector["validate_storage"](value, "A")


def test_real_runtime_ownership_record_keeps_lifecycle_and_screen_admission_separate():
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/runtime-ownership68-observations.json").read_bytes())
    assert record["measurement_complete"] and record["postguards_passed"] and record["lifecycle_passed"]
    assert record["owned_runtimes_resource_free"] and record["cleanup_errors"] == []
    assert record["passed"] is False and record["screen_consistency_passed"] is False
    assert len(record["lifecycle_checks"]) == 8 and all(value is True for value in record["lifecycle_checks"].values())
    assert [row["name"] for row in record["stages"]] == ["simultaneous-profiles", "restart-A", "restart-B"]
    assert record["compared_document_snapshots"] == 36
    assert sum(value["document_contexts"] for row in record["stages"] for value in row["profiles"].values()) == 36
    assert all(value["storage_matches_owned_profile"] for row in record["stages"] for value in row["profiles"].values())
    assert all(record[name] is False for name in ("bfcache_verified", "process_swap_verified", "crash_recovery_verified",
        "cross_process_owner_rejection_verified", "server_team_storage_isolation_verified", "native_0069_verified",
        "privacy_admitted", "production_admitted"))
    for name, value in record["source_sha256"].items():
        assert "\\" not in name and hashlib.sha256((root / name).read_bytes()).hexdigest() == value


@pytest.fixture
def owner_process_collector():
    import runpy

    return runpy.run_path(str(environment.ROOT / "native/drafts/environment/first-script/owner_process.py"))


@pytest.mark.parametrize("blocked", [False, True])
def test_cross_process_result_requires_exact_boolean_lock_state(owner_process_collector, blocked):
    assert owner_process_collector["validate_probe"](
        {"started": not blocked, "rejected_by_lock": blocked, "resource_free": True}, blocked=blocked) is None


@pytest.mark.parametrize("value", [None, {},
    {"started": True, "rejected_by_lock": False, "resource_free": True},
    {"started": False, "rejected_by_lock": True, "resource_free": False},
    {"started": False, "rejected_by_lock": True, "resource_free": 1},
    {"started": False, "rejected_by_lock": True, "resource_free": True, "extra": True},
])
def test_cross_process_result_rejects_missing_contradictory_or_leaked_resources(owner_process_collector, value):
    with pytest.raises(ValueError, match="lock state"):
        owner_process_collector["validate_probe"](value, blocked=True)


@pytest.mark.parametrize("outcome", ["started", "locked", "error"])
def test_cross_process_worker_always_closes_its_runtime(owner_process_collector, monkeypatch, tmp_path, outcome):
    import asyncio

    instances = []
    error_type = owner_process_collector["NativeRuntimeError"]

    class Runtime:
        def __init__(self, *args):
            self.has_resources = False
            self.closed = False
            instances.append(self)

        async def start(self, **kwargs):
            if outcome == "locked":
                raise error_type("Another process owns this Native profile")
            if outcome == "error":
                raise ValueError("Unrelated failure")
            self.has_resources = True

        async def close(self):
            self.closed = True
            self.has_resources = False

    function = owner_process_collector["probe"]
    monkeypatch.setitem(function.__globals__, "NativeRuntime", Runtime)
    if outcome == "error":
        with pytest.raises(ValueError, match="Unrelated"):
            asyncio.run(function(tmp_path / "profile", tmp_path / "chrome.exe"))
    else:
        result = asyncio.run(function(tmp_path / "profile", tmp_path / "chrome.exe"))
        owner_process_collector["validate_probe"](result, blocked=outcome == "locked")
    assert len(instances) == 1 and instances[0].closed and not instances[0].has_resources


def test_published_cross_process_result_proves_orderly_handoff_not_crash_recovery(owner_process_collector):
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/runtime-owner-process68-observations.json").read_bytes())
    assert all(record[name] is True for name in ("passed", "measurement_complete", "postguards_passed",
        "parent_resource_free", "cross_process_owner_rejection_verified", "released_lock_reacquired_by_child",
        "owner_unchanged_after_rejection", "private_identity_unchanged"))
    assert all(record[name] is False for name in ("crash_recovery_verified", "native_0069_verified",
        "server_team_storage_isolation_verified", "privacy_admitted", "production_admitted"))
    assert record["platform"] == "win32"
    assert len(record["child_processes"]) == 2
    for row, blocked in zip(record["child_processes"], (True, False), strict=True):
        assert row["completed"] and row["returncode"] == 0
        owner_process_collector["validate_probe"](row["result"], blocked=blocked)
    for name, value in record["source_sha256"].items():
        assert "\\" not in name and hashlib.sha256((root / name).read_bytes()).hexdigest() == value


def test_checkpointed_browser_and_controller_crash_evidence_reuses_existing_gates():
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/runtime-crash68-observations.json").read_bytes())
    assert record["passed"] and record["measurement_complete"] and record["postguards_passed"]
    assert record["controller_crash_verified"] and record["controller_owned_processes_observed"] > 0
    assert record["requested_rounds"] == len(record["rounds"]) == 3 and record["concurrent_profiles"] == 2
    assert record["existing_gates_reused"] == ["verify_multi_profile_restarts", "verify_controller_crash"]
    assert record["verified_stores"] == ["cookies", "localStorage", "IndexedDB", "CacheStorage", "serviceWorker registration"]
    assert record["checkpoint_before_browser_crash"]
    assert [row["crashed_profile"] for row in record["rounds"]] == [0, 1, 0]
    for row in record["rounds"]:
        assert row["concurrent_profiles"] == row["independent_drivers"] == 2
        assert row["checkpoint_before_crash"] and row["remaining_owned_processes"] == 0
        assert row["policy_capabilities"] == [] and row["processes_observed"] > 2
    assert all(record[name] is False for name in ("uncommitted_transactions_recovery_verified", "protected_policies_enabled",
        "native_0069_verified", "screen_consistency_verified", "server_team_storage_isolation_verified",
        "protected_policy_recovery_verified", "privacy_admitted", "production_admitted"))
    for name, value in record["source_sha256"].items():
        assert "\\" not in name and hashlib.sha256((root / name).read_bytes()).hexdigest() == value


def test_consolidated_screen_batch_is_two_files_and_seven_cases_without_early_admission():
    import hashlib
    import re

    directory = environment.ROOT / "native/drafts/environment"
    record = json.loads((directory / "linked-screen70-preparation.json").read_bytes())
    assert record["apply_check_passed"] and record["active_source_postguards_passed"]
    assert record["do_not_stack_component_patches"]
    assert all(record[name] is False for name in ("selected", "cpp_compiled", "native_tests_executed",
        "runtime_verified", "screen_inheritance_fixed", "privacy_admitted", "production_admitted",
        "public_header_changed", "ipc_schema_changed", "build_time_measured"))
    assert hashlib.sha256((directory / record["base_manifest"]).read_bytes()).hexdigest() == record["base_manifest_sha256"]
    for name, value in record["component_patch_sha256"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == value
    patch = (directory / record["patch"]).read_bytes()
    assert hashlib.sha256(patch).hexdigest() == record["patch_sha256"]
    text = patch.decode("utf-8")
    files = re.findall(r"^diff --git a/(\S+) b/\S+$", text, re.MULTILINE)
    assert set(files) == set(record["base_source_sha256"]) == set(record["prepared_source_sha256"])
    assert len(files) == 2 and all(name.endswith(".cc") for name in files)
    added = "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    cases = re.findall(r"TEST_F\((WebFrameWidget(?:SimTest|ImplRemoteFrameSimTest)),\s*(Glint\w+)\)", added)
    assert [".".join(row) for row in cases] == record["prepared_cases"] and len(cases) == 7
    assert "  if (!glint_logical_screen_infos_)" in added


def test_queued_screen_widget_gate_binds_seven_cases_without_claiming_native_execution():
    import hashlib

    root = environment.ROOT
    directory = root / "native/drafts/environment"
    record = json.loads((directory / "screen-widget-gate-preparation.json").read_bytes())
    linked = json.loads((directory / "linked-screen70-preparation.json").read_bytes())
    assert record["required_cases"] == linked["prepared_cases"] and len(record["required_cases"]) == 7
    assert record["target"] == "screen-widget" and record["binary_target"] == "blink_unittests"
    assert record["current_target_groups"] == 19 and record["proposed_target_groups"] == 20
    assert record["apply_check_passed"] and record["active_source_postguards_passed"]
    assert record["existing_target_mappings_unchanged"] and record["requires_idle_producer_before_integration"]
    assert len(record["python_controls_passed"]) == 12
    assert all(record[name] is False for name in ("selected", "cpp_compiled", "native_tests_executed",
        "runtime_verified", "privacy_admitted", "production_admitted"))
    assert hashlib.sha256((directory / record["patch"]).read_bytes()).hexdigest() == record["patch_sha256"]
    assert hashlib.sha256((directory / record["linked_native_patch"]).read_bytes()).hexdigest() == record["linked_native_patch_sha256"]
    assert hashlib.sha256((root / record["base_source"]).read_bytes()).hexdigest() == record["base_source_sha256"]


def test_queued_widget_verifier_applies_and_rejects_incomplete_results(tmp_path, monkeypatch):
    import runpy
    import subprocess
    import sys

    root = environment.ROOT
    directory = root / "native/drafts/environment"
    metadata = json.loads((directory / "screen-widget-gate-preparation.json").read_bytes())
    path = tmp_path / metadata["base_source"]
    path.parent.mkdir(parents=True)
    path.write_bytes((root / metadata["base_source"]).read_bytes())
    subprocess.run(["git", "apply", "--whitespace=error", str(directory / metadata["patch"])],
                   cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    current = runpy.run_path(str(root / metadata["base_source"]))
    proposed = runpy.run_path(str(path))
    for target in current["SUPPORTED_TARGETS"]:
        assert current["required_tests"](target) == proposed["required_tests"](target)
        assert current["unit_binary_target"](target) == proposed["unit_binary_target"](target)
    assert proposed["unit_binary_target"]("screen-widget") == "blink_unittests"
    required = proposed["required_tests"]("screen-widget")
    good = {"tests": 7, "disabled": 0, "failures": 0, "testsuites": [
        {"name": suite, "testsuite": [{"name": case, "status": "RUN", "result": "COMPLETED"}
                                     for case in sorted(cases)]} for suite, cases in required.items()]}
    proposed["validate_results"](good, target="screen-widget")
    for failure in ("missing", "duplicate", "not-run", "disabled", "failed"):
        value = copy.deepcopy(good)
        rows = value["testsuites"][0]["testsuite"]
        if failure == "missing":
            rows.pop()
        elif failure == "duplicate":
            rows[0]["name"] = rows[1]["name"]
        elif failure == "not-run":
            rows[0]["status"] = "NOTRUN"
        elif failure == "disabled":
            value["disabled"] = 1
        else:
            rows[0]["failures"] = [{"failure": "owned control"}]
        with pytest.raises(ValueError):
            proposed["validate_results"](value, target="screen-widget")
    with pytest.raises(ValueError, match="explicit upstream-156"):
        proposed["verify"](tmp_path, tmp_path / "not-created.json", target="screen-widget", candidate_name=None)
    assert not (tmp_path / "not-created.json").exists()


def test_failed_full_regression_retains_failure_and_distinguishes_qml_followup():
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/canonical-python69-preparation-observations.json").read_bytes())
    assert record["measurement_complete"] and record["postguards_passed"]
    assert record["passed"] is False and record["returncode"] == 1
    assert record["counts"] == {"tests": 4256, "passed": 4254, "failures": 1, "errors": 0, "skipped": 1}
    assert record["failed_test"].endswith("::test_native_qml_configuration_and_profile_creation")
    assert record["changed_tracked_files"] == []
    assert record["controlled_race"]["original"]["returncode"] == 1
    assert record["controlled_race"]["original"]["expected_dialog_failure"]
    assert record["controlled_race"]["model-ready"]["returncode"] == 0
    assert record["qml_module_followup"]["passed"] == 9
    assert all(record[name] is False for name in ("full_regression_after_repair_verified", "native_runtime_verified",
        "privacy_admitted", "production_admitted"))
    assert hashlib.sha256((root / record["corrected_test_source"]).read_bytes()).hexdigest() == record["corrected_test_source_sha256"]


def test_0069_source_build_proof_has_receipt_and_preservation_without_native_test_admission():
    record = json.loads((environment.ROOT / "native/drafts/upstream-156/build69-observations.json").read_bytes())
    assert record["passed"] and record["completed_stages"] == ["sync", "hooks", "patch", "build"]
    assert record["build_jobs"] == 4 and record["build_steps"] == 2079 and record["build_elapsed_seconds"] == 6429.05
    assert record["registered_patches"] == 69 and record["preserved_runtime_assets"] == 269
    assert record["frozen_inputs_count"] == 212 and record["frozen_input_postguards_passed"]
    assert record["preserved_asset_hashes_postguards_passed"]
    assert all(record[name] is False for name in ("cpp_native_cases_executed_on_0069", "browser_runtime_verified",
        "privacy_admitted", "production_admitted"))


def test_actual_0069_first_script_proves_desktop_repair_but_retains_mobile_main_failure():
    import hashlib

    root = environment.ROOT
    record = json.loads((root / "native/drafts/environment/screen69-first-script-observations.json").read_bytes())
    build = json.loads((root / "native/drafts/upstream-156/build69-observations.json").read_bytes())
    assert record["measurement_complete"] and record["postguards_passed"] and record["passed"] is False
    assert record["runtime_core_sha256_measured"] == build["runtime_core_sha256_measured"]
    assert record["receipt_sha256"] == build["build_receipt_sha256"]
    assert record["desktop_owned_screen_gate_passed"] and record["native_control_gate_passed"]
    assert all(record[name] is False for name in ("mobile_main_dpr_fixed", "browser_runtime_fully_verified",
        "cpp_native_cases_executed", "privacy_admitted", "production_admitted"))
    assert [row["passed"] for row in record["phases"]] == [True, True, False, False, True, True]
    for row in record["phases"]:
        assert len(row["observations"]) == 6 and row["browser_connection_closed"]
        if row["mode"] == "manager-mobile-web":
            assert row["observations"]["main"]["first"]["screen"]["dpr"] == 3
            assert row["observations"]["main"]["settled"]["screen"]["dpr"] == 1
            assert row["observations"]["cross"]["settled"]["screen"]["dpr"] == 3
            assert row["observations"]["nested-return"]["settled"]["screen"]["dpr"] == 3
            assert len(row["errors"]) == 4 and all("screen differs" in error for error in row["errors"])
    for name, value in record["source_sha256"].items():
        assert "\\" not in name and hashlib.sha256((root / name).read_bytes()).hexdigest() == value
