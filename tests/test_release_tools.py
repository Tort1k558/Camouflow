"""Native package paths must match the PyInstaller spec on each host OS."""

import sys
from pathlib import Path

import pytest

from scripts import verify_release


@pytest.mark.parametrize("platform,executable", [
    ("win32", "CamouFlow/CamouFlow.exe"),
    ("linux", "CamouFlow/CamouFlow"),
    ("darwin", "CamouFlow.app/Contents/MacOS/CamouFlow"),
])
def test_build_uses_native_package_executable(tmp_path, monkeypatch, platform, executable):
    python = Path(sys.executable)
    monkeypatch.setattr(verify_release, "ROOT", tmp_path)
    monkeypatch.setattr(verify_release.sys, "platform", platform)
    def fake_build(command):
        assert command[0] == str(python)
        dist = Path(command[command.index("--distpath") + 1])
        target = dist / executable
        target.parent.mkdir(parents=True)
        target.touch()
    monkeypatch.setattr(verify_release, "run", fake_build)
    assert verify_release.build(python).relative_to(tmp_path / "dist").as_posix().endswith(executable)


def test_missing_build_interpreter_fails_explicitly(tmp_path):
    with pytest.raises(SystemExit, match="Missing Python interpreter"):
        verify_release.require_venv(tmp_path / "missing-python")


def test_runtime_import_budget_does_not_weaken_hard_timeout(tmp_path, monkeypatch):
    from app import python_runtime_check
    from app.storage import db
    import app.services.scenario_worker as worker

    cases = []
    monkeypatch.setattr(db, "init_db", lambda: None)
    def run_worker(account, job, cancel):
        cases.append((job["scenario"], job["steps"][1]["timeout_ms"]))
        if job["scenario"] == "hard-timeout":
            return {"status": "failed", "error": "Python timeout"}
        return {"status": "success", "error": ""}
    monkeypatch.setattr(worker, "run_worker", run_worker)
    assert python_runtime_check.check_runtime("camoufox", tmp_path / "runtime.json") == 0
    assert cases == [("browser-and-imports", 15000), ("hard-timeout", 3000)]


def test_native_gate_http_proxy_requires_actual_authentication():
    import base64
    from http.client import HTTPConnection
    from threading import Thread
    from scripts.verify_native_runtime import FixtureHandler, FixtureServer

    server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
    server.proxy_mode = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def request(headers):
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            connection.request("GET", "http://native-fixture.invalid/", headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()
    try:
        assert request({})[0] == 407
        assert request({"Proxy-Authorization": "Basic invalid"})[0] == 407
        credentials = base64.b64encode(b"owned-user:owned-pass").decode("ascii")
        status, body = request({"Proxy-Authorization": "Basic " + credentials})
        assert status == 200 and b"Owned Native fixture" in body
        assert server.challenges == 2 and server.authenticated_requests == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_gate_missing_binary_is_reported_without_fallback(tmp_path, monkeypatch):
    import json
    from scripts import verify_native_runtime

    report = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["verify_native_runtime", "--executable", str(tmp_path / "missing"),
                                     "--work-dir", str(tmp_path / "owned"), "--report", str(report)])
    assert verify_native_runtime.main() == 1
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["passed"] is False
    assert result["error_type"] == "NativeRuntimeError"
    assert "not installed" in result["error"]
    assert list((tmp_path / "owned").iterdir()) == []


