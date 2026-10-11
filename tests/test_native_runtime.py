import asyncio
from pathlib import Path

import pytest

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime, NativeRuntimeError


@pytest.mark.parametrize("values", [
    {"environment": "ios"}, {"environment": "android"}, {"width": True}, {"height": 0},
    {"device_scale_factor": float("nan")}, {"device_scale_factor": True},
    {"locale": "en_US"}, {"timezone": "invalid/zone"}, {"permissions": ("unknown",)},
    {"permissions": ({},)},
])
def test_native_configuration_rejects_unsupported_or_inconsistent_inputs(values):
    with pytest.raises(ValueError):
        NativeConfiguration(**values).context_options()


def test_mobile_web_configuration_does_not_claim_android_identity():
    configuration = NativeConfiguration(environment="mobile_web", width=390, height=844, device_scale_factor=3)
    options = configuration.context_options()
    assert options["is_mobile"] and options["has_touch"]
    assert options["viewport"] == {"width": 390, "height": 844}
    assert "user_agent" not in options
    assert "not an Android Chrome" in " ".join(configuration.limitations())
    assert options["permissions"] == []


def test_native_locale_is_configured_for_browser_and_worker_processes():
    assert NativeConfiguration(locale="de-DE").launch_arguments() == ["--lang=de-DE", "--accept-lang=de-DE"]


@pytest.mark.parametrize("key", ["language", "languages", "hardwareConcurrency", "deviceMemory", "timezone", "userAgentData"])
def test_native_diagnostics_detects_document_worker_disagreement(key):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC"}
    observed = {"document": document, "worker": dict(document)}
    assert compare_observed(NativeConfiguration(), observed) == []
    observed["worker"][key] = "inconsistent"
    assert compare_observed(NativeConfiguration(), observed) == [f"Document and dedicated worker disagree on {key}"]


def test_native_diagnostics_reports_blocked_worker_without_fake_observations():
    from app.core.native.diagnostics import compare_observed

    observed = {"document": {"width": 390, "height": 844, "dpr": 3, "language": "en-US", "timezone": "UTC", "touch": 0},
                "worker": None, "workerError": "Worker blocked"}
    assert compare_observed(NativeConfiguration(environment="mobile_web", width=390, height=844, device_scale_factor=3), observed) == [
        "Mobile Web touch capability is unavailable", "Worker blocked"]


def test_native_missing_binary_does_not_touch_profile(tmp_path):
    profile = tmp_path / "profile"
    runtime = NativeRuntime(profile, tmp_path / "missing.exe", NativeConfiguration())
    with pytest.raises(NativeRuntimeError, match="not installed"):
        asyncio.run(runtime.start())
    assert not profile.exists()


def test_native_failed_driver_stop_retains_owner_and_can_be_retried(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    async def check():
        runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())
        context = SimpleNamespace(close=AsyncMock())
        driver = SimpleNamespace(stop=AsyncMock(side_effect=RuntimeError("owned stop failure")))
        lock = Mock()
        runtime.context, runtime.playwright, runtime._profile_lock = context, driver, lock
        with pytest.raises(RuntimeError, match="owned stop failure"):
            await runtime.close()
        assert runtime.context is context and runtime.playwright is driver
        lock.unlock.assert_not_called()
        with pytest.raises(NativeRuntimeError, match="already running"):
            await runtime.start()
        driver.stop.side_effect = None
        await runtime.close()
        assert runtime.context is None and runtime.playwright is None
        lock.unlock.assert_called_once()
    asyncio.run(check())


