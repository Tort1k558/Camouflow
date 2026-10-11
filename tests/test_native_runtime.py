import asyncio
from pathlib import Path

import pytest

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime, NativeRuntimeError


def test_native_adapter_rechecks_resource_ownership_after_async_binary_resolution(monkeypatch):
    from types import SimpleNamespace

    from app.core.browser_interface import BrowserInterface
    from app.core.native import distribution

    browser = BrowserInterface.__new__(BrowserInterface)
    browser._native_runtime = None
    browser._browser_settings = {}
    owner = SimpleNamespace(has_resources=True)
    def resolve(settings):
        browser._native_runtime = owner
        return Path(__file__)
    monkeypatch.setattr(distribution, "resolve_native_executable", resolve)
    with pytest.raises(RuntimeError, match="Previous Native runtime"):
        asyncio.run(browser._start_native())
    assert browser._native_runtime is owner


def test_native_adapter_resolves_and_hashes_managed_files_off_the_event_loop(monkeypatch):
    import threading

    from app.core.browser_interface import BrowserInterface
    from app.core.native import distribution

    caller = threading.get_ident()
    browser = BrowserInterface.__new__(BrowserInterface)
    browser._native_runtime = None
    browser._browser_settings = {"binary_source": "managed"}
    def resolve(settings):
        assert threading.get_ident() != caller
        assert settings == browser._browser_settings and settings is not browser._browser_settings
        raise ValueError("owned fixture stops before launch")
    monkeypatch.setattr(distribution, "resolve_native_executable", resolve)
    with pytest.raises(RuntimeError, match="owned fixture stops before launch"):
        asyncio.run(browser._start_native())
    assert browser._native_runtime is None


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


@pytest.mark.parametrize("key", ["language", "languages", "hardwareConcurrency", "deviceMemory", "timezone", "userAgentData", "userAgentHighEntropy"])
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


def test_native_diagnostics_reports_denied_client_hints_without_inventing_values():
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "userAgentHighEntropy": None, "userAgentDataError": "Access denied"}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": dict(document)}) == [
        "Document high-entropy client hints could not be observed: Access denied",
        "Worker high-entropy client hints could not be observed: Access denied"]


@pytest.mark.parametrize("key", ["vendor", "renderer", "version", "shadingLanguage", "unmaskedVendor",
                                "unmaskedRenderer", "maxTextureSize", "maxViewportDimensions"])
def test_native_graphics_diagnostics_detects_document_worker_disagreement(key):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "graphics": {"webgl2": {"available": True, key: "document"}}}
    worker = {**document, "graphics": {"webgl2": {"available": True, key: "worker"}}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        f"Document and dedicated worker disagree on webgl2 {key}"]


def test_native_graphics_diagnostics_preserves_unavailable_contexts_without_fake_renderer():
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "graphics": {"webgl": {"available": False, "error": "Native graphics context unavailable"}}}
    worker = {**document, "graphics": {"webgl": {"available": False, "error": "Worker context blocked"}}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == []
    worker["graphics"]["webgl"]["available"] = True
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        "Document and dedicated worker disagree on webgl availability"]


@pytest.mark.parametrize("key", ["font", "textWidth", "pixelSha256"])
def test_native_canvas_diagnostics_detects_document_worker_disagreement(key):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "canvas": {"available": True, key: "document"}}
    worker = {**document, "canvas": {"available": True, key: "worker"}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        f"Document and dedicated worker disagree on canvas {key}"]


def test_native_canvas_diagnostics_does_not_invent_pixels_for_unavailable_contexts():
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "canvas": {"available": False, "error": "2D unavailable"}}
    worker = {**document, "canvas": {"available": False, "error": "Worker 2D unavailable"}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == []
    worker["canvas"]["available"] = True
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        "Document and dedicated worker disagree on canvas availability"]


def test_native_missing_binary_does_not_touch_profile(tmp_path):
    profile = tmp_path / "profile"
    runtime = NativeRuntime(profile, tmp_path / "missing.exe", NativeConfiguration())
    with pytest.raises(NativeRuntimeError, match="not installed"):
        asyncio.run(runtime.start())
    assert not profile.exists()


def test_native_failed_driver_stop_retains_owner_and_does_not_reinvoke_one_shot_sdk_stop(tmp_path):
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
        with pytest.raises(RuntimeError, match="owned stop failure"):
            await runtime.close()
        assert runtime.context is context and runtime.playwright is driver
        driver.stop.assert_awaited_once()
        lock.unlock.assert_not_called()
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


def test_native_context_close_timeout_is_explicit_and_driver_cleanup_releases_owner(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    async def check():
        runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())
        async def blocked_close():
            await asyncio.Event().wait()
        context = SimpleNamespace(close=AsyncMock(side_effect=blocked_close))
        driver = SimpleNamespace(stop=AsyncMock())
        lock = Mock()
        runtime.context, runtime.playwright, runtime._profile_lock = context, driver, lock
        runtime.CONTEXT_CLOSE_TIMEOUT_SECONDS = .01
        with pytest.raises(TimeoutError, match="Native browser context close timed out"):
            await runtime.close()
        context.close.assert_awaited_once()
        driver.stop.assert_awaited_once()
        lock.unlock.assert_called_once()
        assert not runtime.has_resources
    asyncio.run(check())