def test_native_gate_lock_abandonment_refuses_customer_directories(tmp_path):
    import json
    import subprocess
    from scripts.verify_native_runtime import ROOT

    profile = tmp_path / "customer-profile"
    profile.mkdir()
    marker = profile / "camouflow-native.json"
    marker.write_text(json.dumps({"engine": "camouflow-native", "schema": 1}), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/verify_native_runtime.py"),
                             "--abandon-lock", str(profile)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert "owned Native test profile" in result.stderr
    assert list(profile.iterdir()) == [marker]


def test_native_gate_closes_only_owned_log_files(tmp_path):
    import logging
    from scripts.verify_native_runtime import close_owned_log_handlers

    owned = tmp_path / "owned"
    owned.mkdir()
    logger = logging.getLogger("native-gate-owned-cleanup")
    inside = logging.FileHandler(owned / "proxy.log")
    outside = logging.FileHandler(tmp_path / "customer.log")
    logger.addHandler(inside)
    logger.addHandler(outside)
    try:
        close_owned_log_handlers(owned)
        assert inside not in logger.handlers and inside.stream is None
        assert outside in logger.handlers and outside.stream is not None
        (owned / "proxy.log").unlink()
    finally:
        for handler in (inside, outside):
            logger.removeHandler(handler)
            handler.close()


def test_native_fixture_serves_requests_while_browser_preconnect_is_idle():
    import socket
    from http.client import HTTPConnection
    from threading import Thread
    from scripts.verify_native_runtime import FixtureHandler, FixtureServer

    server = FixtureServer(("127.0.0.1", 0), FixtureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    idle = socket.create_connection(server.server_address, timeout=2)
    request = HTTPConnection(*server.server_address, timeout=2)
    try:
        request.request("GET", "/")
        response = request.getresponse()
        assert response.status == 200
        assert b"Owned Native fixture" in response.read()
    finally:
        idle.close()
        request.close()
        server.shutdown()
        server.server_close()
        thread.join()


def test_native_build_lock_pins_full_source_revisions():
    import re
    from scripts.native_build import LOCK

    assert LOCK["schema"] == 1
    for name in ("chromium_revision", "depot_tools_revision"):
        assert re.fullmatch(r"[0-9a-f]{40}", LOCK[name])
    assert LOCK["minimum_free_gib"] >= 100
    assert LOCK["build_jobs"] <= 4


@pytest.mark.skipif(sys.platform != "win32", reason="Windows C++ verifier requires Visual Studio")
def test_native_cpp_verifier_requires_explicit_toolchain_and_cleans_owned_temp(tmp_path):
    from scripts.verify_native_cpp import verify

    with pytest.raises(ValueError, match="explicit Visual Studio"):
        verify(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_native_build_transport_is_process_scoped_and_preserves_existing_git_config(tmp_path, monkeypatch):
    import os
    from scripts.native_build import environment

    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.filemode")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    env = environment(tmp_path)
    assert os.environ["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "core.filemode"
    assert env["GIT_CONFIG_VALUE_0"] == "false"
    if os.name == "nt":
        assert env["GIT_CONFIG_COUNT"] == "2"
        assert env["GIT_CONFIG_KEY_1"] == "http.sslBackend"
        assert env["GIT_CONFIG_VALUE_1"] == "openssl"
    assert env["DEPOT_TOOLS_UPDATE"] == "0"
    assert env["DEPOT_TOOLS_METRICS"] == "0"
    assert env["GIT_CONFIG_GLOBAL"] == str(tmp_path / "build.gitconfig")
    assert env["CIPD_CACHE_DIR"] == str(tmp_path / "cipd-cache")


def test_native_build_rejects_relative_workspace():
    from scripts.native_build import preflight

    with pytest.raises(ValueError, match="absolute"):
        preflight(Path("relative-native-build"))


@pytest.mark.parametrize("workspace_free,backing_free,expected", [(1000, 300, 300), (240, 300, 240)])
def test_native_preflight_checks_virtual_workspace_and_physical_backing_space(tmp_path, monkeypatch,
                                                                            workspace_free, backing_free, expected):
    from types import SimpleNamespace
    from scripts import native_build

    workspace = Path("D:/native-build-resource-test") if sys.platform == "win32" else tmp_path / "workspace"
    backing = tmp_path / "backing"
    backing.mkdir()
    monkeypatch.setattr(native_build.shutil, "which", lambda name: "git")
    monkeypatch.setattr(native_build.shutil, "disk_usage", lambda path:
                        SimpleNamespace(free=(backing_free if path == backing else workspace_free) * 1024 ** 3))
    report = native_build.preflight(workspace, backing_volume=backing)
    assert report["free_gib"] == expected
    assert report["workspace_free_gib"] == workspace_free
    assert report["backing_free_gib"] == backing_free
    assert report["backing_volume"] == str(backing)


def test_native_preflight_rejects_full_backing_volume_despite_large_virtual_disk(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scripts import native_build

    workspace = Path("D:/native-build-resource-test") if sys.platform == "win32" else tmp_path / "workspace"
    monkeypatch.setattr(native_build.shutil, "which", lambda name: "git")
    monkeypatch.setattr(native_build.shutil, "disk_usage", lambda path:
                        SimpleNamespace(free=(120 if path == tmp_path else 1000) * 1024 ** 3))
    with pytest.raises(ValueError, match="found 120.0"):
        native_build.preflight(workspace, backing_volume=tmp_path)


@pytest.mark.parametrize("relative", [True, False])
def test_native_preflight_rejects_invalid_backing_paths(tmp_path, monkeypatch, relative):
    from types import SimpleNamespace
    from scripts import native_build

    workspace = Path("D:/native-build-resource-test") if sys.platform == "win32" else tmp_path / "workspace"
    monkeypatch.setattr(native_build.shutil, "which", lambda name: "git")
    monkeypatch.setattr(native_build.shutil, "disk_usage", lambda path: SimpleNamespace(free=1000 * 1024 ** 3))
    backing = Path("relative-backing") if relative else tmp_path / "missing-backing"
    with pytest.raises(ValueError, match="Backing volume must be"):
        native_build.preflight(workspace, backing_volume=backing)


def test_native_preflight_rejects_missing_filesystem_root_instead_of_looping(tmp_path, monkeypatch):
    from scripts import native_build

    workspace = Path("D:/native-build-resource-test") if sys.platform == "win32" else tmp_path / "workspace"
    monkeypatch.setattr(native_build.shutil, "which", lambda name: "git")
    monkeypatch.setattr(Path, "exists", lambda path: False)
    with pytest.raises(ValueError, match="no existing filesystem root"):
        native_build.preflight(workspace)


@pytest.mark.parametrize("jobs", [0, -1, 5, True, "2"])
def test_native_build_rejects_invalid_job_budgets_before_filesystem_changes(tmp_path, jobs):
    from scripts.native_build import execute

    with pytest.raises(ValueError, match="jobs must be between"):
        execute("build", tmp_path / "missing", jobs=jobs)
    assert list(tmp_path.iterdir()) == []


def test_native_build_passes_selected_concurrency_to_compiler_and_receipt(tmp_path, monkeypatch):
    import json
    from scripts import native_build

    source = tmp_path / "chromium/src"
    source.mkdir(parents=True)
    (source.parent / ".gclient").write_text("owned", encoding="utf-8")
    (source / "DEPS").write_text("owned", encoding="utf-8")
    relative = {"win32": "chrome.exe", "linux": "chrome", "darwin": "Chromium.app/Contents/MacOS/Chromium"}[sys.platform]
    commands = []
    def run(args, *a, **kwargs):
        commands.append(args)
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return native_build.LOCK["chromium_revision"]
        if args[0] == "autoninja":
            binary = source / "out/CamouFlowNative" / relative
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"owned test binary")
        return ""
    monkeypatch.setattr(native_build, "preflight", lambda *a, **kw: {})
    monkeypatch.setattr(native_build, "environment", lambda *a: {})
    monkeypatch.setattr(native_build, "checkout", lambda *a: None)
    monkeypatch.setattr(native_build, "bootstrap_windows_git", lambda *a: None)
    monkeypatch.setattr(native_build, "require_stage", lambda *a: None)
    monkeypatch.setattr(native_build, "source_patches", lambda *a: [])
    monkeypatch.setattr(native_build, "depot_command", lambda name, *a: [name])
    monkeypatch.setattr(native_build, "run", run)
    native_build.execute("build", tmp_path, jobs=1)
    assert ["autoninja", "-C", "out/CamouFlowNative", "-j", "1", "chrome"] in commands
    receipt = json.loads((source / "out/CamouFlowNative/camouflow-build.json").read_text(encoding="utf-8"))
    assert receipt["build_jobs"] == 1
    assert receipt["native_patch_runtime_verified"] is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows gclient helpers use batch launchers")
def test_native_build_helper_uses_the_installed_vpython_without_rebootstrapping(tmp_path):
    from scripts.native_build import environment

    executable = tmp_path / "depot_tools/.cipd_bin/vpython3.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    env = environment(tmp_path)
    launcher = tmp_path / "tool-launchers/vpython3.bat"
    assert launcher.read_text(encoding="utf-8") == f'@echo off\n"{executable}" %*\n'
    assert "cipd_bin_setup" not in launcher.read_text(encoding="utf-8")
    assert env["PATH"].split(";")[0] == str(launcher.parent)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows gclient helpers use batch launchers")
def test_native_build_preserves_unrelated_helper_launcher(tmp_path):
    from scripts.native_build import environment

    executable = tmp_path / "depot_tools/.cipd_bin/vpython3.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    launcher = tmp_path / "tool-launchers/vpython3.bat"
    launcher.parent.mkdir()
    launcher.write_text("preserve customer launcher", encoding="utf-8")
    with pytest.raises(ValueError, match="unrelated vpython launcher"):
        environment(tmp_path)
    assert launcher.read_text(encoding="utf-8") == "preserve customer launcher"


def test_native_build_rejects_checkout_inside_application():
    from scripts.native_build import ROOT, preflight

    with pytest.raises(ValueError, match="outside"):
        preflight(ROOT / "native-checkout")


def test_native_build_rejects_unrelated_nonempty_checkout(tmp_path):
    from scripts.native_build import checkout

    directory = tmp_path / "source"
    directory.mkdir()
    customer_file = directory / "customer-data"
    customer_file.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="unrelated"):
        checkout(directory, "https://example.invalid/source", "a" * 40, {})
    assert customer_file.read_text(encoding="utf-8") == "preserve"


def test_native_build_rejects_uncommitted_source_changes(tmp_path, monkeypatch):
    from scripts import native_build

    directory = tmp_path / "source"
    directory.mkdir()
    (directory / ".git").mkdir()
    commands = []
    repository = "https://example.invalid/source"
    def fake_run(args, cwd, env, capture=False):
        commands.append(args)
        if args[1:3] == ["remote", "get-url"]:
            return repository
        return " M native-patch.cc" if args[1] == "status" else ""
    monkeypatch.setattr(native_build, "run", fake_run)
    with pytest.raises(ValueError, match="Uncommitted"):
        native_build.checkout(directory, repository, "a" * 40, {})
    assert not any("fetch" in args or "checkout" in args for args in commands)


def test_native_chromium_patch_embeds_the_tested_hardware_policy():
    from scripts.native_build import ROOT

    contents = (ROOT / "native/patches/0001-native-hardware-privacy-limits.patch").read_text(encoding="utf-8-sig")
    section = contents.split("+++ b/third_party/blink/renderer/core/frame/camouflow_hardware_limits.h\n", 1)[1]
    section = section.split("diff --git ", 1)[0]
    embedded = "\n".join(line[1:] for line in section.splitlines() if line.startswith("+")) + "\n"
    assert embedded == (ROOT / "native/core/hardware_limits.h").read_text(encoding="utf-8-sig")


def _automation_observation(value=True):
    return {"value": value, "firstScriptValue": value, "ownProperty": False,
            "descriptor": {"getter": "function get webdriver() { [native code] }",
                           "setter": True, "enumerable": True, "configurable": True,
                           "illegalInvocation": True}}


@pytest.mark.parametrize("expected", [False, True])
def test_native_automation_gate_preserves_native_binding(expected):
    from scripts.verify_native_automation import validate_observation

    validate_observation(_automation_observation(expected), _automation_observation(), expected, first=expected)


@pytest.mark.parametrize("change", [
    {"value": True}, {"value": 0}, {"firstScriptValue": True}, {"ownProperty": True},
    {"descriptor": {"getter": "function () { return false; }"}},
])
def test_native_automation_gate_rejects_ignored_flags_early_script_leaks_and_js_getters(change):
    from scripts.verify_native_automation import validate_observation

    observed = {**_automation_observation(False), **change}
    with pytest.raises(ValueError):
        validate_observation(observed, _automation_observation(), False, first=False)


def test_native_automation_patch_is_opt_in_and_precedes_inspector_override():
    from scripts.native_build import ROOT

    patch = (ROOT / "native/patches/0004-native-automation-exposure.patch").read_text(encoding="utf-8-sig")
    assert '+      name: "CamouFlowAutomationConcealed",\n+    },' in patch
    assert '+      status:' not in patch
    assert patch.index("CamouFlowAutomationConcealedEnabled()") < patch.index("AutomationControlledEnabled()")


@pytest.mark.parametrize("public_name,embedded_name", [
    ("native/core/font_families.h", "ui/gfx/win/camouflow_font_families.h"),
    ("native/windows/font_collection.h", "ui/gfx/win/camouflow_font_collection.h"),
    ("native/windows/font_configuration.h", "ui/gfx/win/camouflow_font_configuration.h"),
])
def test_native_font_patch_embeds_reviewed_and_compiled_policy(public_name, embedded_name):
    from scripts.native_build import ROOT

    patch = (ROOT / "native/patches/0005-native-windows-font-collection.patch").read_text(encoding="utf-8-sig")
    section = patch.split("+++ b/" + embedded_name + "\n", 1)[1].split("diff --git ", 1)[0]
    embedded = "\n".join(line[1:] for line in section.splitlines() if line.startswith("+")) + "\n"
    assert embedded == (ROOT / public_name).read_text(encoding="utf-8-sig")


def _font_observation(protected=False):
    arial = {"width": 100.0, "hash": "a" * 64, "cssWidth": 100.0}
    excluded = dict(arial) if protected else {"width": 150.0, "hash": "b" * 64, "cssWidth": 150.0}
    return {"arial": arial, "excluded": excluded,
            "downloaded": {"width": 150.0, "hash": "c" * 64, "cssWidth": 150.0},
            "excludedLocalLoaded": not protected}


@pytest.mark.parametrize("protected", [False, True])
def test_native_font_gate_preserves_real_metrics_and_downloaded_fonts(protected):
    from scripts.verify_native_fonts import validate_font_probe

    validate_font_probe(_font_observation(protected), _font_observation(), protected)
    if not protected:
        validate_font_probe(_font_observation(), None, False)


@pytest.mark.parametrize("name,change", [
    ("arial", {"width": float("nan")}), ("arial", {"width": True}),
    ("arial", {"hash": "fake"}), ("arial", {"cssWidth": 105}),
    ("arial", {"hash": "d" * 64}), ("downloaded", {"width": 100.0, "cssWidth": 100.0}),
    ("excluded", {"width": 150.0, "cssWidth": 150.0}),
])
def test_native_font_gate_rejects_leaks_fake_metrics_and_broken_webfonts(name, change):
    from scripts.verify_native_fonts import validate_font_probe

    observed = _font_observation(True)
    observed[name].update(change)
    with pytest.raises(ValueError):
        validate_font_probe(observed, _font_observation(), True)


def test_native_font_gate_requires_controls_and_blocks_local_face_bypass():
    from scripts.verify_native_fonts import validate_font_probe

    with pytest.raises(ValueError):
        validate_font_probe(_font_observation(True), None, True)
    observed = _font_observation(True)
    observed["excludedLocalLoaded"] = True
    with pytest.raises(ValueError):
        validate_font_probe(observed, _font_observation(), True)


@pytest.mark.parametrize("fonts,protected,valid", [
    ([{"family": "Arial"}], True, True),
    ([{"family": "Arial"}, {"family": "Courier New"}], False, True),
    ([{"family": "Arial"}, {"family": "Courier New"}], True, False),
    ([{"family": "Arial"}], False, False), ([], True, False), ([{}], True, False),
])
def test_native_font_enumeration_gate_rejects_ignored_policy_and_missing_controls(fonts, protected, valid):
    from scripts.verify_native_fonts import validate_enumeration

    if valid:
        validate_enumeration(fonts, protected)
    else:
        with pytest.raises(ValueError):
            validate_enumeration(fonts, protected)


def test_native_build_clean_baseline_has_no_patches(tmp_path, monkeypatch):
    from scripts import native_build

    monkeypatch.setattr(native_build, "run", lambda *args, **kwargs: "")
    assert native_build.source_patches(tmp_path, {}) == []


def test_native_build_rejects_unknown_source_changes(tmp_path, monkeypatch):
    from scripts import native_build

    monkeypatch.setattr(native_build, "run", lambda *args, **kwargs: "customer.cc")
    with pytest.raises(ValueError, match="Unrecognized"):
        native_build.source_patches(tmp_path, {})


@pytest.mark.parametrize("name", ["0001-native-hardware-privacy-limits.patch",
                                  "0002-midl-locale-name-hashes.patch",
                                  "0003-native-webrtc-routing-policy.patch",
                                  "0004-native-automation-exposure.patch",
                                  "0005-native-windows-font-collection.patch"])
def test_native_build_verifies_applied_patch_and_records_checksum(tmp_path, monkeypatch, name):
    import hashlib

    from scripts import native_build

    patch = native_build.ROOT / "native/patches" / name
    expected = [line.split(" b/", 1)[1] for line in patch.read_text(encoding="utf-8").splitlines()
                if line.startswith("diff --git ")]
    commands = []

    def fake_run(args, cwd, env, capture=False):
        commands.append(args)
        return "\n".join(expected) if args[1] == "diff" else ""

    monkeypatch.setattr(native_build, "run", fake_run)
    assert native_build.source_patches(tmp_path, {}) == [
        {"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}]
    assert ["git", "read-tree", "--empty"] in commands
    assert ["git", "apply", "--cached", str(patch)] in commands
    assert commands[-1] == ["git", "diff", "--exit-code", "--", *sorted(expected)]


def _hardware_observations(cpu=12, memory=16):
    values = {"hardwareConcurrency": cpu, "deviceMemory": memory, "userAgent": "owned-native",
              "platform": "Win32", "language": "en-US"}
    return {name: dict(values) for name in ("document", "same_origin_frame", "cross_origin_frame", "dedicated", "shared", "service")}


@pytest.mark.parametrize("cpu,memory,reported_cpu,reported_memory", [
    (1, 0.25, 1, 0.25), (64, 16, 12, 16), (1, None, 1, 16), (None, 0.25, 12, 0.25),
])
def test_native_hardware_gate_checks_ceilings_without_inventing_hardware(cpu, memory, reported_cpu, reported_memory):
    from scripts.verify_native_hardware import validate_observations

    baseline = _hardware_observations()["document"]
    validate_observations(_hardware_observations(reported_cpu, reported_memory), baseline, cpu, memory)


def test_native_hardware_gate_rejects_ignored_switches():
    from scripts.verify_native_hardware import validate_observations

    baseline = _hardware_observations()["document"]
    with pytest.raises(ValueError, match="ignored"):
        validate_observations(_hardware_observations(), baseline, 1, 0.25)


def test_native_webrtc_gate_requires_a_real_positive_control():
    from scripts.verify_native_webrtc import validate_probe

    with pytest.raises(ValueError, match="positive control"):
        validate_probe({"loopback_stun_requests": 0}, protected=False)
    validate_probe({"loopback_stun_requests": 1}, protected=False)


@pytest.mark.parametrize("requests,candidates,gathering,error", [
    (1, [], "complete", "ignored or ineffective"),
    (0, [{"protocol": "udp"}], "complete", "ignored or ineffective"),
    (0, [], "gathering", "did not complete"),
])
def test_native_webrtc_gate_rejects_direct_udp_and_incomplete_observations(requests, candidates, gathering, error):
    from scripts.verify_native_webrtc import validate_probe

    with pytest.raises(ValueError, match=error):
        validate_probe({"loopback_stun_requests": requests, "candidates": candidates,
                        "gathering": gathering}, protected=True)


def test_native_webrtc_gate_accepts_completed_protected_gathering_without_udp():
    from scripts.verify_native_webrtc import validate_probe

    validate_probe({"loopback_stun_requests": 0, "candidates": [], "gathering": "complete"}, protected=True)


@pytest.mark.parametrize("context", ["same_origin_frame", "cross_origin_frame", "dedicated", "shared", "service"])
def test_native_hardware_gate_requires_coherent_values_in_every_context(context):
    from scripts.verify_native_hardware import validate_observations

    values = _hardware_observations()
    values[context]["hardwareConcurrency"] = 3
    with pytest.raises(ValueError, match="disagree"):
        validate_observations(values)


def test_native_hardware_gate_rejects_missing_workers_and_changed_identity():
    from scripts.verify_native_hardware import validate_observations

    values = _hardware_observations()
    values.pop("service")
    with pytest.raises(ValueError, match="every"):
        validate_observations(values)
    baseline = _hardware_observations()["document"]
    values = _hardware_observations()
    for value in values.values():
        value["platform"] = "Invented device"
    with pytest.raises(ValueError, match="changed platform"):
        validate_observations(values, baseline)


@pytest.mark.parametrize("cpu,memory", [(True, 16), (0, 16), (12, float("nan")), (12, float("inf")), (12, 0)])
def test_native_hardware_gate_rejects_invalid_api_values(cpu, memory):
    from scripts.verify_native_hardware import validate_observations

    with pytest.raises(ValueError, match="invalid"):
        validate_observations(_hardware_observations(cpu, memory))


def _native_build_stage_fixture(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/DEPS").write_text("pinned dependency inputs", encoding="utf-8")
    (tmp_path / ".gclient").write_text("owned source configuration", encoding="utf-8")
    for name in ("camouflow-git-revisions.json", "camouflow-cipd-installed.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    return tmp_path


def test_native_build_does_not_treat_gclient_entries_as_success(tmp_path):
    from scripts.native_build import require_stage

    chromium = _native_build_stage_fixture(tmp_path)
    (chromium / ".gclient_entries").write_text("partial sync", encoding="utf-8")
    with pytest.raises(ValueError, match="successful completion"):
        require_stage(chromium, "sync")


@pytest.mark.parametrize("stage", ["sync", "hooks"])
def test_native_build_stage_records_are_atomic_and_match_actual_inputs(tmp_path, stage):
    import json

    from scripts.native_build import record_stage, require_stage, stage_identity, stage_path

    chromium = _native_build_stage_fixture(tmp_path)
    record_stage(chromium, stage)
    require_stage(chromium, stage)
    target = stage_path(chromium, stage)
    assert not target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert json.loads(target.read_text(encoding="utf-8")) == stage_identity(chromium, stage)
    assert not list(chromium.glob("*.tmp"))


@pytest.mark.parametrize("name", ["src/DEPS", ".gclient", "camouflow-git-revisions.json", "camouflow-cipd-installed.json"])
def test_native_build_rejects_stage_records_after_input_changes(tmp_path, name):
    from scripts.native_build import record_stage, require_stage

    chromium = _native_build_stage_fixture(tmp_path)
    record_stage(chromium, "sync")
    (chromium / name).write_text("different build inputs", encoding="utf-8")
    with pytest.raises(ValueError, match="inputs changed"):
        require_stage(chromium, "sync")


def test_native_build_rejects_corrupt_stage_record_and_unknown_stage(tmp_path):
    from scripts.native_build import require_stage, stage_path

    chromium = _native_build_stage_fixture(tmp_path)
    stage_path(chromium, "sync").write_text("unfinished record", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid"):
        require_stage(chromium, "sync")
    with pytest.raises(ValueError, match="Unknown"):
        stage_path(chromium, "other")


def test_native_build_records_installed_cipd_instances_without_reresolving_remote_tags(tmp_path, monkeypatch):
    from scripts import native_build

    commands = []
    monkeypatch.setattr(native_build, "depot_command", lambda name, workspace: [name])
    monkeypatch.setattr(native_build, "run", lambda args, *a, **kw: commands.append(args))
    native_build.snapshot_dependencies(tmp_path, tmp_path, {})
    assert commands == [
        ["gclient", "revinfo", "-a", "--ignore-dep-type", "cipd", "--output-json", str(tmp_path / "camouflow-git-revisions.json")],
        ["cipd", "installed", "-root", str(tmp_path), "-json-output", str(tmp_path / "camouflow-cipd-installed.json")],
    ]


def test_native_build_checks_the_chromium_dependency_layers_changed_by_the_patch(tmp_path, monkeypatch):
    import os

    from scripts import native_build

    commands = []
    monkeypatch.setattr(native_build, "run", lambda args, *a, **kw: commands.append(args))
    native_build.check_patch_dependencies(tmp_path, {})
    assert commands[0] == ["git", "diff", "--check"]
    assert [command[-1] for command in commands[1:3]] == [
        os.path.normcase(str(tmp_path / "third_party/blink/renderer/core/frame")),
        os.path.normcase(str(tmp_path / "content/browser/renderer_host")),
    ]
    assert all(command[-2] == os.path.normcase(str(tmp_path)) for command in commands[1:3])
    assert commands[3][:2] == [sys.executable, "-c"]
    assert "CheckAddedCppIncludes" in commands[3][2]
    assert "chrome/browser/renderer_preferences_util.cc" in commands[3][2]
    assert commands[3][-1] == os.path.normcase(str(tmp_path))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows depot_tools uses SDK launcher indirection")
@pytest.mark.parametrize("name", ["gn", "autoninja"])
def test_native_build_uses_pinned_sdk_python_for_build_wrappers(tmp_path, name):
    from scripts.native_build import depot_command

    python = tmp_path / "depot_tools/.cipd_bin/3.11/bin/python3.exe"
    with pytest.raises(ValueError, match="Bootstrap"):
        depot_command(name, tmp_path)
    python.parent.mkdir(parents=True)
    python.touch()
    assert depot_command(name, tmp_path) == [str(python), str(tmp_path / "depot_tools" / (name + ".py"))]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows GN must not use the Microsoft Store Python alias")
def test_native_build_makes_pinned_python_available_to_gn_child_scripts(tmp_path):
    from scripts.native_build import environment

    python = tmp_path / "depot_tools/.cipd_bin/3.11/bin/python3.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    assert environment(tmp_path)["PATH"].split(";")[0] == str(python.parent)


def _midl_name_fixture():
    import struct

    names = ("SystemTraceSessionLib", "ISystemTraceSession")
    records = bytearray()
    for name in names:
        encoded = name.encode("ascii")
        records.extend(struct.pack("<III", 0xffffffff, 0xffffffff, len(encoded) | 0x3800))
        records.extend(encoded + b"W" * (-len(encoded) % 4))
    contents = bytearray(0x54 + 15 * 16 + 512 + len(records))
    contents[:8] = b"MSFT\x02\x00\x01\x00"
    struct.pack_into("<III", contents, 0x0c, 1033, 0, 67)
    struct.pack_into("<I", contents, 0x30, len(names))
    struct.pack_into("<II", contents, 0x54 + 6 * 16, 324, 512)
    struct.pack_into("<II", contents, 0x54 + 7 * 16, 836, len(records))
    contents[324:836] = b"\xff" * 512
    contents[836:] = records
    return bytes(contents)


def test_midl_hash_normalization_uses_stored_locale_and_rebuilds_collision_chains():
    import struct

    from native.toolchain.midl_locale import normalize_name_hashes

    observed = []
    def hash_name(system, locale, name):
        observed.append((system, locale, name))
        return 0x100042
    original = _midl_name_fixture()
    normalized = normalize_name_hashes(original, hash_name)
    assert observed == [(3, 1033, "SystemTraceSessionLib"), (3, 1033, "ISystemTraceSession")]
    assert len(normalized) == len(original)
    assert normalized[:324] == original[:324]
    assert struct.unpack_from("<I", normalized, 324 + 0x42 * 4)[0] == 36
    assert struct.unpack_from("<I", normalized, 836 + 36 + 4)[0] == 0
    assert struct.unpack_from("<H", normalized, 836 + 10)[0] == 0x42
    assert normalized[848:872] == original[848:872]
    assert normalize_name_hashes(normalized, hash_name) == normalized


@pytest.mark.parametrize("failure", ["signature", "directory", "overlap", "truncated", "count", "unicode", "system"])
def test_midl_normalizer_rejects_unsupported_or_malformed_tables(failure):
    import struct

    from native.toolchain.midl_locale import normalize_name_hashes

    contents = bytearray(_midl_name_fixture())
    if failure == "signature":
        contents[0] = 0
    elif failure == "directory":
        struct.pack_into("<I", contents, 0x20, 0xffffffff)
    elif failure == "overlap":
        struct.pack_into("<I", contents, 0x54 + 7 * 16, 400)
    elif failure == "truncated":
        contents.pop()
    elif failure == "count":
        struct.pack_into("<I", contents, 0x30, 20)
    elif failure == "unicode":
        contents[848] = 255
    else:
        struct.pack_into("<I", contents, 0x14, 68)
    with pytest.raises(ValueError):
        normalize_name_hashes(bytes(contents), lambda *args: 42)


def test_midl_patch_embeds_the_tested_normalizer_without_drift():
    from scripts.native_build import ROOT

    patch = (ROOT / "native/patches/0002-midl-locale-name-hashes.patch").read_text(encoding="utf-8-sig")
    section = patch.split("+++ b/build/toolchain/win/midl_locale.py\n", 1)[1]
    embedded = "\n".join(line[1:] for line in section.splitlines() if line.startswith("+")) + "\n"
    assert embedded == (ROOT / "native/toolchain/midl_locale.py").read_text(encoding="utf-8-sig")


@pytest.mark.skipif(sys.platform != "win32", reason="Actual Windows Automation hash API")
def test_midl_normalization_uses_actual_windows_hashes_for_the_declared_locale():
    import ctypes
    import struct

    from native.toolchain.midl_locale import normalize_windows_name_hashes

    function = ctypes.WinDLL("oleaut32").LHashValOfNameSys
    function.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_wchar_p]
    function.restype = ctypes.c_uint32
    english = function(3, 1033, "SystemTraceSessionLib") & 0xffff
    russian = function(3, 1049, "SystemTraceSessionLib") & 0xffff
    assert english != russian
    for locale, expected in ((1033, english), (1049, russian)):
        contents = bytearray(_midl_name_fixture())
        struct.pack_into("<I", contents, 0x0c, locale)
        normalized = normalize_windows_name_hashes(bytes(contents))
        assert struct.unpack_from("<H", normalized, 846)[0] == expected
        assert normalize_windows_name_hashes(normalized) == normalized


def test_native_patch_validation_rejects_extra_edits_in_known_files_without_changing_real_index(tmp_path, monkeypatch):
    import os
    import subprocess

    from scripts import native_build

    source = tmp_path / "source"
    source.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    def git(*args):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", *args], cwd=source, env=env)
    git("init", "--quiet")
    original = "first\n" + "unchanged\n" * 20
    file = source / "profile.cc"
    file.write_text(original, encoding="utf-8", newline="\n")
    git("add", ".")
    git("-c", "user.name=Native fixture", "-c", "user.email=fixture@localhost", "commit", "--quiet", "-m", "baseline")
    expected_index = git("ls-files", "--stage")
    file.write_text(original.replace("first", "native"), encoding="utf-8", newline="\n")
    public = tmp_path / "public"
    patches = public / "native/patches"
    patches.mkdir(parents=True)
    (patches / "0001-native-hardware-privacy-limits.patch").write_bytes(git("diff"))
    (patches / "0002-midl-locale-name-hashes.patch").write_text("", encoding="utf-8")
    (patches / "0003-native-webrtc-routing-policy.patch").write_text("", encoding="utf-8")
    (patches / "0004-native-automation-exposure.patch").write_text("", encoding="utf-8")
    (patches / "0005-native-windows-font-collection.patch").write_text("", encoding="utf-8")
    monkeypatch.setattr(native_build, "ROOT", public)
    assert len(native_build.source_patches(source, env)) == 1
    file.write_text(file.read_text(encoding="utf-8-sig") + "unreviewed edit\n", encoding="utf-8", newline="\n")
    with pytest.raises(subprocess.CalledProcessError):
        native_build.source_patches(source, env)
    assert git("ls-files", "--stage") == expected_index
    assert not list(tmp_path.glob("native-patch-index-*"))


def test_controller_process_identity_survives_reparenting_and_rejects_pid_reuse():
    from scripts.verify_native_runtime import same_process

    original = {"name": "node", "started": "first", "parent": 123}
    assert same_process(original, {**original, "parent": 1})
    assert not same_process(original, {**original, "started": "second"})
    assert same_process(original, {**original, "name": "renamed thread"})
    assert not same_process(original, None)


@pytest.mark.parametrize("rounds,profiles", [(0, 3), (101, 3), (True, 3), (3, 1), (3, 5), (3, True)])
def test_native_multi_profile_restart_gate_rejects_unbounded_or_single_profile_runs(tmp_path, rounds, profiles):
    import asyncio
    from scripts.verify_native_runtime import verify_multi_profile_restarts

    with pytest.raises(ValueError, match="1..100 rounds and 2..4 profiles"):
        asyncio.run(verify_multi_profile_restarts(tmp_path, tmp_path / "missing", "http://127.0.0.1:1",
                                                rounds=rounds, profiles=profiles))
    assert list(tmp_path.iterdir()) == []


def test_native_multi_profile_restart_gate_closes_all_started_profiles_when_start_fails(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts import verify_native_runtime

    runtimes = [SimpleNamespace(start=AsyncMock(return_value=SimpleNamespace(pages=[object()])), close=AsyncMock()),
                SimpleNamespace(start=AsyncMock(side_effect=RuntimeError("owned startup failed")), close=AsyncMock())]
    created = iter(runtimes)
    monkeypatch.setattr(verify_native_runtime, "NativeRuntime", lambda *args: next(created))
    monkeypatch.setattr(verify_native_runtime, "process_snapshot", lambda: {})
    with pytest.raises(RuntimeError, match="owned startup failed"):
        asyncio.run(verify_native_runtime.verify_multi_profile_restarts(tmp_path, tmp_path / "missing", "http://127.0.0.1:1"))
    for runtime in runtimes:
        runtime.start.assert_awaited_once()
        runtime.close.assert_awaited_once()


def test_controller_tree_excludes_preexisting_processes_and_tracks_new_descendants_only():
    from scripts.verify_native_runtime import controller_descendants

    old = {"name": "node", "started": "old", "parent": 500}
    before = {20: old, 30: {"name": "chrome", "started": "old", "parent": 500}}
    current = {10: {"name": "python", "started": "new", "parent": 500},
               20: {**old, "parent": 10},
               30: {"name": "node", "started": "new", "parent": 10},
               40: {"name": "chrome", "started": "new", "parent": 30},
               50: {"name": "unrelated", "started": "new", "parent": 500}}
    assert set(controller_descendants(before, current, 10)) == {30, 40}


def test_controller_process_snapshot_parses_posix_start_times_and_names_with_spaces(monkeypatch):
    from scripts import verify_native_runtime

    monkeypatch.setattr(verify_native_runtime.sys, "platform", "darwin")
    monkeypatch.setattr(verify_native_runtime.subprocess, "check_output", lambda *a, **kw:
        " 100 90 Sun Oct 11 07:00:00 2026 /Applications/Chromium.app/Contents/MacOS/Chromium\n"
        " 101 100 Sun Oct 11 07:00:01 2026 /Applications/Chromium Helper (Renderer)\n")
    rows = verify_native_runtime.process_snapshot()
    assert rows[100] == {"parent": 90, "started": "Sun Oct 11 07:00:00 2026", "name": "Chromium"}
    assert rows[101]["name"] == "Chromium Helper (Renderer)"


def test_linux_process_snapshot_separates_executable_identity_from_thread_names(tmp_path, monkeypatch):
    from pathlib import Path
    from scripts.verify_native_runtime import executable_name, linux_process_snapshot

    root = tmp_path / "proc"
    root.mkdir()
    for pid, state in ((100, "S"), (101, "Z"), (102, "S")):
        directory = root / str(pid)
        directory.mkdir()
        fields = [state, "7", *(["0"] * 17), "12345"]
        (directory / "stat").write_text(f"{pid} (Main Thread (Node)) " + " ".join(fields), encoding="utf-8")
    def readlink(path):
        if path.parent.name == "100":
            return Path("/sdk/playwright/driver/node")
        raise PermissionError("Unobservable sandboxed executable")
    monkeypatch.setattr(Path, "readlink", readlink)
    rows = linux_process_snapshot(root)
    assert rows[100] == {"parent": 7, "started": "12345", "name": "Main Thread (Node)", "executable": "node"}
    assert executable_name(rows[100]) == "node"
    assert 101 not in rows
    assert rows[102]["executable"] is None
    assert executable_name(rows[102]) is None
