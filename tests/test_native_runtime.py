import asyncio
import sys
from pathlib import Path

import pytest

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime, NativeRuntimeError


@pytest.mark.parametrize("length", [90, 130, 150, 170])
@pytest.mark.parametrize("name", ["desktop", "mobile"])
def test_native_storage_matrix_uses_exact_distinct_owned_paths(length, name):
    from pathlib import PureWindowsPath
    from scripts.verify_native_storage_paths import profile_for_length

    root = PureWindowsPath("D:/Native/np-owned")
    profile = profile_for_length(root, length, name)
    assert len(str(profile)) == length
    assert profile.relative_to(root).parts[-2:] == (name, "native")


def test_native_storage_matrix_rejects_work_directory_that_would_skip_short_cases():
    from pathlib import PureWindowsPath
    from scripts.verify_native_storage_paths import profile_for_length

    with pytest.raises(ValueError, match="cannot accommodate"):
        profile_for_length(PureWindowsPath("D:/" + "p" * 90), 90, "desktop")


@pytest.mark.parametrize("failure", ["", "storage", "delete"])
def test_native_storage_matrix_checks_every_phase_and_keeps_failures(monkeypatch, failure):
    import asyncio
    from pathlib import PureWindowsPath
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts import verify_native_storage_paths as probe

    runtimes = []
    def runtime(profile, executable, config):
        async def evaluate(script, *args):
            if script == probe.STORAGE:
                if failure == "storage":
                    raise RuntimeError("owned storage error")
                return probe.expected_storage(args[0] or "replacement")
            return failure != "delete"
        page = SimpleNamespace(goto=AsyncMock(), evaluate=AsyncMock(side_effect=evaluate))
        instance = SimpleNamespace(start=AsyncMock(return_value=SimpleNamespace(pages=[page])), close=AsyncMock())
        runtimes.append(instance)
        return instance

    monkeypatch.setattr(probe, "NativeRuntime", runtime)
    report = {"checks": []}
    asyncio.run(probe.verify(PureWindowsPath("D:/owned/chrome.exe"), PureWindowsPath("D:/np-owned"),
                            "http://127.0.0.1:1", report))
    assert len(report["checks"]) == 8
    assert report["passed"] is (not failure)
    assert {check["environment"] for check in report["checks"]} == {"desktop", "mobile_web"}
    for check, instance in zip(report["checks"], runtimes):
        assert check["passed"] is (not failure)
        assert [phase["name"] for phase in check["phases"]] == (
            [] if failure == "storage" else ["create", "replace"] if failure else ["create", "replace", "restart"])
        assert instance.close.await_count >= 2


def test_native_privacy_keys_persist_and_are_not_shared_between_profiles(tmp_path):
    from app.core.native.identity import IDENTITY_FILE, load_or_create_identity

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    identity = load_or_create_identity(first)
    assert load_or_create_identity(first).seed == identity.seed
    assert load_or_create_identity(second).seed != identity.seed
    assert len(identity.seed) == 32
    assert identity.seed.hex() not in repr(identity)
    assert not (first / IDENTITY_FILE).read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows ACL creation")
@pytest.mark.parametrize("existing", [False, True])
def test_native_windows_identity_has_private_acl_and_preserves_legacy_bytes(tmp_path, existing):
    import json
    import os
    import subprocess
    from PyQt6.QtCore import QFile, QFileDevice, QIODevice
    from app.core.native.identity import IDENTITY_FILE, load_or_create_identity

    path = tmp_path / IDENTITY_FILE
    original = b'{ "seed": "' + b"ab" * 32 + b'", "schema": 1 }\n'
    if existing:
        source = QFile(str(path))
        assert source.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.NewOnly,
            QFileDevice.Permission.ReadOwner | QFileDevice.Permission.WriteOwner | QFileDevice.Permission.ReadOther)
        assert source.write(original) == len(original)
        source.close()
    identity = load_or_create_identity(tmp_path)
    contents = path.read_bytes()
    if existing:
        assert contents == original and identity.seed == bytes.fromhex("ab" * 32)
    assert load_or_create_identity(tmp_path).seed == identity.seed
    assert path.read_bytes() == contents
    query = (
        "$ErrorActionPreference='Stop'; $acl=Get-Acl -LiteralPath $env:GLINT_OWNED_KEY; "
        "$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
        "$foreign=@($acl.Access | Where-Object { $_.AccessControlType -eq 'Allow' -and "
        "($_.FileSystemRights.value__ -band 7) -ne 0 -and "
        "$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -ne $sid }); "
        "[pscustomobject]@{protected=$acl.AreAccessRulesProtected; foreign=$foreign.Count} | ConvertTo-Json -Compress"
    )
    observed = json.loads(subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", query],
        env={**os.environ, "GLINT_OWNED_KEY": str(path)}, text=True, timeout=20))
    assert observed == {"protected": True, "foreign": 0}
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows identity publication")
@pytest.mark.parametrize("failure", ["volume", "open", "write", "flush", "fsync", "rename"])
@pytest.mark.parametrize("existing", [False, True])
def test_native_windows_identity_write_failure_never_rotates_or_leaves_temporary_keys(tmp_path, monkeypatch, failure, existing):
    from unittest.mock import Mock
    from app.core.native import identity as module

    path = tmp_path / module.IDENTITY_FILE
    original = b'{"schema":1,"seed":"' + b"ab" * 32 + b'"}'
    if existing:
        path.write_bytes(original)
    if failure == "volume":
        monkeypatch.setattr(module, "_require_windows_acls", Mock(side_effect=OSError("owned ACL query failure")))
    elif failure in {"open", "write", "flush"}:
        original_file = module.QFile

        class FailingFile(original_file):
            def open(self, *args):
                return False if failure == "open" else super().open(*args)

            def write(self, payload):
                return -1 if failure == "write" else super().write(payload)

            def flush(self):
                return False if failure == "flush" else super().flush()

        monkeypatch.setattr(module, "QFile", FailingFile)
    elif failure == "fsync":
        monkeypatch.setattr(module.os, "fsync", Mock(side_effect=OSError("owned sync failure")))
    else:
        monkeypatch.setattr(module.os, "replace" if existing else "rename", Mock(side_effect=OSError("owned publication failure")))
    with pytest.raises(OSError):
        module.load_or_create_identity(tmp_path)
    assert path.read_bytes() == original if existing else not path.exists()
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows filesystem ACL flags")
@pytest.mark.parametrize("failure", ["mount", "query", "unsupported", None])
def test_native_windows_identity_requires_confirmed_persistent_acls(tmp_path, monkeypatch, failure):
    import ctypes
    from unittest.mock import Mock
    from types import SimpleNamespace
    from app.core.native.identity import _require_windows_acls

    def mount(_directory, volume, _length):
        volume.value = "C:\\"
        return failure != "mount"

    def query(_volume, _name, _size, _serial, _component, flags, _filesystem, _length):
        flags._obj.value = 0 if failure == "unsupported" else 8
        return failure != "query"

    kernel = SimpleNamespace(GetVolumePathNameW=Mock(side_effect=mount), GetVolumeInformationW=Mock(side_effect=query))
    monkeypatch.setattr(ctypes, "WinDLL", Mock(return_value=kernel))
    if failure is None:
        _require_windows_acls(tmp_path)
    else:
        with pytest.raises(OSError, match="filesystem|ACL"):
            _require_windows_acls(tmp_path)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows atomic identity publication")
@pytest.mark.parametrize("collision", ["temporary", "identity"])
def test_native_windows_identity_never_overwrites_unowned_collision_files(tmp_path, monkeypatch, collision):
    from app.core.native import identity as module

    path = tmp_path / module.IDENTITY_FILE
    temporary = tmp_path / ("." + module.IDENTITY_FILE + ".owned-collision.tmp")
    monkeypatch.setattr(module.secrets, "token_hex", lambda _size: "owned-collision")
    if collision == "temporary":
        temporary.write_bytes(b"unowned temporary file")
    else:
        def publish(_source, _target):
            path.write_bytes(b"another owner's identity")
            raise FileExistsError("Identity appeared during publication")

        monkeypatch.setattr(module.os, "rename", publish)
    with pytest.raises(OSError):
        module.load_or_create_identity(tmp_path)
    if collision == "temporary":
        assert temporary.read_bytes() == b"unowned temporary file" and not path.exists()
    else:
        assert path.read_bytes() == b"another owner's identity" and not temporary.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows identity ACL failure")