@pytest.mark.parametrize("interruption", ["cancel", "timeout"])
def test_native_interrupted_stop_waits_for_the_same_sdk_operation_before_releasing_owner(tmp_path, interruption):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from playwright.async_api._context_manager import PlaywrightContextManager

    async def check():
        entered, release = asyncio.Event(), asyncio.Event()
        async def stop_connection():
            entered.set()
            await release.wait()
        manager = PlaywrightContextManager()
        connection = SimpleNamespace(stop_async=AsyncMock(side_effect=stop_connection))
        manager._connection = connection
        runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())
        lock = Mock()
        runtime.context = SimpleNamespace(close=AsyncMock())
        runtime.playwright = SimpleNamespace(stop=manager.__aexit__)
        runtime._profile_lock = lock
        if interruption == "timeout":
            runtime.DRIVER_STOP_TIMEOUT_SECONDS = .05
        closing = asyncio.create_task(runtime.close())
        await asyncio.wait_for(entered.wait(), timeout=1)
        if interruption == "cancel":
            closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await closing
        else:
            with pytest.raises(asyncio.TimeoutError):
                await closing
        assert manager._exit_was_called
        assert runtime._driver_stop_task is not None and not runtime._driver_stop_task.done()
        lock.unlock.assert_not_called()
        with pytest.raises(NativeRuntimeError, match="already running"):
            await runtime.start()
        release.set()
        await runtime.close()
        assert runtime.context is None and runtime.playwright is None
        assert runtime._driver_stop_task is None
        lock.unlock.assert_called_once()
        connection.stop_async.assert_awaited_once()
    asyncio.run(check())


@pytest.mark.parametrize("interruption", ["cancel", "cancel_timeout", "deadline"])
def test_native_cancelled_driver_start_retains_and_cleans_the_same_start_operation(tmp_path, monkeypatch, interruption):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from PyQt6.QtCore import QLockFile
    from app.core.native import runtime as module

    async def check():
        entered, release = asyncio.Event(), asyncio.Event()
        driver = SimpleNamespace(stop=AsyncMock(), chromium=SimpleNamespace(launch_persistent_context=AsyncMock()))
        async def start_driver():
            entered.set()
            await release.wait()
            return driver
        manager = SimpleNamespace(start=AsyncMock(side_effect=start_driver))
        monkeypatch.setattr(module, "async_playwright", lambda: manager)
        runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())
        if interruption != "cancel":
            runtime.DRIVER_START_TIMEOUT_SECONDS = .05
        starting = asyncio.create_task(runtime.start())
        await asyncio.wait_for(entered.wait(), timeout=1)
        startup = runtime._driver_start_task
        if interruption != "deadline":
            starting.cancel()
        await asyncio.sleep(0)
        other = QLockFile(str(runtime.profile_dir / "native-runtime.lock"))
        other.setStaleLockTime(0)
        assert not other.tryLock(0)
        if interruption != "cancel":
            with pytest.raises(asyncio.TimeoutError):
                await starting
            assert runtime._driver_start_task is startup and not startup.done()
            with pytest.raises(NativeRuntimeError, match="already running"):
                await runtime.start()
            release.set()
            await runtime.close()
        else:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await starting
        manager.start.assert_awaited_once()
        driver.stop.assert_awaited_once()
        driver.chromium.launch_persistent_context.assert_not_awaited()
        assert runtime.playwright is None and runtime._driver_start_task is None and runtime._profile_lock is None
        assert other.tryLock(0)
        other.unlock()
    asyncio.run(check())


@pytest.mark.parametrize("resource", ["_profile_lock", "_driver_start_task", "_driver_stop_task", "context", "playwright"])
def test_native_adapter_never_replaces_a_runtime_that_still_owns_resources(tmp_path, resource):
    from app.core.browser_interface import BrowserInterface

    runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())
    assert not runtime.has_resources
    setattr(runtime, resource, object())
    assert runtime.has_resources
    browser = BrowserInterface.__new__(BrowserInterface)
    browser._native_runtime = runtime
    with pytest.raises(RuntimeError, match="Previous Native runtime"):
        asyncio.run(browser._start_native())
    assert browser._native_runtime is runtime


@pytest.mark.parametrize("values", [
    {"hardware_concurrency": 4}, {"fingerprint_noise": True}, {"platform": "android"},
    {"persistent_context": False}, {"permissions": "camera"},
    {"extra_http_headers": {"User-Agent": "other browser"}},
    {"extra_http_headers": {"sec-ch-ua-mobile": "?1"}},
])
def test_native_profile_settings_fail_closed_for_unsupported_identity(values):
    with pytest.raises(ValueError):
        NativeConfiguration.from_settings(values)


@pytest.mark.parametrize("header", ["Sec-CH-UA", "Sec-CH-UA-Arch", "sec-ch-ua-bitness",
    "SEC-CH-UA-PLATFORM-VERSION", "Sec-CH-UA-Full-Version", "Sec-CH-UA-Full-Version-List",
    "Sec-CH-UA-Model", "Sec-CH-UA-WoW64", "Sec-CH-UA-Form-Factors", "Sec-CH-UA-Future-Hint"])
