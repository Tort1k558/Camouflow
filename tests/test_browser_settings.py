"""Settings must survive persistence and reach the selected browser engine."""
import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.browser_interface import BrowserInterface
from app.core.browser_launchers import CamoufoxLaunchBuilder, CloakBrowserLaunchBuilder
from app.core.camoufox_profile_fingerprint import (
    load_or_create_profile_fingerprint_bundle,
)
from app.storage import db


def cloak_builder(path, settings):
    return CloakBrowserLaunchBuilder(path, db.CLOAKBROWSER_DEFAULTS, settings, None,
                                    lambda: "en-US", lambda: "America/New_York")


def test_cloak_window_and_screen_are_independent(tmp_path):
    options = cloak_builder(tmp_path, {"window_width": 1100, "window_height": 700,
        "screen_width": 1920, "screen_height": 1080}).build()
    assert options["viewport"] == {"width": 1100, "height": 700}
    assert "--window-size=1100,700" in options["args"]
    assert "--fingerprint-screen-width=1920" in options["args"]
    assert "--fingerprint-screen-height=1080" in options["args"]
    assert "viewport" not in cloak_builder(tmp_path, {}).build()


def test_camoufox_fixed_window_fingerprint_roundtrip_and_resize(tmp_path):
    first, overrides, gpu = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1100, 700))
    second, restored, restored_gpu = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1100, 700))
    assert asdict(first) == asdict(second)
    assert all(overrides[key] == value for key, value in restored.items())
    assert gpu == restored_gpu
    resized, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1000, 650))
    assert resized.navigator == first.navigator
    assert (resized.screen.outerWidth, resized.screen.outerHeight) == (1000, 650)
    third, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1000, 650))
    assert asdict(resized) == asdict(third)


def test_camoufox_requested_os_change_is_not_ignored(tmp_path):
    first, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    second, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="linux")
    assert "Windows" in first.navigator.userAgent
    assert "Linux" in second.navigator.userAgent


def test_existing_camoufox_profile_gets_persistent_noise_seeds_without_identity_reset(tmp_path):
    first, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    path = tmp_path / "camoufox_fingerprint.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ("audio:seed",):
        payload["overrides"].pop(key)
    path.write_text(json.dumps(payload), encoding="utf-8")
    migrated, seeds, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    restored, later_seeds, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    assert asdict(first) == asdict(migrated) == asdict(restored)
    assert seeds["audio:seed"] == later_seeds["audio:seed"]


def test_camoufox_context_gpu_and_screen_defaults_survive_save(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SETTINGS_FILE", tmp_path / "settings.json")
    values = {"screen_width": 1920, "screen_height": 1080, "webgl_vendor": "vendor", "webgl_renderer": "renderer",
              "extra_http_headers": {"X-Audit": "global"}, "permissions": ["geolocation"], "java_script_enabled": False,
              "bypass_csp": True, "ignore_https_errors": True, "accept_downloads": False}
    db.db_set_camoufox_defaults(values)
    assert all(db.db_get_camoufox_defaults()[key] == value for key, value in values.items())


def test_camoufox_persistent_launch_applies_context_options(tmp_path):
    options = CamoufoxLaunchBuilder("test", tmp_path, {"locale": "en-US", "timezone": "America/New_York",
        "os": ["windows"], "java_script_enabled": False, "bypass_csp": True,
        "permissions": ["geolocation"], "screen_width": 1920, "screen_height": 1080,
        "extra_http_headers": {"X-Audit": "test"}}, db.CAMOUFOX_DEFAULTS, None, None,
        SimpleNamespace(detect_timezone=lambda: None), Mock(), Mock(), lambda: "en-US").build()
    assert options["java_script_enabled"] is False
    assert options["bypass_csp"] is True
    assert options["extra_http_headers"] == {"X-Audit": "test"}
    assert options["config"]["screen.width"] == 1920
    assert "window.history.length" not in options["config"]


@pytest.mark.parametrize("clear", [True, False])
def test_disabled_humanization_does_not_add_typing_delays(clear, monkeypatch):
    sleeper = AsyncMock()
    monkeypatch.setattr("app.core.browser_interface.asyncio.sleep", sleeper)
    browser = SimpleNamespace(_browser_settings={"humanize": False}, browser_engine="cloakbrowser")
    element = SimpleNamespace(fill=AsyncMock(), type=AsyncMock())
    asyncio.run(BrowserInterface._human_type(browser, element, "audit", clear=clear))
    (element.fill if clear else element.type).assert_awaited_once_with("audit")
    sleeper.assert_not_awaited()


@pytest.mark.parametrize("persistent", [True, False])
def test_cloak_context_uses_native_launcher_and_inherited_defaults(tmp_path, monkeypatch, persistent):
    import cloakbrowser

    monkeypatch.setattr("app.core.browser_interface.profile_dir_for_email", lambda name: tmp_path / name)
    monkeypatch.setattr("app.core.browser_interface.db_get_camoufox_defaults", lambda: dict(db.CAMOUFOX_DEFAULTS))
    monkeypatch.setattr("app.core.browser_interface.db_get_cloakbrowser_defaults", lambda: {
        **db.CLOAKBROWSER_DEFAULTS, "locale": "de-DE", "timezone": "Europe/Berlin",
        "humanize": False, "extra_http_headers": {"X-Audit": "global"}})
    context = SimpleNamespace(browser=Mock())
    launch = AsyncMock(return_value=context)
    monkeypatch.setattr(cloakbrowser, "launch_persistent_context_async" if persistent else "launch_context_async", launch)
    browser = BrowserInterface("test", browser_engine="cloakbrowser", browser_settings={"persistent_context": persistent})
    asyncio.run(browser._start_cloakbrowser())
    assert browser.context is context
    options = launch.call_args.kwargs
    assert options["locale"] == "de-DE"
    assert options["timezone"] == "Europe/Berlin"
    assert options["extra_http_headers"] == {"X-Audit": "global"}
    assert "timezone_id" not in options
    assert "viewport" not in options
    assert browser._browser_settings["humanize"] is False