@pytest.mark.parametrize("existing", [False, True])
def test_native_identity_acl_failure_aborts_before_driver_and_releases_owner(tmp_path, monkeypatch, existing):
    import json
    from unittest.mock import Mock
    from PyQt6.QtCore import QLockFile
    from app.core.native import identity, runtime as module

    (tmp_path / "camouflow-native.json").write_text(json.dumps({"engine": "camouflow-native", "schema": 1}), encoding="utf-8")
    path = tmp_path / identity.IDENTITY_FILE
    original = b'{"schema":1,"seed":"' + b"ab" * 32 + b'"}'
    if existing:
        path.write_bytes(original)
    monkeypatch.setattr(identity, "_save_windows_identity", Mock(side_effect=PermissionError("Owned ACL failure")))
    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    runtime = NativeRuntime(tmp_path, Path(__file__).resolve(), NativeConfiguration())
    with pytest.raises(PermissionError, match="ACL"):
        asyncio.run(runtime.start())
    driver.assert_not_called()
    assert not runtime.has_resources and runtime._privacy_identity is None
    assert path.read_bytes() == original if existing else not path.exists()
    lock = QLockFile(str(tmp_path / "native-runtime.lock"))
    assert lock.tryLock(0)
    lock.unlock()


def test_native_privacy_loader_rejects_shared_hard_links_without_replacing_keys(tmp_path):
    import os

    from app.core.native.identity import IDENTITY_FILE, load_or_create_identity

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    load_or_create_identity(first)
    original = first / IDENTITY_FILE
    linked = second / IDENTITY_FILE
    before = original.read_bytes()
    os.link(original, linked)
    for profile in (first, second):
        with pytest.raises(ValueError, match="hard linked"):
            load_or_create_identity(profile)
    assert original.read_bytes() == linked.read_bytes() == before
    linked.unlink()
    assert load_or_create_identity(first).seed != load_or_create_identity(second).seed


def test_native_hard_linked_key_aborts_before_browser_driver_and_releases_profile_lock(tmp_path, monkeypatch):
    import json
    import os
    from unittest.mock import Mock

    from PyQt6.QtCore import QLockFile

    from app.core.native import runtime as module
    from app.core.native.identity import IDENTITY_FILE, load_or_create_identity

    profile = tmp_path / "owned"
    profile.mkdir()
    (profile / "camouflow-native.json").write_text(
        json.dumps({"engine": "camouflow-native", "schema": 1}), encoding="utf-8")
    load_or_create_identity(profile)
    os.link(profile / IDENTITY_FILE, tmp_path / "shared-key")
    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    runtime = NativeRuntime(profile, Path(__file__), NativeConfiguration())
    with pytest.raises(ValueError, match="hard linked"):
        asyncio.run(runtime.start())
    driver.assert_not_called()
    assert not runtime.has_resources and runtime._privacy_identity is None
    lock = QLockFile(str(profile / "native-runtime.lock"))
    assert lock.tryLock(0)
    lock.unlock()


def test_native_privacy_derivation_is_stable_and_separated_by_profile_partition_and_surface(tmp_path):
    from app.core.native.identity import load_or_create_identity

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    identity = load_or_create_identity(first)
    key = identity.derive(b"owned-browser-partition-A", "canvas")
    assert len(key) == 32 and key != identity.seed
    assert load_or_create_identity(first).derive(b"owned-browser-partition-A", "canvas") == key
    assert identity.derive(b"owned-browser-partition-B", "canvas") != key
    assert identity.derive(b"owned-browser-partition-A", "audio") != key
    assert load_or_create_identity(second).derive(b"owned-browser-partition-A", "canvas") != key


def test_native_privacy_derivation_matches_independent_dotnet_hmac_vector():
    from app.core.native.identity import NativePrivacyIdentity

    assert NativePrivacyIdentity(bytes(range(32))).derive(b"owned-browser-partition-A", "canvas").hex() == (
        "16ac09b09ddeb0bc278456d1e474d4d1fa4b6135a7529f05dc95391936c630fc")


@pytest.mark.parametrize("surface,expected", [
    ("canvas", "20dce1593e6c4c336c2fd3d3d280bbb25897e5535eb281995f1e258a92dd57f2"),
    ("webgl", "2d9d6bba187081cec70f0cfb691f45f0edbdf6102225ebbdc0ead57d6e5f0ef3"),
    ("webgpu", "c06c3fb80ba7ff2d923ae600f5bec7177a82629b0e2d1154794b9b2bc26e3fbd"),
    ("audio", "967498cf8b7b8528a376c6e8b2579e22f9b476d87171ac51527da8e07733ef17"),
])
def test_native_profile_identity_reference_matches_native_candidate_vectors(surface, expected):
    from app.core.native.identity import NativePrivacyIdentity
    from scripts.verify_native_profile_identity_draft import PATCH, reference_vectors

    identity = NativePrivacyIdentity(bytes(range(32)))
    key = identity.derive_profile_identity(b"owned-browser-partition-A", surface)
    assert key.hex() == expected == reference_vectors()[surface]
    assert expected in PATCH.read_text(encoding="utf-8-sig")
    assert key == identity.derive_profile_identity(b"owned-browser-partition-B", surface)
    assert key == identity.derive_profile_identity(b"a" * 8192, surface)
    assert key != identity.derive(b"owned-browser-partition-A", surface)
    assert key != NativePrivacyIdentity(bytes(reversed(range(32)))).derive_profile_identity(
        b"owned-browser-partition-A", surface)


def test_native_profile_identity_reference_survives_reload_with_independent_owned_roots(tmp_path):
    from app.core.native.identity import load_or_create_identity

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    identity = load_or_create_identity(first)
    keys = {surface: identity.derive_profile_identity(b"owned-browser-partition", surface)
            for surface in ("canvas", "webgl", "webgpu", "audio")}
    assert len(set(keys.values())) == 4
    assert identity.seed not in keys.values()
    reloaded = load_or_create_identity(first)
    independent = load_or_create_identity(second)
    for surface, expected in keys.items():
        assert reloaded.derive_profile_identity(b"different-browser-partition", surface) == expected
        assert independent.derive_profile_identity(b"owned-browser-partition", surface) != expected


@pytest.mark.parametrize("method", ["derive", "derive_profile_identity"])
@pytest.mark.parametrize("partition,surface", [(b"", "canvas"), (b"a" * 8193, "canvas"),
                                               ("https://example.test", "canvas"), (bytearray(b"a"), "canvas"),
                                               (b"a", "unknown"), (b"a", "Canvas"), (b"a", None)])
def test_native_privacy_derivation_rejects_untrusted_shapes(partition, surface, method):
    from app.core.native.identity import NativePrivacyIdentity

    with pytest.raises(ValueError):
        getattr(NativePrivacyIdentity(bytes(range(32))), method)(partition, surface)


@pytest.mark.parametrize("payload", ['{}', '{"schema":true,"seed":"' + 'a' * 64 + '"}',
                                   '{"schema":2,"seed":"' + 'a' * 64 + '"}',
                                   '{"schema":1,"seed":"' + 'A' * 64 + '"}',
                                   '{"schema":1,"seed":"aa"}', 'x' * 257])
def test_native_privacy_invalid_key_never_silently_rotates(tmp_path, payload):
    from app.core.native.identity import IDENTITY_FILE, load_or_create_identity

    path = tmp_path / IDENTITY_FILE
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match="invalid"):
        load_or_create_identity(tmp_path)
    assert path.read_text(encoding="utf-8") == payload


def test_native_privacy_key_failure_releases_profile_without_starting_driver(tmp_path, monkeypatch):
    import json
    from unittest.mock import Mock
    from PyQt6.QtCore import QLockFile
    from app.core.native import runtime as module
    from app.core.native.identity import IDENTITY_FILE

    profile = tmp_path / "owned"
    profile.mkdir()
    (profile / "camouflow-native.json").write_text(json.dumps({"engine": "camouflow-native", "schema": 1}), encoding="utf-8")
    (profile / IDENTITY_FILE).write_text("invalid", encoding="utf-8")
    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    runtime = NativeRuntime(profile, Path(__file__), NativeConfiguration())
    with pytest.raises(ValueError, match="identity is invalid"):
        asyncio.run(runtime.start())
    driver.assert_not_called()
    assert not runtime.has_resources and runtime._privacy_identity is None
    lock = QLockFile(str(profile / "native-runtime.lock"))
    assert lock.tryLock(0)
    lock.unlock()


@pytest.mark.parametrize("values", [{"cpu_limit": True}, {"cpu_limit": 65}, {"cpu_limit": -1},
                                   {"memory_limit": 3}, {"memory_limit": float("nan")}, {"memory_limit": True},
                                   {"fonts": "Arial"}, {"fonts": ["Arial", "arial"]}, {"fonts": ["Tahoma"]},
                                   {"fonts": ["Arial", "Bad,Font"]}, {"fonts": ["Arial", " Bad"]},
                                   {"restrict_webrtc": "true"}, {"conceal_automation": 1}, {"unknown": True}])
def test_native_privacy_policy_rejects_invalid_controls_without_silent_normalization(values):
    from app.core.native.privacy import NativePrivacyPolicy

    with pytest.raises(ValueError):
        NativePrivacyPolicy.from_dict(values)


@pytest.mark.parametrize("mode", ["Native", "", "rgb", None, True, 1, [], {}])
def test_native_font_rasterization_rejects_invalid_modes(mode):
    from app.core.native.privacy import NativePrivacyPolicy

    with pytest.raises(ValueError, match="rasterization"):
        NativePrivacyPolicy.from_dict({"font_rasterization": mode})


