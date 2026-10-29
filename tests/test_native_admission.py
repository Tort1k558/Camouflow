import asyncio
from dataclasses import replace
import hashlib
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.native import admission
from app.core.native.configuration import NativeConfiguration
from app.core.native.distribution import MARKER, host_architecture
from app.core.native.privacy import NativePrivacyPolicy
from app.core.native.runtime import NativeRuntime


@pytest.fixture
def reviewed_package(tmp_path, monkeypatch):
    monkeypatch.setattr(admission.sys, "platform", "win32")
    store = tmp_path / "store"
    digest = "a" * 64
    root = store / "releases" / digest
    root.mkdir(parents=True)
    (store / "camouflow-native-binaries.json").write_text(json.dumps(MARKER), encoding="utf-8")
    files = {}
    for name in ("chrome.exe", "148.0.7778.96/chrome.dll", "148.0.7778.96/chrome_elf.dll", "148.0.7778.96/resources.pak"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned synthetic package: " + name.encode())
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {"schema": 1, "native_version": "0.1.0-dev", "chromium_version": "148.0.7778.96",
                "platform": "win32", "architecture": host_architecture(), "build_kind": "chromium-fork",
                "executable": "chrome.exe", "executable_sha256": files["chrome.exe"], "files_sha256": files,
                "native_patch_runtime_verified": False}
    manifest = root / "native-release.json"
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    monkeypatch.setattr(admission, "_REVIEWED_PACKAGES", {digest: {
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "platform": "win32",
        "capabilities": ("hardware", "fonts", "webrtc", "automation", "identity", "font-rasterization", "text-rendering"),
    }})
    return root / "chrome.exe", manifest


def policy():
    return NativePrivacyPolicy(cpu_limit=4, memory_limit=4, fonts=("Arial", "Segoe UI", "Tahoma"),
                               restrict_webrtc=True, conceal_automation=True, native_user_agent=True,
                               font_rasterization="grayscale")


@pytest.mark.parametrize("preset", ["gamma-1400", "gamma-2200", "contrast-300", "contrast-500",
    "gamma-1400-contrast-300", "gamma-1400-contrast-500", "gamma-2200-contrast-300", "gamma-2200-contrast-500"])
def test_reviewed_text_tuning_admission_is_exact_and_optional(reviewed_package, preset):
    executable, _ = reviewed_package
    requested = replace(policy(), font_rasterization="native", text_tuning=preset)
    verified = admission.verify_runtime_policy(executable, requested)
    assert "text-rendering" in verified.capabilities and "font-rasterization" not in verified.capabilities
    assert NativeConfiguration(privacy_policy=requested).launch_arguments(admission=verified)[2:] == requested.prepared_arguments()
    with pytest.raises(ValueError, match="differs"):
        NativeConfiguration(privacy_policy=replace(requested, text_tuning="native")).launch_arguments(admission=verified)
    admission._REVIEWED_PACKAGES[executable.parent.name]["capabilities"] = ("hardware", "fonts", "webrtc", "automation", "identity")
    with pytest.raises(ValueError, match="not verified"):
        admission.verify_runtime_policy(executable, requested)


def test_admission_is_bound_to_policy_and_never_reads_a_verified_boolean(reviewed_package):
    executable, _ = reviewed_package
    requested = policy()
    verified = admission.verify_runtime_policy(executable, requested)
    configuration = NativeConfiguration(privacy_policy=requested)
    assert verified.capabilities == tuple(requested.required_capabilities())
    assert configuration.launch_arguments(admission=verified) == ["--lang=en-US", "--accept-lang=en-US", *requested.prepared_arguments()]
    assert configuration.context_options(admission=verified)["viewport"] == {"width": 1366, "height": 768}
    with pytest.raises(ValueError, match="differs"):
        NativeConfiguration(privacy_policy=replace(requested, cpu_limit=2)).launch_arguments(admission=verified)
    for unverified in (None, True, {"native_patch_runtime_verified": True}):
        with pytest.raises(ValueError, match="verified"):
            configuration.launch_arguments(admission=unverified)


@pytest.mark.parametrize("mutation", ["dll", "resource", "missing", "extra", "manifest-flag", "coherent-manifest", "marker", "unreviewed", "capability"])
def test_changed_or_unreviewed_packages_never_create_profiles_or_start_driver(reviewed_package, tmp_path, monkeypatch, mutation):
    from app.core.native import runtime as module

    executable, manifest = reviewed_package
    resource = executable.parent / "148.0.7778.96/resources.pak"
    if mutation in {"dll", "resource"}:
        (executable.parent / "148.0.7778.96/chrome.dll" if mutation == "dll" else resource).write_bytes(b"modified")
    elif mutation == "missing":
        resource.unlink()
    elif mutation == "extra":
        (executable.parent / "unexpected.dll").write_bytes(b"extra")
    elif mutation in {"manifest-flag", "coherent-manifest"}:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        if mutation == "manifest-flag":
            metadata["native_patch_runtime_verified"] = True
        else:
            resource.write_bytes(b"self-consistent replacement")
            metadata["files_sha256"]["148.0.7778.96/resources.pak"] = hashlib.sha256(resource.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(metadata), encoding="utf-8")
    elif mutation == "marker":
        (executable.parent.parent.parent / "camouflow-native-binaries.json").unlink()
    elif mutation == "unreviewed":
        monkeypatch.setattr(admission, "_REVIEWED_PACKAGES", {})
    else:
        admission._REVIEWED_PACKAGES[executable.parent.name]["capabilities"] = ()
    driver = Mock()
    monkeypatch.setattr(module, "async_playwright", driver)
    profile = tmp_path / "not-created"
    runtime = NativeRuntime(profile, executable, NativeConfiguration(privacy_policy=policy()))
    with pytest.raises(ValueError):
        asyncio.run(runtime.start())
    driver.assert_not_called()
    assert not profile.exists() and not runtime.has_resources
    assert runtime.native_policy_capabilities == []


def test_runtime_checks_package_off_event_loop_and_clears_admission_on_close(reviewed_package, tmp_path, monkeypatch):
    from app.core.native import runtime as module

    executable, _ = reviewed_package
    requested = policy()
    caller = threading.get_ident()
    verify = admission.verify_runtime_policy
    verifications = []

    def checking(*args):
        assert threading.get_ident() != caller
        verifications.append(args)
        return verify(*args)

    monkeypatch.setattr(admission, "verify_runtime_policy", checking)
    context = SimpleNamespace(close=AsyncMock())
    launch = AsyncMock(return_value=context)
    driver = SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch), stop=AsyncMock())
    factory = SimpleNamespace(start=AsyncMock(return_value=driver))
    monkeypatch.setattr(module, "async_playwright", lambda: factory)
    runtime = NativeRuntime(tmp_path / "profile", executable, NativeConfiguration(privacy_policy=requested))

    async def run():
        for _ in range(2):
            assert await runtime.start() is context
            assert runtime.native_policy_capabilities == requested.required_capabilities()
            assert launch.await_args.kwargs["args"][-len(requested.prepared_arguments()):] == requested.prepared_arguments()
            await runtime.close()
            assert not runtime.has_resources and runtime.native_policy_capabilities == []

    asyncio.run(run())
    assert len(verifications) == 2


