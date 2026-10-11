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
        "Native settings changed during check; run it again" if changed else "verified owned startup")


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


@pytest.mark.parametrize("version,supported", [((3, 12, 0), False), ((3, 12, 10), False), ((3, 12, 11), True),
                                             ((3, 13, 0), False), ((3, 13, 4), True), ((3, 14, 0), True)])
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