@pytest.mark.parametrize("preset,arguments", [
    ("native", []), ("gamma-1400", ["--text-gamma=1.4"]), ("gamma-2200", ["--text-gamma=2.2"]),
    ("contrast-300", ["--text-contrast=0.3"]), ("contrast-500", ["--text-contrast=0.5"]),
    ("gamma-1400-contrast-300", ["--text-gamma=1.4", "--text-contrast=0.3"]),
    ("gamma-1400-contrast-500", ["--text-gamma=1.4", "--text-contrast=0.5"]),
    ("gamma-2200-contrast-300", ["--text-gamma=2.2", "--text-contrast=0.3"]),
    ("gamma-2200-contrast-500", ["--text-gamma=2.2", "--text-contrast=0.5"]),
])
def test_native_text_tuning_prepares_only_bounded_upstream_arguments(preset, arguments, tmp_path, monkeypatch):
    from dataclasses import asdict
    from unittest.mock import Mock
    from app.core.native import runtime as module
    from app.core.native.privacy import NativePrivacyPolicy

    policy = NativePrivacyPolicy.from_dict({"text_tuning": preset})
    assert NativePrivacyPolicy.from_dict(asdict(policy)) == policy
    assert policy.prepared_arguments() == arguments
    assert NativeConfiguration(privacy_policy=policy).environment_settings()["privacy_policy"].get("text_tuning", "native") == preset
    assert policy.required_capabilities() == ([] if preset == "native" else ["text-rendering"])
    if preset == "native":
        assert policy == NativePrivacyPolicy()
        return
    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    runtime = NativeRuntime(tmp_path / "not-created", tmp_path / "unknown.exe", NativeConfiguration(privacy_policy=policy))
    with pytest.raises(ValueError, match="verified"):
        asyncio.run(runtime.start())
    driver.assert_not_called()
    assert not runtime.has_resources and not runtime.profile_dir.exists()


@pytest.mark.parametrize("preset", [None, True, 1, 1.4, [], {}, "", "off", "gamma-2000", "contrast-400", "--text-gamma=1.4"])
def test_native_text_tuning_rejects_unknown_or_unbounded_inputs(preset):
    from app.core.native.privacy import NativePrivacyPolicy

    with pytest.raises(ValueError, match="text tuning"):
        NativePrivacyPolicy.from_dict({"text_tuning": preset})


def test_native_text_tuning_default_serialization_keeps_legacy_policy_shape_and_pins_native():
    from app.core.native.privacy import NativePrivacyPolicy

    policy = NativePrivacyPolicy(fonts=("Arial", "Courier New"))
    serialized = policy.to_dict()
    assert set(serialized) == {"cpu_limit", "memory_limit", "fonts", "restrict_webrtc", "conceal_automation",
                               "native_user_agent", "font_rasterization"}
    assert NativePrivacyPolicy.from_dict(serialized) == policy
    serialized["fonts"].append("Tahoma")
    assert policy.fonts == ("Arial", "Courier New")
    pinned = NativeConfiguration(privacy_policy=policy).environment_settings()
    effective = NativeConfiguration.from_settings({"privacy_policy": {"text_tuning": "gamma-2200"}, **pinned})
    assert effective.privacy_policy.text_tuning == "native"


@pytest.mark.parametrize("rasterization", ["aliased", "grayscale", "cleartype-rgb", "cleartype-bgr"])
@pytest.mark.parametrize("preset", ["gamma-1400", "gamma-2200", "contrast-300", "contrast-500",
    "gamma-1400-contrast-300", "gamma-1400-contrast-500", "gamma-2200-contrast-300", "gamma-2200-contrast-500"])
def test_native_text_tuning_refuses_unverified_rasterization_composition(rasterization, preset):
    from app.core.native.privacy import NativePrivacyPolicy

    with pytest.raises(ValueError, match="requires Native"):
        NativePrivacyPolicy.from_dict({"font_rasterization": rasterization, "text_tuning": preset})


@pytest.mark.parametrize("mode", ["native", "aliased", "grayscale", "cleartype-rgb", "cleartype-bgr"])
def test_native_font_rasterization_drafts_never_enable_unverified_runtime(mode, tmp_path, monkeypatch):
    from dataclasses import asdict
    from unittest.mock import Mock

    from app.core.native import runtime as module
    from app.core.native.privacy import NativePrivacyPolicy

    policy = NativePrivacyPolicy.from_dict({"font_rasterization": mode})
    assert NativePrivacyPolicy.from_dict(asdict(policy)) == policy
    configuration = NativeConfiguration(privacy_policy=policy)
    if mode == "native":
        assert policy == NativePrivacyPolicy()
        assert policy.prepared_arguments() == []
        assert policy.required_capabilities() == []
        configuration.launch_arguments()
        return
    assert policy.prepared_arguments() == ["--glint-windows-font-rasterization=" + mode]
    assert policy.required_capabilities() == ["font-rasterization"]
    with pytest.raises(ValueError, match="verified"):
        configuration.launch_arguments()
    with pytest.raises(ValueError, match="verified"):
        configuration.context_options()
    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    runtime = NativeRuntime(tmp_path / "not-created", Path(__file__), configuration)
    with pytest.raises(ValueError, match="verified"):
        asyncio.run(runtime.start())
    driver.assert_not_called()
    assert not runtime.has_resources and not runtime.profile_dir.exists()


