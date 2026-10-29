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
    assert "no_viewport=True" in (environment.ROOT / "scripts/capture_native_environment.py").read_text(encoding="utf-8-sig")
