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


def test_native_build_clean_baseline_has_no_patches(tmp_path, monkeypatch):
    from scripts import native_build

    monkeypatch.setattr(native_build, "run", lambda *args, **kwargs: "")
    assert native_build.source_patches(tmp_path, {}) == []


def test_native_build_rejects_unknown_source_changes(tmp_path, monkeypatch):
    from scripts import native_build

    monkeypatch.setattr(native_build, "run", lambda *args, **kwargs: "customer.cc")
    with pytest.raises(ValueError, match="Unrecognized"):
        native_build.source_patches(tmp_path, {})


def test_native_build_verifies_applied_patch_and_records_checksum(tmp_path, monkeypatch):
    import hashlib

    from scripts import native_build

    patch = native_build.ROOT / "native/patches/0001-native-hardware-privacy-limits.patch"
    expected = [line.split(" b/", 1)[1] for line in patch.read_text(encoding="utf-8").splitlines()
                if line.startswith("diff --git ")]
    commands = []

    def fake_run(args, cwd, env, capture=False):
        commands.append(args)
        return "\n".join(expected) if args[1] == "diff" else ""

    monkeypatch.setattr(native_build, "run", fake_run)
    assert native_build.source_patches(tmp_path, {}) == [
        {"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}]
    assert commands[-1] == ["git", "apply", "--reverse", "--check", str(patch)]


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
    assert [command[-1] for command in commands[1:]] == [
        os.path.normcase(str(tmp_path / "third_party/blink/renderer/core/frame")),
        os.path.normcase(str(tmp_path / "content/browser/renderer_host")),
    ]
    assert all(command[-2] == os.path.normcase(str(tmp_path)) for command in commands[1:])


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