def test_native_privacy_policy_prepares_exact_cpp_switches_without_activating_them(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from app.core.native import runtime as module
    from app.core.native.privacy import NativePrivacyPolicy

    policy = NativePrivacyPolicy(cpu_limit=4, memory_limit=.25, fonts=("Arial", "Segoe UI"),
        restrict_webrtc=True, conceal_automation=True, native_user_agent=True)
    assert policy.required_capabilities() == ["hardware", "fonts", "webrtc", "automation", "identity"]
    assert policy.prepared_arguments() == ["--camouflow-hardware-concurrency=4", "--camouflow-device-memory=0.25",
        "--camouflow-font-families=Arial,Segoe UI", "--camouflow-webrtc-ip-handling-policy=disable_non_proxied_udp",
        "--enable-blink-features=CamouFlowAutomationConcealed", "--camouflow-native-user-agent"]
    configuration = NativeConfiguration(privacy_policy=policy)
    configuration.validate()
    with pytest.raises(ValueError, match="verified"):
        configuration.context_options()
    with pytest.raises(ValueError, match="verified"):
        configuration.launch_arguments()
    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    runtime = NativeRuntime(tmp_path / "not-created", Path(__file__), configuration)
    with pytest.raises(ValueError, match="verified"):
        asyncio.run(runtime.start())
    driver.assert_not_called()
    assert not runtime.has_resources and not runtime.profile_dir.exists()


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


@pytest.mark.parametrize("key,choices", [
    ("color_scheme", ("light", "dark")), ("reduced_motion", ("no-preference", "reduce")),
    ("forced_colors", ("none", "active")), ("contrast", ("no-preference", "more")),
])
def test_native_media_preferences_are_explicit_context_options(key, choices):
    from dataclasses import asdict
    from app.core.native.configuration import MEDIA_PREFERENCES
    from app.storage.db import NATIVE_DEFAULTS

    assert NATIVE_DEFAULTS[key] == "" and MEDIA_PREFERENCES[key] == choices
    assert key not in NativeConfiguration().context_options()
    for value in choices:
        configuration = NativeConfiguration.from_settings({key: value})
        assert configuration.context_options()[key] == value
        assert asdict(configuration)[key] == value
        assert configuration.launch_arguments() == NativeConfiguration().launch_arguments()


@pytest.mark.parametrize("key", ["color_scheme", "reduced_motion", "forced_colors", "contrast"])
@pytest.mark.parametrize("value", [None, True, 0, [], {}, "system", "DARK", " light"])
def test_native_media_preferences_reject_invalid_values_without_fallback(key, value):
    with pytest.raises(ValueError, match="media preference"):
        NativeConfiguration.from_settings({key: value})
    with pytest.raises(ValueError, match="media preference"):
        NativeConfiguration(**{key: value}).context_options()


@pytest.mark.parametrize("key,selected,other", [
    ("color_scheme", "dark", "light"), ("reduced_motion", "reduce", "no-preference"),
    ("forced_colors", "active", "none"), ("contrast", "more", "no-preference"),
])
@pytest.mark.parametrize("mutation", [None, "missing", "wrong", "both", "neither", "integer", "extra", "malformed"])
def test_native_media_diagnostics_require_exact_native_observations(key, selected, other, mutation):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC"}
    values = {selected: True, other: False}
    if mutation == "wrong":
        values = {selected: False, other: True}
    elif mutation == "both":
        values[other] = True
    elif mutation == "neither":
        values[selected] = False
    elif mutation == "integer":
        values[selected] = 1
    elif mutation == "extra":
        values["invented"] = False
    elif mutation == "malformed":
        values = []
    if mutation != "missing":
        document["mediaPreferences"] = {key: values}
    observed = {"document": document, "worker": dict(document)}
    configuration = NativeConfiguration.from_settings({key: selected})
    expected = [] if mutation is None else ["Document media preference differs from configured " + key]
    assert compare_observed(configuration, observed) == expected
    assert compare_observed(NativeConfiguration(), observed) == []


@pytest.mark.parametrize("key", ["language", "languages", "hardwareConcurrency", "deviceMemory", "timezone", "intlLocale", "userAgentData", "userAgentHighEntropy"])
def test_native_diagnostics_detects_document_worker_disagreement(key):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC"}
    observed = {"document": document, "worker": dict(document)}
    assert compare_observed(NativeConfiguration(), observed) == []
    observed["worker"][key] = "inconsistent"
    assert compare_observed(NativeConfiguration(), observed) == [f"Document and dedicated worker disagree on {key}"]


def coherent_identity_observations():
    import copy

    values = {"userAgent": "Mozilla/5.0 Chrome/148.0.0.0 Safari/537.36", "platform": "Win32",
              "language": "en-US", "languages": ["en-US", "en"], "timezone": "UTC", "intlLocale": "en-US",
              "hardwareConcurrency": 12, "deviceMemory": 8,
              "userAgentData": {"platform": "Windows", "mobile": False,
                                "brands": [{"brand": "Chromium", "version": "148"}]},
              "userAgentHighEntropy": {"fullVersionList": [{"brand": "Chromium", "version": "148.0.7778.96"}],
                                       "brands": [{"brand": "Chromium", "version": "148"}],
                                       "platform": "Windows", "mobile": False}}
    return {"document": values, "worker": copy.deepcopy(values)}


@pytest.mark.parametrize("scope", ["document", "worker"])
@pytest.mark.parametrize("key,value", [
    ("hardwareConcurrency", None), ("hardwareConcurrency", True), ("hardwareConcurrency", 0),
    ("hardwareConcurrency", -1), ("hardwareConcurrency", 1.5), ("hardwareConcurrency", "12"),
    ("deviceMemory", True), ("deviceMemory", 0), ("deviceMemory", -1),
    ("deviceMemory", "8"), ("deviceMemory", float("nan")), ("deviceMemory", float("inf")),
    ("deviceMemory", 10 ** 400),
])
def test_native_identity_audit_rejects_invalid_hardware_observations(scope, key, value):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    observed[scope][key] = value
    assert audit_observed_identity(observed, "148.0.7778.96")


def test_native_identity_audit_preserves_explicit_device_memory_unavailability():
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    for values in observed.values():
        values["deviceMemory"] = None
        values["hardwareConcurrency"] = 128
    assert audit_observed_identity(observed, "148.0.7778.96") == []
    del observed["worker"]["deviceMemory"]
    assert audit_observed_identity(observed, "148.0.7778.96") == ["Worker device memory observation is invalid"]


def test_native_identity_audit_preserves_reduced_ua_and_real_full_version():
    from app.core.native.diagnostics import audit_observed_identity

    assert audit_observed_identity(coherent_identity_observations(), "148.0.7778.96") == []


def coherent_request_identity_headers():
    return {"User-Agent": coherent_identity_observations()["document"]["userAgent"],
            "Accept-Language": "en-US,en;q=0.9", "Sec-CH-UA-Platform": '"Windows"',
            "Sec-CH-UA-Mobile": "?0"}


def test_native_request_identity_audit_compares_emitted_values_without_inferring_tls():
    from app.core.native.diagnostics import audit_observed_request_identity

    observed = coherent_identity_observations()
    headers = coherent_request_identity_headers()
    assert audit_observed_request_identity(headers, observed) == []
    observed["document"]["language"] = "de-DE"
    headers["Accept-Language"] = "de-DE,de;q=0.9"
    assert audit_observed_request_identity(headers, observed) == []


@pytest.mark.parametrize("header,value", [
    ("User-Agent", "other"), ("Accept-Language", "de-DE"),
    ("Sec-CH-UA-Platform", '"Linux"'), ("Sec-CH-UA-Mobile", "?1"),
    ("Sec-CH-UA-Platform", "Windows"), ("Sec-CH-UA-Mobile", "false"),
])
def test_native_request_identity_audit_rejects_http_js_contradictions(header, value):
    from app.core.native.diagnostics import audit_observed_request_identity

    headers = coherent_request_identity_headers()
    headers[header] = value
    assert audit_observed_request_identity(headers, coherent_identity_observations())


@pytest.mark.parametrize("header", list(coherent_request_identity_headers()))
def test_native_request_identity_audit_requires_all_compared_headers(header):
    from app.core.native.diagnostics import audit_observed_request_identity

    headers = coherent_request_identity_headers()
    del headers[header]
    assert audit_observed_request_identity(headers, coherent_identity_observations())


@pytest.mark.parametrize("headers,observed", [
    (None, {}), ({"User-Agent": []}, {}),
    ({"User-Agent": "one", "user-agent": "two"}, {}),
    ({}, None), ({}, {"document": None}),
])
def test_native_request_identity_audit_rejects_unavailable_or_ambiguous_evidence(headers, observed):
    from app.core.native.diagnostics import audit_observed_request_identity

    assert audit_observed_request_identity(headers, observed)


@pytest.mark.parametrize("navigator_platform,hint_platform,ua_marker", [
    ("Win32", "Windows", "Windows NT 10.0; Win64; x64"),
    ("MacIntel", "macOS", "Macintosh; Intel Mac OS X 10_15_7"),
    ("Linux x86_64", "Linux", "X11; Linux x86_64"),
    ("Linux x86_64", "Chrome OS", "X11; CrOS x86_64 14541.0.0"),
    ("Linux x86_64", "Chromium OS", "X11; CrOS x86_64 14541.0.0"),
    ("Linux armv8l", "Android", "Linux; Android 10; K"),
    ("Linux x86_64", "Android", "X11; Linux x86_64"),
])
def test_native_identity_audit_preserves_known_chromium_platform_reduction(
        navigator_platform, hint_platform, ua_marker):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    for values in observed.values():
        values["platform"] = navigator_platform
        values["userAgentData"]["platform"] = hint_platform
        values["userAgentHighEntropy"]["platform"] = hint_platform
        values["userAgent"] = f"Mozilla/5.0 ({ua_marker}) Chrome/148.0.0.0 Safari/537.36"
        values["userAgentHighEntropy"]["platformVersion"] = "15.0.0"
    assert audit_observed_identity(observed, "148.0.7778.96") == []


@pytest.mark.parametrize("scope", ["document", "worker"])
@pytest.mark.parametrize("navigator_platform,hint_platform,ua_marker", [
    ("Win32", "macOS", ""), ("MacIntel", "Windows", ""),
    ("Linux x86_64", "Windows", ""),
    ("Linux x86_64", "Linux", "Windows NT 10.0"),
    ("Win32", "Windows", "Macintosh"),
    ("Linux x86_64", "Linux", "CrOS x86_64"),
    ("Win32", "Windows", "X11; Linux x86_64"),
    ("MacIntel", "macOS", "Linux; Android 10; K"),
    ("Linux x86_64", "Chrome OS", "X11; Linux x86_64"),
])
def test_native_identity_audit_rejects_os_contradictions(
        scope, navigator_platform, hint_platform, ua_marker):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    values = observed[scope]
    values["platform"] = navigator_platform
    values["userAgentData"]["platform"] = hint_platform
    values["userAgent"] = f"Mozilla/5.0 ({ua_marker}) Chrome/148.0.0.0 Safari/537.36"
    assert any("disagrees with Client Hints OS" in issue
               for issue in audit_observed_identity(observed, "148.0.7778.96"))


@pytest.mark.parametrize("field", ["navigator", "hints"])
@pytest.mark.parametrize("invalid", [[], {}, None, False])
def test_native_identity_audit_reports_malformed_platform_without_throwing(field, invalid):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    values = observed["document"]
    if field == "navigator":
        values["platform"] = invalid
    else:
        values["userAgentData"]["platform"] = invalid
    assert audit_observed_identity(observed, "148.0.7778.96")


@pytest.mark.parametrize("scope", ["document", "worker"])
@pytest.mark.parametrize("key,value", [
    ("platform", "Android"), ("mobile", True), ("mobile", 0),
    ("brands", [{"brand": "Chromium", "version": "149"}]),
])
def test_native_identity_audit_rejects_high_entropy_base_hint_contradictions(scope, key, value):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    observed[scope]["userAgentHighEntropy"][key] = value
    assert f"{scope.capitalize()} high-entropy Client Hints {key} disagrees with base hints" in (
        audit_observed_identity(observed, "148.0.7778.96"))


@pytest.mark.parametrize("key", ["platform", "mobile", "brands"])
def test_native_identity_audit_requires_high_entropy_base_hint_fields(key):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    del observed["document"]["userAgentHighEntropy"][key]
    assert f"Document high-entropy Client Hints {key} disagrees with base hints" in (
        audit_observed_identity(observed, "148.0.7778.96"))


@pytest.mark.parametrize("field", ["userAgent", "platform", "language", "timezone", "intlLocale",
                                   "languages", "userAgentData", "userAgentHighEntropy"])
def test_native_identity_audit_never_accepts_matching_missing_values(field):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    for values in observed.values():
        del values[field]
    assert audit_observed_identity(observed, "148.0.7778.96")


@pytest.mark.parametrize("mutation", ["ua", "primary-language", "low-version", "full-version", "duplicate-brand",
                                     "invalid-mobile", "missing-platform", "worker-unavailable", "invalid-runtime"])
def test_native_identity_audit_rejects_incoherent_versions_or_missing_evidence(mutation):
    from app.core.native.diagnostics import audit_observed_identity

    observed = coherent_identity_observations()
    values = observed["document"]
    version = "148.0.7778.96"
    if mutation == "ua":
        values["userAgent"] = values["userAgent"].replace("148.", "152.")
    elif mutation == "primary-language":
        values["languages"][0] = "de-DE"
    elif mutation == "low-version":
        values["userAgentData"]["brands"][0]["version"] = "152"
    elif mutation == "full-version":
        values["userAgentHighEntropy"]["fullVersionList"][0]["version"] = "148.0.7778.1"
    elif mutation == "duplicate-brand":
        values["userAgentData"]["brands"] *= 2
    elif mutation == "invalid-mobile":
        values["userAgentData"]["mobile"] = 0
    elif mutation == "missing-platform":
        values["userAgentData"]["platform"] = ""
    elif mutation == "worker-unavailable":
        observed["worker"] = None
    else:
        version = "unknown"
    assert audit_observed_identity(observed, version)


def test_native_profile_inspection_includes_missing_identity_evidence():
    import asyncio

    from app.core.native.diagnostics import inspect_native_profile

    class Page:
        async def evaluate(self, expression):
            values = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC"}
            return {"document": values, "worker": dict(values)}

    report = asyncio.run(inspect_native_profile(Page(), NativeConfiguration(), "148.0.7778.96"))
    assert "Document identity is missing userAgent" in report["mismatches"]
    assert "Worker Client Hints coherence could not be observed" in report["mismatches"]
    assert report["native_patch_capabilities"] == []


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
                                "unmaskedRenderer", "maxTextureSize", "maxViewportDimensions",
                                "extensions", "limits", "contextAttributes"])