def test_native_refuses_existing_unrelated_browser_data(tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    original = profile / "Preferences"
    original.write_text("customer data", encoding="utf-8")
    runtime = NativeRuntime(profile, Path(__file__), NativeConfiguration())
    with pytest.raises(NativeRuntimeError, match="own empty profile"):
        asyncio.run(runtime.start())
    assert original.read_text(encoding="utf-8") == "customer data"
    assert list(profile.iterdir()) == [original]


@pytest.mark.parametrize("values", [
    {"hardware_concurrency": 4}, {"fingerprint_noise": True}, {"platform": "android"},
    {"persistent_context": False}, {"permissions": "camera"},
    {"extra_http_headers": {"User-Agent": "other browser"}},
    {"extra_http_headers": {"sec-ch-ua-mobile": "?1"}},
])
def test_native_profile_settings_fail_closed_for_unsupported_identity(values):
    with pytest.raises(ValueError):
        NativeConfiguration.from_settings(values)


def test_native_profile_settings_reach_supported_configuration():
    configuration = NativeConfiguration.from_settings({"environment": "mobile_web", "window_width": 390,
        "window_height": 844, "device_scale_factor": 3, "permissions": ["geolocation"]})
    assert configuration.context_options()["permissions"] == ["geolocation"]
    assert configuration.width == 390 and configuration.height == 844


def test_native_browser_interface_uses_separate_storage_and_never_falls_back(tmp_path, monkeypatch):
    from unittest.mock import Mock
    import app.core.browser_interface as interface
    from app.storage import db

    monkeypatch.setattr(interface, "checked_profile_dir_for_email", lambda name: tmp_path / "profile")
    monkeypatch.setattr(interface, "db_get_native_defaults", lambda: dict(db.NATIVE_DEFAULTS))
    monkeypatch.setattr(interface, "db_get_camoufox_defaults", lambda: {})
    monkeypatch.setattr(interface, "db_get_cloakbrowser_defaults", lambda: {})
    monkeypatch.setattr(interface.BrowserInterface, "_init_proxy_logger", lambda self: Mock())
    fallback = Mock(side_effect=AssertionError("Native must not launch Camoufox"))
    monkeypatch.setattr(interface, "_import_camoufox", fallback)
    browser = interface.BrowserInterface("Owned profile", browser_engine="native", keep_browser_open=False)
    assert browser.user_data_dir == (tmp_path / "profile/native").resolve()
    assert browser._browser_settings["environment"] == "desktop"
    assert "fingerprint_noise" not in browser._browser_settings
    with pytest.raises(RuntimeError, match="explicit Native Chromium executable"):
        asyncio.run(browser.start())
    fallback.assert_not_called()


@pytest.mark.parametrize("settings", [
    {"hardware_concurrency": 4}, {"device_memory": 8}, {"user_agent": "Invented device"},
    {"webgl_vendor": "Invented GPU"}, {"webgl_renderer": "Invented renderer"},
    {"environment": "android"}, {"window_width": True}, {"extra_http_headers": {"Accept-Language": "other"}},
])
def test_native_profile_json_rejects_unsupported_settings_before_any_mutation(monkeypatch, settings):
    import json
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.ui.bridge import profiles

    monkeypatch.setattr(profiles, "db_get_native_defaults", lambda: {})
    bridge = SimpleNamespace(_emit_message=Mock(), _ensure_allowed=Mock(return_value=True), _mutate=Mock())
    profiles.ProfilesBridge.saveProfileBrowserSettingsJson(bridge, "owned", "native", json.dumps(settings))
    bridge._mutate.assert_not_called()
    assert "Native browser settings error:" in bridge._emit_message.call_args.args[0]


def test_native_profile_json_validates_merged_defaults_and_preserves_only_overrides(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.ui.bridge import profiles

    monkeypatch.setattr(profiles, "db_get_native_defaults", lambda: {"environment": "mobile_web", "window_height": 844})
    update = Mock()
    monkeypatch.setattr(profiles, "db_update_account", update)
    bridge = SimpleNamespace(_emit_message=Mock(), _ensure_allowed=Mock(return_value=True), _mutate=Mock())
    profiles.ProfilesBridge.saveProfileBrowserSettingsJson(bridge, "owned", "native", '{"window_width":420}')
    work, targets = bridge._mutate.call_args.args
    assert targets == ["owned"]
    work(None)
    update.assert_called_once_with("owned", {"native_settings": {"window_width": 420}})
    bridge._emit_message.assert_not_called()