@pytest.mark.parametrize("scope,key,value,message", [
    ("document", "hardwareConcurrency", 8, "CPU"),
    ("worker", "hardwareConcurrency", True, "CPU"),
    ("document", "deviceMemory", 8, "memory"),
    ("worker", "deviceMemory", float("nan"), "memory"),
    ("document", "webdriver", True, "webdriver"),
    ("worker", "userAgent", "HeadlessChrome/148.0.0.0", "UA policy"),
])
def test_diagnostics_reject_controls_that_were_requested_but_not_observed(scope, key, value, message):
    from app.core.native.diagnostics import compare_observed

    configuration = NativeConfiguration(privacy_policy=policy())
    document = {"width": 1366, "height": 768, "dpr": 1, "language": "en-US", "timezone": "UTC",
                "hardwareConcurrency": 1, "deviceMemory": .25, "webdriver": False, "userAgent": "Chrome/148.0.0.0"}
    observed = {"document": dict(document), "worker": dict(document)}
    assert compare_observed(configuration, observed) == []
    observed[scope][key] = value
    assert any(message in issue for issue in compare_observed(configuration, observed))


@pytest.mark.parametrize("failure", ["bind", "start", "cleanup"])
def test_admitted_verifier_preserves_early_failure_and_owned_cleanup(reviewed_package, tmp_path, monkeypatch, failure):
    from scripts import verify_native_admitted_policy as verifier

    executable, _ = reviewed_package
    monkeypatch.setattr(verifier, "require_idle_builder", lambda *args: None)
    close = AsyncMock(side_effect=RuntimeError("owned cleanup") if failure == "cleanup" else None)
    monkeypatch.setattr(verifier, "NativeRuntime", lambda *args: SimpleNamespace(
        start=AsyncMock(side_effect=RuntimeError("owned startup")), close=close, has_resources=False))
    if failure == "bind":
        def bind(*args):
            raise OSError("owned bind failure")
        monkeypatch.setattr(verifier, "FixtureServer", bind)
    destination = tmp_path / "evidence"
    report = asyncio.run(verifier.verify(executable, destination))
    assert not report["passed"] and report["inputs_unchanged"]
    assert "owned" in report["error"]
    assert bool(report["errors"]) is (failure == "cleanup")
    close.assert_awaited_once()
    assert json.loads((destination / "report.json").read_text(encoding="utf-8")) == report
    assert not (destination / "control").exists()