def test_native_graphics_diagnostics_detects_document_worker_disagreement(key):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "graphics": {"webgl2": {"available": True, key: "document"}}}
    worker = {**document, "graphics": {"webgl2": {"available": True, key: "worker"}}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        f"Document and dedicated worker disagree on webgl2 {key}"]


@pytest.mark.parametrize("mutation", [None, "missing-context", "missing-limits", "boolean-limit", "texture-conflict",
                                    "duplicate-extension", "missing-features", "subgroup-conflict", "missing-info"])
def test_native_graphics_audit_rejects_identically_incomplete_capabilities(mutation):
    import copy
    from app.core.native.diagnostics import audit_observed_graphics

    gl_limits = {name: 16 for name in ("MAX_TEXTURE_SIZE", "MAX_CUBE_MAP_TEXTURE_SIZE", "MAX_RENDERBUFFER_SIZE",
                 "MAX_VERTEX_ATTRIBS", "MAX_TEXTURE_IMAGE_UNITS", "MAX_VERTEX_TEXTURE_IMAGE_UNITS")}
    gl = {"available": True, "vendor": "native", "renderer": "native", "version": "native",
          "shadingLanguage": "native", "unmaskedVendor": None, "unmaskedRenderer": None,
          "maxTextureSize": 16, "maxViewportDimensions": [16, 16], "extensions": [],
          "limits": gl_limits, "contextAttributes": {"alpha": True}}
    gpu = {"available": True, "features": [],
           "limits": {name: 16 for name in ("maxTextureDimension2D", "maxBindGroups", "maxBufferSize",
                      "maxStorageBufferBindingSize", "maxComputeWorkgroupSizeX", "maxComputeInvocationsPerWorkgroup")},
           "info": {"vendor": "", "architecture": "", "device": "", "description": "",
                    "isFallbackAdapter": False, "subgroupMinSize": 4, "subgroupMaxSize": 8}}
    row = {"graphics": {"webgl": gl, "webgl2": copy.deepcopy(gl)}, "webgpu": gpu}
    if mutation == "missing-context":
        row["graphics"].pop("webgl")
    elif mutation == "missing-limits":
        gl.pop("limits")
    elif mutation == "boolean-limit":
        gl["limits"]["MAX_TEXTURE_SIZE"] = True
    elif mutation == "texture-conflict":
        gl["maxTextureSize"] = 32
    elif mutation == "duplicate-extension":
        gl["extensions"] = ["native-extension", "native-extension"]
    elif mutation == "missing-features":
        gpu.pop("features")
    elif mutation == "subgroup-conflict":
        gpu["info"]["subgroupMinSize"] = 16
    elif mutation == "missing-info":
        gpu.pop("info")
    observed = {"document": row, "worker": copy.deepcopy(row)}
    issues = audit_observed_graphics(observed)
    assert bool(issues) is (mutation is not None)
    if issues:
        assert any(issue.startswith("Document") for issue in issues)
        assert any(issue.startswith("Worker") for issue in issues)


def test_native_graphics_audit_preserves_unavailable_apis_without_capability_claim():
    from app.core.native.diagnostics import audit_observed_graphics

    row = {"graphics": {kind: {"available": False, "error": "Unavailable"} for kind in ("webgl", "webgl2")},
           "webgpu": {"available": False, "error": "Unavailable"}}
    assert audit_observed_graphics({"document": row, "worker": row}) == []


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


@pytest.mark.parametrize("key", ["info", "features", "limits"])
def test_native_webgpu_diagnostics_reports_document_worker_disagreement(key):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "webgpu": {"available": True, key: "document"}}
    worker = {**document, "webgpu": {"available": True, key: "worker"}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        f"Document and dedicated worker disagree on webgpu {key}"]


def test_native_webgpu_diagnostics_preserves_unavailable_adapters_without_fake_values():
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "webgpu": {"available": False, "error": "Native adapter unavailable"}}
    worker = {**document, "webgpu": {"available": False, "error": "WebGPU unavailable"}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == []
    worker["webgpu"]["available"] = True
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        "Document and dedicated worker disagree on webgpu availability"]
    worker["webgpu"] = None
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        "WebGPU observations could not be compared"]
    del worker["webgpu"]
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        "WebGPU observations could not be compared"]


@pytest.mark.parametrize("screen,expected", [
    ({"width": 1366, "height": 768, "availWidth": 1366, "availHeight": 728}, []),
    ({"width": 1920, "height": 768}, ["Document screen width differs from configured 1366"]),
    ({"width": 1366, "height": 768, "availWidth": 1920},
     ["Document screen availWidth is inconsistent with width"]),
    ({"width": 1366, "height": 768, "availHeight": -1},
     ["Document screen availHeight is inconsistent with height"]),
    ({"width": 1366, "height": 768, "availHeight": "768"},
     ["Document screen availHeight is inconsistent with height"]),
    (None, ["Document screen geometry could not be observed"]),
])
def test_native_screen_diagnostics_reports_geometry_contradictions(screen, expected):
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "screen": screen}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": dict(document)}) == expected


def test_native_canvas_diagnostics_does_not_invent_pixels_for_unavailable_contexts():
    from app.core.native.diagnostics import compare_observed

    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "canvas": {"available": False, "error": "2D unavailable"}}
    worker = {**document, "canvas": {"available": False, "error": "Worker 2D unavailable"}}
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == []
    worker["canvas"]["available"] = True
    assert compare_observed(NativeConfiguration(), {"document": document, "worker": worker}) == [
        "Document and dedicated worker disagree on canvas availability"]


@pytest.mark.parametrize("proxy", [
    [], "http://127.0.0.1:8080", {}, {"server": []}, {"server": "   "},
    {"server": "http://127.0.0.1:8080", "username": 1},
    {"server": "http://127.0.0.1:8080", "password": None},
    {"server": "http://127.0.0.1:8080", "bypass": []},
    {"server": "http://127.0.0.1:8080", "unknown": "private-value"},
])
def test_native_invalid_proxy_does_not_create_profile_or_start_driver(tmp_path, monkeypatch, proxy):
    from unittest.mock import Mock

    from app.core.native import runtime as module

    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    profile = tmp_path / "not-created"
    runtime = NativeRuntime(profile, Path(__file__), NativeConfiguration())
    with pytest.raises(ValueError, match="^Invalid Native proxy configuration$"):
        asyncio.run(runtime.start(proxy=proxy))
    driver.assert_not_called()
    assert not runtime.has_resources and not profile.exists()