def test_native_identity_header_namespace_cannot_override_native_values(header):
    with pytest.raises(ValueError, match="identity headers"):
        NativeConfiguration.from_settings({"extra_http_headers": {header: "inconsistent"}})


def test_native_configuration_allows_non_identity_http_headers():
    assert NativeConfiguration.from_settings({"extra_http_headers": {
        "X-Owned-Fixture": "value", "Accept": "text/html", "Sec-Fetch-Site": "same-origin"
    }}) == NativeConfiguration()


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


def test_native_binary_health_uses_disposable_storage_and_verifies_teardown(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core.native import health

    executable = tmp_path / "owned.exe"
    executable.touch()
    work = tmp_path / "health"
    closed = AsyncMock()
    profiles = []

    def runtime(profile, binary, configuration):
        profiles.append(profile)
        assert binary == executable
        return SimpleNamespace(start=AsyncMock(return_value=SimpleNamespace(browser=SimpleNamespace(version="148.0.7778.96"))),
                               close=closed)

    monkeypatch.setattr(health, "NativeRuntime", runtime)
    assert asyncio.run(health.probe_native_binary(executable, NativeConfiguration(), work)) == "148.0.7778.96"
    closed.assert_awaited_once()
    assert profiles[0].parent == work
    assert not profiles[0].exists()


def test_native_binary_health_does_not_call_failed_teardown_success(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core.native import health

    executable = tmp_path / "owned.exe"
    executable.touch()
    monkeypatch.setattr(health, "NativeRuntime", lambda *args: SimpleNamespace(
        start=AsyncMock(return_value=SimpleNamespace(browser=SimpleNamespace(version="148.0.7778.96"))),
        close=AsyncMock(side_effect=RuntimeError("owned close failed"))))
    with pytest.raises(RuntimeError, match="owned close failed"):
        asyncio.run(health.probe_native_binary(executable, NativeConfiguration(), tmp_path / "health"))


@pytest.mark.parametrize("failed", [False, True])
def test_native_profile_probe_observes_owned_page_and_always_verifies_teardown(tmp_path, monkeypatch, failed):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.core.native import health

    executable = tmp_path / "owned.exe"
    executable.touch()
    page = object()
    context = SimpleNamespace(browser=SimpleNamespace(version="148.0.7778.96"), pages=[page])
    closed = AsyncMock()
    monkeypatch.setattr(health, "NativeRuntime", lambda *args: SimpleNamespace(start=AsyncMock(return_value=context), close=closed))
    expected = {"browser_version": "148.0.7778.96", "mismatches": []}
    inspect = AsyncMock(return_value=expected, side_effect=RuntimeError("owned observation failed") if failed else None)
    monkeypatch.setattr(health, "inspect_native_profile", inspect)
    configuration = NativeConfiguration()
    if failed:
        with pytest.raises(RuntimeError, match="owned observation failed"):
            asyncio.run(health.probe_native_profile(executable, configuration, tmp_path / "health"))
    else:
        assert asyncio.run(health.probe_native_profile(executable, configuration, tmp_path / "health")) == expected
    inspect.assert_awaited_once_with(page, configuration, "148.0.7778.96")
    closed.assert_awaited_once()
    assert not list((tmp_path / "health").iterdir())


def test_background_read_can_finish_after_its_qt_owner_is_deleted(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PyQt6 import sip
    from PyQt6.QtCore import QObject
    from app.ui.bridge import background

    owner = QObject()
    applied, reported, fetch = Mock(), Mock(), Mock(return_value="owned result")
    reader = background.BackgroundRead(owner, applied, reported)
    tasks = []
    monkeypatch.setattr(background, "get_server_session", lambda: None)
    monkeypatch.setattr(background.threading, "Thread", lambda **kwargs: SimpleNamespace(start=lambda: tasks.append(kwargs["target"])))
    reader.submit(fetch)
    sip.delete(owner)
    assert sip.isdeleted(reader)
    tasks[0]()
    fetch.assert_called_once_with(None)
    applied.assert_not_called()
    reported.assert_not_called()


@pytest.mark.parametrize("engine,changed", [("native", False), ("native", True), ("camoufox", False)])
def test_native_binary_health_ui_rejects_stale_or_other_engine_results(engine, changed):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.ui.bridge.browser_settings import BrowserSettingsBridge

    bridge = SimpleNamespace(_engine=engine, _native={"locale": "en-US"}, _native_probe_running=True,
                             _compatibility_report="previous", _emit_message=Mock(), changed=SimpleNamespace(emit=Mock()))
    bridge._native_settings_signature = lambda: BrowserSettingsBridge._native_settings_signature(bridge)
    signature = bridge._native_settings_signature()
    if changed:
        bridge._native["locale"] = "de-DE"
    BrowserSettingsBridge._apply_native_compatibility(bridge, signature, "verified owned startup")
    assert not bridge._native_probe_running
    assert bridge._compatibility_report == ("previous" if engine != "native" else
        "Native settings or release changed during check; run it again" if changed else "verified owned startup")


@pytest.mark.parametrize("available", [True, False])
def test_native_health_ui_reports_actual_canvas_audio_and_anonymous_media_counts(monkeypatch, available):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from app.core.native import distribution, health
    from app.ui.bridge import browser_settings

    canvas = {"available": available, "textWidth": 123.5, "pixelSha256": "a" * 64,
              "hashError": "", "error": "2D blocked"}
    audio = {"available": available, "frames": 4096, "probeSampleRate": 44100,
             "absoluteSum": 123.5, "error": "Audio blocked"}
    media = {"available": available, "counts": {"audioinput": 1, "audiooutput": 0, "videoinput": 0},
             "error": "Devices blocked"}
    observed = {"document": {"canvas": canvas, "audio": audio, "media": media}, "worker": {"canvas": canvas}}
    monkeypatch.setattr(distribution, "resolve_native_executable", lambda settings: Path(__file__))
    monkeypatch.setattr(health, "probe_native_profile", AsyncMock(return_value={
        "browser_version": "148.0.7778.96", "observed": observed, "mismatches": []}))
    monkeypatch.setattr(browser_settings.threading, "Thread", lambda **kwargs: SimpleNamespace(start=kwargs["target"]))
    emit = Mock()
    bridge = SimpleNamespace(_engine="native", _native={}, _native_probe_running=False,
        _native_settings_signature=lambda: "owned", changed=SimpleNamespace(emit=Mock()),
        _emit_message=Mock(), nativeCompatibilityChecked=SimpleNamespace(emit=emit))
    browser_settings.BrowserSettingsBridge.checkCompatibility(bridge)
    signature, report = emit.call_args.args
    assert signature == "owned"
    if available:
        assert "Canvas: width=123.500; SHA-256=aaaaaaaaaaaa" in report
        assert "4096 frames at 44100 Hz" in report and "not hardware sample rate" in report
        assert "Media device counts (no IDs/labels): audioinput=1" in report
    else:
        assert "Canvas: unavailable (2D blocked)" in report
        assert "Offline audio: unavailable (Audio blocked)" in report
        assert "Media devices: unavailable (Devices blocked)" in report


def test_native_compatibility_defers_hashing_to_worker_and_snapshots_settings(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.native import distribution
    from app.ui.bridge import browser_settings

    pending = []
    resolver = Mock(side_effect=ValueError("owned verification fixture"))
    monkeypatch.setattr(distribution, "resolve_native_executable", resolver)
    monkeypatch.setattr(browser_settings.threading, "Thread", lambda **kwargs: SimpleNamespace(start=lambda: pending.append(kwargs["target"])))
    emit = Mock()
    bridge = SimpleNamespace(_engine="native", _native={"binary_source": "managed", "binary_store": "original"},
        _native_probe_running=False, _native_settings_signature=lambda: "owned", changed=SimpleNamespace(emit=Mock()),
        _emit_message=Mock(), nativeCompatibilityChecked=SimpleNamespace(emit=emit))
    browser_settings.BrowserSettingsBridge.checkCompatibility(bridge)
    resolver.assert_not_called()
    assert bridge._native_probe_running and len(pending) == 1
    bridge._native["binary_store"] = "changed"
    pending[0]()
    resolver.assert_called_once_with({"binary_source": "managed", "binary_store": "original"})
    assert emit.call_args.args[0] == "owned"
    assert "owned verification fixture" in emit.call_args.args[1]


def _native_release_archive(tmp_path, version="0.1.0-dev", metadata_changes=None, extra_entries=()):
    import hashlib
    import io
    import json
    import sys
    import tarfile

    from app.core.native.distribution import host_architecture, sha256_file

    binary = b"owned synthetic native binary"
    metadata = {"schema": 1, "native_version": version, "chromium_version": "148.0.7778.96",
                "platform": sys.platform, "architecture": host_architecture(), "build_kind": "upstream-bootstrap",
                "executable": "owned-browser", "executable_sha256": hashlib.sha256(binary).hexdigest(),
                **(metadata_changes or {})}
    target = tmp_path / (version + ".tar.gz")
    with tarfile.open(target, "w:gz") as archive:
        for name, contents in (("owned-browser", binary), ("native-release.json", json.dumps(metadata).encode("utf-8")), *extra_entries):
            member = tarfile.TarInfo(name)
            member.size = len(contents)
            member.mode = 0o755
            archive.addfile(member, io.BytesIO(contents))
    return target, sha256_file(target)


def test_native_binary_installations_are_versioned_and_never_overwrite_old_releases(tmp_path):
    from app.core.native.distribution import NativeBinaryStore

    store = NativeBinaryStore(tmp_path / "native-binaries")
    archive, digest = _native_release_archive(tmp_path)
    first = store.install_archive(archive, digest)
    assert first == store.inspect(digest)
    first_binary = Path(first["executable_path"])
    before = first_binary.read_bytes()
    archive, second_digest = _native_release_archive(tmp_path, "0.2.0-dev")
    second = store.install_archive(archive, second_digest)
    assert second["executable_path"] != first["executable_path"]
    assert first_binary.read_bytes() == before
    assert store.install_archive(archive, second_digest) == second
    assert not list(store.root.glob("native-install-*"))


def test_native_binary_install_checks_archive_integrity_before_extracting(tmp_path):
    from app.core.native.distribution import NativeBinaryStore

    store = NativeBinaryStore(tmp_path / "native-binaries")
    archive, _ = _native_release_archive(tmp_path)
    with pytest.raises(ValueError, match="archive checksum mismatch"):
        store.install_archive(archive, "0" * 64)
    assert not list((store.root / "releases").iterdir())
    assert not list(store.root.glob("native-install-*"))


@pytest.mark.parametrize("entry", ["../outside", "/absolute", "file:stream", "back\\slash", "CON", "trailing."])
def test_native_binary_archive_paths_cannot_escape_or_alias_windows_files(tmp_path, entry):
    from app.core.native.distribution import NativeBinaryStore

    store = NativeBinaryStore(tmp_path / "native-binaries")
    archive, digest = _native_release_archive(tmp_path, extra_entries=[(entry, b"owned synthetic content")])
    with pytest.raises(ValueError, match="Unsafe"):
        store.install_archive(archive, digest)
    assert not (store.root / "releases" / digest).exists()
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("changes", [{"platform": "unsupported"}, {"architecture": "unsupported"},
                                   {"native_version": "../other"}, {"schema": True},
                                   {"executable_sha256": "0" * 64}, {"executable": "../other"},
                                   {"build_kind": "unknown"}])
def test_native_binary_candidate_validation_precedes_publication(tmp_path, changes):
    from app.core.native.distribution import NativeBinaryStore

    store = NativeBinaryStore(tmp_path / "native-binaries")
    archive, digest = _native_release_archive(tmp_path, metadata_changes=changes)
    with pytest.raises(ValueError):
        store.install_archive(archive, digest)
    assert not (store.root / "releases" / digest).exists()
    assert not list(store.root.glob("native-install-*"))


def test_native_binary_store_preserves_unrelated_directories_and_detects_local_binary_changes(tmp_path):
    from app.core.native.distribution import NativeBinaryStore

    customer = tmp_path / "customer"
    customer.mkdir()
    (customer / "keep").write_text("customer data", encoding="utf-8")
    archive, digest = _native_release_archive(tmp_path)
    with pytest.raises(ValueError, match="unrelated"):
        NativeBinaryStore(customer).install_archive(archive, digest)
    assert (customer / "keep").read_text(encoding="utf-8") == "customer data"
    store = NativeBinaryStore(tmp_path / "native-binaries")
    installed = store.install_archive(archive, digest)
    Path(installed["executable_path"]).write_bytes(b"changed binary")
    with pytest.raises(ValueError, match="executable checksum mismatch"):
        store.inspect(digest)


def _native_checksummed_release_archive(tmp_path, manifest_changes=None):
    import hashlib

    binary = b"owned synthetic native binary"
    library = b"owned synthetic native library"
    files = {"owned-browser": hashlib.sha256(binary).hexdigest(),
             "lib/native.dll": hashlib.sha256(library).hexdigest()}
    return _native_release_archive(tmp_path, metadata_changes={
        "build_kind": "chromium-fork", "files_sha256": files,
        **(manifest_changes or {})}, extra_entries=[("lib/native.dll", library)])


@pytest.mark.parametrize("mutation", ["changed_library", "missing_library", "extra_file", "linked_file"])
def test_native_fork_release_inspection_checks_all_payload_files_not_only_executable(tmp_path, mutation):
    from app.core.native.distribution import NativeBinaryStore

    store = NativeBinaryStore(tmp_path / "native-binaries")
    archive, digest = _native_checksummed_release_archive(tmp_path)
    installed = store.install_archive(archive, digest)
    assert installed == store.inspect(digest)
    payload = Path(installed["executable_path"]).parent
    library = payload / "lib/native.dll"
    if mutation == "changed_library":
        library.write_bytes(b"changed library")
    elif mutation == "missing_library":
        library.unlink()
    elif mutation == "extra_file":
        (payload / "unexpected.dll").write_bytes(b"unexpected library")
    else:
        outside = tmp_path / "outside.dll"
        outside.write_bytes(library.read_bytes())
        library.unlink()
        try:
            library.symlink_to(outside)
        except OSError:
            pytest.skip("Creating symlinks requires Windows Developer Mode or privileges")
    with pytest.raises(ValueError):
        store.inspect(digest)


@pytest.mark.parametrize("action", ["activate", "resolve", "rollback"])
def test_changed_native_payload_blocks_selection_before_launch_and_preserves_active_release(tmp_path, monkeypatch, action):
    import asyncio
    import json

    from app.core.native import distribution

    launches = []
    async def probe(executable, configuration, work_dir):
        launches.append(executable)
        return "148.0.7778.96"
    monkeypatch.setattr(distribution, "probe_native_binary", probe)
    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    archive, digest = _native_checksummed_release_archive(tmp_path)
    installed = store.install_archive(archive, digest)
    asyncio.run(store.activate(digest))
    if action == "rollback":
        archive, next_digest = _native_checksummed_release_archive(tmp_path, {"native_version": "0.2.0-dev"})
        store.install_archive(archive, next_digest)
        asyncio.run(store.activate(next_digest))
    expected_launches = len(launches)
    current = (store.root / "current.json").read_bytes()
    (Path(installed["executable_path"]).parent / "lib/native.dll").write_bytes(b"changed library")
    with pytest.raises(ValueError, match="payload checksum mismatch"):
        if action == "activate":
            asyncio.run(store.activate(digest))
        elif action == "resolve":
            distribution.resolve_native_executable({"binary_source": "managed", "binary_store": str(store.root)})
        else:
            asyncio.run(store.rollback())
    assert len(launches) == expected_launches
    assert (store.root / "current.json").read_bytes() == current
    if action == "rollback":
        assert json.loads(current)["active"] == next_digest
        assert store.resolve_active()["release_sha256"] == next_digest


@pytest.mark.parametrize("mutation", ["missing_manifest", "empty_manifest", "wrong_library_hash",
                                     "omitted_library", "extra_manifest_file", "metadata_self_hash",
                                     "noncanonical_path", "case_collision", "wrong_executable_hash"])
def test_native_fork_file_manifest_validation_precedes_release_publication(tmp_path, mutation):
    import hashlib

    from app.core.native.distribution import NativeBinaryStore

    checksum = hashlib.sha256(b"owned synthetic native binary").hexdigest()
    files = {"owned-browser": checksum, "lib/native.dll": hashlib.sha256(b"owned synthetic native library").hexdigest()}
    if mutation == "missing_manifest":
        archive, digest = _native_release_archive(tmp_path, metadata_changes={"build_kind": "chromium-fork"})
    else:
        if mutation == "empty_manifest":
            files = {}
        elif mutation == "wrong_library_hash":
            files["lib/native.dll"] = "0" * 64
        elif mutation == "omitted_library":
            files.pop("lib/native.dll")
        elif mutation == "extra_manifest_file":
            files["missing.dll"] = "a" * 64
        elif mutation == "metadata_self_hash":
            files["native-release.json"] = "a" * 64
        elif mutation == "noncanonical_path":
            files["lib//native.dll"] = files.pop("lib/native.dll")
        elif mutation == "case_collision":
            files["OWNED-BROWSER"] = checksum
        else:
            files["owned-browser"] = "0" * 64
        archive, digest = _native_checksummed_release_archive(tmp_path, {"files_sha256": files})
    store = NativeBinaryStore(tmp_path / "native-binaries")
    with pytest.raises(ValueError):
        store.install_archive(archive, digest)
    assert not (store.root / "releases" / digest).exists()
    assert not list(store.root.glob("native-install-*"))


def test_native_binary_store_rejects_case_collisions_and_extraction_limits(tmp_path, monkeypatch):
    from app.core.native import distribution

    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    archive, digest = _native_release_archive(tmp_path, extra_entries=[("FILE", b"one"), ("file", b"two")])
    with pytest.raises(ValueError, match="colliding"):
        store.install_archive(archive, digest)
    monkeypatch.setattr(distribution, "MAX_UNPACKED_BYTES", 1)
    archive, digest = _native_release_archive(tmp_path, "0.2.0-dev")
    with pytest.raises(ValueError, match="extraction limits"):
        store.install_archive(archive, digest)
    assert not list((store.root / "releases").iterdir())


def test_native_binary_store_rejects_archive_links_outside_its_owned_directory(tmp_path):
    import tarfile

    from app.core.native.distribution import NativeBinaryStore, sha256_file

    archive, _ = _native_release_archive(tmp_path)
    modified = tmp_path / "linked.tar.gz"
    with tarfile.open(archive, "r:gz") as original, tarfile.open(modified, "w:gz") as output:
        for member in original:
            output.addfile(member, original.extractfile(member))
        link = tarfile.TarInfo("linked")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        output.addfile(link)
    store = NativeBinaryStore(tmp_path / "native-binaries")
    digest = sha256_file(modified)
    with pytest.raises((ValueError, tarfile.FilterError)):
        store.install_archive(modified, digest)
    assert not (store.root / "releases" / digest).exists()


def test_native_binary_store_cannot_update_while_another_owner_holds_the_lock(tmp_path):
    from PyQt6.QtCore import QLockFile

    from app.core.native.distribution import NativeBinaryStore

    root = tmp_path / "native-binaries"
    root.mkdir()
    lock = QLockFile(str(root / "native-update.lock"))
    lock.setStaleLockTime(0)
    assert lock.tryLock(0)
    try:
        archive, digest = _native_release_archive(tmp_path)
        with pytest.raises(ValueError, match="Another process"):
            NativeBinaryStore(root).install_archive(archive, digest)
        assert not (root / "releases").exists()
    finally:
        lock.unlock()


@pytest.mark.parametrize("version,supported", [((3, 12, 0), False), ((3, 12, 11), False), ((3, 12, 14), False),
    ((3, 12, 15), True), ((3, 13, 4), False), ((3, 13, 15), False), ((3, 13, 16), True),
    ((3, 14, 0), False), ((3, 14, 7), False), ((3, 14, 8), True), ((3, 15, 0), True),
    ((3, 16, 0), False), ((4, 0, 0), False)])
def test_native_binary_archive_links_require_security_fixed_python_versions(monkeypatch, version, supported):
    from app.core.native import distribution

    monkeypatch.setattr(distribution.sys, "platform", "darwin")
    monkeypatch.setattr(distribution.sys, "version_info", version)
    assert distribution.archive_links_supported() is supported


def test_native_binary_activation_and_rollback_probe_before_atomic_selection(tmp_path, monkeypatch):
    import json
    from unittest.mock import AsyncMock

    from app.core.native import distribution

    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    first_archive, first_digest = _native_release_archive(tmp_path)
    second_archive, second_digest = _native_release_archive(tmp_path, "0.2.0-dev")
    store.install_archive(first_archive, first_digest)
    store.install_archive(second_archive, second_digest)
    probe = AsyncMock(return_value="148.0.7778.96")
    monkeypatch.setattr(distribution, "probe_native_binary", probe)
    asyncio.run(store.activate(first_digest))
    asyncio.run(store.activate(second_digest))
    assert store.resolve_active()["release_sha256"] == second_digest
    assert json.loads((store.root / "current.json").read_text(encoding="utf-8")) == {"active": second_digest, "previous": first_digest}
    asyncio.run(store.rollback())
    assert store.resolve_active()["release_sha256"] == first_digest
    assert probe.await_count == 3
    assert not list(store.root.glob("native-current-*.tmp"))


@pytest.mark.parametrize("failure", ["startup", "version"])
def test_native_failed_activation_preserves_the_existing_release_and_reports_failure(tmp_path, monkeypatch, failure):
    from unittest.mock import AsyncMock

    from app.core.native import distribution

    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    first_archive, first_digest = _native_release_archive(tmp_path)
    second_archive, second_digest = _native_release_archive(tmp_path, "0.2.0-dev")
    store.install_archive(first_archive, first_digest)
    store.install_archive(second_archive, second_digest)
    monkeypatch.setattr(distribution, "probe_native_binary", AsyncMock(return_value="148.0.7778.96"))
    asyncio.run(store.activate(first_digest))
    before = (store.root / "current.json").read_bytes()
    monkeypatch.setattr(distribution, "probe_native_binary", AsyncMock(
        side_effect=RuntimeError("owned startup failed") if failure == "startup" else None,
        return_value="unexpected"))
    with pytest.raises((RuntimeError, ValueError)):
        asyncio.run(store.activate(second_digest))
    assert (store.root / "current.json").read_bytes() == before
    assert store.resolve_active()["release_sha256"] == first_digest


def test_native_binary_selection_does_not_fallback_from_corrupt_state_or_allow_profile_downgrades(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    from app.core.native import distribution

    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    with pytest.raises(ValueError, match="No managed"):
        store.resolve_active()
    archive, first = _native_release_archive(tmp_path)
    store.install_archive(archive, first)
    monkeypatch.setattr(distribution, "probe_native_binary", AsyncMock(return_value="148.0.7778.96"))
    asyncio.run(store.activate(first))
    archive, newer = _native_release_archive(tmp_path, "0.2.0-dev", {"chromium_version": "149.0.0.0"})
    store.install_archive(archive, newer)
    monkeypatch.setattr(distribution, "probe_native_binary", AsyncMock(return_value="149.0.0.0"))
    asyncio.run(store.activate(newer))
    with pytest.raises(ValueError, match="downgrade is blocked"):
        asyncio.run(store.rollback())
    (store.root / "current.json").write_text('{"active":"unsafe"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid"):
        store.resolve_active()


def test_native_managed_selection_uses_verified_active_release_not_explicit_fallback(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    from app.core.native import distribution

    archive, digest = _native_release_archive(tmp_path)
    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    store.install_archive(archive, digest)
    monkeypatch.setattr(distribution, "probe_native_binary", AsyncMock(return_value="148.0.7778.96"))
    asyncio.run(store.activate(digest))
    settings = {"binary_source": "managed", "binary_store": str(store.root), "executable_path": str(archive)}
    selected = distribution.resolve_native_executable(settings)
    assert selected == Path(store.resolve_active()["executable_path"])
    selected.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        distribution.resolve_native_executable(settings)
    assert archive.is_file()


@pytest.mark.parametrize("settings", [
    {"binary_source": "unknown"}, {"binary_source": "managed"},
    {"binary_source": "managed", "binary_store": "relative"},
    {"executable_path": "relative.exe"}, {"executable_path": True}, {},
])
def test_native_binary_selection_rejects_invalid_or_missing_source(settings):
    from app.core.native.distribution import resolve_native_executable

    with pytest.raises(ValueError):
        resolve_native_executable(settings)


def test_native_explicit_selection_preserves_existing_absolute_executable_contract(tmp_path):
    from app.core.native.distribution import resolve_native_executable

    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"explicit")
    assert resolve_native_executable({"executable_path": str(executable)}) == executable


def _native_release_bridge(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.ui.bridge.browser_settings import BrowserSettingsBridge

    bridge = SimpleNamespace(_engine="native", _native={"binary_source": "managed", "binary_store": str(tmp_path / "store")},
        nativeBinaryStore=str(tmp_path / "store"), _native_release_running=False, _native_release_report="previous",
        changed=SimpleNamespace(emit=Mock()), _emit_message=Mock(), nativeReleaseCompleted=SimpleNamespace(emit=Mock()))
    bridge._native_settings_signature = lambda: BrowserSettingsBridge._native_settings_signature(bridge)
    bridge._apply_native_release = lambda signature, report: BrowserSettingsBridge._apply_native_release(bridge, signature, report)
    bridge.nativeReleaseCompleted.emit.side_effect = bridge._apply_native_release
    return bridge


def test_native_release_activation_invalidates_inflight_compatibility_result(tmp_path):
    from app.ui.bridge.browser_settings import BrowserSettingsBridge

    bridge = _native_release_bridge(tmp_path)
    bridge._native_probe_running = True
    signature = bridge._native_settings_signature()
    bridge._apply_native_release(signature, "Activated Native 0.1.0-preview")
    assert bridge._compatibility_report == "Native release changed; run compatibility check again"
    BrowserSettingsBridge._apply_native_compatibility(bridge, signature, "old release was verified")
    assert not bridge._native_probe_running
    assert bridge._compatibility_report == "Native settings or release changed during check; run it again"


@pytest.mark.parametrize("engine,busy,source", [("camoufox", False, "managed"), ("native", True, "managed"), ("native", False, "explicit")])
def test_native_release_ui_does_not_run_for_another_engine_busy_operation_or_explicit_source(tmp_path, monkeypatch, engine, busy, source):
    from unittest.mock import Mock
    from app.ui.bridge import browser_settings

    bridge = _native_release_bridge(tmp_path)
    bridge._engine, bridge._native_release_running = engine, busy
    bridge._native["binary_source"] = source
    thread = Mock()
    monkeypatch.setattr(browser_settings.threading, "Thread", thread)
    browser_settings.BrowserSettingsBridge._run_native_release(bridge, "rollback")
    thread.assert_not_called()
    if source == "explicit":
        assert "Select Managed release" in bridge._native_release_report


@pytest.mark.parametrize("checksum", ["", "unsafe", "A" * 64])
def test_native_release_ui_rejects_bad_checksum_before_creating_store(tmp_path, checksum):
    from app.ui.bridge.browser_settings import BrowserSettingsBridge

    archive = tmp_path / "owned.tar.gz"
    archive.write_bytes(b"invalid")
    bridge = _native_release_bridge(tmp_path)
    BrowserSettingsBridge._run_native_release(bridge, "install", str(archive), checksum)
    assert "SHA-256" in bridge._native_release_report
    assert not bridge._native_release_running and not (tmp_path / "store").exists()


def test_native_release_ui_thread_start_failure_releases_busy_state_without_mutation(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from app.ui.bridge import browser_settings

    bridge = _native_release_bridge(tmp_path)
    monkeypatch.setattr(browser_settings.threading, "Thread", Mock(side_effect=RuntimeError("owned thread limit")))
    browser_settings.BrowserSettingsBridge._run_native_release(bridge, "rollback")
    assert not bridge._native_release_running
    assert "Cannot start Native release operation" in bridge._native_release_report
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize("action,failed,changed", [("install", False, False), ("rollback", False, False),
                                                  ("install", True, False), ("install", False, True)])
def test_native_release_ui_runs_verified_store_operations_and_preserves_changed_settings(tmp_path, monkeypatch, action, failed, changed):
    from unittest.mock import AsyncMock, Mock
    from types import SimpleNamespace
    from PyQt6.QtCore import QUrl
    from app.core.native import distribution
    from app.ui.bridge import browser_settings

    archive = tmp_path / "owned.tar.gz"
    archive.write_bytes(b"owned")
    bridge = _native_release_bridge(tmp_path)
    release = {"native_version": "0.1.0-preview", "chromium_version": "148.0.7778.96",
               "build_kind": "upstream-bootstrap", "release_sha256": "a" * 64}
    async def activated(*args):
        if failed:
            raise ValueError("owned startup failed")
        if changed:
            bridge._native["binary_store"] = str(tmp_path / "other-store")
        return release
    store = SimpleNamespace(root=tmp_path / "store", install_archive=Mock(return_value=release),
                            activate=AsyncMock(side_effect=activated), rollback=AsyncMock(side_effect=activated))
    factory = Mock(return_value=store)
    monkeypatch.setattr(distribution, "NativeBinaryStore", factory)
    thread = Mock(side_effect=lambda **kwargs: SimpleNamespace(start=kwargs["target"]))
    monkeypatch.setattr(browser_settings.threading, "Thread", thread)
    browser_settings.BrowserSettingsBridge._run_native_release(bridge, action, QUrl.fromLocalFile(str(archive)).toString(), "a" * 64)
    assert not bridge._native_release_running
    assert thread.call_args.kwargs["daemon"] is False
    assert bridge._native["binary_source"] == "managed"
    if action == "install":
        store.install_archive.assert_called_once_with(archive, "a" * 64)
        store.activate.assert_awaited_once_with("a" * 64)
    else:
        store.install_archive.assert_not_called()
        store.rollback.assert_awaited_once_with()
    if failed:
        assert "owned startup failed" in bridge._native_release_report
        assert bridge._native_release_report.startswith("Blocked:")
    else:
        assert "upstream-bootstrap" in bridge._native_release_report
    if changed:
        assert "Settings changed" in bridge._native_release_report
        assert bridge._native["binary_store"] == str(tmp_path / "other-store")