@pytest.mark.parametrize("proxy", [
    {"server": "http://127.0.0.1:8080"},
    {"server": "127.0.0.1:8080"},
    {"server": "http://127.0.0.1:8080", "username": "owned-user", "password": "owned:value",
     "bypass": "localhost,127.0.0.1"},
    {"server": "socks5://127.0.0.1:1080", "username": "", "password": "", "bypass": ""},
])
def test_native_valid_proxy_values_remain_owned_across_async_driver_start(tmp_path, monkeypatch, proxy):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core.native import runtime as module

    context = SimpleNamespace(close=AsyncMock())
    launch = AsyncMock(return_value=context)
    driver = SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch), stop=AsyncMock())
    expected = dict(proxy)

    async def start_driver():
        proxy["server"] = "changed-after-validation"
        return driver

    monkeypatch.setattr(module, "async_playwright", lambda: SimpleNamespace(start=AsyncMock(side_effect=start_driver)))
    runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())

    async def check():
        try:
            assert await runtime.start(proxy=proxy) is context
            assert launch.await_args.kwargs["proxy"] == expected
            assert launch.await_args.kwargs["proxy"] is not proxy
        finally:
            await runtime.close()

    asyncio.run(check())
    assert not runtime.has_resources


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


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_native_failed_driver_start_releases_profile_and_allows_retry(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from PyQt6.QtCore import QLockFile
    from app.core.native import runtime as module

    async def check():
        context = SimpleNamespace(close=AsyncMock())
        driver = SimpleNamespace(stop=AsyncMock(), chromium=SimpleNamespace(
            launch_persistent_context=AsyncMock(return_value=context)))
        manager = SimpleNamespace(start=AsyncMock(side_effect=[failure("owned driver failure"), driver]))
        monkeypatch.setattr(module, "async_playwright", lambda: manager)
        runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())
        with pytest.raises(failure, match="owned driver failure" if failure is RuntimeError else None):
            await runtime.start()
        assert not runtime.has_resources
        other = QLockFile(str(runtime.profile_dir / "native-runtime.lock"))
        other.setStaleLockTime(0)
        assert other.tryLock(0)
        other.unlock()
        await runtime.close()
        assert await runtime.start() is context
        await runtime.close()
        assert not runtime.has_resources
        assert manager.start.await_count == 2
        driver.stop.assert_awaited_once()
        context.close.assert_awaited_once()

    asyncio.run(check())


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_native_driver_failure_during_cancelled_start_cleanup_releases_owner(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from PyQt6.QtCore import QLockFile
    from app.core.native import runtime as module

    async def check():
        entered, release = asyncio.Event(), asyncio.Event()

        async def start_driver():
            entered.set()
            await release.wait()
            raise failure("owned late startup failure")

        monkeypatch.setattr(module, "async_playwright", lambda: SimpleNamespace(
            start=AsyncMock(side_effect=start_driver)))
        runtime = NativeRuntime(tmp_path / "owned", Path(__file__), NativeConfiguration())
        starting = asyncio.create_task(runtime.start())
        await asyncio.wait_for(entered.wait(), timeout=1)
        starting.cancel()
        await asyncio.sleep(0)
        other = QLockFile(str(runtime.profile_dir / "native-runtime.lock"))
        other.setStaleLockTime(0)
        assert not other.tryLock(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await starting
        assert not runtime.has_resources
        assert other.tryLock(0)
        other.unlock()
        await runtime.close()

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

    monkeypatch.setattr(profiles, "db_get_native_defaults", lambda: {"environment": "mobile_web", "window_height": 844, "color_scheme": "dark"})
    update = Mock()
    monkeypatch.setattr(profiles, "db_update_account", update)
    bridge = SimpleNamespace(_emit_message=Mock(), _ensure_allowed=Mock(return_value=True), _mutate=Mock())
    profiles.ProfilesBridge.saveProfileBrowserSettingsJson(bridge, "owned", "native", '{"window_width":420,"color_scheme":"light"}')
    work, targets = bridge._mutate.call_args.args
    assert targets == ["owned"]
    work(None)
    update.assert_called_once_with("owned", {"native_settings": {"window_width": 420, "color_scheme": "light"}})
    bridge._emit_message.assert_not_called()


@pytest.mark.parametrize("failure", [None, "timeout", "teardown", "cleanup", "cancel", "cleanup-cancel"])
def test_native_manager_close_reports_do_not_turn_failure_into_graceful_success(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    import app.core.browser_interface as interface

    monkeypatch.setattr(interface, "checked_profile_dir_for_email", lambda name: tmp_path / "profile")
    monkeypatch.setattr(interface, "db_get_native_defaults", lambda: {})
    monkeypatch.setattr(interface, "db_get_camoufox_defaults", lambda: {})
    monkeypatch.setattr(interface, "db_get_cloakbrowser_defaults", lambda: {})
    monkeypatch.setattr(interface.BrowserInterface, "_init_proxy_logger", lambda self: Mock())
    browser = interface.BrowserInterface("Owned close report", browser_engine="native", keep_browser_open=False)
    assert browser.native_close_report is None
    runtime = SimpleNamespace(has_resources=True, CLOSE_TIMEOUT_SECONDS=.1)
    async def cleanup():
        if failure == "cleanup":
            raise RuntimeError("Sensitive raw cleanup message must not enter the report")
        if failure == "cleanup-cancel":
            raise asyncio.CancelledError()
        runtime.has_resources = False
    runtime.close = cleanup
    browser._native_runtime = runtime
    browser.browser = Mock()
    browser.context = Mock()
    browser._teardown_browser = AsyncMock(side_effect={"timeout": TimeoutError(), "teardown": RuntimeError("private"),
                                                      "cancel": asyncio.CancelledError()}.get(failure))
    kill = Mock()
    monkeypatch.setattr(browser._lifecycle, "kill_profile_processes", kill)
    if failure in {"cancel", "cleanup-cancel"}:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(browser.close())
    else:
        assert asyncio.run(browser.close()) is None
    report = browser.native_close_report
    assert report["forced"] is (failure == "timeout")
    assert report["resources_retained"] is (failure in {"cleanup", "cleanup-cancel"})
    assert report["teardown_error"] == {"timeout": "timeout", "teardown": "RuntimeError", "cancel": "cancelled"}.get(failure)
    assert report["cleanup_error"] == {"cleanup": "RuntimeError", "cleanup-cancel": "cancelled"}.get(failure)
    assert report["complete"] is (failure != "cleanup-cancel")
    assert report["kept_open"] is False
    assert "private" not in str(report) and "Sensitive" not in str(report)
    if failure == "timeout":
        kill.assert_called_once()
    else:
        kill.assert_not_called()
    report["forced"] = not report["forced"]
    assert browser.native_close_report["forced"] is (failure == "timeout")
    if failure not in {"cleanup", "cleanup-cancel"}:
        previous = browser.native_close_report
        browser._teardown_browser.side_effect = None
        asyncio.run(browser.close())
        assert browser.native_close_report == previous


def test_native_manager_close_kept_open_is_not_reported_as_completed(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock, Mock
    import app.core.browser_interface as interface

    monkeypatch.setattr(interface, "checked_profile_dir_for_email", lambda name: tmp_path / "profile")
    monkeypatch.setattr(interface, "db_get_native_defaults", lambda: {})
    monkeypatch.setattr(interface, "db_get_camoufox_defaults", lambda: {})
    monkeypatch.setattr(interface, "db_get_cloakbrowser_defaults", lambda: {})
    monkeypatch.setattr(interface.BrowserInterface, "_init_proxy_logger", lambda self: Mock())
    browser = interface.BrowserInterface("Owned keep open", browser_engine="native", keep_browser_open=True)
    browser.context = Mock()
    browser._teardown_browser = AsyncMock()
    asyncio.run(browser.close())
    assert browser.native_close_report["kept_open"] is True
    assert browser.native_close_report["complete"] is False
    browser._teardown_browser.assert_not_awaited()
    asyncio.run(browser.close(force=True))
    assert browser.native_close_report["kept_open"] is False and browser.native_close_report["complete"] is True
    assert browser.native_close_report["forced"] is False


def test_native_environment_settings_are_validated_copies_without_grants_or_paths():
    from app.core.native.configuration import NativeConfiguration
    from app.core.native.privacy import NativePrivacyPolicy

    configuration = NativeConfiguration(environment="mobile_web", width=420, height=844, device_scale_factor=3,
        locale="de-DE", timezone="Europe/Berlin", permissions=("camera",), color_scheme="dark",
        reduced_motion="reduce", forced_colors="active", contrast="more",
        privacy_policy=NativePrivacyPolicy(cpu_limit=2, memory_limit=2, fonts=("Arial", "Courier New"), restrict_webrtc=True))
    settings = configuration.environment_settings()
    assert set(settings) == {"environment", "window_width", "window_height", "device_scale_factor", "locale", "timezone",
                             "privacy_policy", "color_scheme", "reduced_motion", "forced_colors", "contrast"}
    assert "permissions" not in settings
    assert settings["privacy_policy"]["fonts"] == ["Arial", "Courier New"]
    assert NativeConfiguration.from_settings(settings).privacy_policy == configuration.privacy_policy
    settings["privacy_policy"]["fonts"].append("Changed draft")
    assert configuration.privacy_policy.fonts == ("Arial", "Courier New")
    with pytest.raises(ValueError, match="verified"):
        configuration.launch_arguments()
    with pytest.raises(ValueError):
        NativeConfiguration(width=True).environment_settings()


@pytest.mark.parametrize("explicit_grants", [False, True])
def test_native_pin_defaults_prepares_only_environment_and_keeps_existing_overrides(monkeypatch, explicit_grants):
    import json
    from copy import deepcopy
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.ui.bridge import profiles
    from app.core.native.configuration import NativeConfiguration

    defaults = {"environment": "mobile_web", "window_width": 390, "window_height": 844, "device_scale_factor": 3,
                "locale": "de-DE", "timezone": "Europe/Berlin", "color_scheme": "dark", "headless": True,
                "privacy_policy": {"cpu_limit": 2, "fonts": ["Arial"]}, "permissions": ["camera"],
                "binary_source": "managed", "binary_store": "global-store", "executable_path": "global-exe",
                "storage_state_path": "global-state", "extra_http_headers": {"Authorization": "global-secret"}}
    original = deepcopy(defaults)
    monkeypatch.setattr(profiles, "db_get_native_defaults", lambda: defaults)
    bridge = SimpleNamespace(_ensure_allowed=Mock(return_value=True), _emit_message=Mock(), _mutate=Mock())
    overrides = {"window_width": 420, "color_scheme": "light", "executable_path": "owned-exe",
                 "extra_http_headers": {"X-Owned": "preserved"}, "variables": {"owned": "value"}}
    if explicit_grants:
        overrides["permissions"] = ["notifications"]
    prepared = json.loads(profiles.ProfilesBridge.pinNativeProfileDefaultsJson(bridge, json.dumps(overrides)))
    assert prepared["window_width"] == 420 and prepared["window_height"] == 844
    assert prepared["locale"] == "de-DE" and prepared["timezone"] == "Europe/Berlin"
    assert prepared["color_scheme"] == "light" and prepared["headless"] is True and prepared["persistent_context"] is True
    assert prepared["privacy_policy"]["fonts"] == ["Arial"]
    assert prepared["executable_path"] == "owned-exe" and prepared["extra_http_headers"] == {"X-Owned": "preserved"}
    assert prepared["variables"] == overrides["variables"]
    assert (prepared.get("permissions") == ["notifications"]) is explicit_grants
    assert not {"binary_store", "binary_source", "storage_state_path"} & prepared.keys()
    assert "global-secret" not in json.dumps(prepared) and defaults == original
    changed_defaults = {**defaults, "locale": "fr-FR", "window_width": 900, "color_scheme": "dark", "privacy_policy": {}}
    effective = NativeConfiguration.from_settings({**changed_defaults, **prepared})
    assert effective.locale == "de-DE" and effective.width == 420 and effective.color_scheme == "light"
    assert effective.privacy_policy.cpu_limit == 2
    bridge._mutate.assert_not_called()
    bridge._emit_message.assert_not_called()
    bridge._ensure_allowed.assert_called_once_with("manager")


@pytest.mark.parametrize("draft", ["", "[", "[]", "null", '{"locale":null}', '{"device_scale_factor":true}',
                                    '{"privacy_policy":{"unknown":true}}', '{"headless":1}',
                                    '{"user_agent":"invented"}', '{"extra_http_headers":{"Accept-Language":"other"}}',
                                    '{"variables":{"number":NaN}}', '{"variables":{"text":"\\ud800"}}'])
def test_native_pin_defaults_rejects_invalid_drafts_without_mutation(monkeypatch, draft):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.ui.bridge import profiles

    monkeypatch.setattr(profiles, "db_get_native_defaults", lambda: {})
    bridge = SimpleNamespace(_ensure_allowed=Mock(return_value=True), _emit_message=Mock(), _mutate=Mock())
    assert profiles.ProfilesBridge.pinNativeProfileDefaultsJson(bridge, draft) == ""
    assert "Cannot pin Glint environment:" in bridge._emit_message.call_args.args[0]
    bridge._mutate.assert_not_called()


def test_native_pin_defaults_requires_manager_before_reading_defaults(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.ui.bridge import profiles

    read = Mock(side_effect=AssertionError("Denied preview read defaults"))
    monkeypatch.setattr(profiles, "db_get_native_defaults", read)
    bridge = SimpleNamespace(_ensure_allowed=Mock(return_value=False))
    assert profiles.ProfilesBridge.pinNativeProfileDefaultsJson(bridge, "{}") == ""
    read.assert_not_called()


@pytest.mark.parametrize("draft", [None, {}, " " * (1024 * 1024 + 1), "[" * 2000 + "]" * 2000],
                         ids=["null", "object", "oversized", "deeply-nested"])
def test_native_pin_defaults_bounds_input_before_reading_defaults(monkeypatch, draft):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.ui.bridge import profiles

    read = Mock(side_effect=AssertionError("Invalid draft read defaults"))
    monkeypatch.setattr(profiles, "db_get_native_defaults", read)
    bridge = SimpleNamespace(_ensure_allowed=Mock(return_value=True), _emit_message=Mock())
    assert profiles.ProfilesBridge.pinNativeProfileDefaultsJson(bridge, draft) == ""
    read.assert_not_called()
    assert "Cannot pin Glint environment:" in bridge._emit_message.call_args.args[0]


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
                               close=closed, has_resources=False)

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
        close=AsyncMock(side_effect=RuntimeError("owned close failed")), has_resources=True))
    work = tmp_path / "health"
    with pytest.raises(RuntimeError, match="owned profile retained") as caught:
        asyncio.run(health.probe_native_binary(executable, NativeConfiguration(), work))
    assert str(caught.value.__cause__) == "owned close failed"
    assert len(list(work.glob("native-health-*"))) == 1


@pytest.mark.parametrize("state", ["close-failed-retained", "close-failed-released", "close-returned-retained"])
def test_native_health_preserves_profile_until_runtime_releases_resources(tmp_path, monkeypatch, state):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.core.native import health

    executable = tmp_path / "owned.exe"
    executable.touch()
    profiles = []
    def runtime(profile, *_):
        profiles.append(profile)
        (profile / "owned.txt").write_text("owned diagnostic state", encoding="utf-8")
        return SimpleNamespace(start=AsyncMock(return_value=SimpleNamespace(browser=SimpleNamespace(version="148.0.7778.96"))),
            close=AsyncMock(side_effect=RuntimeError("owned cleanup error") if state.startswith("close-failed") else None),
            has_resources=state != "close-failed-released")
    monkeypatch.setattr(health, "NativeRuntime", runtime)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(health.probe_native_binary(executable, NativeConfiguration(), tmp_path / "health"))
    if state == "close-failed-released":
        assert not profiles[0].exists()
        assert str(caught.value) == "owned cleanup error"
    else:
        assert (profiles[0] / "owned.txt").read_text(encoding="utf-8") == "owned diagnostic state"
        assert str(profiles[0]) in str(caught.value)
        assert caught.value.__cause__ is not None


@pytest.mark.parametrize("failed", [False, True])
def test_native_profile_probe_observes_owned_page_and_always_verifies_teardown(tmp_path, monkeypatch, failed):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.core.native import health

    executable = tmp_path / "owned.exe"
    executable.touch()
    page = SimpleNamespace(goto=AsyncMock())
    context = SimpleNamespace(browser=SimpleNamespace(version="148.0.7778.96"), pages=[page], route=AsyncMock())
    closed = AsyncMock()
    monkeypatch.setattr(health, "NativeRuntime", lambda *args: SimpleNamespace(start=AsyncMock(return_value=context), close=closed,
                                                                            has_resources=False))
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
    page.goto.assert_awaited_once_with("http://127.0.0.1/glint-native-health", wait_until="load", timeout=10000)
    closed.assert_awaited_once()
    assert not list((tmp_path / "health").iterdir())


@pytest.mark.parametrize("failure", ["", "bypass", "navigate", "inspect", "missing-frame", "frame-inspect", "cancel"])
def test_native_context_health_owns_only_diagnostic_page_and_closes_on_failure(monkeypatch, failure):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock, call

    from app.core.native import health

    frame = SimpleNamespace()
    page = SimpleNamespace(route=AsyncMock(), goto=AsyncMock(), close=AsyncMock(),
                           frame=lambda **kwargs: None if failure == "missing-frame" else frame)
    session = SimpleNamespace(send=AsyncMock())
    context = SimpleNamespace(new_page=AsyncMock(return_value=page), route=AsyncMock(),
                              new_cdp_session=AsyncMock(return_value=session))
    expected = {"mismatches": [], "native_patch_capabilities": [], "observed": {"document": {}}}
    frame_report = {"mismatches": ["owned discrepancy"], "observed": {"document": {}}}
    inspect = AsyncMock(side_effect=[expected, frame_report])
    if failure == "bypass":
        async def fail_bypass(method, parameters):
            if method == "Network.setBypassServiceWorker":
                raise RuntimeError("Owned service worker bypass failed")
        session.send.side_effect = fail_bypass
    elif failure == "navigate":
        page.goto.side_effect = RuntimeError("Owned navigation failed")
    elif failure == "inspect":
        inspect.side_effect = RuntimeError("Owned inspection failed")
    elif failure == "frame-inspect":
        inspect.side_effect = [expected, RuntimeError("Owned iframe inspection failed")]
    elif failure == "cancel":
        inspect.side_effect = [expected, asyncio.CancelledError()]
    monkeypatch.setattr(health, "inspect_native_profile", inspect)
    compare = Mock(return_value=["owned context discrepancy"])
    monkeypatch.setattr(health, "compare_document_identity", compare)
    configuration = NativeConfiguration()
    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(health.inspect_native_context(context, configuration, "148.0.7778.96"))
    elif failure:
        with pytest.raises(RuntimeError, match="did not load" if failure == "missing-frame" else "Owned"):
            asyncio.run(health.inspect_native_context(context, configuration, "148.0.7778.96"))
    else:
        report = asyncio.run(health.inspect_native_context(context, configuration, "148.0.7778.96"))
        assert report["contexts"] == {"same_origin_frame": frame_report}
        assert report["mismatches"] == ["owned context discrepancy", "Same-origin iframe: owned discrepancy"]
        assert expected["mismatches"] == []
    context.route.assert_not_awaited()
    context.new_cdp_session.assert_awaited_once_with(page)
    assert session.send.await_args_list == [
        call("Network.enable", {}), call("Network.setBypassServiceWorker", {"bypass": True})]
    if failure == "bypass":
        page.route.assert_not_awaited()
        page.goto.assert_not_awaited()
        inspect.assert_not_awaited()
    else:
        page.route.assert_awaited_once()
    page.close.assert_awaited_once()
    if failure in {"inspect", "missing-frame"}:
        inspect.assert_awaited_once_with(page, configuration, "148.0.7778.96")
    elif failure in {"", "frame-inspect", "cancel"}:
        assert inspect.await_args_list == [call(page, configuration, "148.0.7778.96"),
                                          call(frame, configuration, "148.0.7778.96")]


def test_native_context_health_rejects_invalid_configuration_before_opening_page():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.core.native import health

    context = SimpleNamespace(new_page=AsyncMock())
    with pytest.raises(ValueError):
        asyncio.run(health.inspect_native_context(context, NativeConfiguration(width=True), "148.0.7778.96"))
    context.new_page.assert_not_awaited()


@pytest.mark.parametrize("include_frame", [False, True])
def test_native_health_fixture_blocks_other_requests_without_network_fallback(include_frame):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core.native import health

    page = SimpleNamespace(goto=AsyncMock())
    context = SimpleNamespace(route=AsyncMock(), pages=[page])
    kwargs = {"configuration": NativeConfiguration(width=390, height=844)} if include_frame else {}
    assert asyncio.run(health._prepare_diagnostic_page(context, **kwargs)) is page
    pattern, handler = context.route.await_args.args
    assert pattern == "**/*"
    owned = SimpleNamespace(request=SimpleNamespace(url="http://127.0.0.1/glint-native-health"),
                            abort=AsyncMock(), fulfill=AsyncMock())
    asyncio.run(handler(owned))
    owned.abort.assert_not_awaited()
    response = owned.fulfill.await_args.kwargs
    assert response["status"] == 200
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in response["body"]
    policy = "default-src 'none'; worker-src blob:"
    if include_frame:
        policy += "; frame-src 'self'; style-src 'unsafe-inline'"
    assert response["headers"]["Content-Security-Policy"] == policy
    assert ('<iframe' in response["body"]) is include_frame
    child = SimpleNamespace(request=SimpleNamespace(url=health.DIAGNOSTIC_FRAME_URL),
                            abort=AsyncMock(), fulfill=AsyncMock())
    asyncio.run(handler(child))
    if include_frame:
        child.abort.assert_not_awaited()
        assert '<iframe' not in child.fulfill.await_args.kwargs["body"]
        assert 'width="390" height="844"' in response["body"]
    else:
        child.abort.assert_awaited_once_with("blockedbyclient")
        child.fulfill.assert_not_awaited()
    outside = SimpleNamespace(request=SimpleNamespace(url="https://example.com/"),
                              abort=AsyncMock(), fulfill=AsyncMock())
    asyncio.run(handler(outside))
    outside.abort.assert_awaited_once_with("blockedbyclient")
    outside.fulfill.assert_not_awaited()


@pytest.mark.parametrize("key", ["userAgent", "platform", "language", "languages", "hardwareConcurrency",
    "deviceMemory", "timezone", "intlLocale", "userAgentData", "userAgentHighEntropy", "screen", "dpr", "touch",
    "mediaPreferences", "graphics", "webgpu"])
@pytest.mark.parametrize("change", ["different", "missing"])
def test_native_same_origin_document_identity_rejects_drift_and_missing_values(key, change):
    from copy import deepcopy
    from app.core.native.diagnostics import compare_document_identity

    keys = ["userAgent", "platform", "language", "languages", "hardwareConcurrency", "deviceMemory", "timezone",
            "intlLocale", "userAgentData", "userAgentHighEntropy", "screen", "dpr", "touch", "mediaPreferences",
            "graphics", "webgpu"]
    first = {name: {"owned": name} for name in keys}
    original = deepcopy(first)
    second = deepcopy(first)
    assert compare_document_identity(first, second) == []
    if change == "different":
        second[key]["owned"] = "changed"
    else:
        del second[key]
    assert compare_document_identity(first, second) == ["Document and same-origin iframe disagree on " + key]
    assert first == original


def test_native_health_navigation_failure_still_releases_owned_runtime(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core.native import health

    executable = tmp_path / "owned.exe"
    executable.touch()
    page = SimpleNamespace(goto=AsyncMock(side_effect=RuntimeError("owned navigation failed")))
    context = SimpleNamespace(browser=SimpleNamespace(version="148.0.7778.96"),
                              pages=[page], route=AsyncMock())
    close = AsyncMock()
    monkeypatch.setattr(health, "NativeRuntime", lambda *args: SimpleNamespace(
        start=AsyncMock(return_value=context), close=close, has_resources=False))
    with pytest.raises(RuntimeError, match="owned navigation failed"):
        asyncio.run(health.probe_native_profile(executable, NativeConfiguration(), tmp_path / "health"))
    close.assert_awaited_once()
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
        "browser_version": "148.0.7778.96", "observed": observed, "mismatches": [], "native_patch_capabilities": []}))
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


@pytest.mark.parametrize("phase", ["stage", "unpack"])
def test_native_binary_install_rejects_insufficient_space_without_changing_active_release(tmp_path, monkeypatch, phase):
    from types import SimpleNamespace

    from app.core.native import distribution

    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    archive, digest = _native_release_archive(tmp_path)
    previous = store.install_archive(archive, digest)
    current = store.root / "current.json"
    current.write_text('{"active":"' + digest + '","previous":null}', encoding="utf-8")
    before = current.read_bytes()
    archive, candidate = _native_release_archive(tmp_path, "0.2.0-dev")
    free = iter([0] if phase == "stage" else [distribution.MAX_ARCHIVE_BYTES, 0])
    monkeypatch.setattr(distribution.shutil, "disk_usage", lambda path: SimpleNamespace(free=next(free)))

    def unexpected_extract(*args, **kwargs):
        pytest.fail("Disk preflight must fail before any payload extraction")

    monkeypatch.setattr(distribution.tarfile.TarFile, "extract", unexpected_extract)
    with pytest.raises(OSError, match="Insufficient disk space"):
        store.install_archive(archive, candidate)
    assert current.read_bytes() == before
    assert store.inspect(digest) == previous
    assert not (store.root / "releases" / candidate).exists()
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


@pytest.mark.parametrize("mutation", ["binary", "library", "active-pointer"])
def test_native_activation_rechecks_candidate_and_pointer_after_health_probe(tmp_path, monkeypatch, mutation):
    import json
    from unittest.mock import AsyncMock
    from app.core.native import distribution

    store = distribution.NativeBinaryStore(tmp_path / "native-binaries")
    archive, first = _native_checksummed_release_archive(tmp_path)
    store.install_archive(archive, first)
    archive, candidate = _native_checksummed_release_archive(tmp_path, {"native_version": "0.2.0-dev"})
    installed = store.install_archive(archive, candidate)
    monkeypatch.setattr(distribution, "probe_native_binary", AsyncMock(return_value="148.0.7778.96"))
    asyncio.run(store.activate(first))
    current = store.root / "current.json"
    original = current.read_bytes()
    changed_pointer = json.dumps({"active": first, "previous": candidate}).encode()
    async def probe(*_):
        if mutation == "binary":
            Path(installed["executable_path"]).write_bytes(b"changed after probe")
        elif mutation == "library":
            (Path(installed["executable_path"]).parent / "lib/native.dll").write_bytes(b"changed after probe")
        else:
            current.write_bytes(changed_pointer)
        return "148.0.7778.96"
    monkeypatch.setattr(distribution, "probe_native_binary", probe)
    with pytest.raises(ValueError):
        asyncio.run(store.activate(candidate))
    assert current.read_bytes() == (changed_pointer if mutation == "active-pointer" else original)
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
