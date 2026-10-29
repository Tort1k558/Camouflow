"""Native package paths must match the PyInstaller spec on each host OS."""

import sys
from pathlib import Path

import pytest

from scripts import verify_release


def test_native_suite_collects_failures_and_continues_without_reusing_reports(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from scripts import verify_native_suite as suite

    monkeypatch.setattr(suite.sys, "platform", "win32")
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"owned-fixture-not-a-browser")
    for name in ("chrome.dll", "chrome_elf.dll"):
        (tmp_path / name).write_bytes(name.encode())
    destination = tmp_path / "reports"
    calls = []
    def run(command, **kwargs):
        gate = Path(command[1]).stem.removeprefix("verify_native_")
        calls.append(gate)
        report = Path(command[command.index("--report") + 1])
        report.write_text(json.dumps({"passed": gate != "hardware", "checks": [{"passed": True}],
            "binary_sha256_measured": suite.checksum(executable)}), encoding="utf-8")
        return SimpleNamespace(returncode=0 if gate != "hardware" else 1)
    monkeypatch.setattr(suite.subprocess, "run", run)
    report = suite.verify(executable, destination, ["hardware", "webrtc"])
    assert calls == ["hardware", "webrtc"]
    assert not report["passed"] and not report["full_suite"]
    assert [gate["passed"] for gate in report["gates"]] == [False, True]
    assert report == json.loads((destination / "suite.json").read_text(encoding="utf-8"))
    assert report["gates"][1]["report_sha256"] == suite.checksum(destination / "webrtc.json")
    with pytest.raises(FileExistsError):
        suite.verify(executable, destination, ["webrtc"])


def test_native_suite_stops_on_binary_drift_and_preserves_failed_evidence(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from scripts import verify_native_suite as suite

    monkeypatch.setattr(suite.sys, "platform", "win32")
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"original")
    for name in ("chrome.dll", "chrome_elf.dll"):
        (tmp_path / name).write_bytes(name.encode())
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        executable.write_bytes(b"changed")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(suite.subprocess, "run", run)
    report = suite.verify(executable, tmp_path / "reports", ["hardware", "webrtc"])
    assert len(calls) == 1 and not report["passed"]
    assert "changed" in report["error"]
    assert not report["gates"][0]["passed"]
    assert not json.loads((tmp_path / "reports/suite.json").read_text(encoding="utf-8"))["passed"]


@pytest.mark.parametrize("report", [
    {"passed": True, "checks": []},
    {"passed": True, "checks": [{"passed": False}], "binary_sha256_measured": "owned"},
    {"passed": True, "checks": [{"passed": True}], "binary_sha256_measured": "wrong"},
    {"passed": False, "checks": [{"passed": True}], "binary_sha256_measured": "owned"},
])
def test_native_suite_rejects_false_or_unbound_evidence(report):
    from scripts.verify_native_suite import validate_report

    with pytest.raises(ValueError):
        validate_report("hardware", report, "owned")


@pytest.mark.parametrize("drift", ["disk-dll", "report-dll"])
def test_native_suite_rejects_dll_drift_even_when_launcher_is_unchanged(tmp_path, monkeypatch, drift):
    import json
    from types import SimpleNamespace
    from scripts import verify_native_suite as suite

    monkeypatch.setattr(suite.sys, "platform", "win32")
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"launcher unchanged")
    for name in ("chrome.dll", "chrome_elf.dll"):
        (tmp_path / name).write_bytes(name.encode())
    original = suite.measure_runtime_core(executable)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        core = dict(original)
        if drift == "disk-dll":
            (tmp_path / "chrome.dll").write_bytes(b"new linked code")
        else:
            core["chrome.dll"] = "a" * 64
        Path(command[command.index("--report") + 1]).write_text(json.dumps({
            "passed": True, "checks": [{"passed": True}], "binary_sha256_measured": original["chrome.exe"],
            "runtime_core_sha256_measured": core}), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(suite.subprocess, "run", run)
    report = suite.verify(executable, tmp_path / "reports", ["hardware", "webrtc"])
    assert not report["passed"]
    assert all(not gate["passed"] for gate in report["gates"])
    assert report["runtime_core_sha256_measured"] == original
    assert suite.checksum(executable) == original["chrome.exe"]
    assert len(calls) == (1 if drift == "disk-dll" else 2)


def test_native_suite_propagates_explicit_versioned_dll_layout_only_to_supported_gates(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from scripts import verify_native_suite as suite

    monkeypatch.setattr(suite.sys, "platform", "win32")
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"owned versioned launcher")
    libraries = tmp_path / "148.0.7778.96"
    libraries.mkdir()
    for name in ("chrome.dll", "chrome_elf.dll"):
        (libraries / name).write_bytes(name.encode())
    core = suite.measure_runtime_core(executable, libraries)
    def run(command, **kwargs):
        gate = Path(command[1]).stem.removeprefix("verify_native_")
        if gate in {"runtime", "identity", "combined"}:
            assert command[command.index("--windows-library-directory") + 1] == str(libraries)
        else:
            assert "--windows-library-directory" not in command
        checks = (sorted(suite.REQUIRED_RUNTIME_CHECKS) if gate == "runtime" else
                  [{"name": name, "passed": True} for name in sorted(suite.REQUIRED_COMBINED_CHECKS)] if gate == "combined" else
                  [{"passed": True}])
        Path(command[command.index("--report") + 1]).write_text(json.dumps({
            "passed": True, "checks": checks, "binary_sha256_measured": core["chrome.exe"],
            "runtime_core_sha256_measured": core, "arguments": suite.ARGUMENTS}), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(suite.subprocess, "run", run)
    report = suite.verify(executable, tmp_path / "reports", ["runtime", "hardware", "identity", "combined"], library_directory=libraries)
    assert report["passed"] and not report["full_suite"]
    assert report["runtime_core_sha256_measured"] == core


def test_native_suite_requires_all_runtime_lifecycle_checks():
    from scripts.verify_native_suite import REQUIRED_RUNTIME_CHECKS, validate_report

    report = {"passed": True, "binary_sha256_measured": "owned", "checks": list(REQUIRED_RUNTIME_CHECKS)}
    validate_report("runtime", report, "owned")
    report["checks"].pop()
    with pytest.raises(ValueError, match="missing"):
        validate_report("runtime", report, "owned")


@pytest.mark.parametrize("failure", [None, "resource", "removed-resource", "metadata", "child-release"])
def test_native_suite_binds_installed_payload_and_stops_on_drift(tmp_path, monkeypatch, failure):
    import json
    from types import SimpleNamespace
    from app.core.native.distribution import NativeBinaryStore
    from scripts import package_native_windows as packaging, verify_native_suite as suite

    monkeypatch.setattr(suite.sys, "platform", "win32")
    output, staged, runtime_report, archive = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    packaged = packaging.package(output, staged, runtime_report, archive)
    store = NativeBinaryStore(tmp_path / "store")
    release = store.install_archive(archive, packaged["sha256"])
    executable = Path(release["executable_path"])
    libraries = executable.parent / release["chromium_version"]
    calls = []

    def run(command, **kwargs):
        gate = Path(command[1]).stem.removeprefix("verify_native_")
        calls.append(gate)
        assert command[command.index("--windows-library-directory") + 1] == str(libraries)
        if gate == "runtime":
            assert command[command.index("--release-store") + 1] == str(store.root)
            assert command[command.index("--release-sha256") + 1] == packaged["sha256"]
        else:
            assert "--release-store" not in command
        value = {"passed": True, "checks": sorted(suite.REQUIRED_RUNTIME_CHECKS) if gate == "runtime" else [{"passed": True}],
                 "binary_sha256_measured": release["executable_sha256"],
                 "release_sha256_measured": "0" * 64 if failure == "child-release" else packaged["sha256"],
                 "payload_files_sha256_measured": release["files_sha256"]}
        Path(command[command.index("--report") + 1]).write_text(json.dumps(value), encoding="utf-8")
        if gate == "runtime":
            resource = libraries / "locales/en-US.pak"
            if failure == "resource":
                resource.write_bytes(b"changed non-code resource")
            elif failure == "removed-resource":
                resource.unlink()
            elif failure == "metadata":
                path = executable.parent / "native-release.json"
                metadata = json.loads(path.read_text(encoding="utf-8"))
                metadata["unexpected_change"] = True
                path.write_text(json.dumps(metadata), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(suite.subprocess, "run", run)
    destination = tmp_path / "reports"
    result = suite.verify(executable, destination, ["runtime", "identity"], library_directory=libraries,
                          release_store=store.root, release_digest=packaged["sha256"])
    assert result["passed"] is (failure is None)
    assert result["release_sha256_measured"] == packaged["sha256"]
    assert result["payload_files_sha256_measured"] == release["files_sha256"]
    assert calls == (["runtime", "identity"] if failure in {None, "child-release"} else ["runtime"])
    assert result == json.loads((destination / "suite.json").read_text(encoding="utf-8"))
    if failure == "child-release":
        assert "bind" in result["gates"][0]["error"]
    elif failure is not None:
        assert "error" in result


@pytest.mark.parametrize("store,digest", [(None, "a" * 64), (Path("unused"), "")])
def test_native_suite_requires_paired_release_options_before_creating_evidence(tmp_path, monkeypatch, store, digest):
    from scripts import verify_native_suite as suite

    monkeypatch.setattr(suite.sys, "platform", "win32")
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"owned launcher")
    destination = tmp_path / "evidence"
    with pytest.raises(ValueError, match="both store and checksum"):
        suite.verify(executable, destination, ["runtime"], release_store=store, release_digest=digest)
    assert not destination.exists()


def test_native_suite_refuses_to_write_profiles_or_reports_inside_binary_store(tmp_path, monkeypatch):
    from scripts import verify_native_suite as suite

    monkeypatch.setattr(suite.sys, "platform", "win32")
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"owned launcher")
    destination = tmp_path / "reports"
    with pytest.raises(ValueError, match="outside.*binary store"):
        suite.verify(executable, destination, ["runtime"], release_store=tmp_path, release_digest="a" * 64)
    assert not destination.exists()


@pytest.mark.parametrize("platform,executable", [
    ("win32", "CamouFlow/CamouFlow.exe"),
    ("linux", "CamouFlow/CamouFlow"),
    ("darwin", "CamouFlow.app/Contents/MacOS/CamouFlow"),
])
@pytest.mark.parametrize("external", [False, True])
def test_build_uses_native_package_executable(tmp_path, monkeypatch, platform, executable, external):
    python = Path(sys.executable)
    artifacts = tmp_path / "external" if external else tmp_path
    artifacts.mkdir(exist_ok=True)
    monkeypatch.setattr(verify_release, "ROOT", tmp_path)
    monkeypatch.setattr(verify_release.sys, "platform", platform)
    def fake_build(command):
        assert command[0] == str(python)
        dist = Path(command[command.index("--distpath") + 1])
        assert dist.is_relative_to(artifacts / "dist")
        assert Path(command[command.index("--workpath") + 1]).is_relative_to(artifacts / "build")
        target = dist / executable
        target.parent.mkdir(parents=True)
        target.touch()
    monkeypatch.setattr(verify_release, "run", fake_build)
    assert verify_release.build(python, artifacts_dir=artifacts if external else None).relative_to(artifacts / "dist").as_posix().endswith(executable)


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
    retained = Path(result["retained_profile_directory"])
    assert retained == retained.resolve() and retained.is_dir()
    assert retained.parent == tmp_path / "owned"
    assert list((tmp_path / "owned").iterdir()) == [retained]


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
        assert env["GIT_CONFIG_COUNT"] == "7"
        assert env["GIT_CONFIG_KEY_1"] == "http.sslBackend"
        assert env["GIT_CONFIG_VALUE_1"] == "openssl"
        assert {env[f"GIT_CONFIG_KEY_{index}"]: env[f"GIT_CONFIG_VALUE_{index}"] for index in range(2, 6)} == {
            "core.autocrlf": "false", "core.filemode": "false", "core.fscache": "true", "core.preloadIndex": "true"}
        assert env["GIT_CONFIG_KEY_6"] == "http.sslVerify"
        assert env["GIT_CONFIG_VALUE_6"] == "true"
    else:
        assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["DEPOT_TOOLS_UPDATE"] == "0"
    assert env["DEPOT_TOOLS_METRICS"] == "0"
    assert env["GIT_CONFIG_GLOBAL"] == str(tmp_path / "build.gitconfig")
    assert env["CIPD_CACHE_DIR"] == str(tmp_path / "cipd-cache")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Git overrides only")
@pytest.mark.parametrize("autocrlf", ["true", "input"])
def test_native_dependency_git_settings_override_machine_defaults_without_editing_them(tmp_path, monkeypatch, autocrlf):
    import os
    import subprocess
    from scripts.native_build import environment

    system = tmp_path / "machine.gitconfig"
    original = (f"[core]\n\tautocrlf = {autocrlf}\n\tfilemode = true\n"
                "\tfscache = false\n\tpreloadindex = false\n")
    system.write_text(original, encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.autocrlf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")
    env = environment(tmp_path)
    dependency = tmp_path / "dependency"
    dependency.mkdir()
    subprocess.run(["git", "init", str(dependency)], env=env, check=True, capture_output=True)
    for key, value in {"core.autocrlf": "false", "core.filemode": "false",
                       "core.fscache": "true", "core.preloadIndex": "true"}.items():
        result = subprocess.run(["git", "config", "--get", key], cwd=dependency, env=env,
                                check=True, capture_output=True, text=True)
        assert result.stdout.strip() == value
    assert system.read_text(encoding="utf-8") == original
    assert os.environ["GIT_CONFIG_COUNT"] == "1"
    assert os.environ["GIT_CONFIG_VALUE_0"] == "true"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Git TLS backends")
@pytest.mark.parametrize("backend", ["openssl", "schannel"])
def test_native_git_backend_is_explicit_and_keeps_certificate_validation(tmp_path, monkeypatch, backend):
    import os
    import subprocess
    from scripts.native_build import environment

    monkeypatch.setenv("GIT_SSL_NO_VERIFY", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "http.sslVerify")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")
    env = environment(tmp_path, git_ssl_backend=backend)
    assert "GIT_SSL_NO_VERIFY" not in env
    assert os.environ["GIT_SSL_NO_VERIFY"] == "1"
    assert os.environ["GIT_CONFIG_VALUE_0"] == "false"
    for key, value in {"http.sslBackend": backend, "http.sslVerify": "true"}.items():
        result = subprocess.run(["git", "config", "--get", key], cwd=tmp_path, env=env,
                                check=True, capture_output=True, text=True)
        assert result.stdout.strip() == value


@pytest.mark.parametrize("backend", ["auto", "curl", "", None])
def test_native_git_backend_rejects_unknown_selection_before_writes(tmp_path, backend):
    from scripts.native_build import environment

    with pytest.raises(ValueError, match="explicit supported"):
        environment(tmp_path, git_ssl_backend=backend)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(sys.platform == "win32", reason="Schannel is supported on Windows")
def test_native_git_backend_rejects_schannel_off_windows(tmp_path):
    from scripts.native_build import environment

    with pytest.raises(ValueError, match="requires Windows"):
        environment(tmp_path, git_ssl_backend="schannel")
    assert list(tmp_path.iterdir()) == []


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


@pytest.mark.parametrize("missing_dll", [None, "chrome.dll", "chrome_elf.dll"])
@pytest.mark.parametrize("candidate_name", [None, "upstream-156"])
@pytest.mark.parametrize("local_toolchain", [False, True])
def test_native_build_passes_selected_concurrency_to_compiler_and_receipt(tmp_path, monkeypatch, missing_dll, candidate_name, local_toolchain):
    import json
    from scripts import native_build
    if local_toolchain and (not candidate_name or sys.platform != "win32"):
        with pytest.raises(ValueError, match="explicit.*candidate build"):
            native_build.execute("build", tmp_path, candidate_name=candidate_name, local_toolchain=True)
        assert not (tmp_path / "chromium").exists()
        return
    if missing_dll and sys.platform != "win32":
        pytest.skip("Windows core DLL receipt")
    candidate = native_build.load_candidate(candidate_name) if candidate_name else None
    if candidate:
        native_build.candidate_workspace(tmp_path, candidate, claim=True)
    selected_lock = native_build.LOCK if candidate is None else candidate["lock"]

    source = tmp_path / "chromium/src"
    source.mkdir(parents=True)
    (source.parent / ".gclient").write_text("owned", encoding="utf-8")
    (source / "DEPS").write_text("owned", encoding="utf-8")
    output = source / "out/CamouFlowNative"
    output.mkdir(parents=True)
    receipt_path = output / "camouflow-build.json"
    receipt_path.write_text("stale receipt", encoding="utf-8")
    relative = {"win32": "chrome.exe", "linux": "chrome", "darwin": "Chromium.app/Contents/MacOS/Chromium"}[sys.platform]
    commands = []
    def run(args, *a, **kwargs):
        commands.append(args)
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return selected_lock["chromium_revision"]
        if args[0] == "autoninja":
            binary = source / "out/CamouFlowNative" / relative
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"owned test binary")
            if sys.platform == "win32":
                for name in ("chrome.dll", "chrome_elf.dll"):
                    if name != missing_dll:
                        (binary.parent / name).write_bytes(name.encode("ascii"))
        return ""
    monkeypatch.setattr(native_build, "preflight", lambda *a, **kw: {})
    selected_environment = {"GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": "a" * 64} if local_toolchain else {}
    monkeypatch.setattr(native_build, "environment", lambda *a, **kwargs: dict(selected_environment))
    monkeypatch.setattr(native_build, "local_windows_toolchain", lambda *a: dict(selected_environment))
    monkeypatch.setattr(native_build, "checkout", lambda *a: None)
    monkeypatch.setattr(native_build, "bootstrap_windows_git", lambda *a: None)
    monkeypatch.setattr(native_build, "require_stage", lambda *a: None)
    monkeypatch.setattr(native_build, "v8_source_patches", lambda *a: [])
    monkeypatch.setattr(native_build, "source_patches", lambda *a: [])
    candidate_checks = []
    def check_candidate(source, env, selected):
        candidate_checks.append(selected)
        return []
    monkeypatch.setattr(native_build, "candidate_source_patches", check_candidate)
    monkeypatch.setattr(native_build, "depot_command", lambda name, *a: [name])
    monkeypatch.setattr(native_build, "run", run)
    if missing_dll:
        with pytest.raises(ValueError, match=missing_dll):
            native_build.execute("build", tmp_path, jobs=1, candidate_name=candidate_name, local_toolchain=local_toolchain)
        assert not receipt_path.exists()
        return
    native_build.execute("build", tmp_path, jobs=1, candidate_name=candidate_name, local_toolchain=local_toolchain)
    assert ["autoninja", "-C", "out/CamouFlowNative", "-j", "1", "chrome"] in commands
    receipt = json.loads((source / "out/CamouFlowNative/camouflow-build.json").read_text(encoding="utf-8"))
    assert receipt["build_jobs"] == 1
    assert receipt["native_patch_runtime_verified"] is False
    if local_toolchain:
        assert receipt["local_windows_toolchain_sha256"] == "a" * 64
    else:
        assert "local_windows_toolchain_sha256" not in receipt
    assert receipt["chromium_revision"] == selected_lock["chromium_revision"]
    if candidate:
        assert candidate_checks == [candidate, candidate]
        assert receipt["candidate_manifest_sha256"] == candidate["manifest_sha256"]
    else:
        assert not candidate_checks and "candidate_manifest_sha256" not in receipt
    core = native_build.measure_runtime_core(source / "out/CamouFlowNative" / relative)
    assert receipt["runtime_core_sha256_measured"] == core
    assert receipt["binary_sha256_measured"] == core[Path(relative).name]


@pytest.mark.parametrize("changed", ["patches", "v8_patches", "output_arguments", "input_arguments", "toolchain"])
def test_native_build_does_not_record_success_if_inputs_change_during_compilation(tmp_path, monkeypatch, changed):
    from scripts import native_build
    candidate = native_build.load_candidate("upstream-156") if changed == "toolchain" else None
    if candidate:
        native_build.candidate_workspace(tmp_path, candidate, claim=True)
        monkeypatch.setattr(native_build, "load_candidate", lambda name: candidate)

    source = tmp_path / "chromium/src"
    output = source / "out/CamouFlowNative"
    output.mkdir(parents=True)
    (source.parent / ".gclient").write_text("owned", encoding="utf-8")
    (source / "DEPS").write_text("owned", encoding="utf-8")
    inputs = tmp_path / "inputs"
    (inputs / "native").mkdir(parents=True)
    arguments = inputs / "native/args.gn"
    arguments.write_text("is_debug = false\n", encoding="utf-8")
    receipt = output / "camouflow-build.json"
    receipt.write_text("stale previous build", encoding="utf-8")
    compiled = False

    def run(args, *a, **kwargs):
        nonlocal compiled
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return (candidate["lock"] if candidate else native_build.LOCK)["chromium_revision"]
        if args[0] == "autoninja":
            compiled = True
            if changed == "output_arguments":
                (output / "args.gn").write_text("is_debug = true\n", encoding="utf-8")
            elif changed == "input_arguments":
                arguments.write_text("is_debug = true\n", encoding="utf-8")
        return ""

    monkeypatch.setattr(native_build, "ROOT", inputs)
    monkeypatch.setattr(native_build, "checkout", lambda *a: None)
    monkeypatch.setattr(native_build, "v8_source_patches", lambda *a: [{"name": "changed-v8"}] if compiled and changed == "v8_patches" else [])
    monkeypatch.setattr(native_build, "preflight", lambda *a, **kw: {})
    monkeypatch.setattr(native_build, "environment", lambda *a, **kwargs: {"GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": "a" * 64})
    monkeypatch.setattr(native_build, "local_windows_toolchain", lambda *a: {"GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": "b" * 64})
    monkeypatch.setattr(native_build, "candidate_source_patches", lambda *a: [])
    monkeypatch.setattr(native_build, "bootstrap_windows_git", lambda *a: None)
    monkeypatch.setattr(native_build, "require_stage", lambda *a: None)
    monkeypatch.setattr(native_build, "source_patches", lambda *a: [{"name": "changed"}] if compiled and changed == "patches" else [])
    monkeypatch.setattr(native_build, "depot_command", lambda name, *a: [name])
    monkeypatch.setattr(native_build, "run", run)
    with pytest.raises(ValueError, match="changed during compilation"):
        native_build.execute("build", tmp_path, jobs=1, candidate_name="upstream-156" if candidate else None,
                             local_toolchain=changed == "toolchain")
    assert compiled and not receipt.exists()


@pytest.mark.parametrize("mutation", ["http_ua", "metadata", "http_hint", "getter", "own_property",
    "illegal_invocation", "plugins", "chrome", "empty_versions", "missing_headless_control",
    "http_js_platform", "http_js_language"])
def test_native_identity_gate_rejects_incoherent_or_injected_observations(mutation):
    from copy import deepcopy
    from scripts.verify_native_identity import HINTS, validate_observation

    baseline = {"userAgent": "HeadlessChrome/148.0.0.0",
        "language": "en-US", "userAgentData": {"platform": "Windows", "mobile": False},
        "metadata": {"fullVersionList": [{"brand": "Chromium", "version": "148.0.7778.96"}]},
        "headers": {"user-agent": "HeadlessChrome/148.0.0.0", **{name.lower(): "native" for name in HINTS}},
        "getter": "function get userAgent() { [native code] }", "ownProperty": False,
        "illegalInvocation": True, "plugins": ["PDF Viewer"], "chromeType": "object"}
    baseline["headers"].update({"accept-language": "en-US,en;q=0.9",
                                "sec-ch-ua-platform": '"Windows"', "sec-ch-ua-mobile": "?0"})
    observed = deepcopy(baseline)
    observed["userAgent"] = observed["headers"]["user-agent"] = "Chrome/148.0.0.0"
    if mutation in {"http_js_platform", "http_js_language"}:
        key, value = (("sec-ch-ua-platform", '"Linux"') if mutation == "http_js_platform"
                      else ("accept-language", "de-DE"))
        baseline["headers"][key] = observed["headers"][key] = value
    elif mutation == "http_ua":
        observed["headers"]["user-agent"] = "HeadlessChrome/148.0.0.0"
    elif mutation == "metadata":
        observed["metadata"]["platform"] = "invented"
    elif mutation == "http_hint":
        observed["headers"]["sec-ch-ua-platform"] = "invented"
    elif mutation == "getter":
        observed["getter"] = "function fake() {}"
    elif mutation == "own_property":
        observed["ownProperty"] = True
    elif mutation == "illegal_invocation":
        observed["illegalInvocation"] = False
    elif mutation == "plugins":
        observed["plugins"] = ["invented"]
    elif mutation == "chrome":
        observed["chromeType"] = "undefined"
    elif mutation == "empty_versions":
        baseline["metadata"] = observed["metadata"] = {}
    else:
        baseline["userAgent"] = "Chrome/148.0.0.0"
    with pytest.raises(ValueError):
        validate_observation(observed, baseline, protected=True, worker=False)


@pytest.mark.parametrize("protected,worker", [(False, False), (True, False), (False, True), (True, True)])
def test_native_identity_gate_accepts_only_preserved_native_identity(protected, worker):
    from copy import deepcopy
    from scripts.verify_native_identity import HINTS, validate_observation

    baseline = {"userAgent": "HeadlessChrome/148.0.0.0",
        "language": "en-US", "userAgentData": {"platform": "Windows", "mobile": False},
        "metadata": {"fullVersionList": [{"brand": "Chromium", "version": "148.0.7778.96"}]},
        "headers": {"user-agent": "HeadlessChrome/148.0.0.0", **{name.lower(): None for name in HINTS}},
        "getter": "function get userAgent() { [native code] }", "ownProperty": False,
        "illegalInvocation": True, "plugins": None if worker else ["PDF Viewer"], "chromeType": "undefined" if worker else "object"}
    baseline["headers"].update({"accept-language": "en-US,en;q=0.9",
                                "sec-ch-ua-platform": None if worker else '"Windows"',
                                "sec-ch-ua-mobile": None if worker else "?0"})
    observed = deepcopy(baseline)
    if protected:
        observed["userAgent"] = observed["headers"]["user-agent"] = "Chrome/148.0.0.0"
    validate_observation(observed, baseline, protected=protected, worker=worker)


@pytest.mark.parametrize("mutation", [None, "leak", "missing_control", "event_loss", "stack_loss", "fake_stack", "boolean_counter", "missing_error_type", "wrong_error_type"])
def test_native_cdp_gate_requires_side_effect_free_previews_and_real_positive_controls(mutation):
    from scripts.verify_native_cdp import COUNTERS, ERROR_TYPES, validate_observation

    expected = {name: name + ": Owned normal preview\n    at ownedNativePlainError (owned:1:1)" for name in ERROR_TYPES}
    observed = {"serialization_hits": dict.fromkeys(COUNTERS, 0),
                "explicit_read_controls": dict.fromkeys(COUNTERS, 1),
                "console_events": len(COUNTERS) + len(ERROR_TYPES), "native_previews": expected.copy(),
                "expected_native_previews": expected.copy()}
    if mutation == "leak":
        observed["serialization_hits"]["inheritedName"] = 1
        observed["explicit_read_controls"]["inheritedName"] = 2
    elif mutation == "missing_control":
        observed["explicit_read_controls"]["ownStack"] = 0
    elif mutation == "event_loss":
        observed["console_events"] -= 1
    elif mutation == "stack_loss":
        observed["native_previews"]["Error"] = "Error: Owned normal preview"
    elif mutation == "fake_stack":
        observed["native_previews"]["Error"] = observed["expected_native_previews"]["Error"] = "invented"
    elif mutation == "boolean_counter":
        observed["serialization_hits"]["ownStack"] = False
    elif mutation == "missing_error_type":
        observed["native_previews"].pop("TypeError")
    elif mutation == "wrong_error_type":
        observed["native_previews"]["TypeError"] = observed["expected_native_previews"]["TypeError"] = expected["Error"]
    if mutation is None:
        validate_observation(observed)
    else:
        with pytest.raises(ValueError):
            validate_observation(observed)


@pytest.mark.parametrize("protected,hits", [(False, 1), (True, 0), (True, 1)])
def test_native_cdp_formatter_gate_requires_zero_preview_execution_only_in_protected_mode(protected, hits):
    from scripts.verify_native_cdp import validate_formatter_observation

    observed = {"serialization_hits": hits, "same_error_read_hits": 1, "fresh_error_read_hits": 2,
                "console_events": 1, "same_error_stack": "Owned formatter: Owned formatted error",
                "fresh_error_stack": "Owned formatter: Owned fresh error"}
    if protected and hits:
        with pytest.raises(ValueError, match="prepareStackTrace"):
            validate_formatter_observation(observed, protected=protected)
    else:
        validate_formatter_observation(observed, protected=protected)


@pytest.mark.parametrize("key,value", [("serialization_hits", False), ("serialization_hits", -1),
                                      ("console_events", 0), ("console_events", 2),
                                      ("same_error_read_hits", 0), ("fresh_error_read_hits", 1),
                                      ("same_error_stack", "cached inspector error"), ("fresh_error_stack", "invented")])
def test_native_cdp_formatter_gate_rejects_broken_controls_and_cached_failures(key, value):
    from scripts.verify_native_cdp import validate_formatter_observation

    observed = {"serialization_hits": 0, "same_error_read_hits": 1, "fresh_error_read_hits": 2,
                "console_events": 1, "same_error_stack": "Owned formatter: Owned formatted error",
                "fresh_error_stack": "Owned formatter: Owned fresh error"}
    observed[key] = value
    with pytest.raises(ValueError):
        validate_formatter_observation(observed, protected=True)


def test_native_inspector_patch_uses_upstream_throwing_no_javascript_scope_inside_trycatch():
    from scripts.native_build import ROOT

    patch = (ROOT / "native/patches/0007-native-inspector-error-accessors.patch").read_text(encoding="utf-8-sig")
    assert "DisallowJavascriptExecutionScope no_javascript" in patch
    assert "DisallowJavascriptExecutionScope::THROW_ON_FAILURE" in patch
    assert "CRASH_ON_FAILURE" not in patch
    assert patch.index("v8::TryCatch tryCatch(isolate)") < patch.index("DisallowJavascriptExecutionScope no_javascript")


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


@pytest.mark.parametrize("url,retained", [
    ("http://127.0.0.1:1234/owned-font.ttf", True),
    ("http://localhost:1234/owned-font.ttf", True),
    ("http://127.0.0.1:4321/owned-font.ttf", False),
    ("https://example.com/owned-font.ttf", False),
    ("http://127.0.0.1:1234/other.ttf", False),
])
def test_font_network_trace_is_limited_to_owned_fixture(url, retained):
    from scripts.verify_native_fonts import record_network_event

    events = []
    record_network_event(events, "response", "native-legacy", 0, "http://127.0.0.1:1234", url, {"status": 200})
    assert len(events) == int(retained)
    if retained:
        assert events[0]["mode"] == "native-legacy" and events[0]["details"] == {"status": 200}
    events = [{} for _ in range(512)]
    record_network_event(events, "requestfailed", "native-default", 0,
                         "http://127.0.0.1:1234", url, {"failure": "net::ERR_FAILED"})
    assert len(events) == 512


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


@pytest.mark.parametrize("changed", [False, True])
def test_native_v8_patch_provenance_requires_the_verified_dependency_revision(tmp_path, monkeypatch, changed):
    import json
    from unittest.mock import Mock
    from scripts import native_build

    source = tmp_path / "chromium/src"
    (source / "v8").mkdir(parents=True)
    revision = "a" * 40
    (source.parent / "camouflow-git-revisions.json").write_text(json.dumps({
        "src/v8": {"url": "https://chromium.googlesource.com/v8/v8.git", "rev": revision}}), encoding="utf-8")
    monkeypatch.setattr(native_build, "run", lambda *a, **kw: "b" * 40 if changed else revision)
    validate = Mock(return_value=[{"name": "0007-native-inspector-error-accessors.patch", "sha256": "c" * 64}])
    monkeypatch.setattr(native_build, "_source_patches", validate)
    if changed:
        with pytest.raises(ValueError, match="V8 revision differs"):
            native_build.v8_source_patches(source, {})
        validate.assert_not_called()
    else:
        assert native_build.v8_source_patches(source, {}) == [{
            "name": "0007-native-inspector-error-accessors.patch", "sha256": "c" * 64,
            "repository": "v8", "revision": revision}]
        validate.assert_called_once_with(source / "v8", {}, ("0007-native-inspector-error-accessors.patch",), index_dir=source.parent)


@pytest.mark.parametrize("name", ["0001-native-hardware-privacy-limits.patch",
                                  "0002-midl-locale-name-hashes.patch",
                                  "0003-native-webrtc-routing-policy.patch",
                                  "0004-native-automation-exposure.patch",
                                  "0005-native-windows-font-collection.patch",
                                  "0006-native-headless-user-agent.patch",
                                  "0008-native-leveldb-path-separators.patch",
                                  "0009-native-sql-extended-paths.patch",
                                  "0010-native-windows-profile-namespace.patch",
                                  "0011-native-privacy-partition-serialization.patch",
                                  "0012-native-browser-privacy-key-derivation.patch",
                                  "0013-native-owned-profile-key-loader.patch",
                                  "0014-native-private-key-service-lifecycle.patch",
                                  "0015-native-browser-context-key-ownership.patch",
                                  "0016-native-private-key-readiness.patch",
                                  "0017-native-browser-context-tests.patch",
                                  "0018-native-document-policy-delivery.patch",
                                  "0019-native-worker-policy-delivery.patch",
                                  "0020-native-worker-policy-consumer.patch",
                                  "0021-native-dedicated-worker-startup-gate.patch",
                                  "0022-native-worker-canvas-thread-handoff.patch",
                                  "0023-native-shared-worker-startup-gate.patch",
                                  "0024-native-service-worker-canvas-thread-handoff.patch",
                                  "0025-native-service-worker-startup-gate.patch",
                                  "0026-native-worker-canvas-handoff-tests.patch",
                                  "0027-native-shared-worker-bootstrap-failure.patch",
                                  "0028-native-worker-handoff-fixture-lifetime.patch",
                                  "0029-native-document-partition-validator-tests.patch",
                                  "0030-native-document-commit-prototype.patch"])
def test_native_build_verifies_applied_patch_and_records_checksum(tmp_path, monkeypatch, name):
    import hashlib

    from scripts import native_build

    patch = native_build.ROOT / "native/patches" / name
    patch_files = {
        item: {line.split(" b/", 1)[1] for line in item.read_text(encoding="utf-8-sig").splitlines()
               if line.startswith("diff --git ")}
        for item in sorted(patch.parent.glob("*.patch"))
    }
    expected_files = set(patch_files[patch])
    while True:
        related = [item for item, files in patch_files.items() if files & expected_files]
        expanded = set().union(*(patch_files[item] for item in related))
        if expanded == expected_files:
            break
        expected_files = expanded
    expected = sorted(expected_files)
    commands = []

    def fake_run(args, cwd, env, capture=False):
        commands.append(args)
        return "\n".join(expected) if args[1] == "diff" else ""

    monkeypatch.setattr(native_build, "run", fake_run)
    assert native_build.source_patches(tmp_path, {}) == [
        {"name": item.name, "sha256": hashlib.sha256(item.read_bytes()).hexdigest()} for item in related]
    assert ["git", "read-tree", "--empty"] in commands
    for item in related:
        assert ["git", "apply", "--cached", str(item)] in commands
    assert commands[-1] == ["git", "diff", "--exit-code", "--", *sorted(expected)]


def test_glint_branding_preparation_is_nonmutating_and_patch_roundtrips(tmp_path, monkeypatch):
    import subprocess

    from PyQt6.QtGui import QImage
    from scripts import prepare_glint_branding as branding

    source = tmp_path / "source"
    public = tmp_path / "public"
    for name in ("native/build-lock.json", "logo.ico", "app/qml/theme/brand.svg"):
        target = public / name
        target.parent.mkdir(parents=True, exist_ok=True)
        contents = (branding.ROOT / name).read_bytes()
        if name.endswith(".svg"):
            contents = contents.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        target.write_bytes(contents)
    original = {
        "chrome/app/theme/chromium/BRANDING": b"PRODUCT_FULLNAME=Chromium\nPRODUCT_SHORTNAME=Chromium\nPRODUCT_INSTALLER_FULLNAME=Chromium Installer\nPRODUCT_INSTALLER_SHORTNAME=Chromium Installer\n",
        "chrome/browser/profiles/profile_shortcut_manager_win.cc": b"const int kCurrentProfileIconVersion = 10;\n",
        "chrome/app/theme/chromium/product_logo.svg": b'<svg xmlns="http://www.w3.org/2000/svg"/>',
        "chrome/app/theme/chromium/win/chromium.ico": b"\x00old-icon",
        "chrome/app/theme/chromium/win/app_list.ico": b"\x00old-app-icon",
    }
    diagnostic_files = {
        "content/browser/renderer_host/render_process_host_impl.cc": 3,
        "third_party/blink/renderer/core/frame/camouflow_hardware_configuration.h": 1,
        "ui/gfx/win/camouflow_font_configuration.h": 3,
        "components/embedder_support/user_agent_utils.cc": 1,
        "components/embedder_support/user_agent_utils_unittest.cc": 1,
    }
    for name, count in diagnostic_files.items():
        original[name] = b'CHECK(false) << "Invalid CamouFlow Native test";\n' * count
    for size in (16, 24, 48, 64, 128, 256):
        original[f"chrome/app/theme/chromium/product_logo_{size}.png"] = b"\x00old-image"
    for name, contents in original.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    real_run = subprocess.run

    def run(args, **kwargs):
        if args == ["git", "rev-parse", "HEAD"]:
            import json
            lock = json.loads((public / "native/build-lock.json").read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(args, 0, lock["chromium_revision"] + "\n")
        return real_run(args, **kwargs)

    monkeypatch.setattr(branding, "ROOT", public)
    monkeypatch.setattr(branding.subprocess, "run", run)
    patch = tmp_path / "glint.patch"
    report = branding.prepare(source, patch)
    assert report["applied"] is False
    assert report["product_name"] == "Glint"
    assert all((source / name).read_bytes() == contents for name, contents in original.items())
    assert not patch.read_bytes().startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in patch.read_bytes()
    from scripts.verify_glint_branding import verify as verify_branding
    replay = verify_branding(source, patch, tmp_path / "branding-replay")
    assert replay["passed"] is True
    assert replay["source_unchanged"] is True
    assert replay["files"] == report["assets"]
    assert all((source / name).read_bytes() == contents for name, contents in original.items())
    with pytest.raises(ValueError, match="new canonical output"):
        verify_branding(source, patch, tmp_path / "branding-replay")
    with pytest.raises(ValueError, match="outside Chromium"):
        verify_branding(source, patch, source / "forbidden-branding-output")
    corrupted = tmp_path / "different-brand.patch"
    corrupted.write_text(patch.read_text(encoding="utf-8").replace(
        "+PRODUCT_FULLNAME=Glint", "+PRODUCT_FULLNAME=Other"), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="differs from fresh generation"):
        verify_branding(source, corrupted, tmp_path / "different-brand-replay")
    unexpected = tmp_path / "extra-path.patch"
    unexpected.write_text(patch.read_text(encoding="utf-8") +
                          "diff --git a/extra.cc b/extra.cc\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="unexpected source paths"):
        verify_branding(source, unexpected, tmp_path / "extra-path-replay")
    assert all((source / name).read_bytes() == contents for name, contents in original.items())
    real_run(["git", "-c", "core.autocrlf=false", "apply", "--check", str(patch)], cwd=source, check=True)
    real_run(["git", "-c", "core.autocrlf=false", "apply", str(patch)], cwd=source, check=True)
    assert (source / "chrome/app/theme/chromium/win/chromium.ico").read_bytes() == (public / "logo.ico").read_bytes()
    assert (source / "chrome/app/theme/chromium/product_logo.svg").read_bytes() == (public / "app/qml/theme/brand.svg").read_bytes().replace(b"\r\n", b"\n")
    assert "PRODUCT_FULLNAME=Glint" in (source / "chrome/app/theme/chromium/BRANDING").read_text(encoding="utf-8")
    assert "kCurrentProfileIconVersion = 11" in (source / "chrome/browser/profiles/profile_shortcut_manager_win.cc").read_text(encoding="utf-8")
    for name, count in diagnostic_files.items():
        contents = (source / name).read_text(encoding="utf-8")
        assert "CamouFlow Native" not in contents
        assert contents.count("Glint") == count
    for size in (16, 24, 48, 64, 128, 256):
        image = QImage(str(source / f"chrome/app/theme/chromium/product_logo_{size}.png"))
        assert (image.width(), image.height()) == (size, size)
        assert not image.isNull()
    with pytest.raises(ValueError, match="overwrite"):
        branding.prepare(source, patch)


@pytest.mark.parametrize("mutation", [None, "duplicate", "missing", "skip", "failure", "incomplete", "foreign", "disabled", "malformed"])
@pytest.mark.parametrize("target", ["keys", "contexts", "delivery", "worker-handoff", "document-partition", "document-navigation",
                                    "surface-navigation", "window-transport", "gpu-pack-copy", "worker-surfaces", "gpu-metadata-codec", "gpu-metadata",
                                    "identity-keys", "identity-contexts", "identity-transport", "identity-handoff", "audio-math"])
def test_native_privacy_unit_report_requires_exact_completed_cases(mutation, target):
    from scripts.verify_native_privacy_units import required_tests, validate_results

    report = {"tests": {"keys": 43, "contexts": 26, "delivery": 34, "worker-handoff": 4, "document-partition": 9, "document-navigation": 12,
                        "surface-navigation": 42, "window-transport": 13, "gpu-pack-copy": 14, "worker-surfaces": 55, "gpu-metadata-codec": 14, "gpu-metadata": 34,
                        "identity-keys": 62, "identity-contexts": 37, "identity-transport": 20, "identity-handoff": 15, "audio-math": 11}[target], "failures": 0, "disabled": 0, "testsuites": [
        {"name": suite, "testsuite": [{"name": name, "status": "RUN", "result": "COMPLETED"}
                                      for name in sorted(cases)]}
        for suite, cases in required_tests(target).items()]}
    case = report["testsuites"][0]["testsuite"][0]
    if mutation == "duplicate":
        report["testsuites"][0]["testsuite"][1] = dict(case)
    elif mutation == "missing":
        report["testsuites"][0]["testsuite"].pop()
    elif mutation == "skip":
        case["status"] = "NOTRUN"
    elif mutation == "failure":
        case["failures"] = [{"failure": "owned negative control"}]
    elif mutation == "incomplete":
        case["result"] = "SKIPPED"
    elif mutation == "foreign":
        report["testsuites"][0]["name"] = "OtherTests"
    elif mutation == "disabled":
        report["disabled"] = 1
    elif mutation == "malformed":
        case["name"] = []
    if mutation is None:
        validate_results(report, target=target)
    else:
        with pytest.raises(ValueError):
            validate_results(report, target=target)


@pytest.mark.parametrize("running", [False, True])
def test_native_privacy_verification_refuses_existing_compiler(monkeypatch, running):
    import subprocess
    from scripts import verify_native_privacy_units as privacy

    monkeypatch.setattr(privacy.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 0, "23096\n" if running else ""))
    if running:
        with pytest.raises(ValueError, match="already running"):
            privacy.require_idle_builder()
    else:
        privacy.require_idle_builder()


@pytest.mark.parametrize("case,conflict", [
    ("owned-tool", True), ("owned-command", True), ("foreign", False),
    ("unreadable-executable", True), ("unreadable-command", True),
    ("relative-executable", True), ("case-and-slashes", True),
])
def test_native_builder_scope_preserves_conflicts_without_blocking_foreign_projects(case, conflict):
    from pathlib import PureWindowsPath
    from scripts import verify_native_privacy_units as privacy

    scope = PureWindowsPath("D:/GlintWorkspace")
    row = {"ProcessId": 123, "Name": "ninja.exe", "ExecutablePath": "E:/other/tools/ninja.exe",
           "CommandLine": "E:/other/tools/ninja.exe -j 3 test_game_replay"}
    if case == "owned-tool":
        row["ExecutablePath"] = "D:/GlintWorkspace/chromium/src/third_party/ninja/ninja.exe"
    elif case == "owned-command":
        row["CommandLine"] = 'ninja -C "D:/GlintWorkspace/chromium/src/out/CamouFlowNative"'
    elif case == "unreadable-executable":
        row["ExecutablePath"] = None
    elif case == "unreadable-command":
        row["CommandLine"] = None
    elif case == "relative-executable":
        row["ExecutablePath"] = "tools/ninja.exe"
    elif case == "case-and-slashes":
        row["ExecutablePath"] = "d:\\GLINTWORKSPACE\\tools\\ninja.exe"
    assert privacy._compiler_conflicts(scope, row) is conflict


@pytest.mark.parametrize("raw", ["null", "1", '[{"ProcessId":true,"Name":"ninja.exe"}]',
                                '[{"ProcessId":1,"Name":"unknown.exe"}]'])
def test_native_builder_scope_rejects_malformed_observations(tmp_path, monkeypatch, raw):
    import subprocess
    from scripts import verify_native_privacy_units as privacy

    monkeypatch.setattr(privacy.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 0, raw))
    with pytest.raises(ValueError, match="process observation"):
        privacy.require_idle_builder(tmp_path)


def test_native_builder_scope_normalizes_binary_output_to_workspace(tmp_path, monkeypatch):
    import json
    import subprocess
    from scripts import verify_native_privacy_units as privacy

    scope = tmp_path / "chromium/src/out/CamouFlowNative"
    scope.mkdir(parents=True)
    row = {"ProcessId": 123, "Name": "ninja.exe",
           "ExecutablePath": str(tmp_path / "chromium/src/third_party/ninja/ninja.exe"),
           "CommandLine": "ninja -C out/CamouFlowNative chrome"}
    monkeypatch.setattr(privacy.subprocess, "run", lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 0, json.dumps(row)))
    with pytest.raises(ValueError, match="ninja.exe PID 123"):
        privacy.require_idle_builder(scope)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows owned-profile unit verifier")
@pytest.mark.parametrize("failure", [None, "browser_change", "test_failure", "compiler_failure", "source_change", "compiler_and_browser_change", "compiler_and_browser_removed", "toolchain_change"])
@pytest.mark.parametrize("target", ["keys", "contexts", "delivery", "worker-handoff", "document-partition", "document-navigation", "font-rasterization",
                                    "identity-keys", "identity-contexts", "identity-transport"])
@pytest.mark.parametrize("candidate_mode,local_toolchain", [(False, False), (True, False), (True, True)])
def test_native_privacy_unit_verifier_binds_build_results_and_preserves_failure(tmp_path, monkeypatch, failure, target, candidate_mode, local_toolchain):
    import json
    import subprocess
    from scripts import verify_native_privacy_units as privacy

    workspace = tmp_path / "work"
    source = workspace / "chromium/src"
    output = source / "out/CamouFlowNative"
    output.mkdir(parents=True)
    if target == "delivery":
        for name, relative in privacy.DELIVERY_SOURCE_FILES.items():
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((privacy.ROOT / "native/drafts/document_delivery" / name).read_bytes())
    (output / "args.gn").write_text("owned args\n", encoding="utf-8")
    (output / "camouflow-build.json").write_text("owned receipt", encoding="utf-8")
    report = tmp_path / "proof.json"
    candidate = privacy.build.load_candidate("upstream-156") if candidate_mode else None
    selected_lock = privacy.build.LOCK if candidate is None else candidate["lock"]
    if candidate is not None:
        (workspace / "glint-build-candidate.json").write_text(json.dumps({
            "schema": 1, "candidate": candidate["name"], "chromium_revision": selected_lock["chromium_revision"]}), encoding="utf-8")
    monkeypatch.setattr(privacy.build, "preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(privacy, "require_idle_builder", lambda *args: None)
    monkeypatch.setattr(privacy.build, "environment", lambda *args, **kwargs: {"GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": "a" * 64})
    monkeypatch.setattr(privacy.build, "local_windows_toolchain", lambda *args: {
        "GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": ("b" if failure == "toolchain_change" else "a") * 64})
    monkeypatch.setattr(privacy.build, "run", lambda *args, **kwargs: selected_lock["chromium_revision"])

    def require_stage(*args):
        assert args[:2] in ((workspace / "chromium", "sync"), (workspace / "chromium", "hooks"))
        if candidate_mode:
            assert len(args) == 3 and args[2]["manifest_sha256"] == candidate["manifest_sha256"]
        else:
            assert len(args) == 2

    monkeypatch.setattr(privacy.build, "require_stage", require_stage)
    source_patches = [{"name": name, "sha256": "a" * 64} for name in (
        "0015-native-browser-context-key-ownership.patch", "0016-native-private-key-readiness.patch",
        "0017-native-browser-context-tests.patch", "0018-native-document-policy-delivery.patch",
        "0019-native-worker-policy-delivery.patch", "0020-native-worker-policy-consumer.patch",
        "0022-native-worker-canvas-thread-handoff.patch", "0024-native-service-worker-canvas-thread-handoff.patch",
        "0026-native-worker-canvas-handoff-tests.patch",
        "0029-native-document-partition-validator-tests.patch",
        "0030-native-document-commit-prototype.patch", "0032-native-document-surface-policy.patch",
        "0042-native-initial-policy-fixture-scheme-lifetime.patch",
        "0049-native-profile-identity-derivation.patch", "0050-native-immutable-fingerprint-mode.patch",
        "0051-native-identity-context-tests.patch", "0052-native-surface-identity-v3-transport.patch",
        "0053-native-identity-handoff-tests.patch", "0054-native-profile-identity-launch.patch",
        "0062-native-windows-font-rasterization.patch")]
    monkeypatch.setattr(privacy.build, "source_patches", lambda *args: [dict(item) for item in source_patches])
    monkeypatch.setattr(privacy.build, "v8_source_patches", lambda *args: [])
    if candidate_mode:
        source_patches = [{"name": row["file"], "sha256": row["sha256"]} for row in candidate["manifest"]["patches"]]

        def candidate_sources(selected_source, env, selected):
            assert selected_source == source and selected["manifest_sha256"] == candidate["manifest_sha256"]
            return [dict(row) for row in source_patches]

        monkeypatch.setattr(privacy.build, "candidate_source_patches", candidate_sources)
        monkeypatch.setattr(privacy.build, "source_patches", lambda *args: pytest.fail("Candidate used default patch chain"))
        monkeypatch.setattr(privacy.build, "v8_source_patches", lambda *args: pytest.fail("Candidate used default V8 chain"))
    monkeypatch.setattr(privacy.build, "check_patch_dependencies", lambda *args: None)
    monkeypatch.setattr(privacy.build, "depot_command", lambda *args: ["autoninja"])
    measurements = []

    def measure(*args):
        measurements.append(True)
        if failure == "compiler_and_browser_removed" and len(measurements) > 1:
            raise privacy.NativeRuntimeError("Native browser is not installed")
        return {"chrome.exe": "b" * 64 if failure in {"browser_change", "compiler_and_browser_change"} and len(measurements) > 1 else "a" * 64}

    monkeypatch.setattr(privacy, "measure_runtime_core", measure)
    commands = []
    build_target = ("gfx_unittests" if target == "font-rasterization" else
                    "blink_unittests" if target == "worker-handoff" else
                    "content_unittests" if target in {"contexts", "delivery", "document-navigation", "identity-contexts", "identity-transport"} else "camouflow_native_privacy_unittests")

    def run(args, **kwargs):
        with pytest.raises(ValueError, match="owns this workspace"):
            with privacy.build.workspace_lock(workspace):
                pytest.fail("Native compiler verification did not retain its workspace lock")
        commands.append(args)
        kwargs["stdout"].write("Owned subprocess output\n")
        if args[0] == "autoninja":
            if failure in {"compiler_failure", "compiler_and_browser_change", "compiler_and_browser_removed"}:
                raise subprocess.CalledProcessError(1, args)
            (output / (build_target + ".exe")).write_bytes(b"owned unit executable")
        else:
            results = {"tests": sum(map(len, privacy.required_tests(target).values())),
                       "failures": 1 if failure == "test_failure" else 0, "disabled": 0,
                       "testsuites": [{"name": suite, "testsuite": [
                           {"name": name, "status": "RUN", "result": "COMPLETED"} for name in sorted(cases)]}
                           for suite, cases in privacy.required_tests(target).items()]}
            report.with_name("proof-tests.json").write_text(json.dumps(results), encoding="utf-8")
            if failure == "source_change":
                source_patches[0]["sha256"] = "b" * 64
                if target == "delivery":
                    (source / privacy.DELIVERY_SOURCE_FILES["privacy_document_service.cc"]).write_text(
                        "// changed during verification\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(privacy.subprocess, "run", run)
    selected_name = candidate["name"] if candidate is not None else None
    proof = privacy.verify(workspace, report, target=target, candidate_name=selected_name, local_toolchain=local_toolchain)
    expected_pass = failure is None or (failure == "toolchain_change" and not local_toolchain)
    assert proof["passed"] is expected_pass
    assert json.loads(report.read_text(encoding="utf-8")) == proof
    assert "Owned subprocess output" in report.with_name("proof-build.log").read_text(encoding="utf-8")
    assert commands[0][-3:] == ["-j", "4", build_target]
    if failure in {"compiler_failure", "compiler_and_browser_change", "compiler_and_browser_removed"}:
        assert len(commands) == 1
    else:
        assert commands[1][0] == str(output / (build_target + ".exe"))
        if target in {"worker-handoff", "document-partition", "document-navigation", "font-rasterization"}:
            assert "*" not in commands[1][1]
            assert set(commands[1][1].removeprefix("--gtest_filter=").split(":")) == {
                f"{suite}.{case}" for suite, cases in privacy.required_tests(target).items() for case in cases}
    assert proof["target"] == target
    assert proof["source_chromium_revision"] == selected_lock["chromium_revision"]
    assert proof["browser_runtime_verified"] is False and proof["privacy_admitted"] is False
    assert proof["postguards_passed"] is (failure not in {"browser_change", "source_change", "compiler_and_browser_change", "compiler_and_browser_removed"}
                                         and not (failure == "toolchain_change" and local_toolchain))
    if local_toolchain:
        assert proof["local_windows_toolchain_sha256"] == "a" * 64
    else:
        assert "local_windows_toolchain_sha256" not in proof
    if candidate_mode:
        assert proof["candidate"] == "upstream-156" and proof["candidate_manifest_sha256"] == candidate["manifest_sha256"]
    else:
        assert "candidate" not in proof and "candidate_manifest_sha256" not in proof
    if expected_pass:
        assert proof["tests"] == {"keys": 43, "contexts": 26, "delivery": 34, "worker-handoff": 4, "document-partition": 9, "document-navigation": 12, "font-rasterization": 5,
                                  "identity-keys": 62, "identity-contexts": 37, "identity-transport": 20}[target] and proof["baseline_browser_code_unchanged"]
        assert len(proof["test_binary_sha256"]) == 64
        if target == "delivery":
            assert len(proof["delivery_source_sha256"]) == 10
    else:
        assert proof.get("error") and "baseline_browser_code_unchanged" not in proof
        if failure == "compiler_and_browser_change":
            assert "autoninja" in proof["error"] and "Verification changed baseline" in proof["postguard_error"]
        if failure == "compiler_and_browser_removed":
            assert "autoninja" in proof["error"] and "Native browser is not installed" in proof["postguard_error"]
    with pytest.raises(ValueError, match="overwrite"):
        privacy.verify(workspace, report, target=target, candidate_name=selected_name, local_toolchain=local_toolchain)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows candidate unit verifier")
@pytest.mark.parametrize("mutation,expected", [
    ("implicit", "explicit --candidate"), ("revision", "different revision"),
    ("missing", "new empty workspace"), ("unknown", "Unknown Native build candidate"),
])
def test_privacy_units_reject_candidate_binding_before_lock_or_compiler(tmp_path, monkeypatch, mutation, expected):
    import json
    from scripts import verify_native_privacy_units as privacy

    workspace = tmp_path / "workspace"
    (workspace / "chromium/src").mkdir(parents=True)
    candidate = privacy.build.load_candidate("upstream-156")
    marker = {"schema": 1, "candidate": "upstream-156", "chromium_revision": candidate["lock"]["chromium_revision"]}
    if mutation == "revision":
        marker["chromium_revision"] = "f" * 40
    if mutation != "missing":
        (workspace / "glint-build-candidate.json").write_text(json.dumps(marker), encoding="utf-8")
    monkeypatch.setattr(privacy.build, "preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(privacy, "require_idle_builder", lambda *args: pytest.fail("Invalid candidate reached compiler setup"))
    name = None if mutation == "implicit" else "unknown" if mutation == "unknown" else "upstream-156"
    report = tmp_path / "proof.json"
    with pytest.raises(ValueError, match=expected):
        privacy.verify(workspace, report, candidate_name=name)
    assert not report.exists() and not (workspace / "glint-build.lock").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native unit verifier")
def test_privacy_units_refuse_a_workspace_owned_by_sync_before_compiler_setup(tmp_path, monkeypatch):
    from scripts import verify_native_privacy_units as privacy

    workspace = tmp_path / "workspace"
    (workspace / "chromium/src").mkdir(parents=True)
    monkeypatch.setattr(privacy.build, "preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(privacy, "require_idle_builder", lambda *args: pytest.fail("Busy workspace reached compiler setup"))
    with privacy.build.workspace_lock(workspace):
        with pytest.raises(ValueError, match="owns this workspace"):
            privacy.verify(workspace, tmp_path / "proof.json")
    assert not (tmp_path / "proof.json").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native unit verifier")
@pytest.mark.parametrize("selection", [True, "true", 1, None])
def test_privacy_units_require_explicit_candidate_for_local_toolchain(tmp_path, selection):
    from scripts import verify_native_privacy_units as privacy

    report = tmp_path / "proof.json"
    with pytest.raises(ValueError, match="explicit candidate"):
        privacy.verify(tmp_path, report, local_toolchain=selection)
    assert not report.exists() and not (tmp_path / "glint-build.lock").exists()


def test_native_key_derivation_patch_reuses_canonical_message_header():
    from scripts import native_build

    patch = (native_build.ROOT / "native/patches/0012-native-browser-privacy-key-derivation.patch").read_text(encoding="utf-8-sig")
    name = "content/browser/camouflow_native/privacy_partition.h"
    section = patch.split(f"diff --git a/{name} b/{name}\n", 1)[1].split("\ndiff --git ", 1)[0]
    copied = "\n".join(line[1:] for line in section.splitlines()
                       if line.startswith("+") and not line.startswith("+++")) + "\n"
    assert copied == (native_build.ROOT / "native/core/privacy_partition.h").read_text(encoding="utf-8-sig")


def test_native_key_derivation_cpp_vectors_match_python_profile_identity():
    import re
    from app.core.native.identity import NativePrivacyIdentity
    from scripts import native_build

    patch = (native_build.ROOT / "native/patches/0012-native-browser-privacy-key-derivation.patch").read_text(encoding="utf-8-sig")
    partition = b"CamouFlowNative/partition/v1\0"
    for host, port in ((b"sub.example.test", 8443), (b"top.test", 443)):
        partition += (b"\0" + (5).to_bytes(4, "big") + b"https" + len(host).to_bytes(4, "big")
                      + host + port.to_bytes(2, "big"))
    partition += b"\1\0"
    expected = dict(re.findall(r'Vector\{"(canvas|webgl|webgpu|audio)", "([0-9a-f]{64})"\}', patch))
    assert set(expected) == {"canvas", "webgl", "webgpu", "audio"}
    identity = NativePrivacyIdentity(bytes(range(32)))
    assert expected == {surface: identity.derive(partition, surface).hex() for surface in expected}


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


@pytest.mark.parametrize("privacy_sources", [False, True])
def test_native_build_checks_the_chromium_dependency_layers_changed_by_the_patch(tmp_path, monkeypatch, privacy_sources):
    import os

    from scripts import native_build

    commands = []
    if privacy_sources:
        (tmp_path / "content/browser/camouflow_native").mkdir(parents=True)
    monkeypatch.setattr(native_build, "run", lambda args, *a, **kw: commands.append(args))
    native_build.check_patch_dependencies(tmp_path, {})
    assert commands[0] == ["git", "diff", "--check"]
    assert [command[-1] for command in commands[1:3]] == [
        os.path.normcase(str(tmp_path / "third_party/blink/renderer/core/frame")),
        os.path.normcase(str(tmp_path / "content/browser/renderer_host")),
    ]
    assert all(command[-2] == os.path.normcase(str(tmp_path)) for command in commands[1:3])
    if privacy_sources:
        assert commands[3][-1] == os.path.normcase(str(tmp_path / "content/browser/camouflow_native"))
        assert commands[3][-2] == os.path.normcase(str(tmp_path))
    assert commands[-1][:2] == [sys.executable, "-c"]
    assert "CheckAddedCppIncludes" in commands[-1][2]
    assert "chrome/browser/renderer_preferences_util.cc" in commands[-1][2]
    assert commands[-1][-1] == os.path.normcase(str(tmp_path))


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
    (patches / "0006-native-headless-user-agent.patch").write_text("", encoding="utf-8")
    (patches / "0008-native-leveldb-path-separators.patch").write_text("", encoding="utf-8")
    (patches / "0009-native-sql-extended-paths.patch").write_text("", encoding="utf-8")
    (patches / "0010-native-windows-profile-namespace.patch").write_text("", encoding="utf-8")
    (patches / "0011-native-privacy-partition-serialization.patch").write_text("", encoding="utf-8")
    (patches / "0012-native-browser-privacy-key-derivation.patch").write_text("", encoding="utf-8")
    (patches / "0013-native-owned-profile-key-loader.patch").write_text("", encoding="utf-8")
    (patches / "0014-native-private-key-service-lifecycle.patch").write_text("", encoding="utf-8")
    (patches / "0015-native-browser-context-key-ownership.patch").write_text("", encoding="utf-8")
    (patches / "0016-native-private-key-readiness.patch").write_text("", encoding="utf-8")
    (patches / "0017-native-browser-context-tests.patch").write_text("", encoding="utf-8")
    (patches / "0018-native-document-policy-delivery.patch").write_text("", encoding="utf-8")
    (patches / "0019-native-worker-policy-delivery.patch").write_text("", encoding="utf-8")
    (patches / "0020-native-worker-policy-consumer.patch").write_text("", encoding="utf-8")
    for name in ("0021-native-dedicated-worker-startup-gate.patch", "0022-native-worker-canvas-thread-handoff.patch",
                 "0023-native-shared-worker-startup-gate.patch", "0024-native-service-worker-canvas-thread-handoff.patch",
                 "0025-native-service-worker-startup-gate.patch", "0026-native-worker-canvas-handoff-tests.patch",
                 "0027-native-shared-worker-bootstrap-failure.patch",
                 "0028-native-worker-handoff-fixture-lifetime.patch",
                 "0029-native-document-partition-validator-tests.patch",
                 "0030-native-document-commit-prototype.patch",
                 "0031-native-worker-surface-policy.patch", "0032-native-document-surface-policy.patch",
                 "0033-native-surface-readback.patch", "0034-native-gpu-metadata-minimization.patch",
                 "0035-native-initial-origin-calculation.patch",
                 "0036-native-worker-complete-surface-type.patch",
                 "0037-native-webgl-readback-compilation.patch",
                 "0038-native-renderer-struct-pointer-presence.patch",
                 "0039-native-document-ready-commit-cancellation.patch",
                 "0040-native-ready-commit-observer-lifetime.patch",
                 "0041-native-child-transport-fixture-interface.patch",
                 "0042-native-initial-policy-fixture-scheme-lifetime.patch",
                 "0043-native-surface-navigation-throttle-registration.patch",
                 "0044-native-inline-navigation-rejection-fixture.patch",
                 "0045-native-navigation-observer-fixture-lifetime.patch",
                 "0046-native-webgl-bounded-readback.patch",
                 "0047-native-webgl-clipped-publication.patch",
                 "0048-native-readback-fixture-result-api.patch",
                 "0049-native-profile-identity-derivation.patch",
                 "0050-native-immutable-fingerprint-mode.patch",
                 "0051-native-identity-context-tests.patch",
                 "0052-native-surface-identity-v3-transport.patch",
                 "0053-native-identity-handoff-tests.patch",
                 "0054-native-profile-identity-launch.patch",
                 "0055-native-gpu-readback-metadata-transport.patch",
                 "0056-native-gpu-metadata-protocol-tests.patch",
                 "0057-native-gpu-metadata-attachment-tests.patch",
                 "0058-native-gpu-passthrough-attachment-tests.patch",
                 "0059-native-identical-v8-snapshot.patch",
                 "0060-native-glint-branding.patch",
                 "0061-native-glint-ui-resources.patch",
                 "0062-native-windows-font-rasterization.patch"):
        (patches / name).write_text("", encoding="utf-8")
    monkeypatch.setattr(native_build, "ROOT", public)
    assert len(native_build.source_patches(source, env)) == 1
    file.write_text(file.read_text(encoding="utf-8-sig") + "unreviewed edit\n", encoding="utf-8", newline="\n")
    with pytest.raises(subprocess.CalledProcessError):
        native_build.source_patches(source, env)
    assert git("ls-files", "--stage") == expected_index
    assert not list(tmp_path.glob("native-patch-index-*"))


@pytest.mark.parametrize("mutation", ["extra_edit", "untracked_file", "deleted_file", "staged_extra_edit"])
def test_native_v8_patch_validation_checks_real_nested_checkout_without_changing_indexes(tmp_path, monkeypatch, mutation):
    import json
    import os
    import subprocess

    from scripts import native_build

    source = tmp_path / "chromium/src"
    v8 = source / "v8"
    v8.mkdir(parents=True)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    def git(directory, *args):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", *args], cwd=directory, env=env)
    for directory in (source, v8):
        git(directory, "init", "--quiet")
    (source / ".gitignore").write_text("/v8/\n", encoding="utf-8", newline="\n")
    file = v8 / "src/inspector/value-mirror.cc"
    file.parent.mkdir(parents=True)
    original = "first\n" + "unchanged\n" * 20
    file.write_text(original, encoding="utf-8", newline="\n")
    for directory in (source, v8):
        git(directory, "add", ".")
        git(directory, "-c", "user.name=Native fixture", "-c", "user.email=fixture@localhost",
            "commit", "--quiet", "-m", "baseline")
    revision = git(v8, "rev-parse", "HEAD").decode().strip()
    (source.parent / "camouflow-git-revisions.json").write_text(json.dumps({
        "src/v8": {"url": "https://chromium.googlesource.com/v8/v8.git", "rev": revision}}), encoding="utf-8")
    public = tmp_path / "public"
    patches = public / "native/patches"
    patches.mkdir(parents=True)
    patch = patches / "0007-native-inspector-error-accessors.patch"
    file.write_text(original.replace("first", "native"), encoding="utf-8", newline="\n")
    patch.write_bytes(git(v8, "diff"))
    monkeypatch.setattr(native_build, "ROOT", public)
    result = native_build.v8_source_patches(source, env)
    assert len(result) == 1
    assert result[0]["repository"] == "v8"
    assert result[0]["revision"] == revision
    if mutation in {"extra_edit", "staged_extra_edit"}:
        file.write_text(file.read_text(encoding="utf-8-sig") + "unreviewed edit\n", encoding="utf-8", newline="\n")
        if mutation == "staged_extra_edit":
            git(v8, "add", ".")
    elif mutation == "untracked_file":
        (v8 / "unreviewed.cc").write_text("unreviewed\n", encoding="utf-8")
    else:
        file.unlink()
    indexes = {directory: git(directory, "ls-files", "--stage") for directory in (source, v8)}
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        native_build.v8_source_patches(source, env)
    for directory, expected in indexes.items():
        assert git(directory, "ls-files", "--stage") == expected
    assert git(source, "status", "--porcelain") == b""
    assert not list(source.parent.glob("native-patch-index-*"))


def _native_windows_packaging_fixture(tmp_path, monkeypatch):
    import json

    from app.core.native.distribution import sha256_file
    from scripts import package_native_windows as packaging
    from scripts.verify_native_runtime import measure_runtime_core

    output, staged = tmp_path / "src/out/CamouFlowNative", tmp_path / "Chrome-bin"
    output.mkdir(parents=True)
    (output.parent.parent / "LICENSE").write_text("Synthetic source license fixture\n", encoding="utf-8")
    staged.mkdir()
    monkeypatch.setattr(packaging, "RELEASE_VOLUME", tmp_path.drive.upper())
    version = packaging.LOCK["chromium_version"]
    for relative in ("chrome.exe", "chrome.dll", "chrome_elf.dll", "locales/en-US.pak"):
        source = output / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"synthetic owned packaging fixture: " + relative.encode())
        target = staged / (relative if relative == "chrome.exe" else version + "/" + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    (output / "args.gn").write_text("is_debug=false\n", encoding="utf-8")
    checksum = sha256_file(output / "chrome.exe")
    receipt = {"schema": 1, "platform": "win32", "binary": "chrome.exe",
               "native_version": packaging.LOCK["native_version"],
               "chromium_revision": packaging.LOCK["chromium_revision"],
               "depot_tools_revision": packaging.LOCK["depot_tools_revision"],
               "binary_sha256_measured": checksum, "args_sha256": sha256_file(output / "args.gn"),
               "runtime_core_sha256_measured": measure_runtime_core(output / "chrome.exe"),
               "native_patch_runtime_verified": False, "patches": []}
    (output / "camouflow-build.json").write_text(json.dumps(receipt), encoding="utf-8")
    report = tmp_path / "runtime.json"
    report.write_text(json.dumps({"passed": True, "platform": "Windows", "version": version,
                                 "binary_sha256_measured": checksum,
                                 "runtime_core_sha256_measured": measure_runtime_core(output / "chrome.exe"),
                                 "checks": sorted(packaging.REQUIRED_RUNTIME_CHECKS)}), encoding="utf-8")
    return output, staged, report, tmp_path / "native.tar.gz"


def _candidate_windows_packaging_fixture(tmp_path, monkeypatch):
    import json
    from scripts import package_native_windows as packaging

    output, staged, report, archive = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    candidate = packaging.load_candidate("upstream-156")
    directory = tmp_path / "candidate-inputs"
    (directory / "patches").mkdir(parents=True)
    (directory / "manifest.json").write_bytes((candidate["directory"] / "manifest.json").read_bytes())
    for row in candidate["manifest"]["patches"]:
        (directory / "patches" / row["file"]).write_bytes((candidate["directory"] / "patches" / row["file"]).read_bytes())
    candidate = {**candidate, "directory": directory}
    monkeypatch.setattr(packaging, "load_candidate", lambda name: candidate)
    lock = candidate["lock"]
    old_version = staged / packaging.LOCK["chromium_version"]
    new_version = staged / lock["chromium_version"]
    assert old_version.resolve().is_relative_to(staged) and new_version.resolve().is_relative_to(staged)
    old_version.rename(new_version)
    receipt = json.loads((output / "camouflow-build.json").read_text(encoding="utf-8"))
    receipt.update(native_version=lock["native_version"], chromium_revision=lock["chromium_revision"],
                   depot_tools_revision=lock["depot_tools_revision"], candidate_manifest_sha256=candidate["manifest_sha256"])
    receipt["patches"] = [{"name": row["file"], "sha256": row["sha256"],
        **({"repository": "v8", "revision": candidate["manifest"]["dependencies"]["v8"]["revision"]} if repository == "v8" else {})}
        for repository in (".", "v8") for row in candidate["manifest"]["patches"] if row.get("directory", ".") == repository]
    (output / "camouflow-build.json").write_text(json.dumps(receipt), encoding="utf-8")
    runtime = json.loads(report.read_text(encoding="utf-8"))
    runtime["version"] = lock["chromium_version"]
    report.write_text(json.dumps(runtime), encoding="utf-8")
    return output, staged, report, archive, candidate


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only candidate suite")
@pytest.mark.parametrize("layout", ["flat", "installed"])
def test_native_candidate_suite_binds_all_gates_to_receipt_version_and_inputs(tmp_path, monkeypatch, layout):
    import json
    from types import SimpleNamespace
    from scripts import verify_native_suite as suite, verify_native_privacy_units as units, package_native_windows as packaging
    from app.core.native.distribution import NativeBinaryStore

    output, staged, runtime_report, archive, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(suite.native_build, "load_candidate", lambda name: candidate)
    monkeypatch.setattr(units, "require_idle_builder", lambda *args: None)
    executable = output / "chrome.exe"
    options = {}
    if layout == "installed":
        result = packaging.package(output, staged, runtime_report, archive, candidate_name="upstream-156")
        store = NativeBinaryStore(tmp_path / "store")
        release = store.install_archive(archive, result["sha256"])
        executable = Path(release["executable_path"])
        options = {"release_store": store.root, "release_digest": result["sha256"],
                   "library_directory": executable.parent / candidate["lock"]["chromium_version"]}
    core = suite.measure_runtime_core(executable, options.get("library_directory"))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        gate = Path(command[1]).stem.removeprefix("verify_native_")
        checks = (sorted(suite.REQUIRED_RUNTIME_CHECKS) if gate == "runtime" else
                  [{"name": name, "passed": True} for name in sorted(suite.REQUIRED_COMBINED_CHECKS)] if gate == "combined" else
                  [{"passed": True}])
        report = {"passed": True, "checks": checks, "binary_sha256_measured": core["chrome.exe"],
                  "runtime_core_sha256_measured": core, "arguments": suite.ARGUMENTS,
                  "browser_version" if gate == "hardware" else "version": candidate["lock"]["chromium_version"]}
        if gate == "runtime" and layout == "installed":
            report.update(release_sha256_measured=release["release_sha256"],
                          payload_files_sha256_measured=release["files_sha256"])
        Path(command[command.index("--report") + 1]).write_text(json.dumps(report), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(suite.subprocess, "run", run)
    proof = suite.verify(executable, tmp_path / "reports", list(suite.GATES), candidate_name="upstream-156", **options)
    assert proof["passed"] and proof["full_suite"]
    assert len(calls) == 8
    assert proof["candidate"] == "upstream-156"
    assert proof["expected_version"] == candidate["lock"]["chromium_version"]
    assert proof["candidate_manifest_sha256"] == candidate["manifest_sha256"]
    assert proof["privacy_admitted"] is False
    assert proof["build_receipt_sha256"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only candidate suite")
@pytest.mark.parametrize("mutation", ["version", "receipt-drift", "args-drift", "patch-drift", "manifest-drift"])
def test_native_candidate_suite_rejects_changed_version_or_inputs(tmp_path, monkeypatch, mutation):
    import json
    from types import SimpleNamespace
    from scripts import verify_native_suite as suite, verify_native_privacy_units as units

    output, _, _, _, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(suite.native_build, "load_candidate", lambda name: candidate)
    monkeypatch.setattr(units, "require_idle_builder", lambda *args: None)
    executable = output / "chrome.exe"
    core = suite.measure_runtime_core(executable)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        gate = Path(command[1]).stem.removeprefix("verify_native_")
        if mutation == "receipt-drift":
            (output / "camouflow-build.json").write_text("{}", encoding="utf-8")
        elif mutation == "args-drift":
            (output / "args.gn").write_text("changed", encoding="utf-8")
        elif mutation == "patch-drift":
            (candidate["directory"] / "patches" / candidate["manifest"]["patches"][0]["file"]).write_text("changed", encoding="utf-8")
        elif mutation == "manifest-drift":
            (candidate["directory"] / "manifest.json").write_text("{}", encoding="utf-8")
        Path(command[command.index("--report") + 1]).write_text(json.dumps({
            "passed": True, "checks": [{"passed": True}], "binary_sha256_measured": core["chrome.exe"],
            "runtime_core_sha256_measured": core,
            "browser_version" if gate == "hardware" else "version": "148.0.7778.96" if mutation == "version" else candidate["lock"]["chromium_version"]
        }), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(suite.subprocess, "run", run)
    proof = suite.verify(executable, tmp_path / "reports", ["hardware", "webrtc"], candidate_name="upstream-156")
    assert not proof["passed"] and all(not gate["passed"] for gate in proof["gates"])
    assert len(calls) == (2 if mutation == "version" else 1)
    assert json.loads((tmp_path / "reports/suite.json").read_text(encoding="utf-8")) == proof


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only candidate suite")
@pytest.mark.parametrize("mutation", ["missing-manifest", "patch-chain", "revision", "core", "arguments", "missing-receipt"])
def test_native_candidate_suite_rejects_bad_receipt_before_creating_evidence(tmp_path, monkeypatch, mutation):
    import json
    from unittest.mock import Mock
    from scripts import verify_native_suite as suite, verify_native_privacy_units as units

    output, _, _, _, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(suite.native_build, "load_candidate", lambda name: candidate)
    monkeypatch.setattr(units, "require_idle_builder", lambda *args: None)
    path = output / "camouflow-build.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "missing-manifest":
        del receipt["candidate_manifest_sha256"]
    elif mutation == "patch-chain":
        receipt["patches"].pop()
    elif mutation == "revision":
        receipt["chromium_revision"] = "e" * 40
    elif mutation == "core":
        receipt["runtime_core_sha256_measured"] = {}
    elif mutation == "arguments":
        receipt["args_sha256"] = "e" * 64
    if mutation == "missing-receipt":
        path.unlink()
    else:
        path.write_text(json.dumps(receipt), encoding="utf-8")
    runner = Mock()
    monkeypatch.setattr(suite.subprocess, "run", runner)
    with pytest.raises((ValueError, OSError)):
        suite.verify(output / "chrome.exe", tmp_path / "reports", ["hardware"], candidate_name="upstream-156")
    runner.assert_not_called()
    assert not (tmp_path / "reports").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only candidate suite")
def test_native_candidate_suite_refuses_live_builder_before_creating_evidence(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from scripts import verify_native_suite as suite, verify_native_privacy_units as units

    output, _, _, _, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(suite.native_build, "load_candidate", lambda name: candidate)
    idle = Mock(side_effect=ValueError("Owned builder is active"))
    monkeypatch.setattr(units, "require_idle_builder", idle)
    runner = Mock()
    monkeypatch.setattr(suite.subprocess, "run", runner)
    with pytest.raises(ValueError, match="builder is active"):
        suite.verify(output / "chrome.exe", tmp_path / "reports", ["hardware"], candidate_name="upstream-156")
    idle.assert_called_once()
    runner.assert_not_called()
    assert not (tmp_path / "reports").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only candidate suite")
@pytest.mark.parametrize("target", ["camouflow-build.json", "args.gn"])
def test_native_candidate_suite_rejects_input_change_during_initial_measurement(tmp_path, monkeypatch, target):
    from unittest.mock import Mock
    from scripts import verify_native_suite as suite, verify_native_privacy_units as units

    output, _, _, _, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(suite.native_build, "load_candidate", lambda name: candidate)
    monkeypatch.setattr(units, "require_idle_builder", lambda *args: None)
    original = suite.checksum
    changed = False
    def race(path):
        nonlocal changed
        if path.name != target or changed:
            return original(path)
        changed = True
        if target == "camouflow-build.json":
            path.write_text("{}", encoding="utf-8")
            return original(path)
        digest = original(path)
        path.write_text("changed", encoding="utf-8")
        return digest
    monkeypatch.setattr(suite, "checksum", race)
    runner = Mock()
    monkeypatch.setattr(suite.subprocess, "run", runner)
    with pytest.raises(ValueError, match="changed"):
        suite.verify(output / "chrome.exe", tmp_path / "reports", ["hardware"], candidate_name="upstream-156")
    assert changed
    runner.assert_not_called()
    assert not (tmp_path / "reports").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only candidate suite")
@pytest.mark.parametrize("field,value", [("candidate", "other"), ("candidate_manifest_sha256", "e" * 64),
    ("native_version", "0.1.0"), ("chromium_version", "148.0.7778.96"), ("build_receipt_sha256", "not-a-digest")])
def test_native_candidate_suite_rejects_conflicting_installed_metadata(tmp_path, monkeypatch, field, value):
    import json
    from unittest.mock import Mock
    from scripts import verify_native_suite as suite, verify_native_privacy_units as units, package_native_windows as packaging
    from app.core.native.distribution import NativeBinaryStore

    output, staged, runtime, archive, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(suite.native_build, "load_candidate", lambda name: candidate)
    monkeypatch.setattr(units, "require_idle_builder", lambda *args: None)
    packaged = packaging.package(output, staged, runtime, archive, candidate_name="upstream-156")
    store = NativeBinaryStore(tmp_path / "store")
    installed = store.install_archive(archive, packaged["sha256"])
    executable = Path(installed["executable_path"])
    path = executable.parent / "native-release.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata[field] = value
    path.write_text(json.dumps(metadata), encoding="utf-8")
    runner = Mock()
    monkeypatch.setattr(suite.subprocess, "run", runner)
    with pytest.raises(ValueError):
        suite.verify(executable, tmp_path / "reports", ["hardware"], candidate_name="upstream-156",
            release_store=store.root, release_digest=packaged["sha256"],
            library_directory=executable.parent / candidate["lock"]["chromium_version"])
    runner.assert_not_called()
    assert not (tmp_path / "reports").exists()


def test_native_candidate_suite_cli_forwards_explicit_selection(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from scripts import verify_native_suite as suite

    executable, report = tmp_path / "chrome.exe", tmp_path / "reports"
    runner = Mock(return_value={"passed": True})
    monkeypatch.setattr(suite, "verify", runner)
    monkeypatch.setattr(sys, "argv", ["verify_native_suite.py", "--executable", str(executable),
        "--report-dir", str(report), "--candidate", "upstream-156"])
    assert suite.main() == 0
    runner.assert_called_once_with(executable, report, list(suite.GATES), library_directory=None,
        release_store=None, release_digest="", candidate_name="upstream-156")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
def test_native_windows_candidate_package_preserves_manifest_without_admitting_policy(tmp_path, monkeypatch):
    import json
    import tarfile
    from scripts import package_native_windows as packaging
    from app.core.native.distribution import NativeBinaryStore

    output, staged, report, archive, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    result = packaging.package(output, staged, report, archive, candidate_name="upstream-156")
    assert result["native_patch_runtime_verified"] is False
    with tarfile.open(archive, "r:gz") as bundle:
        metadata = json.load(bundle.extractfile("native-release.json"))
    assert metadata["candidate"] == "upstream-156"
    assert metadata["candidate_manifest_sha256"] == candidate["manifest_sha256"]
    assert metadata["chromium_version"] == candidate["lock"]["chromium_version"]
    assert metadata["native_version"] == "0.2.0-dev"
    assert len(metadata["build_receipt"]["patches"]) == len(candidate["manifest"]["patches"]) == 67
    assert metadata["native_patch_runtime_verified"] is False
    store = NativeBinaryStore(tmp_path / "store")
    installed = store.install_archive(archive, result["sha256"])
    assert installed["candidate"] == "upstream-156"
    assert store.inspect(result["sha256"])["native_patch_runtime_verified"] is False


def test_native_windows_candidate_packaging_cli_forwards_explicit_selection(monkeypatch, tmp_path):
    from unittest.mock import Mock
    from scripts import package_native_windows as packaging

    output, staged, report, archive = [tmp_path / name for name in ("output", "staged", "report.json", "bundle.tar.gz")]
    runner = Mock(return_value={"native_patch_runtime_verified": False})
    monkeypatch.setattr(packaging, "package", runner)
    monkeypatch.setattr(sys, "argv", ["package_native_windows.py", "--build-output", str(output), "--staged", str(staged),
        "--runtime-report", str(report), "--archive", str(archive), "--candidate", "upstream-156"])
    assert packaging.main() == 0
    runner.assert_called_once_with(output, staged, report, archive, candidate_name="upstream-156")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
@pytest.mark.parametrize("mutation", ["missing-manifest", "wrong-manifest", "missing-patch", "patch-order",
    "patch-hash", "v8-revision", "runtime-version", "implicit-selection", "manifest-drift", "patch-drift"])
def test_native_windows_candidate_package_rejects_incomplete_identity_and_drift(tmp_path, monkeypatch, mutation):
    import json
    from scripts import package_native_windows as packaging

    output, staged, report, archive, candidate = _candidate_windows_packaging_fixture(tmp_path, monkeypatch)
    path = output / "camouflow-build.json"
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "missing-manifest":
        del receipt["candidate_manifest_sha256"]
    elif mutation == "wrong-manifest":
        receipt["candidate_manifest_sha256"] = "e" * 64
    elif mutation == "missing-patch":
        receipt["patches"].pop()
    elif mutation == "patch-order":
        receipt["patches"].reverse()
    elif mutation == "patch-hash":
        receipt["patches"][0]["sha256"] = "e" * 64
    elif mutation == "v8-revision":
        receipt["patches"][-1]["revision"] = "e" * 40
    elif mutation == "runtime-version":
        runtime = json.loads(report.read_text(encoding="utf-8"))
        runtime["version"] = packaging.LOCK["chromium_version"]
        report.write_text(json.dumps(runtime), encoding="utf-8")
    elif mutation == "manifest-drift":
        (candidate["directory"] / "manifest.json").write_text("{}", encoding="utf-8")
    elif mutation == "patch-drift":
        (candidate["directory"] / "patches" / candidate["manifest"]["patches"][0]["file"]).write_text("changed", encoding="utf-8")
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError):
        packaging.package(output, staged, report, archive,
                          candidate_name=None if mutation == "implicit-selection" else "upstream-156")
    assert not archive.exists()
    assert not list(tmp_path.glob("native-package-*"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
def test_native_windows_package_is_reproducible_and_installable_without_claiming_patch_verification(tmp_path, monkeypatch):
    import hashlib
    import json
    import tarfile

    from app.core.native.distribution import NativeBinaryStore
    from scripts.package_native_windows import package

    output, staged, report, destination = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    first = package(output, staged, report, destination)
    second = package(output, staged, report, tmp_path / "second.tar.gz")
    assert first["sha256"] == second["sha256"]
    assert not first["native_patch_runtime_verified"]
    with tarfile.open(destination, "r:gz") as archive:
        metadata = json.load(archive.extractfile("native-release.json"))
        assert set(metadata["files_sha256"]) == set(archive.getnames()) - {"native-release.json"}
        for name, digest in metadata["files_sha256"].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest
        assert {"licenses/Chromium-LICENSE", "licenses/CamouFlow-LICENSE"}.issubset(metadata["files_sha256"])
        assert not metadata["native_patch_runtime_verified"]
        assert metadata["build_receipt_sha256"] == hashlib.sha256((output / "camouflow-build.json").read_bytes()).hexdigest()
        assert metadata["runtime_report_sha256"] == hashlib.sha256(report.read_bytes()).hexdigest()
    release = NativeBinaryStore(tmp_path / "store").install_archive(destination, first["sha256"])
    assert release["build_kind"] == "chromium-fork"
    assert not list(tmp_path.glob("native-package-*"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
@pytest.mark.parametrize("mutation", ["receipt_revision", "receipt_core", "boolean_schema", "binary_changed", "args_changed",
                                     "report_failed", "report_other_binary", "report_partial", "report_version",
                                     "report_missing_core", "report_changed_core", "compiled_dll_changed",
                                     "staged_dll_changed", "missing_dll", "extra_file", "debug_symbols", "overwrite", "missing_license"])
def test_native_windows_package_rejects_unverified_or_changed_inputs(tmp_path, monkeypatch, mutation):
    import json

    from scripts import package_native_windows as packaging

    output, staged, report, destination = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    if mutation in {"receipt_revision", "receipt_core", "boolean_schema"}:
        record = output / "camouflow-build.json"
        value = json.loads(record.read_text(encoding="utf-8-sig"))
        if mutation == "receipt_core":
            value["runtime_core_sha256_measured"]["chrome.dll"] = "a" * 64
        else:
            value["chromium_revision" if mutation == "receipt_revision" else "schema"] = "a" * 40 if mutation == "receipt_revision" else True
        record.write_text(json.dumps(value), encoding="utf-8")
    elif mutation == "compiled_dll_changed":
        (output / "chrome.dll").write_bytes(b"new linked code with the same launcher")
        (staged / packaging.LOCK["chromium_version"] / "chrome.dll").write_bytes((output / "chrome.dll").read_bytes())
    elif mutation in {"binary_changed", "args_changed"}:
        (output / ("chrome.exe" if mutation == "binary_changed" else "args.gn")).write_bytes(b"changed")
    elif mutation.startswith("report_"):
        value = json.loads(report.read_text(encoding="utf-8-sig"))
        if mutation == "report_missing_core":
            del value["runtime_core_sha256_measured"]
        elif mutation == "report_changed_core":
            value["runtime_core_sha256_measured"]["chrome.dll"] = "a" * 64
        else:
            key, changed = {"report_failed": ("passed", False), "report_other_binary": ("binary_sha256_measured", "a" * 64),
                            "report_partial": ("checks", ["concurrent-profile-isolation"]),
                            "report_version": ("version", "152.0.0.0")}[mutation]
            value[key] = changed
        report.write_text(json.dumps(value), encoding="utf-8")
    elif mutation in {"staged_dll_changed", "missing_dll"}:
        path = staged / packaging.LOCK["chromium_version"] / "chrome.dll"
        if mutation == "missing_dll":
            path.unlink()
        else:
            path.write_bytes(b"changed")
    elif mutation in {"extra_file", "debug_symbols"}:
        name = "unknown.dat" if mutation == "extra_file" else "chrome.pdb"
        (staged / name).write_bytes(b"unwanted")
        if mutation == "debug_symbols":
            (output / name).write_bytes(b"unwanted")
    elif mutation == "missing_license":
        (output.parent.parent / "LICENSE").unlink()
    else:
        destination.write_bytes(b"existing archive")
    with pytest.raises(ValueError):
        packaging.package(output, staged, report, destination)
    assert not list(tmp_path.glob("native-package-*"))
    if mutation == "overwrite":
        assert destination.read_bytes() == b"existing archive"
    else:
        assert not destination.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
def test_native_windows_package_rejects_staged_files_changed_during_archiving(tmp_path, monkeypatch):
    import tarfile

    from scripts.package_native_windows import package

    output, staged, report, destination = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    addfile = tarfile.TarFile.addfile
    def changing_addfile(bundle, info, fileobj=None):
        addfile(bundle, info, fileobj)
        if info.name == "chrome.exe":
            (staged / "chrome.exe").write_bytes(b"changed while packaging")
    monkeypatch.setattr(tarfile.TarFile, "addfile", changing_addfile)
    with pytest.raises(ValueError, match="changed while packaging"):
        package(output, staged, report, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob("native-package-*"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
@pytest.mark.parametrize("input_name", ["receipt", "report", "args", "compiled_dll", "compiled_locale", "license"])
@pytest.mark.parametrize("remove", [False, True])
def test_native_windows_package_postguards_all_provenance_and_compiled_inputs(tmp_path, monkeypatch, input_name, remove):
    import tarfile

    from scripts.package_native_windows import package

    output, staged, report, destination = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    paths = {"receipt": output / "camouflow-build.json", "report": report, "args": output / "args.gn",
             "compiled_dll": output / "chrome.dll", "compiled_locale": output / "locales/en-US.pak",
             "license": output.parent.parent / "LICENSE"}
    addfile = tarfile.TarFile.addfile

    def changing_addfile(bundle, info, fileobj=None):
        addfile(bundle, info, fileobj)
        if info.name == "native-release.json":
            if remove:
                paths[input_name].unlink()
            else:
                paths[input_name].write_bytes(b"changed after payload was archived")

    monkeypatch.setattr(tarfile.TarFile, "addfile", changing_addfile)
    with pytest.raises(ValueError, match="input changed while archiving"):
        package(output, staged, report, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob("native-package-*"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
def test_native_windows_package_postguards_after_archive_hashing(tmp_path, monkeypatch):
    from scripts import package_native_windows as packaging

    output, staged, report, destination = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    sha256_file = packaging.sha256_file

    def hashing(path):
        digest = sha256_file(path)
        if path.name == "bundle.tar.gz":
            report.write_bytes(b"changed during final archive hashing")
        return digest

    monkeypatch.setattr(packaging, "sha256_file", hashing)
    with pytest.raises(ValueError, match="input changed while archiving"):
        packaging.package(output, staged, report, destination)
    assert not destination.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only own-fork packager")
@pytest.mark.parametrize("changed", [False, True])
def test_native_windows_package_verifies_official_visual_assets_from_root_build_output(tmp_path, monkeypatch, changed):
    from scripts import package_native_windows as packaging

    output, staged, report, destination = _native_windows_packaging_fixture(tmp_path, monkeypatch)
    for name in ("Logo.png", "SmallLogo.png"):
        (output / name).write_bytes(b"synthetic owned visual asset " + name.encode())
        target = staged / packaging.LOCK["chromium_version"] / "VisualElements" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((output / name).read_bytes())
    if changed:
        (staged / packaging.LOCK["chromium_version"] / "VisualElements/Logo.png").write_bytes(b"changed")
        with pytest.raises(ValueError, match="Staged file differs"):
            packaging.package(output, staged, report, destination)
        assert not destination.exists()
    else:
        result = packaging.package(output, staged, report, destination)
        assert result["files"] == 8


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


@pytest.mark.parametrize("failure", ["capabilities", "observations"])
def test_restart_gate_rejects_lost_policy_and_closes_profiles(tmp_path, monkeypatch, failure):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.core.native.configuration import NativeConfiguration
    from app.core.native.privacy import NativePrivacyPolicy
    from scripts import verify_native_runtime as gate

    configuration = NativeConfiguration(privacy_policy=NativePrivacyPolicy(cpu_limit=2))
    required = configuration.privacy_policy.required_capabilities()
    runtimes = []
    def create(profile, executable, selected):
        assert selected is configuration
        page = SimpleNamespace(goto=AsyncMock())
        context = SimpleNamespace(pages=[page], browser=SimpleNamespace(version="148.0.7778.96"))
        runtime = SimpleNamespace(start=AsyncMock(return_value=context), close=AsyncMock(), context=context,
                                  native_policy_capabilities=[] if failure == "capabilities" else required)
        runtimes.append(runtime)
        return runtime
    monkeypatch.setattr(gate, "NativeRuntime", create)
    monkeypatch.setattr(gate, "process_snapshot", lambda: {})
    inspect = AsyncMock(return_value={"mismatches": ["CPU ceiling"]})
    monkeypatch.setattr(gate, "inspect_native_profile", inspect)
    with pytest.raises(ValueError, match="policy"):
        asyncio.run(gate.verify_multi_profile_restarts(tmp_path, tmp_path / "chrome.exe", "http://127.0.0.1:1",
                                                       configuration=configuration))
    assert len(runtimes) == 3
    for runtime in runtimes:
        runtime.close.assert_awaited_once()
    assert inspect.await_count == (1 if failure == "observations" else 0)


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


def test_controller_process_snapshot_bounds_windows_cim_and_preserves_owner_identity(monkeypatch):
    from scripts import verify_native_runtime

    monkeypatch.setattr(verify_native_runtime.sys, "platform", "win32")

    def snapshot(command, **kwargs):
        assert command[:3] == ["powershell.exe", "-NoProfile", "-Command"]
        assert "-Property ProcessId,ParentProcessId,Name,CreationDate" in command[3]
        assert "-OperationTimeoutSec 30" in command[3]
        assert kwargs["timeout"] == 60
        return '{"ProcessId":123,"ParentProcessId":42,"Name":"chrome.exe","CreationDate":"owned-start"}'

    monkeypatch.setattr(verify_native_runtime.subprocess, "check_output", snapshot)
    assert verify_native_runtime.process_snapshot() == {
        123: {"parent": 42, "name": "chrome.exe", "started": "owned-start"}}


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


@pytest.mark.parametrize("failure", [None, "missing-context", "missing-about-blank", "missing-srcdoc", "missing-path", "repeat", "blob", "htmlDataUrl", "worker-html", "worker-pixels", "restart", "invalid-digest",
                                     "geometry-missing", "geometry-false", "geometry-numeric", "geometry-extra",
                                     "clipped-padding", "opaque-anchor", "transparent-anchor",
                                     "errors-missing", "errors-extra", "errors-type", "worker-zero-width", "worker-zero-height", "worker-empty-export",
                                     "html-capture-missing", "html-capture-false", "html-capture-numeric", "worker-capture"])
def test_native_canvas_baseline_requires_complete_consistent_readbacks(failure):
    from copy import deepcopy
    from scripts.verify_native_canvas import CONTEXTS, ERRORS_EXPECTED, GEOMETRY_EXPECTED, validate_observations

    digest = "a" * 64
    observed = {name: {"pixels": digest, "repeat": digest, "blob": digest,
                      "htmlBlob": None if name in {"dedicated", "shared", "service"} else digest,
                      "htmlDataUrl": None if name in {"dedicated", "shared", "service"} else digest,
                      "htmlCapture": None if name in {"dedicated", "shared", "service"} else True,
                      "geometry": dict(GEOMETRY_EXPECTED), "errors": dict(ERRORS_EXPECTED)}
                for name in CONTEXTS}
    previous = deepcopy(observed)
    if failure == "missing-context":
        del observed["shared"]
    elif failure == "html-capture-missing":
        del observed["document"]["htmlCapture"]
    elif failure == "html-capture-false":
        observed["document"]["htmlCapture"] = False
    elif failure == "html-capture-numeric":
        observed["document"]["htmlCapture"] = 1
    elif failure == "worker-capture":
        observed["service"]["htmlCapture"] = True
    elif failure in {"missing-about-blank", "missing-srcdoc"}:
        del observed["about_blank_frame" if failure == "missing-about-blank" else "srcdoc_frame"]
    elif failure == "missing-path":
        del observed["document"]["pixels"]
    elif failure in {"repeat", "blob", "htmlDataUrl"}:
        observed["document"][failure] = "b" * 64
    elif failure == "worker-html":
        observed["service"]["htmlBlob"] = digest
    elif failure == "worker-pixels":
        observed["dedicated"].update(pixels="b" * 64, repeat="b" * 64, blob="b" * 64)
    elif failure == "restart":
        previous["document"]["pixels"] = "b" * 64
    elif failure == "invalid-digest":
        observed["document"]["pixels"] = "z" * 64
    elif failure == "geometry-missing":
        del observed["shared"]["geometry"]["partialMatchesFull"]
    elif failure == "geometry-false":
        observed["service"]["geometry"]["transparentExport"] = False
    elif failure == "geometry-numeric":
        observed["dedicated"]["geometry"]["outsideRemainsTransparent"] = 1
    elif failure == "geometry-extra":
        observed["document"]["geometry"]["unmeasured"] = True
    elif failure == "errors-missing":
        del observed["shared"]["errors"]["zeroWidthRead"]
    elif failure == "errors-extra":
        observed["dedicated"]["errors"]["unmeasured"] = "IndexSizeError"
    elif failure == "errors-type":
        observed["service"]["errors"] = None
    elif failure in {"worker-zero-width", "worker-zero-height", "worker-empty-export"}:
        field = {"worker-zero-width": "zeroWidthRead", "worker-zero-height": "zeroHeightRead",
                 "worker-empty-export": "emptyOffscreenExport"}[failure]
        observed["service"]["errors"][field] = "no-error"
    elif failure in {"clipped-padding", "opaque-anchor", "transparent-anchor"}:
        field = {"clipped-padding": "clippedPaddingMatches", "opaque-anchor": "opaqueCornerRendered",
                 "transparent-anchor": "transparentAlphaRendered"}[failure]
        observed["service"]["geometry"][field] = False
    if failure is None:
        validate_observations(observed, previous)
    else:
        with pytest.raises(ValueError):
            validate_observations(observed, previous)


@pytest.mark.parametrize("failure", [None, "taintedRead", "taintedDataUrl", "taintedBlob", "taintedOffscreenRead", "taintedOffscreenBlob", "zeroWidthRead", "emptyDataUrl", "emptyBlob", "missing-frame",
                                    "taintedZeroWidth", "taintedOffscreenZeroWidth", "htmlBitmapTaint", "offscreenBitmapTaint",
                                    "clearedTaint", "clearedOffscreenTaint", "resetHtmlBlank", "resetOffscreenBlank",
                                    "resetHtmlState", "resetOffscreenState", "resetHtmlExport", "resetOffscreenExport",
                                    "retaintedRead", "retaintedOffscreenRead"])
def test_native_canvas_security_requires_unchanged_origin_checks_and_empty_behavior(failure):
    from scripts.verify_native_canvas import SECURITY_EXPECTED, validate_security

    observed = {name: dict(SECURITY_EXPECTED) for name in ("document", "same_origin_frame", "cross_origin_frame")}
    if failure == "missing-frame":
        del observed["cross_origin_frame"]
    elif failure:
        observed["cross_origin_frame"][failure] = "unexpected"
    if failure:
        with pytest.raises(ValueError, match="security"):
            validate_security(observed)
    else:
        validate_security(observed)


@pytest.mark.parametrize("stuck", [False, True])
def test_native_hardware_context_close_has_a_deadline_and_never_hides_timeout(monkeypatch, stuck):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts import verify_native_hardware

    async def check():
        async def close():
            if stuck:
                await asyncio.Event().wait()
        context = SimpleNamespace(close=AsyncMock(side_effect=close))
        monkeypatch.setattr(verify_native_hardware, "CONTEXT_CLOSE_TIMEOUT_SECONDS", .01)
        if stuck:
            with pytest.raises(TimeoutError):
                await verify_native_hardware.close_context(context)
        else:
            await verify_native_hardware.close_context(context)
        context.close.assert_awaited_once()
    asyncio.run(check())


def test_native_browser_hardware_validation_embeds_the_same_policy_before_switch_propagation():
    from scripts.native_build import ROOT

    contents = (ROOT / "native/patches/0001-native-hardware-privacy-limits.patch").read_text(encoding="utf-8-sig")
    section = contents.split("+++ b/content/browser/renderer_host/camouflow_hardware_limits.h\n", 1)[1]
    embedded = "\n".join(line[1:] for line in section.splitlines() if line.startswith("+")) + "\n"
    assert embedded == (ROOT / "native/core/hardware_limits.h").read_text(encoding="utf-8-sig")
    assert contents.index("CHECK(camouflow::native::ParseHardwareLimits") < contents.index("renderer_cmd->CopySwitchesFrom")


@pytest.mark.parametrize("diagnostic", ["Invalid CamouFlow Native hardware limits", "Invalid Glint hardware limits",
                                       "Invalid Glint unrelated setting", "Browser executable not found", "Browser launch timed out"])
def test_native_hardware_rejection_requires_specific_native_diagnostic(diagnostic):
    from playwright.async_api import Error
    from scripts.verify_native_hardware import validate_rejection

    if diagnostic in {"Invalid CamouFlow Native hardware limits", "Invalid Glint hardware limits"}:
        validate_rejection(Error(diagnostic))
    else:
        with pytest.raises(ValueError, match="expected native CHECK"):
            validate_rejection(Error(diagnostic))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows runtime core layout")
@pytest.mark.parametrize("changed", [None, "chrome.dll", "chrome_elf.dll"])
def test_native_canvas_cli_binds_evidence_to_core_dlls(tmp_path, monkeypatch, changed):
    import json
    from scripts import verify_native_canvas as canvas

    for name in ("chrome.exe", "chrome.dll", "chrome_elf.dll"):
        (tmp_path / name).write_bytes(name.encode())
    report_path = tmp_path / "canvas.json"
    monkeypatch.setattr(sys, "argv", ["verify_native_canvas", "--executable", str(tmp_path / "chrome.exe"),
                                     "--work-dir", str(tmp_path / "work"), "--report", str(report_path)])

    async def simulated_observation(executable, profile, origin, report):
        if changed:
            (executable.parent / changed).write_bytes(b"changed native implementation")

    monkeypatch.setattr(canvas, "verify", simulated_observation)
    assert canvas.main() == (1 if changed else 0)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(report["runtime_core_sha256_measured"]) == {"chrome.exe", "chrome.dll", "chrome_elf.dll"}
    assert report["binary_sha256_measured"] == report["runtime_core_sha256_measured"]["chrome.exe"]
    assert report["passed"] is (changed is None)
    if changed:
        assert "runtime core changed" in report["error"]


def test_native_canvas_cli_refuses_to_overwrite_evidence(tmp_path, monkeypatch):
    from scripts import verify_native_canvas as canvas

    report = tmp_path / "existing.json"
    report.write_text('{"original": true}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["verify_native_canvas", "--executable", str(tmp_path / "chrome.exe"),
                                     "--work-dir", str(tmp_path / "work"), "--report", str(report)])
    with pytest.raises(SystemExit) as error:
        canvas.main()
    assert error.value.code == 2
    assert report.read_text(encoding="utf-8") == '{"original": true}'


@pytest.mark.skipif(sys.platform != "win32", reason="Windows runtime core layout")
@pytest.mark.parametrize("missing", [None, "chrome.dll", "chrome_elf.dll"])
def test_native_runtime_core_requires_both_dlls_and_detects_relink_without_launcher_change(tmp_path, missing):
    from scripts.verify_native_runtime import measure_runtime_core

    for name in ("chrome.exe", "chrome.dll", "chrome_elf.dll"):
        (tmp_path / name).write_bytes(name.encode())
    executable = tmp_path / "chrome.exe"
    before = measure_runtime_core(executable)
    if missing:
        (tmp_path / missing).unlink()
        with pytest.raises(ValueError, match="missing or linked"):
            measure_runtime_core(executable)
    else:
        (tmp_path / "chrome.dll").write_bytes(b"new native policy code")
        after = measure_runtime_core(executable)
        assert before["chrome.exe"] == after["chrome.exe"]
        assert before["chrome.dll"] != after["chrome.dll"]
        assert set(after) == {"chrome.exe", "chrome.dll", "chrome_elf.dll"}


@pytest.mark.parametrize("failure", [None, "cpu", "memory", "webdriver", "arial", "restricted",
                                     "missing-context", "missing-native", "worker-webdriver", "canvas", "restart",
                                     "headless-ua", "http-ua", "fake-version"])
def test_native_combined_policies_require_all_contexts_and_stable_native_observations(failure):
    from copy import deepcopy
    from scripts.verify_native_canvas import CONTEXTS, ERRORS_EXPECTED, GEOMETRY_EXPECTED
    from scripts.verify_native_combined import validate_observations

    digest = "a" * 64
    observed = {name: {"canvas": {"pixels": digest, "repeat": digest, "blob": digest,
                    "htmlBlob": None if name in {"dedicated", "shared", "service"} else digest,
                    "htmlDataUrl": None if name in {"dedicated", "shared", "service"} else digest,
                    "htmlCapture": None if name in {"dedicated", "shared", "service"} else True,
                    "geometry": dict(GEOMETRY_EXPECTED), "errors": dict(ERRORS_EXPECTED)},
                    "native": {"cpu": 1, "memory": 0.25, "arial": 120.0, "restricted": 120.0,
                               "userAgent": "Mozilla/5.0 Chrome/148.0.0.0 Safari/537.36",
                               "userAgentHeader": "Mozilla/5.0 Chrome/148.0.0.0 Safari/537.36",
                               "webdriver": None if name in {"dedicated", "shared", "service"} else False}}
                for name in CONTEXTS}
    previous = deepcopy(observed)
    if failure in {"cpu", "memory", "webdriver", "arial", "restricted"}:
        observed["document"]["native"][failure] = {"cpu": 12, "memory": 16, "webdriver": True,
                                                     "arial": float("nan"), "restricted": 130}[failure]
    elif failure == "missing-context":
        del observed["shared"]
    elif failure == "missing-native":
        del observed["document"]["native"]
    elif failure == "worker-webdriver":
        observed["service"]["native"]["webdriver"] = False
    elif failure == "canvas":
        observed["dedicated"]["canvas"]["geometry"]["transparentExport"] = False
    elif failure == "restart":
        previous["document"]["native"]["arial"] = 121.0
    elif failure == "headless-ua":
        observed["document"]["native"]["userAgent"] = "Mozilla/5.0 HeadlessChrome/148.0.0.0"
    elif failure == "http-ua":
        observed["shared"]["native"]["userAgentHeader"] = "other"
    elif failure == "fake-version":
        observed["service"]["native"]["userAgent"] = "Mozilla/5.0 Chrome/152.0.0.0"
    if failure is None:
        validate_observations(observed, previous, browser_version="148.0.7778.96")
    else:
        with pytest.raises(ValueError):
            validate_observations(observed, previous, browser_version="148.0.7778.96")


@pytest.mark.parametrize("failure", [None, "missing-restart", "duplicate", "arguments", "missing-dll", "invalid-hash", "other-launcher"])
def test_native_suite_combined_gate_requires_complete_policy_and_code_evidence(failure):
    from scripts.verify_native_combined import ARGUMENTS, REQUIRED_CHECKS
    from scripts.verify_native_suite import GATES, validate_report

    digest = "a" * 64
    report = {"passed": True, "binary_sha256_measured": digest, "arguments": list(ARGUMENTS),
              "checks": [{"name": name, "passed": True} for name in sorted(REQUIRED_CHECKS)],
              "runtime_core_sha256_measured": {name: digest for name in ("chrome.exe", "chrome.dll", "chrome_elf.dll")}}
    assert "combined" in GATES
    if failure == "missing-restart":
        report["checks"].pop()
    elif failure == "duplicate":
        report["checks"][-1] = dict(report["checks"][0])
    elif failure == "arguments":
        report["arguments"].pop()
    elif failure == "missing-dll":
        del report["runtime_core_sha256_measured"]["chrome.dll"]
    elif failure == "invalid-hash":
        report["runtime_core_sha256_measured"]["chrome.dll"] = "z" * 64
    elif failure == "other-launcher":
        report["runtime_core_sha256_measured"]["chrome.exe"] = "b" * 64
    if failure is None:
        validate_report("combined", report, digest)
    else:
        with pytest.raises(ValueError):
            validate_report("combined", report, digest)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows versioned package layout")
@pytest.mark.parametrize("layout", ["versioned", "flat", "unrelated", "non-version", "missing"])
def test_native_runtime_code_measurement_supports_only_explicit_owned_windows_layouts(tmp_path, layout):
    from scripts.verify_native_runtime import measure_runtime_core

    root = tmp_path / "browser"
    root.mkdir()
    executable = root / "chrome.exe"
    executable.write_bytes(b"synthetic launcher")
    libraries = {"versioned": root / "148.0.7778.96", "flat": root,
                 "unrelated": tmp_path / "other", "non-version": root / "other", "missing": root / "0.0.0.0"}[layout]
    if layout != "missing":
        libraries.mkdir(exist_ok=True)
        for name in ("chrome.dll", "chrome_elf.dll"):
            (libraries / name).write_bytes(name.encode())
    if layout in {"versioned", "flat"}:
        assert set(measure_runtime_core(executable, libraries)) == {"chrome.exe", "chrome.dll", "chrome_elf.dll"}
        if layout == "versioned":
            with pytest.raises(ValueError, match="missing or linked"):
                measure_runtime_core(executable)
    else:
        with pytest.raises(ValueError, match="canonical and belong"):
            measure_runtime_core(executable, libraries)


def test_native_privacy_verifier_rejects_unknown_target():
    from scripts.verify_native_privacy_units import validate_results

    with pytest.raises(ValueError, match="Unknown native privacy test target"):
        validate_results({}, target="unknown")


def test_native_context_verifier_requires_every_registered_context_case():
    import re
    from scripts.native_build import ROOT
    from scripts.verify_native_privacy_units import REQUIRED_CONTEXT_TESTS

    patch = "\n".join((ROOT / "native/patches" / name).read_text(encoding="utf-8-sig") for name in (
        "0017-native-browser-context-tests.patch", "0032-native-document-surface-policy.patch"))
    # A follow-up may remove/re-add an existing fixture declaration while
    # changing its body; patch additions are not the final C++ declaration count.
    names = set(re.findall(r"^\+TEST_F\(NativePrivacyBrowserContextTest, (\w+)\)", patch, re.MULTILINE))
    assert len(names) == 26
    assert set(names) == REQUIRED_CONTEXT_TESTS["NativePrivacyBrowserContextTest"]


def test_native_delivery_verifier_requires_every_draft_endpoint_case():
    import re

    from scripts.verify_native_privacy_units import REQUIRED_DELIVERY_TESTS, ROOT

    observed = {}
    endpoint_fixtures = (
        "privacy_document_service_unittest.cc",
        "privacy_worker_service_unittest.cc",
        "privacy_worker_bootstrap_unittest.cc",
    )
    for name in endpoint_fixtures:
        path = ROOT / "native/drafts/document_delivery" / name
        for suite, case in re.findall(r"TEST_F\(\s*(\w+),\s*(\w+)\)", path.read_text(encoding="utf-8-sig")):
            observed.setdefault(suite, []).append(case)
    assert sum(map(len, observed.values())) == 34
    assert {suite: set(cases) for suite, cases in observed.items()} == REQUIRED_DELIVERY_TESTS


def test_native_worker_surface_verifier_covers_registered_fixtures_and_legacy_worker_cases():
    import re

    from scripts.verify_native_privacy_units import REQUIRED_DELIVERY_TESTS, REQUIRED_WORKER_SURFACE_TESTS, ROOT

    patch = (ROOT / "native/patches/0031-native-worker-surface-policy.patch").read_text(encoding="utf-8-sig")
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    observed = {}
    for suite, case in re.findall(r"TEST_F\(\s*(NativePrivacyWorkerSurface\w+),\s*(\w+)\)", additions):
        observed.setdefault(suite, set()).add(case)
    assert sum(map(len, observed.values())) == 30
    for suite in ("NativePrivacyWorkerServiceTest", "NativePrivacyWorkerBootstrapTest"):
        observed[suite] = REQUIRED_DELIVERY_TESTS[suite]
    assert observed == REQUIRED_WORKER_SURFACE_TESTS
    assert sum(map(len, observed.values())) == 55


def test_native_delivery_verifier_snapshots_composed_sources(tmp_path):
    import hashlib
    from scripts.verify_native_privacy_units import DELIVERY_SOURCE_FILES, ROOT, snapshot_delivery_sources

    with pytest.raises(ValueError, match="canonical regular file"):
        snapshot_delivery_sources(tmp_path)
    for name, relative in DELIVERY_SOURCE_FILES.items():
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / "native/drafts/document_delivery" / name).read_bytes())
    before = snapshot_delivery_sources(tmp_path)
    assert len(before) == 10
    relative = DELIVERY_SOURCE_FILES["privacy_worker_service.cc"]
    path = tmp_path / relative
    path.write_text("// later composed patch changes this file\n", encoding="utf-8")
    after = snapshot_delivery_sources(tmp_path)
    assert after != before and after[relative] == hashlib.sha256(path.read_bytes()).hexdigest()
    path.unlink()
    path.mkdir()
    with pytest.raises(ValueError, match="canonical regular file"):
        snapshot_delivery_sources(tmp_path)


def test_delivery_snapshot_never_replaces_full_source_chain_verification(tmp_path, monkeypatch):
    from scripts import verify_native_privacy_units as privacy

    revision = "a" * 40
    monkeypatch.setattr(privacy, "require_idle_builder", lambda *args: None)
    monkeypatch.setattr(privacy.build, "environment", lambda *args, **kwargs: {})
    monkeypatch.setattr(privacy.build, "candidate_workspace", lambda *args: None)
    monkeypatch.setattr(privacy.build, "run", lambda *args, **kwargs: revision)
    monkeypatch.setattr(privacy.build, "require_stage", lambda *args: None)

    def invalid_chain(*args):
        raise ValueError("Unrecognized composed source changes")

    monkeypatch.setattr(privacy.build, "candidate_source_patches", invalid_chain)
    monkeypatch.setattr(privacy, "snapshot_delivery_sources", lambda *args: pytest.fail("Unverified source was accepted"))
    monkeypatch.setattr(privacy.subprocess, "run", lambda *args, **kwargs: pytest.fail("Unverified source started a compiler"))
    with pytest.raises(ValueError, match="Unrecognized composed source"):
        privacy._verify_locked(tmp_path, tmp_path / "proof.json", vs_installation=None, jobs=4,
                               target="delivery", required=privacy.required_tests("delivery"),
                               candidate={"name": "upstream-156"}, lock={"chromium_revision": revision},
                               git_ssl_backend="schannel")


@pytest.mark.parametrize("draft,patch_name,prefix,files", [
    ("canvas", "core_helpers_integration.patch", "third_party/blink/renderer/core/html/canvas/glint", (
        "canvas_partition_seed.cc", "canvas_partition_seed.h",
        "canvas_readback_candidate.cc", "canvas_readback_candidate.h", "canvas_readback_copy.cc",
        "canvas_readback_copy.h", "canvas_readback_image.cc", "canvas_readback_image.h")),
    ("canvas", "blink_test_integration.patch", "third_party/blink/renderer/platform/graphics/glint", (
        "canvas_readback_candidate.cc", "canvas_readback_candidate.h", "canvas_readback_copy.cc",
        "canvas_readback_copy.h", "canvas_readback_copy_unittest.cc", "canvas_readback_image.cc",
        "canvas_readback_image.h", "canvas_readback_image_unittest.cc")),
    ("canvas", "test_integration.patch", "content/browser/camouflow_native/canvas", (
        "canvas_readback_candidate.cc", "canvas_readback_candidate.h", "canvas_readback_copy.cc",
        "canvas_readback_copy.h", "canvas_readback_copy_unittest.cc")),
    ("document_delivery", "worker_bootstrap_integration.patch", "content/renderer/worker", (
        "privacy_worker_bootstrap.cc", "privacy_worker_bootstrap.h", "privacy_worker_bootstrap_unittest.cc")),
    ("document_delivery", "../../patches/0018-native-document-policy-delivery.patch",
     "content/browser/camouflow_native", (
         "privacy_document_service.cc", "privacy_document_service.h", "privacy_document_service_unittest.cc")),
    ("document_delivery", "../../patches/0018-native-document-policy-delivery.patch",
     "third_party/blink/public/mojom/native_privacy", ("native_privacy_document.mojom",)),
    ("document_delivery", "../../patches/0019-native-worker-policy-delivery.patch",
     "content/browser/camouflow_native", (
         "privacy_worker_service.cc", "privacy_worker_service.h", "privacy_worker_service_unittest.cc")),
    ("document_delivery", "../../patches/0020-native-worker-policy-consumer.patch", "content/renderer/worker", (
        "privacy_worker_bootstrap.cc", "privacy_worker_bootstrap.h", "privacy_worker_bootstrap_unittest.cc")),
])
def test_native_draft_registration_embeds_exact_canonical_sources(draft, patch_name, prefix, files):
    from scripts.native_build import ROOT

    directory = ROOT / "native/drafts" / draft
    patch = (directory / patch_name).read_text(encoding="utf-8-sig")
    for name in files:
        relative = f"{prefix}/{name}"
        section = patch.split(f"diff --git a/{relative} b/{relative}\n", 1)[1].split("\ndiff --git ", 1)[0]
        copied = "\n".join(line[1:] for line in section.splitlines()
                           if line.startswith("+") and not line.startswith("+++")) + "\n"
        assert copied == (directory / name).read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("registered,draft", [
    ("0021-native-dedicated-worker-startup-gate.patch", "dedicated_worker_startup_gate.patch"),
    ("0022-native-worker-canvas-thread-handoff.patch", "worker_canvas_thread_handoff.patch"),
    ("0023-native-shared-worker-startup-gate.patch", "shared_worker_startup_gate.patch"),
    ("0024-native-service-worker-canvas-thread-handoff.patch", "service_worker_canvas_thread_handoff.patch"),
    ("0025-native-service-worker-startup-gate.patch", "service_worker_startup_gate.patch"),
    ("0026-native-worker-canvas-handoff-tests.patch", "worker_canvas_handoff_tests.patch"),
    ("0027-native-shared-worker-bootstrap-failure.patch", "shared_worker_bootstrap_failure.patch"),
    ("0028-native-worker-handoff-fixture-lifetime.patch", "worker_handoff_fixture_lifetime.patch"),
    ("0029-native-document-partition-validator-tests.patch", "document_partition_validator_tests.patch"),
])
def test_native_worker_startup_registered_patches_match_reviewed_candidates(registered, draft):
    from scripts.native_build import ROOT

    assert (ROOT / "native/patches" / registered).read_text(encoding="utf-8-sig") == (
        ROOT / "native/drafts/document_delivery" / draft
    ).read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("mode", ["baseline", "ready", "unavailable"])
@pytest.mark.parametrize("kind", ["dedicated", "shared", "service"])
def test_native_worker_startup_observations_require_execution_evidence(mode, kind):
    from scripts.verify_native_worker_startup import validate_observation

    if mode == "unavailable":
        observed = {"status": "registration-error" if kind == "service" else "worker-error", "executions": 0}
    else:
        observed = {"status": "reply", "id": "owned", "executions": 1}
    validate_observation(observed, mode=mode, kind=kind, identifier="owned")
    for failure in ("timeout", "executed", "missing", "boolean"):
        invalid = dict(observed)
        if failure == "timeout":
            invalid["status"] = "timeout"
        elif failure == "executed":
            invalid["executions"] += 1
        elif failure == "boolean":
            invalid["executions"] = False
        else:
            del invalid["executions"]
        with pytest.raises(ValueError):
            validate_observation(invalid, mode=mode, kind=kind, identifier="owned")


@pytest.mark.parametrize("mode", ["baseline", "ready", "unavailable"])
def test_native_worker_startup_configuration_uses_only_explicit_probe_flags(mode):
    from scripts.verify_native_worker_startup import (
        BOOTSTRAP_ARGUMENT, FEATURE_ARGUMENT, KEY_ARGUMENT, StartupConfiguration,
    )

    arguments = StartupConfiguration(probe_mode=mode).launch_arguments()
    assert FEATURE_ARGUMENT in arguments
    assert (BOOTSTRAP_ARGUMENT in arguments) is (mode != "baseline")
    assert (KEY_ARGUMENT in arguments) is (mode == "ready")
    with pytest.raises(ValueError):
        StartupConfiguration(probe_mode="unknown").launch_arguments()


@pytest.mark.parametrize("feature", ["ThirdPartyStoragePartitioning", "ThirdPartyStoragePartitioning<Trial", "ThirdPartyStoragePartitioning:param/value"])
def test_native_worker_startup_preserves_unrelated_driver_exclusions(feature):
    from scripts.verify_native_worker_startup import StartupConfiguration, partitioning_argument

    measured = ["chrome.exe", "--disable-features=Translate," + feature + ",MediaRouter", "--headless"]
    replacement = partitioning_argument(measured)
    assert replacement == "--disable-features=Translate,MediaRouter"
    assert partitioning_argument([replacement]) == replacement
    assert replacement in StartupConfiguration(disabled_features_argument=replacement).launch_arguments()
    configuration = StartupConfiguration(disabled_features_argument=replacement, ignored_driver_argument=measured[1])
    assert configuration.context_options()["ignore_default_args"] == [measured[1]]
    with pytest.raises(ValueError):
        StartupConfiguration(disabled_features_argument=replacement).context_options()
    with pytest.raises(ValueError):
        StartupConfiguration(ignored_driver_argument=measured[1]).context_options()
    with pytest.raises(ValueError):
        StartupConfiguration(disabled_features_argument=measured[1]).launch_arguments()


@pytest.mark.parametrize("arguments", [None, [1], [], ["--disable-features="],
    ["--disable-features=ThirdPartyStoragePartitioning"],
    ["--disable-features=Translate", "--disable-features=MediaRouter"],
    ["--disable-features=Translate,,MediaRouter"]])
def test_native_worker_startup_rejects_ambiguous_driver_exclusions(arguments):
    from scripts.verify_native_worker_startup import partitioning_argument

    with pytest.raises(ValueError):
        partitioning_argument(arguments)


@pytest.mark.parametrize("failure", [None, "patch", "hash", "binary", "revision", "shape"])
def test_native_worker_startup_receipt_requires_matching_registered_chain(tmp_path, failure):
    import hashlib
    import json
    from scripts.verify_native_worker_startup import LOCK, ROOT, validate_receipt

    executable = tmp_path / "chrome.exe"
    patches = [next((ROOT / "native/patches").glob(f"{number:04d}-*.patch")) for number in range(15, 28)]
    receipt = {"chromium_revision": LOCK["chromium_revision"], "binary_sha256_measured": "a" * 64,
               "patches": [{"name": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}
                           for patch in patches]}
    if failure == "patch":
        receipt["patches"].pop()
    elif failure == "hash":
        receipt["patches"][-1]["sha256"] = "b" * 64
    elif failure == "binary":
        receipt["binary_sha256_measured"] = "b" * 64
    elif failure == "revision":
        receipt["chromium_revision"] = "b" * 40
    elif failure == "shape":
        receipt = []
    raw = json.dumps(receipt).encode("utf-8")
    (tmp_path / "camouflow-build.json").write_bytes(raw)
    if failure is None:
        assert validate_receipt(executable, {"chrome.exe": "a" * 64}) == raw
    else:
        with pytest.raises(ValueError):
            validate_receipt(executable, {"chrome.exe": "a" * 64})


@pytest.mark.parametrize("mode,fault", [("baseline", None), ("ready", None), ("unavailable", None),
    ("ready", "execution"), ("ready", "requests"), ("ready", "timeout"), ("unavailable", "execution")])
def test_native_shared_worker_clients_require_reuse_and_close_owned_pages(mode, fault):
    import asyncio
    from scripts.verify_native_worker_startup import verify_shared_clients

    class Page:
        closed = False

        async def goto(self, origin, timeout):
            assert origin == "http://owned" and timeout == 20000

        async def evaluate(self, probe, arguments):
            if arguments.get("reuse"):
                assert context.pages[-2].closed
            if fault == "timeout":
                return {"status": "timeout"}
            if mode == "unavailable":
                return {"status": "worker-error"}
            return {"status": "reply", "id": arguments["id"]}

        async def close(self):
            self.closed = True

    class Context:
        def __init__(self):
            self.pages = []

        async def new_page(self):
            page = Page()
            self.pages.append(page)
            return page

    class Server:
        def count(self, identifier):
            return 2 if fault == "execution" else (0 if mode == "unavailable" else 1)

        def script_count(self, identifier):
            return 2 if fault == "requests" else 1

    context = Context()
    report = {"checks": []}
    if fault:
        with pytest.raises(ValueError):
            asyncio.run(verify_shared_clients(context, "http://owned", Server(), mode, "initial", report))
        assert report["checks"][-1]["passed"] is False
    else:
        asyncio.run(verify_shared_clients(context, "http://owned", Server(), mode, "initial", report))
        assert len(report["checks"]) == 2
        assert all(check["passed"] for check in report["checks"])
        assert all(len(check["observed"]) == (2 if mode == "unavailable" else 3) for check in report["checks"])
    assert context.pages and all(page.closed for page in context.pages)


def test_native_runtime_verifier_import_does_not_cache_application_database_root():
    import subprocess
    from scripts.native_build import ROOT

    result = subprocess.run([sys.executable, "-c", "import sys; import scripts.verify_native_runtime; "
                             "assert 'app.storage.db' not in sys.modules"], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_runtime_verifier_requires_owned_database_before_account_creation():
    from scripts.native_build import ROOT

    code = (ROOT / "scripts/verify_native_runtime.py").read_text(encoding="utf-8-sig")
    assert code.index("db.DATA_ROOT.resolve() != (profile_root / \"workspace\").resolve()") < code.index("db.db_add_account(account)")


def test_native_windows_build_generates_real_third_party_credits():
    from scripts.native_build import ROOT

    arguments = (ROOT / "native/args.gn").read_text(encoding="utf-8-sig")
    assert "generate_about_credits = true" in arguments.splitlines()


@pytest.mark.parametrize("arguments", [["--release-store", "D:/owned"], ["--release-sha256", "a" * 64]])
def test_native_runtime_release_evidence_requires_store_and_checksum_together(monkeypatch, arguments):
    from scripts import verify_native_runtime

    monkeypatch.setattr(sys, "argv", ["verify_native_runtime", *arguments])
    with pytest.raises(SystemExit) as error:
        verify_native_runtime.main()
    assert error.value.code == 2


@pytest.mark.skipif(sys.platform != "win32", reason="Windows immutable package evidence")
@pytest.mark.parametrize("mismatch", ["platform", "build_kind", "executable_path", "chromium_version"])
def test_native_runtime_rejects_release_identity_mismatch_before_browser_start(tmp_path, monkeypatch, mismatch):
    import asyncio
    from types import SimpleNamespace
    from app.core.native import distribution
    from scripts import verify_native_runtime

    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"synthetic launcher")
    libraries = tmp_path / "148.0.7778.96"
    libraries.mkdir()
    for name in ("chrome.dll", "chrome_elf.dll"):
        (libraries / name).write_bytes(name.encode())
    release = {"platform": "win32", "build_kind": "chromium-fork", "executable_path": str(executable),
               "chromium_version": libraries.name}
    release[mismatch] = {"platform": "linux", "build_kind": "sdk", "executable_path": str(tmp_path / "other.exe"),
                         "chromium_version": "0.0.0.0"}[mismatch]
    monkeypatch.setattr(distribution, "NativeBinaryStore", lambda root: SimpleNamespace(inspect=lambda digest: release))
    with pytest.raises(ValueError, match="release identity or DLL layout"):
        asyncio.run(verify_native_runtime.verify(tmp_path / "profiles", executable, "http://127.0.0.1:1", None,
                    library_directory=libraries, release_store=tmp_path / "store", release_digest="a" * 64))


@pytest.mark.parametrize("mutation", [None, "comment", "wrong_suite", "wrong_macro", "duplicate", "declaration_only"])
def test_identity_fixture_audit_requires_actual_unique_definitions(mutation):
    from scripts.verify_native_profile_identity_draft import require_fixture_definitions

    text = "TEST_F(OwnedSuite,\n       RequiredCase) { EXPECT_TRUE(true); }\n"
    if mutation == "comment":
        text = "// RequiredCase\n"
    elif mutation == "wrong_suite":
        text = text.replace("OwnedSuite", "OtherSuite")
    elif mutation == "wrong_macro":
        text = text.replace("TEST_F", "TEST_P")
    elif mutation == "duplicate":
        text += text
    elif mutation == "declaration_only":
        text = "TEST_F(OwnedSuite, RequiredCase);\n"
    if mutation is None:
        require_fixture_definitions(text, "OwnedSuite", ("RequiredCase",))
    else:
        with pytest.raises(ValueError, match="definitions differ"):
            require_fixture_definitions(text, "OwnedSuite", ("RequiredCase",))


@pytest.mark.parametrize("mutation", [None, "missing", "reordered", "duplicate", "extra"])
def test_identity_document_handoff_requires_all_four_pinned_parameters(mutation):
    from scripts.verify_native_profile_identity_draft import require_document_identity_parameters

    modes = ["TestMode::kUnpartitionedStorageAndLinks",
             "TestMode::kUnpartitionedStorageParttionedWithSelfLinks",
             "TestMode::kPartitionedStorageUnpartitionedLinks",
             "TestMode::kPartitionedStorageAndLinksWithSelfLinks"]
    if mutation == "missing":
        modes.pop()
    elif mutation == "reordered":
        modes.reverse()
    elif mutation == "duplicate":
        modes[1] = modes[0]
    elif mutation == "extra":
        modes.append("TestMode::kUnknown")
    text = "INSTANTIATE_TEST_SUITE_P(\nDocumentLoaderTest, DocumentLoaderTest, testing::Values(" + ",\n".join(modes) + "));\n"
    if mutation is None:
        assert require_document_identity_parameters(text) == 4
    else:
        with pytest.raises(ValueError, match="parameter coverage changed"):
            require_document_identity_parameters(text)


def test_identity_fixture_catalog_matches_all_six_candidate_patches():
    import re
    from scripts import verify_native_profile_identity_draft as identity

    patches = (identity.PATCH, identity.MODE_PATCH, identity.CONTEXT_PATCH,
               identity.TRANSPORT_PATCH, identity.HANDOFF_PATCH, identity.LAUNCH_PATCH)
    added = "\n".join(line[1:] for patch in patches
                      for line in patch.read_text(encoding="utf-8-sig").splitlines()
                      if line.startswith("+") and not line.startswith("+++"))
    definitions = re.findall(r"^TEST(?:_F|_P)?\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*\{", added, re.MULTILINE)
    assert len(definitions) == len(set(definitions)) == 41
    identity.require_fixture_definitions(added, "NativeProfileIdentityKeyTest", identity.DERIVATION_FIXTURES, macro="TEST")
    identity.require_fixture_definitions(added, "NativePrivacyKeyServiceTest", identity.SERVICE_FIXTURES + identity.MODE_FIXTURES)
    identity.require_fixture_definitions(added, "NativePrivacyBrowserContextTest", identity.CONTEXT_FIXTURES + identity.LAUNCH_FIXTURES)
    for path, names in identity.TRANSPORT_FIXTURES.items():
        suite = "GlintSurfacePolicyProducerTest" if path.startswith(identity.PRODUCER) else "GlintSurfacePolicyPreflightTest"
        identity.require_fixture_definitions(added, suite, names)
    for path, names in identity.HANDOFF_FIXTURES.items():
        document = path.endswith("document_loader_test.cc")
        identity.require_fixture_definitions(added, "DocumentLoaderTest" if document else "GlintWorkerSurfaceThreadTest",
                                            names, macro="TEST_P" if document else "TEST_F")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows standalone codec runner")
@pytest.mark.parametrize("failure", [None, "compile", "missing_case", "input_change", "browser_change"])
def test_native_metadata_codec_runner_binds_inputs_and_actual_results(tmp_path, monkeypatch, failure):
    import json
    import subprocess
    from scripts import verify_native_gpu_metadata_codec as codec

    workspace = tmp_path / "workspace"
    source = workspace / "chromium/src"
    repo = tmp_path / "repo"
    vs = tmp_path / "vs"
    files = [source / "gpu/command_buffer/common/gl2_types.h",
             source / "testing/gtest/include/gtest/gtest.h",
             source / "third_party/googletest/src/googletest/src/gtest-all.cc",
             source / "third_party/googletest/src/googletest/src/gtest_main.cc",
             vs / "Common7/Tools/VsDevCmd.bat", repo / "scripts/verify_native_privacy_units.py",
             repo / "native/drafts/gpu-transport/glint_readback_metadata.h",
             repo / "native/drafts/gpu-transport/glint_readback_metadata_unittest.cc",
             source / "out/CamouFlowNative/args.gn", source / "out/CamouFlowNative/camouflow-build.json"]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic unit input", encoding="utf-8")
    monkeypatch.setattr(codec, "ROOT", repo)
    monkeypatch.setattr(codec.build, "environment", lambda *_: {})
    monkeypatch.setattr(codec.build, "run", lambda *args, **kwargs: codec.build.LOCK["chromium_revision"])
    measurements = []
    def measure(*_):
        measurements.append(True)
        return {"chrome.exe": "changed" if failure == "browser_change" and len(measurements) > 1 else "unchanged"}
    monkeypatch.setattr(codec.build, "measure_runtime_core", measure)
    def run(command, **kwargs):
        owned = kwargs["cwd"]
        if command[0] == "cmd.exe":
            if failure == "compile":
                raise subprocess.CalledProcessError(1, command)
            (owned / "metadata-codec-tests.exe").write_bytes(b"synthetic test program")
            if failure == "input_change":
                files[2].write_text("changed input", encoding="utf-8")
        else:
            required = codec.required_tests("gpu-metadata-codec")
            names = sorted(required["GlintReadbackMetadataTest"])
            if failure == "missing_case":
                names.pop()
            result = {"tests": len(names), "failures": 0, "disabled": 0,
                      "testsuites": [{"name": "GlintReadbackMetadataTest", "testsuite": [
                          {"name": name, "status": "RUN", "result": "COMPLETED"} for name in names]}]}
            (owned / "tests.json").write_text(json.dumps(result), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(codec.subprocess, "run", run)
    report = tmp_path / "codec.json"
    proof = codec.verify(workspace, report, vs)
    assert proof["passed"] is (failure is None)
    assert proof["chromium_target_built"] is False
    assert proof["privacy_admitted"] is False
    assert report.is_file()
    with pytest.raises(ValueError, match="overwrite"):
        codec.verify(workspace, report, vs)


@pytest.mark.parametrize("engine,store", [("native", None), ("camoufox", "store")])
def test_packaged_runtime_requires_native_store_pair(tmp_path, engine, store):
    from app.python_runtime_check import check_runtime

    with pytest.raises(ValueError, match="explicit managed"):
        check_runtime(engine, tmp_path / "report.json", native_store=store)
    assert not (tmp_path / "report.json").exists()


def test_packaged_native_runtime_preserves_store_and_existing_evidence(tmp_path):
    from app.python_runtime_check import check_runtime

    store = tmp_path / "store"
    store.mkdir()
    with pytest.raises(ValueError, match="outside"):
        check_runtime("native", store / "report.json", native_store=store)
    report = tmp_path / "report.json"
    report.write_text("original", encoding="utf-8")
    with pytest.raises(ValueError, match="overwrite"):
        check_runtime("native", report, native_store=store)
    assert report.read_text(encoding="utf-8") == "original"
    assert list(store.iterdir()) == []


def test_release_native_runtime_command_and_evidence(tmp_path, monkeypatch):
    import json
    from scripts import verify_release as release

    commands = []
    def run(command):
        commands.append(command)
        Path(command[-1]).write_text(json.dumps({"passed": True}), encoding="utf-8")
    monkeypatch.setattr(release, "run", run)
    exe = tmp_path / "CamouFlow.exe"
    store = tmp_path / "store"
    reports = tmp_path / "reports"
    release.runtime_check(exe, ["native"], native_store=store, report_dir=reports)
    assert commands == [[str(exe), "--check-native-runtime", str(store), str(reports / "native.json")]]
    with pytest.raises(SystemExit, match="overwrite"):
        release.runtime_check(exe, ["native"], native_store=store, report_dir=reports)
    assert len(commands) == 1


@pytest.mark.parametrize("mismatch", [False, True])
def test_packaged_native_runtime_requires_observed_policy(tmp_path, monkeypatch, mismatch):
    import json
    from app import python_runtime_check
    from app.storage import db
    from app.services import scenario_worker
    from app.core.native import distribution, health

    store = tmp_path / "store"
    store.mkdir()
    class Store:
        def __init__(self, root):
            self.root = root

        def resolve_active(self):
            return {"executable_path": str(store / "chrome.exe"), "release_sha256": "synthetic"}

    async def probe(executable, configuration, profile):
        assert profile.is_relative_to(tmp_path)
        return {"mismatches": ["CPU"] if mismatch else [],
                "native_patch_capabilities": configuration.privacy_policy.required_capabilities()}

    calls = []
    def worker(account, job, event):
        step = job["steps"][1]
        calls.append(step["timeout_ms"])
        assert account["native_settings"]["binary_store"] == str(store)
        return {"status": "failed" if job["scenario"] == "hard-timeout" else "success",
                "error": "Python timeout" if job["scenario"] == "hard-timeout" else ""}

    monkeypatch.setattr(db, "init_db", lambda: None)
    monkeypatch.setattr(distribution, "NativeBinaryStore", Store)
    monkeypatch.setattr(health, "probe_native_profile", probe)
    monkeypatch.setattr(scenario_worker, "run_worker", worker)
    monkeypatch.setenv("CAMOUFLOW_DATA_DIR", "preserved")
    report = tmp_path / "report.json"
    assert python_runtime_check.check_runtime("native", report, native_store=store) == int(mismatch)
    assert calls == ([] if mismatch else [15000, 3000])
    assert json.loads(report.read_text(encoding="utf-8"))["passed"] is not mismatch
    import os
    assert os.environ["CAMOUFLOW_DATA_DIR"] == "preserved"


@pytest.mark.parametrize("pinned,revision,status,aligned", [
    ("148.0.7778.96", "a" * 40, "behind-stable", False),
    ("156.0.8078.36", "b" * 40, "aligned", True),
    ("156.0.8078.36", "a" * 40, "review-required", False),
    ("157.0.0.1", "a" * 40, "review-required", False),
])
def test_upstream_audit_compares_numeric_versions_and_exact_revision(pinned, revision, status, aligned):
    import datetime as dt
    from scripts import audit_native_upstream as upstream

    releases = [{"version": version, "channel": "Stable", "platform": "Windows", "time": 1000,
                 "hashes": {"chromium": "b" * 40}} for version in ("99.0.0.1", "156.0.8078.36", "155.0.8059.85")]
    report = upstream.compare({"chromium_version": pinned, "chromium_revision": revision}, releases,
                              dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc))
    assert report["status"] == status and report["upstream_aligned"] is aligned
    assert report["highest_observed_stable"]["version"] == "156.0.8078.36"
    assert report["production_admitted"] is False and report["security_review_complete"] is False


@pytest.mark.parametrize("field,value", [("channel", "Beta"), ("platform", "Linux"), ("version", "invalid"),
                                         ("time", True), ("time", -1), ("time", 99999999999999),
                                         ("hashes", []), ("hashes", {"chromium": "not-a-commit"})])
def test_upstream_audit_rejects_malformed_official_metadata(field, value):
    import datetime as dt
    from scripts import audit_native_upstream as upstream

    release = {"version": "156.0.8078.36", "channel": "Stable", "platform": "Windows", "time": 1000,
               "hashes": {"chromium": "b" * 40}, field: value}
    with pytest.raises(ValueError):
        upstream.compare({"chromium_version": "148.0.7778.96", "chromium_revision": "a" * 40}, [release],
                         dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc))


def test_upstream_audit_preserves_existing_evidence_before_network(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from scripts import audit_native_upstream as upstream

    output = tmp_path / "report.json"
    output.write_text("original", encoding="utf-8")
    request = Mock()
    monkeypatch.setattr(upstream.urllib.request, "urlopen", request)
    with pytest.raises(ValueError, match="new evidence"):
        upstream.audit(output)
    request.assert_not_called()
    assert output.read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("failure", [None, "redirect", "oversized", "changed-lock"])
def test_upstream_audit_binds_lock_and_bounded_https_response(tmp_path, monkeypatch, failure):
    import hashlib
    import json
    from unittest.mock import MagicMock
    from scripts import audit_native_upstream as upstream

    root = tmp_path / "repo"
    (root / "native").mkdir(parents=True)
    lock = root / "native/build-lock.json"
    original = json.dumps({"chromium_version": "148.0.7778.96", "chromium_revision": "a" * 40}).encode()
    lock.write_bytes(original)
    monkeypatch.setattr(upstream, "ROOT", root)
    raw = json.dumps([{"version": "156.0.8078.36", "channel": "Stable", "platform": "Windows", "time": 1000,
                       "hashes": {"chromium": "b" * 40}}]).encode()
    response = MagicMock()
    response.__enter__.return_value = response
    response.geturl.return_value = "https://untrusted.invalid" if failure == "redirect" else upstream.SOURCE_URL
    def read(limit):
        assert limit == upstream.MAX_RESPONSE_BYTES + 1
        if failure == "changed-lock":
            lock.write_bytes(original + b" ")
        return b"x" * limit if failure == "oversized" else raw
    response.read.side_effect = read
    def open_url(request, timeout):
        assert request.full_url == upstream.SOURCE_URL and timeout == 30
        return response
    monkeypatch.setattr(upstream.urllib.request, "urlopen", open_url)
    output = tmp_path / "report.json"
    if failure is not None:
        with pytest.raises(ValueError):
            upstream.audit(output)
        assert not output.exists()
    else:
        report = upstream.audit(output)
        assert report["status"] == "behind-stable"
        assert report["lock_sha256"] == hashlib.sha256(original).hexdigest()
        assert report["response_sha256"] == hashlib.sha256(raw).hexdigest()
        assert json.loads(output.read_text(encoding="utf-8")) == report
        assert lock.read_bytes() == original


@pytest.mark.parametrize("failure", [None, "base", "manifest", "patch", "stale-base", "wrong-root"])
def test_upstream_candidate_audit_binds_selection_and_refuses_drift(tmp_path, monkeypatch, failure):
    import hashlib
    import json
    from unittest.mock import MagicMock, Mock
    from scripts import audit_native_upstream as upstream, native_build

    root = tmp_path / "repo"
    (root / "native").mkdir(parents=True)
    lock_path = root / "native/build-lock.json"
    base = {"chromium_version": "148.0.7778.96", "chromium_revision": "a" * 40}
    lock_bytes = json.dumps(base).encode()
    lock_path.write_bytes(lock_bytes)
    selected = {**base, "chromium_version": "156.0.8078.36", "chromium_revision": "b" * 40}
    monkeypatch.setattr(upstream, "ROOT", root)
    monkeypatch.setattr(native_build, "ROOT", tmp_path if failure == "wrong-root" else root)
    monkeypatch.setattr(native_build, "LOCK", {} if failure == "stale-base" else base)
    candidate = {"lock": selected, "manifest_sha256": "c" * 64}
    after = {**candidate, "manifest_sha256": "d" * 64} if failure == "manifest" else candidate
    loader = Mock(side_effect=[candidate, ValueError("Changed candidate patch") if failure == "patch" else after])
    monkeypatch.setattr(native_build, "load_candidate", loader)
    response = MagicMock()
    response.__enter__.return_value = response
    response.geturl.return_value = upstream.SOURCE_URL
    raw = json.dumps([{"version": selected["chromium_version"], "channel": "Stable", "platform": "Windows",
                       "time": 1000, "hashes": {"chromium": selected["chromium_revision"]}}]).encode()

    def read(limit):
        assert limit == upstream.MAX_RESPONSE_BYTES + 1
        if failure == "base":
            lock_path.write_bytes(lock_bytes + b" ")
        return raw

    response.read.side_effect = read
    network = Mock(return_value=response)
    monkeypatch.setattr(upstream.urllib.request, "urlopen", network)
    output = tmp_path / "report.json"
    if failure:
        with pytest.raises(ValueError):
            upstream.audit(output, candidate_name="upstream-156")
        assert not output.exists()
        if failure in {"stale-base", "wrong-root"}:
            network.assert_not_called()
    else:
        report = upstream.audit(output, candidate_name="upstream-156")
        assert report["status"] == "aligned" and report["candidate"] == "upstream-156"
        assert report["pinned_version"] == selected["chromium_version"]
        assert report["candidate_manifest_sha256"] == candidate["manifest_sha256"]
        assert report["lock_sha256"] == hashlib.sha256(lock_bytes).hexdigest()
        assert report["response_sha256"] == hashlib.sha256(raw).hexdigest()
        assert report["production_admitted"] is False and report["sources_changed"] is False
        assert lock_path.read_bytes() == lock_bytes


@pytest.mark.parametrize("version,revision,expected,status", [
    ("148.0.7778.96", "a", None, "behind-stable"),
    ("156.0.8078.36", "a", "156.0.8078.75", "behind-stable"),
    ("157.0.8103.27", "c", "157.0.8103.27", "aligned"),
])
def test_upstream_audit_distinguishes_observed_milestone_updates_from_current_stable(version, revision, expected, status):
    import datetime as dt
    from scripts import audit_native_upstream as upstream

    releases = [{"version": value, "channel": "Stable", "platform": "Windows", "time": 1000,
                 "hashes": {"chromium": commit * 40}} for value, commit in (
        ("156.0.8078.36", "a"), ("156.0.8078.75", "b"), ("157.0.8103.27", "c"))]
    report = upstream.compare({"chromium_version": version, "chromium_revision": revision * 40},
                              releases, dt.datetime.now(dt.timezone.utc))
    observed = report["highest_observed_same_milestone"]
    assert (observed["version"] if observed is not None else None) == expected
    assert report["status"] == status
    assert report["highest_observed_stable"]["version"] == "157.0.8103.27"
    assert report["production_admitted"] is False


def test_upstream_audit_unknown_candidate_rejects_before_network(tmp_path, monkeypatch):
    from unittest.mock import Mock
    from scripts import audit_native_upstream as upstream

    network = Mock()
    monkeypatch.setattr(upstream.urllib.request, "urlopen", network)
    with pytest.raises(ValueError, match="Unknown Native build candidate"):
        upstream.audit(tmp_path / "report.json", candidate_name="unknown")
    network.assert_not_called()
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize("change", [None, "modify", "add", "remove"])
def test_gpu_codegen_compares_complete_generated_file_set(tmp_path, monkeypatch, change):
    from scripts import verify_native_gpu_transport_draft as gpu

    target = tmp_path / "gpu/original_autogen.h"
    target.parent.mkdir()
    target.write_bytes(b"original")
    formatter = tmp_path / "formatter.exe"
    formatter.write_bytes(b"owned formatter")
    def generate(command, cwd, env):
        assert cwd == tmp_path and command[-2:] == [str(tmp_path), str(formatter)]
        if change == "modify":
            target.write_bytes(b"changed")
        elif change == "add":
            (target.parent / "unexpected_autogen.h").write_bytes(b"new output")
        elif change == "remove":
            target.unlink()
    monkeypatch.setattr(gpu.build, "run", generate)
    if change:
        with pytest.raises(ValueError, match="Regenerated GPU source differs"):
            gpu.verify_codegen(tmp_path, formatter, {})
    else:
        assert gpu.verify_codegen(tmp_path, formatter, {}) == 1


@pytest.mark.parametrize("directory", [".", "v8"])
@pytest.mark.parametrize("failure", [None, "source", "patch", "apply", "postguard", "deleted-input", "dependency", "directory", "invariant", "codegen", "formatter-changed"])
def test_upstream_draft_replay_checks_inputs_application_and_postguards(tmp_path, monkeypatch, failure, directory):
    import hashlib
    import json
    from scripts import verify_native_rebase_draft as draft

    source = tmp_path / "source"
    source.mkdir()
    original = b"int value = 1;\n"
    input_file = source / directory / "value.cc"
    input_file.parent.mkdir(parents=True, exist_ok=True)
    input_file.write_bytes(original)
    candidate = tmp_path / "draft"
    (candidate / "patches").mkdir(parents=True)
    patch = candidate / "patches/change.patch"
    patch.write_text("diff --git a/value.cc b/value.cc\n--- a/value.cc\n+++ b/value.cc\n@@ -1 +1 @@\n-int value = 1;\n+int value = 2;\n", encoding="utf-8", newline="\n")
    manifest = {"schema": 1, "target_revision": "a" * 40,
                "source_files": [{"path": input_file.relative_to(source).as_posix(), "sha256": hashlib.sha256(original).hexdigest()}],
                "patches": [{"file": "change.patch", "sha256": hashlib.sha256(patch.read_bytes()).hexdigest(), "directory": directory}]}
    if directory == "v8":
        dependencies = ("vars = {'v8_revision': '" + "a" * 40 + "'}\n").encode()
        (source / "DEPS").write_bytes(dependencies)
        manifest["source_files"].append({"path": "DEPS", "sha256": hashlib.sha256(dependencies).hexdigest()})
        manifest["dependencies"] = {"v8": {"revision": "a" * 40}}
    if failure == "dependency":
        manifest["dependencies"] = {"v8": {"revision": "b" * 40}}
    if failure == "directory":
        manifest["patches"][0]["directory"] = "../escape"
    formatter = None
    if failure in {"codegen", "formatter-changed"}:
        from scripts import verify_native_gpu_transport_draft as gpu

        formatter = tmp_path / "formatter.exe"
        formatter.write_bytes(b"owned formatter")
        for name in (".clang-format", "gpu/command_buffer/build_cmd_buffer_lib.py",
                     "gpu/command_buffer/build_gles2_cmd_buffer.py", "gpu/command_buffer/gles2_cmd_buffer_functions.txt"):
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# owned input\n")
            manifest["source_files"].append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        def generate(owned, executable, env):
            assert executable == formatter and owned == tmp_path / "output/src"
            if failure == "codegen":
                raise ValueError("Owned generation failure")
            formatter.write_bytes(b"changed formatter")
            return 1
        monkeypatch.setattr(gpu, "verify_codegen", generate)
    (candidate / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(draft, "DRAFT", candidate)
    if failure == "source":
        input_file.write_bytes(b"changed source")
    if failure == "patch":
        patch.write_bytes(b"changed patch")
    output = tmp_path / "output"
    if failure in {"source", "patch", "dependency", "directory"}:
        with pytest.raises(ValueError):
            draft.verify(source, output)
        assert not output.exists()
        return
    run = draft.subprocess.run
    def wrapped(command, **kwargs):
        if "apply" in command and "--check" in command and failure == "apply":
            return draft.subprocess.CompletedProcess(command, 1, "", "owned application failure")
        result = run(command, **kwargs)
        if "apply" in command and "--check" not in command:
            if failure == "postguard":
                input_file.write_bytes(b"changed during replay")
            elif failure == "deleted-input":
                input_file.unlink()
        return result
    monkeypatch.setattr(draft.subprocess, "run", wrapped)
    if failure == "invariant":
        def reject_invariants(inputs, work):
            raise ValueError("Owned ABI drift")
        monkeypatch.setattr(draft, "verify_source_invariants", reject_invariants)
    report = draft.verify(source, output, formatter=formatter)
    assert report["passed"] is (failure is None)
    assert report["compiled"] is False and report["runtime_verified"] is False and report["production_admitted"] is False
    if formatter is not None:
        assert report["codegen"]["passed"] is False
    if failure is None:
        assert (output / "src" / directory / "value.cc").read_bytes() == b"int value = 2;\n"
    assert json.loads((output / "report.json").read_text(encoding="utf-8")) == report
    with pytest.raises(ValueError, match="new external"):
        draft.verify(source, output)


@pytest.mark.parametrize("failure", [None, "renumber", "rename", "extra", "duplicate", "resource-id", "resource-shape", "malformed"])
def test_upstream_source_invariants_reject_abi_and_resource_drift(tmp_path, failure):
    from scripts import verify_native_rebase_draft as draft

    ids = "gpu/command_buffer/common/gles2_cmd_ids_autogen.h"
    resources = "chrome/app/chromium_strings.grd"
    original = "  OP(Existing) /* 576 */\n"
    commands = original + "  OP(GetGlintReadFramebufferMetadataCHROMIUM) /* 577 */\n"
    xml = '<grit><messages><message name="IDS_NAME">Chromium</message></messages></grit>'
    updated = xml.replace("Chromium", "Glint")
    if failure == "renumber":
        commands = commands.replace("576", "575")
    elif failure == "rename":
        commands = commands.replace("Existing", "Renamed")
    elif failure == "extra":
        commands += "  OP(Extra) /* 578 */\n"
    elif failure == "duplicate":
        commands = commands.replace("/* 577 */", "/* 576 */")
    elif failure == "resource-id":
        updated = updated.replace("IDS_NAME", "IDS_OTHER")
    elif failure == "resource-shape":
        updated = updated.replace("Glint", "<ph name='NEW'>Glint</ph>")
    elif failure == "malformed":
        updated = "<grit>"
    for name, content in ((ids, commands), (resources, updated)):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    inputs = {ids: original.encode(), resources: xml.encode()}
    if failure:
        with pytest.raises((ValueError, SyntaxError)):
            draft.verify_source_invariants(inputs, tmp_path)
    else:
        assert draft.verify_source_invariants(inputs, tmp_path) == {
            "gpu_commands": {"preserved": 1, "appended": 577}, "grit_structure_preserved": True}


@pytest.mark.parametrize("failure", [None, "patch", "revision", "jobs", "space", "settings", "v8", "sequence"])
def test_native_candidate_selection_pins_inputs_without_mutating_default_lock(tmp_path, monkeypatch, failure):
    import copy
    import hashlib
    import json
    from scripts import native_build as build

    original_lock = copy.deepcopy(build.LOCK)
    directory = tmp_path / "native/drafts/upstream-156"
    (directory / "patches").mkdir(parents=True)
    patch = directory / "patches/0001-owned.patch"
    patch.write_bytes(b"owned patch\n")
    manifest = {"schema": 1, "target_revision": "a" * 40, "target_version": "156.0.8078.36",
                "chromium_repository": build.LOCK["chromium_repository"],
                "build": {"depot_tools_revision": "b" * 40, "minimum_free_gib": 180, "build_jobs": 4},
                "dependencies": {"v8": {"repository": "https://chromium.googlesource.com/v8/v8.git", "revision": "c" * 40}},
                "patches": [{"file": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}]}
    if failure == "patch":
        patch.write_bytes(b"modified")
    elif failure == "revision":
        manifest["target_revision"] = "main"
    elif failure == "jobs":
        manifest["build"]["build_jobs"] = 5
    elif failure == "space":
        manifest["build"]["minimum_free_gib"] = 1
    elif failure == "settings":
        manifest["build"]["chromium_repository"] = "https://untrusted.invalid"
    elif failure == "v8":
        manifest["dependencies"]["v8"]["revision"] = "HEAD"
    elif failure == "sequence":
        manifest["patches"][0]["file"] = "../0001-owned.patch"
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(build, "ROOT", tmp_path)
    if failure:
        with pytest.raises(ValueError):
            build.load_candidate("upstream-156")
    else:
        candidate = build.load_candidate("upstream-156")
        assert candidate["lock"]["chromium_revision"] == "a" * 40
        assert candidate["lock"]["depot_tools_revision"] == "b" * 40
        assert candidate["manifest_sha256"] == hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()
    assert build.LOCK == original_lock
    with pytest.raises(ValueError, match="Unknown"):
        build.load_candidate("../unknown")


@pytest.mark.parametrize("failure", [None, "prepare", "apply", "dirty", "concurrent-edit"])
def test_native_candidate_batch_application_prepares_both_repositories_and_preserves_edits(tmp_path, monkeypatch, failure):
    import hashlib
    import json
    import os
    import subprocess
    from scripts import native_build as build

    source = tmp_path / "src"
    source.mkdir()
    candidate_directory = tmp_path / "draft"
    (candidate_directory / "patches").mkdir(parents=True)
    environment = dict(os.environ)
    revisions = []
    rows = []
    original = bytes(range(256))
    for number, directory in enumerate((".", "v8"), 1):
        repository = source / directory
        repository.mkdir(exist_ok=True)
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=repository, env=environment)
        git("init", "--quiet")
        git("config", "core.autocrlf", "false")
        (repository / ".gitignore").write_text("v8/\n", encoding="utf-8")
        (repository / "value.bin").write_bytes(original)
        git("add", ".")
        git("-c", "user.name=Glint fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "owned baseline")
        revisions.append(git("rev-parse", "HEAD").decode().strip())
        (repository / "value.bin").write_bytes(original[::-1])
        content = git("diff", "--binary", "HEAD")
        content += b"diff --git a/added.txt b/added.txt\nnew file mode 100644\n--- /dev/null\n+++ b/added.txt\n@@ -0,0 +1 @@\n+owned new file\n"
        (repository / "value.bin").write_bytes(original)
        if failure == "prepare" and directory == "v8":
            content = b"invalid patch\n"
        name = f"{number:04d}-owned.patch"
        (candidate_directory / "patches" / name).write_bytes(content)
        rows.append({"file": name, "directory": directory, "sha256": hashlib.sha256(content).hexdigest()})
    candidate = {"name": "upstream-156", "directory": candidate_directory, "manifest_sha256": "a" * 64,
                 "manifest": {"target_revision": revisions[0], "dependencies": {"v8": {"revision": revisions[1]}}, "patches": rows}}
    monkeypatch.setattr(build, "load_candidate", lambda name: candidate)
    if failure == "dirty":
        (source / "user-file").write_bytes(b"preserve")
    run = build.run
    def wrapped(command, cwd, env, **kwargs):
        actual_apply = command[:2] == ["git", "apply"] and "--check" not in command and "--reverse" not in command
        if actual_apply and cwd == source / "v8" and failure in {"apply", "concurrent-edit"}:
            if failure == "concurrent-edit":
                (source / "user-file").write_bytes(b"preserve concurrent edit")
            raise subprocess.CalledProcessError(1, command)
        return run(command, cwd, env, **kwargs)
    monkeypatch.setattr(build, "run", wrapped)
    if failure:
        with pytest.raises((ValueError, subprocess.SubprocessError)):
            build.apply_candidate_patches(source, environment, candidate)
        if failure == "concurrent-edit":
            assert (source / "user-file").read_bytes() == b"preserve concurrent edit"
            assert (source / "value.bin").read_bytes() == original[::-1]
            report = json.loads(next(tmp_path.glob("glint-candidate-patches-*/report.json")).read_bytes())
            assert report["rollback_errors"] and report["passed"] is False
        else:
            for repository in (source, source / "v8"):
                assert (repository / "value.bin").read_bytes() == original
                assert not (repository / "added.txt").exists()
            if failure == "dirty":
                assert (source / "user-file").read_bytes() == b"preserve"
            else:
                report = json.loads(next(tmp_path.glob("glint-candidate-patches-*/report.json")).read_bytes())
                assert report["passed"] is False
                assert report["rolled_back"] == (["."] if failure == "apply" else [])
    else:
        patches = build.apply_candidate_patches(source, environment, candidate)
        assert len(patches) == 2
        for repository in (source, source / "v8"):
            assert (repository / "value.bin").read_bytes() == original[::-1]
            assert (repository / "added.txt").read_bytes() == b"owned new file\n"
        assert build.apply_candidate_patches(source, environment, candidate) == patches
        for repository in (source, source / "v8"):
            assert subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=repository) == b""


def test_native_workspace_lock_rejects_concurrent_operations_and_releases_after_error(tmp_path):
    from scripts import native_build as build

    with pytest.raises(RuntimeError, match="owned operation failed"), build.workspace_lock(tmp_path):
        with pytest.raises(ValueError, match="Another Native"), build.workspace_lock(tmp_path):
            pytest.fail("Concurrent workspace lock was acquired")
        raise RuntimeError("owned operation failed")
    with build.workspace_lock(tmp_path):
        assert (tmp_path / "glint-build.lock").is_file()


def test_native_workspace_lock_is_released_after_owning_process_terminates(tmp_path):
    import subprocess

    from scripts import native_build as build

    command = ("from pathlib import Path\nfrom scripts.native_build import workspace_lock\n"
               "import sys,time\nwith workspace_lock(Path(sys.argv[1])):\n"
               " print('owned-lock-ready',flush=True)\n time.sleep(60)\n")
    process = subprocess.Popen([sys.executable, "-c", command, str(tmp_path)], cwd=build.ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "owned-lock-ready"
        assert process.poll() is None
        with pytest.raises(ValueError, match="Another Native"), build.workspace_lock(tmp_path):
            pytest.fail("Cross-process workspace lock was acquired")
    finally:
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=15)
    with build.workspace_lock(tmp_path):
        pass


def test_native_workspace_lock_blocks_execute_before_tool_or_source_changes(tmp_path, monkeypatch):
    from scripts import native_build as build

    monkeypatch.setattr(build, "preflight", lambda *args, **kwargs: {})
    def forbidden(*args, **kwargs):
        pytest.fail("A concurrent operation reached tool/source mutation")
    monkeypatch.setattr(build, "environment", forbidden)
    with build.workspace_lock(tmp_path):
        with pytest.raises(ValueError, match="Another Native"):
            build.execute("build", tmp_path)
        build.execute("preflight", tmp_path)


@pytest.mark.parametrize("action", ["sync", "hooks", "patch"])
def test_native_candidate_stages_accept_explicit_local_sdk(tmp_path, monkeypatch, action):
    from scripts import native_build as build

    if sys.platform != "win32":
        with pytest.raises(ValueError, match="candidate build stages"):
            build.execute(action, tmp_path, candidate_name="upstream-156", local_toolchain=True)
        return
    calls = []
    monkeypatch.setattr(build, "preflight", lambda *args, **kwargs: {})
    monkeypatch.setattr(build, "_execute_locked", lambda *args, **kwargs: calls.append((args, kwargs)))
    build.execute(action, tmp_path, candidate_name="upstream-156", jobs=4, local_toolchain=True)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == action and args[2] == 4 and args[3]["name"] == "upstream-156"
    assert kwargs["local_toolchain"] is True


@pytest.mark.parametrize("action", ["sync", "hooks"])
@pytest.mark.parametrize("changed", [False, True])
def test_native_dependency_stages_recheck_local_sdk_before_receipt(tmp_path, monkeypatch, action, changed):
    from scripts import native_build as build

    (tmp_path / "chromium").mkdir()
    chromium = _native_build_stage_fixture(tmp_path / "chromium")
    (chromium / ".gclient").unlink()
    if action == "hooks":
        (chromium / ".gclient").write_text("owned fixture", encoding="utf-8")
    candidate = build.load_candidate("upstream-156")
    selected = {"GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": "a" * 64, "DEPOT_TOOLS_WIN_TOOLCHAIN": "1",
                "vs2026_install": str(tmp_path / "selected-vs2026"), "GYP_MSVS_OVERRIDE_PATH": "unrelated inherited path"}
    monkeypatch.setattr(build, "environment", lambda *args, **kwargs: dict(selected))
    monkeypatch.setattr(build, "checkout", lambda *args: None)
    monkeypatch.setattr(build, "bootstrap_windows_git", lambda *args: None)
    monkeypatch.setattr(build, "depot_command", lambda name, *args: [name])
    commands = []
    def run(command, *args, **kwargs):
        commands.append(command)
        assert args[1]["DEPOT_TOOLS_WIN_TOOLCHAIN"] == ("0" if action == "hooks" else "1")
        assert args[1]["GYP_MSVS_OVERRIDE_PATH"] == (selected["vs2026_install"] if action == "hooks" else "unrelated inherited path")
        return candidate["lock"]["chromium_revision"] if command[:2] == ["git", "rev-parse"] else ""
    monkeypatch.setattr(build, "run", run)
    monkeypatch.setattr(build, "require_stage", lambda *args: None)
    monkeypatch.setattr(build, "snapshot_dependencies", lambda *args: None)
    monkeypatch.setattr(build, "local_windows_toolchain", lambda *args: {
        "GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": ("b" if changed else "a") * 64})
    records = []
    monkeypatch.setattr(build, "record_stage", lambda *args: records.append(args))
    if changed:
        with pytest.raises(ValueError, match="changed during " + action):
            build._execute_locked(action, tmp_path, 4, candidate, candidate["lock"], local_toolchain=True)
        assert not records
    else:
        build._execute_locked(action, tmp_path, 4, candidate, candidate["lock"], local_toolchain=True)
        assert records == [(chromium, action, candidate)]
    assert any(command[:2] == ["gclient", "sync" if action == "sync" else "runhooks"] for command in commands)


@pytest.mark.parametrize("action", ["preflight", "bootstrap", "other", "sync", "hooks", "patch"])
def test_native_local_sdk_rejects_implicit_candidate_or_unsupported_stage(tmp_path, action):
    from scripts import native_build as build

    with pytest.raises(ValueError, match="explicit.*candidate build"):
        build.execute(action, tmp_path / "not-created", local_toolchain=True)
    assert not (tmp_path / "not-created").exists()


def test_native_patch_action_requires_explicit_candidate_before_any_workspace_changes(tmp_path):
    from scripts import native_build as build

    workspace = tmp_path / "not-created"
    with pytest.raises(ValueError, match="explicit --candidate"):
        build.execute("patch", workspace)
    assert not workspace.exists()


def test_native_candidate_workspace_cannot_reuse_or_be_opened_as_default(tmp_path):
    from scripts import native_build as build

    candidate = build.load_candidate("upstream-156")
    workspace = tmp_path / "candidate"
    build.candidate_workspace(workspace, candidate)
    assert not workspace.exists()
    build.candidate_workspace(workspace, candidate, claim=True)
    build.candidate_workspace(workspace, candidate)
    with pytest.raises(ValueError, match="explicit"):
        build.candidate_workspace(workspace, None)
    changed = {**candidate, "lock": {**candidate["lock"], "chromium_revision": "a" * 40}}
    with pytest.raises(ValueError, match="different revision"):
        build.candidate_workspace(workspace, changed)
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "user-file").write_bytes(b"preserve")
    with pytest.raises(ValueError, match="new empty workspace"):
        build.candidate_workspace(existing, candidate, claim=True)
    assert (existing / "user-file").read_bytes() == b"preserve"
    assert not (existing / "glint-build-candidate.json").exists()


def test_native_candidate_stage_identity_is_bound_to_manifest(tmp_path):
    from scripts import native_build as build

    chromium = _native_build_stage_fixture(tmp_path)
    candidate = build.load_candidate("upstream-156")
    build.record_stage(chromium, "sync", candidate)
    build.require_stage(chromium, "sync", candidate)
    with pytest.raises(ValueError, match="inputs changed"):
        build.require_stage(chromium, "sync")
    with pytest.raises(ValueError, match="inputs changed"):
        build.require_stage(chromium, "sync", {**candidate, "manifest_sha256": "a" * 64})


@pytest.mark.parametrize("failure", [None, "chromium", "v8", "partial"])
def test_native_candidate_requires_exact_checkout_and_complete_patch_chain(tmp_path, monkeypatch, failure):
    from scripts import native_build as build

    candidate = build.load_candidate("upstream-156")
    source = tmp_path / "src"
    (source / "v8").mkdir(parents=True)
    def run(command, cwd, env, **kwargs):
        if cwd == source:
            return "wrong" if failure == "chromium" else candidate["lock"]["chromium_revision"]
        return "wrong" if failure == "v8" else candidate["manifest"]["dependencies"]["v8"]["revision"]
    def patches(path, env, names, **kwargs):
        assert kwargs["patch_directory"] == candidate["directory"] / "patches"
        return [] if failure == "partial" else [{"name": name, "sha256": "a" * 64} for name in names]
    monkeypatch.setattr(build, "run", run)
    monkeypatch.setattr(build, "_source_patches", patches)
    if failure:
        with pytest.raises(ValueError):
            build.candidate_source_patches(source, {}, candidate)
    else:
        rows = build.candidate_source_patches(source, {}, candidate)
        assert len(rows) == len(candidate["manifest"]["patches"]) == 67 and sum(row.get("repository") == "v8" for row in rows) == 1


def test_native_candidate_safe_buffer_port_keeps_bounded_cpp_paths():
    from scripts import native_build as build

    candidate = build.load_candidate("upstream-156")
    row = candidate["manifest"]["patches"][62]
    assert row["file"] == "0063-native-safe-buffer-portability.patch"
    patch = (candidate["directory"] / "patches" / row["file"]).read_text(encoding="utf-8")
    paths = [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")]
    assert paths == [
        "third_party/blink/renderer/core/frame/camouflow_hardware_limits.h",
        "content/browser/renderer_host/camouflow_hardware_limits.h",
        "third_party/blink/renderer/core/html/canvas/glint/canvas_readback_candidate.cc",
    ]
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert additions.count("std::to_address(concurrency.end())") == 2
    assert additions.count("for (const auto& [name, value] : options)") == 2
    assert "std::span<uint8_t, 4> output" in additions
    assert "std::span(message).subspan(domain_size).first<4>()" in additions
    assert "std::span(message).subspan(domain_size + 4).first<4>()" in additions
    assert not any(token in patch for token in (
        "UNSAFE_BUFFERS", "UNSAFE_TODO", "-Wno-unsafe", "#pragma clang diagnostic"))


def test_native_candidate_audio_copy_uses_bounded_domain_without_changing_policy():
    from scripts import native_build as build

    candidate = build.load_candidate("upstream-156")
    row = candidate["manifest"]["patches"][63]
    assert row["file"] == "0064-native-audio-safe-domain-copy.patch"
    patch = (candidate["directory"] / "patches" / row["file"]).read_text(encoding="utf-8")
    assert [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")] == [
        "third_party/blink/renderer/modules/webaudio/glint/offline_audio_candidate.cc"]
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "std::ranges::copy(std::span(kDomain).first<sizeof(kDomain) - 1>()" in additions
    assert "message.begin()" in additions
    assert not any(token in additions for token in (
        "memcpy", "HMAC", "normalized", "seed_", "digest", "UNSAFE_BUFFERS", "-Wno-unsafe"))


def test_native_candidate_fixture_append_changes_only_three_test_units():
    from scripts import native_build as build

    candidate = build.load_candidate("upstream-156")
    row = candidate["manifest"]["patches"][64]
    assert row["file"] == "0065-native-fixture-portability.patch"
    patch = (candidate["directory"] / "patches" / row["file"]).read_text(encoding="utf-8")
    assert [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")] == [
        "third_party/blink/renderer/core/workers/worker_thread_test.cc",
        "content/browser/camouflow_native/privacy_worker_service_unittest.cc",
        "gpu/command_buffer/service/gles2_cmd_decoder_passthrough_unittest_commands.cc"]
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert additions.count("reporting_proxy_->WaitUntilDidEvaluateTopLevelScript();") == 6
    for function, arguments in (("CalculateWorkerStorageKey", "script_url, Partition()"),
                                ("CalculateWorkerRendererOrigin", "script_url, partition")):
        for flag in ("false", "true"):
            assert f"{function}({arguments}, {flag})" in additions
    assert "offsetof(GuardedResult, guard)" in additions
    assert "kSharedMemoryOffset + sizeof(GuardedResult) <= kSharedBufferSize" in additions
    assert "storage->guard = 0x4c" in additions
    assert "EXPECT_EQ(storage->guard, 0x4c)" in additions
    assert not any(token in additions for token in (
        "WaitForInit", "UNSAFE_BUFFERS", "UNSAFE_TODO", "-Wno-unsafe", "#pragma clang diagnostic"))


def test_157_manifests_separate_source_application_from_runtime_admission():
    import hashlib
    import json
    from scripts import fetch_native_rebase_sources as fetch
    from scripts import native_build as build

    candidate = build.load_candidate("upstream-156")
    root = build.ROOT / "native/drafts/upstream-157-prefix"
    prefix = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    full = json.loads((root / "full-inputs-manifest.json").read_text(encoding="utf-8"))
    assert len(prefix["patches"]) == prefix["selected_prefix_patches"] == 32
    assert len(prefix["source_files"]) == 88
    assert len(full["patches"]) == full["selected_patch_count"] == 65
    assert len(full["source_files"]) == 185 and full["verified_prefix_patches"] == 65
    assert full["source_corpus_complete"] is True
    assert full["source_application_complete"] is True
    assert full["next_port_required_patch"] is None
    assert prefix["next_port_required_patch"] == "0033-native-surface-readback.patch"
    assert prefix["patches"] == full["patches"][:32]
    assert {row["path"] for row in prefix["source_files"]} < {row["path"] for row in full["source_files"]}
    for value in (prefix, full):
        assert value["base_manifest_sha256"] == hashlib.sha256(
            (candidate["directory"] / "checkpoints/001-065.json").read_bytes()).hexdigest()
        assert value["target_revision"] == "f9d7b13a569b352a0267234ea5740fdecc83ffa2"
        assert value["target_version"] == "157.0.8103.27"
        assert value["dependencies"]["v8"]["revision"] == "a4889e05285021952e2ca9648c805a4c989345ae"
        assert value["complete_forward_port"] is False
        assert not value["compiled"] and not value["runtime_verified"] and not value["production_admitted"]
        assert fetch.source_plan(value) == value["source_files"]
    overrides = {row["file"] for row in full["patches"] if row["file"].startswith("upstream-157-prefix/")}
    assert len(overrides) == 11
    baseline = json.loads((candidate["directory"] / "checkpoints/001-065.json").read_bytes())
    for row, original in zip(full["patches"], baseline["patches"], strict=True):
        path = build.ROOT / "native/drafts" / row["file"]
        assert path.name == original["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        if row["file"] not in overrides:
            assert row["file"].startswith("upstream-156/patches/") and row["sha256"] == original["sha256"]
    for name in ("manifest.json", "full-inputs-manifest.json"):
        raw = (root / name).read_bytes()
        assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")


def test_157_audio_port_preserves_chunk_queue_and_checks_actual_buffer_budget():
    from scripts import native_build as build

    path = build.ROOT / "native/drafts/upstream-157-prefix/patches/0033-native-surface-readback.patch"
    patch = path.read_text(encoding="utf-8")
    section = patch.split(
        "diff --git a/third_party/blink/renderer/modules/webaudio/offline_audio_context.cc", 1)[1]
    section = section.split("diff --git ", 1)[0]
    additions = "\n".join(line[1:] for line in section.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "SurfaceSeedResult seed(glint_audio_partition_seed_)" in additions
    assert "if (!glint_audio_policy_captured_)" in additions
    assert "CanCopyOfflineAudio(number_of_channels, buffer_size)" in additions
    assert "glint_audio_policy_captured_ = true" in additions
    assert "total_render_frames_" not in additions and "complete_resolver_" not in additions
    assert additions.index("CopyOfflineAudioBuffer") < additions.index("CloseInternal()")
    assert additions.index("CloseInternal()") < additions.index("resolver->Reject")
    assert "RejectPendingRenderingResolvers();" in additions
    assert "FireCompletionEvent" not in additions and "DispatchEvent" not in additions
    assert not any(line.startswith("-") and not line.startswith("---")
                   for line in section.splitlines())


def test_157_pending_chunk_audio_fixtures_are_bound_and_not_admitted():
    import hashlib
    import hmac
    import json
    import re
    import struct
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-157-prefix"
    descriptor = json.loads((root / "chunked-audio-tests.json").read_text(encoding="utf-8"))
    manifest_path = root / "full-inputs-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert descriptor["schema"] == 1
    assert descriptor["target_revision"] == manifest["target_revision"]
    assert descriptor["target_version"] == manifest["target_version"]
    assert descriptor["required_base_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    for field in ("selected_in_manifest", "compiled", "native_tests_executed", "runtime_verified", "production_admitted"):
        assert descriptor[field] is False
    row = descriptor["patch"]
    assert row["file"] == "0066-native-chunked-audio-tests.patch"
    assert all(Path(patch["file"]).name != row["file"] for patch in manifest["patches"])
    assert not (root / "patches" / row["file"]).exists()
    raw = (root / row["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    patch = raw.decode("utf-8")
    assert [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")] == [descriptor["source"]["path"]]
    assert descriptor["source"]["path"].endswith("/offline_audio_context_test.cc")
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    names = re.findall(r"TEST_F\(OfflineAudioContextTest,\s*(\w+)\)", additions)
    assert names == descriptor["expected_tests"] and len(names) == len(set(names)) == 13
    assert {"GlintProtectedQueuedChunksResumeAfterSuspension",
            "GlintProtectedQueueCloseRejectsAllPendingWork",
            "GlintClosedContextRetainsNativePrecedenceOverMissingPolicy",
            "GlintProtectedQueueContextDestroyedRejectsPendingWork",
            "GlintProtectedQueueFrameDetachSuppressesLateCompletion"} <= set(names)
    assert len(descriptor["api_headers"]) == 5 and descriptor["remaining_uncovered_cases"]
    for header in descriptor["api_headers"]:
        assert len(header["git_blob_sha1"]) == 40 and len(header["sha256"]) == 64
        assert 0 < header["bytes"] < 1024 * 1024
    lifecycle = descriptor["lifecycle_fixture_scope"]
    for field in ("compiled", "executed", "gc_stress_verified", "wait_for_promises_in_destroyed_realm"):
        assert lifecycle[field] is False
    assert {Path(row["path"]).name for row in descriptor["lifecycle_api_sources"]} == {
        "base_audio_context.h", "base_audio_context.cc", "frame.h", "local_frame.h"}
    for source in descriptor["lifecycle_api_sources"]:
        assert len(source["git_blob_sha1"]) == 40 and len(source["sha256"]) == 64
        assert 0 < source["bytes"] < 1024 * 1024
    callback = additions.split("GlintProtectedQueueContextDestroyedRejectsPendingWork", 1)[1].split("TEST_F(", 1)[0]
    assert callback.index("context->ContextDestroyed();") < callback.index("first.WaitUntilSettled();")
    assert "EXPECT_TRUE(future_suspend.IsRejected());" in callback
    assert "context->OnChunkRendered();" in callback and "EXPECT_EQ(completion->count(), 0);" in callback
    detached = additions.split("GlintProtectedQueueFrameDetachSuppressesLateCompletion", 1)[1]
    after_detach = detached.split("Detach(FrameDetachType::kRemove)", 1)[1]
    assert "WaitUntilSettled();" not in after_detach
    assert "EXPECT_EQ(context->GetExecutionContext(), nullptr);" in after_detach
    assert "context->OnChunkRendered();" in after_detach
    assert "DOMExceptionCode::kInvalidStateError" in after_detach
    assert {vector["seed_byte"] for vector in descriptor["hmac_vectors"]} == {4, 5}
    for vector in descriptor["hmac_vectors"]:
        bits = int(vector["input_bits"], 16)
        message = b"glint.audio.offline.f32.candidate.v1" + struct.pack(">I", bits & ~1)
        digest = hmac.new(bytes([vector["seed_byte"]]) * 32, message, hashlib.sha256).digest()
        assert digest.hex() == vector["hmac_sha256"]
        assert f"{(bits & ~1) | (digest[0] & 1):08x}" == vector["output_bits"]
    calibration = descriptor["compatibility_calibration"]
    assert calibration["v1_vectors_are_compatibility_acceptance"] is False
    assert calibration["requires_matched_stock_and_candidate_controls"] is True
    assert calibration["native_candidate_observed"] is False
    assert calibration["production_gate_passed"] is False
    assert calibration["native148_observed"] is True
    observed = root / calibration["matched148_observations"]["file"]
    assert observed.name == "audio-constant-observations.json"
    assert hashlib.sha256(observed.read_bytes()).hexdigest() == calibration["matched148_observations"]["sha256"]
    control = root / calibration["script"]["file"]
    assert control.name == "audio-constant-control.js"
    raw_control = control.read_bytes()
    assert hashlib.sha256(raw_control).hexdigest() == calibration["script"]["sha256"]
    assert b"\r" not in raw_control and not raw_control.startswith(b"\xef\xbb\xbf")
    conflict = calibration["analytical_control_conflict"]
    vector = next(row for row in descriptor["hmac_vectors"] if row["seed_byte"] == conflict["seed_byte"])
    assert conflict["input_bits"] == vector["input_bits"]
    assert conflict["v1_predicted_bits"] == vector["output_bits"]
    assert conflict["stock148_observed_bits"] == conflict["input_bits"] != conflict["v1_predicted_bits"]


def test_compressor_matrix_preserves_native_calibration_and_scope():
    import hashlib
    import json
    import runpy
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    raw = (root / "matrix-observations.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["schema"] == 1 and data["compiled_experiment"]
    for field in ("selected_in_engine", "compiled_browser", "native156_runtime_verified",
                  "variant_browser_execution_verified", "variant_device_cohort_verified", "production_admitted"):
        assert data[field] is False
    assert len(data["artifacts"]) == 6
    for artifact in data["artifacts"]:
        content = (root / artifact["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
        assert b"\r" not in content and not content.startswith(b"\xef\xbb\xbf")
    module = runpy.run_path(str(root / "matrix.py"), run_name="glint_matrix_test")
    case_bytes, cases = module["load_cases"](root / "cases.json")
    assert hashlib.sha256(case_bytes).hexdigest() == data["case_manifest_sha256"]
    assert len(cases) == len(data["cases"]) == data["case_count"] == 15
    assert {case["id"] for case in cases} == {row["id"] for row in data["cases"]}
    assert {case["rate"] for case in cases} == {44100, 48000, 96000}
    assert any(case["frames"] == 8193 for case in cases)
    assert any(case["release"] == 0 for case in cases)
    assert any(case["channels"] == 2 for case in cases)
    assert data["all_cpp_legacy_native_results_equal"] and data["all_cpp_block_and_interleaving_checks_equal"]
    assert data["all_browser_captures_match_native_samples"] and data["all_browser_shapes_and_completion_identity_verified"]
    assert data["browser_repetitions_per_case"] == {"stock-baseline": 3, "a-native-baseline": 3}
    assert sum(row["browser_captures"] for row in data["cases"]) == data["browser_capture_count"] == 90
    changed = [row["id"] for row in data["cases"] if row["variant_changed_channel_samples"]]
    assert changed == data["variant_changed_cases"] == ["random-default", "constant-compressed", "ratio-one"]
    for row in data["cases"]:
        assert row["browser_captures"] == 6
        assert (row["native_samples_sha256"] != row["float32_samples_sha256"]) == bool(row["variant_changed_channel_samples"])
        assert 0 <= row["rms_error"] <= row["max_abs_error"] < 0.000001
    assert len(data["driver_negative_controls"]) == 8
    assert all(row["rejected"] and row["exit_code"] == 2 and row["samples_written"] is False
               for row in data["driver_negative_controls"])
    original = json.loads((root / "observations.json").read_text(encoding="utf-8"))["browser_baseline_calibration"]
    for field in ("receipt_sha256", "native_core_sha256", "stock_core_sha256"):
        assert data[field] == original[field]
    assert data["browser_postguards_passed"] and data["all_runtime_resources_closed"]
    assert data["sandbox_requested"] and data["no_sandbox_flag_absent"]


@pytest.mark.parametrize("failure", ["not-object", "schema-bool", "cases-type", "empty", "too-many",
                                    "duplicate", "unsafe-id", "missing-field", "extra-field",
                                    "unknown-signal", "signal-type", "graph-type", "channels-bool",
                                    "frames-float", "frames-range", "seed-range", "nonfinite",
                                    "nan", "negative-release", "zero-ratio", "huge-number", "missing-default"])
def test_compressor_matrix_rejects_malformed_case_manifests(tmp_path, failure):
    import json
    import runpy
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    module = runpy.run_path(str(root / "matrix.py"), run_name="glint_matrix_validation_test")
    data = json.loads((root / "cases.json").read_text(encoding="utf-8"))
    row = data["cases"][0]
    if failure == "not-object":
        data = []
    elif failure == "schema-bool":
        data["schema"] = True
    elif failure == "cases-type":
        data["cases"] = {}
    elif failure == "empty":
        data["cases"] = []
    elif failure == "too-many":
        data["cases"] = [row] * 33
    elif failure == "duplicate":
        data["cases"].append(dict(row))
    elif failure == "unsafe-id":
        row["id"] = "../outside"
    elif failure == "missing-field":
        del row["release"]
    elif failure == "extra-field":
        row["extra"] = 1
    elif failure == "unknown-signal":
        row["signal"] = "unknown"
    elif failure == "signal-type":
        row["signal"] = []
    elif failure == "graph-type":
        row["graph"] = []
    elif failure == "channels-bool":
        row["channels"] = True
    elif failure == "frames-float":
        row["frames"] = 8192.0
    elif failure == "frames-range":
        row["frames"] = 131073
    elif failure == "seed-range":
        row["seed"] = 0x100000000
    elif failure == "nonfinite":
        row["amplitude"] = float("inf")
    elif failure == "nan":
        row["attack"] = float("nan")
    elif failure == "negative-release":
        row["release"] = -0.1
    elif failure == "zero-ratio":
        row["ratio"] = 0
    elif failure == "huge-number":
        row["knee"] = 10 ** 1000
    elif failure == "missing-default":
        row["id"] = "other-case"
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        module["load_cases"](path)


def test_compressor_math_workbench_binds_sources_without_granting_profile_admission():
    import hashlib
    import json
    import runpy
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    raw = (root / "observations.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["schema"] == 1 and data["compiled_experiment"] is True
    for field in ("selected_in_engine", "compiled_browser", "native156_runtime_verified",
                  "profile_policy_transport_implemented", "variant_device_cohort_verified",
                  "production_admitted", "variant_compatibility_admitted"):
        assert data[field] is False
    artifacts = {row["file"]: row["sha256"] for row in data["artifacts"]}
    assert len(artifacts) == len(data["artifacts"]) == 4
    assert set(artifacts) == {"compressor_math_policy.h", "driver.cc", "probe.py", "compressor-control.js"}
    for name, digest in artifacts.items():
        content = (root / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        assert b"\r" not in content and not content.startswith(b"\xef\xbb\xbf")
    module = runpy.run_path(str(root / "probe.py"), run_name="glint_compressor_probe_test")
    assert module["EXPECTED_SOURCES"] == data["source_sha256"]
    assert len(data["source_sha256"]) == 7
    metrics = data["prototype"]
    assert metrics["frames"] == 8192 and metrics["channels"] == 2 and metrics["sample_rate"] == 44100
    assert metrics["legacy_native_different_samples"] == 0
    assert metrics["segmentation_differences"] == metrics["interleaved_differences"] == 0
    assert metrics["native_float32_different_samples"] == 2
    assert 0 < metrics["rms_error"] < metrics["max_abs_error"] < 0.000001
    assert metrics["selector_values_checked"] == 1025 and data["mono_input_stereo_channels_identical"]
    assert metrics["pow_edge_cases_checked"] == 72 and metrics["pow_edge_category_mismatches"] == 0
    assert metrics["pow_edge_mismatches"] == [] and data["corrected_pow_category_parity"]
    failure = data["initial_pow_category_failure"]
    assert failure["count"] == len(failure["cases"]) == 5
    assert failure["policy_sha256"] != artifacts["compressor_math_policy.h"]
    assert data["native_samples_sha256"] != data["float32_samples_sha256"]
    assert {row["case"] for row in data["tool_negative_controls"]} == {
        "existing-output", "source-drift", "invalid-object"}
    assert all(row["rejected"] and row["exit_code"] == 1 for row in data["tool_negative_controls"])
    assert data["active_build_input_count_unchanged"] == 201 and data["remaining_unverified"]


def test_first_156_runtime_observations_preserve_baseline_and_failure_boundaries():
    import hashlib
    import json
    import re
    from scripts import native_build as build
    from scripts.package_native_windows import REQUIRED_RUNTIME_CHECKS

    root = build.ROOT / "native/drafts/upstream-156"
    raw = (root / "windows-runtime-observations.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    manifest_raw = (root / "checkpoints/001-065.json").read_bytes()
    assert data["schema"] == 1 and data["target_version"] == "156.0.8078.36"
    assert data["target_revision"] == json.loads(manifest_raw)["target_revision"]
    assert data["candidate_manifest_sha256"] == hashlib.sha256(manifest_raw).hexdigest()
    assert data["compiled_patch_count"] == 65
    for field in ("identity_browser_verified", "full_policy_suite_verified", "audio_math_included",
                  "release_admitted", "production_admitted"):
        assert data[field] is False
    core = data["runtime_core_sha256"]
    assert set(core) == {"chrome.exe", "chrome.dll", "chrome_elf.dll"}
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in core.values())
    startup = data["startup"]
    assert startup["passed"] and startup["browser_version"] == data["target_version"]
    assert startup["sandbox_requested"] and startup["no_sandbox_flag_absent"]
    assert startup["resources_closed"] and startup["postguards_passed"]
    assert "HeadlessChrome/156." in startup["page"]["version"]
    keys = data["native_identity_keys"]
    assert keys["passed"] and keys["tests"] == 62 and keys["target"] == "identity-keys"
    assert keys["postguards_passed"] and keys["baseline_browser_code_unchanged"]
    for target, count in (("identity-contexts", 37), ("identity-transport", 20)):
        units = data["native_" + target.replace("-", "_")]
        assert units["passed"] and units["target"] == target and units["tests"] == count
        assert units["postguards_passed"] and units["baseline_browser_code_unchanged"]
        assert len(units["test_binary_sha256"]) == 64 and units["scope"]
    repeats = data["baseline_lifecycle_under_build"]
    assert repeats["passed"] and repeats["postguards_passed"]
    assert repeats["retention_patched_verifier_copy"] and repeats["execution_copy_root_adjusted"]
    assert repeats["canonical_verifier_changed"] is False
    assert repeats["timeout_increased"] is repeats["forced_kill_added"] is False
    assert repeats["first_close_timeout_resolved"] is False and repeats["not_a_performance_benchmark"]
    assert len(repeats["repetitions"]) == 3 and len(repeats["verifier_sha256"]) == 64
    assert {row["repetition"] for row in repeats["repetitions"]} == {1, 2, 3}
    assert all(row["passed"] and row["checks"] == 18 and row["elapsed_seconds"] > 0
               and row["owned_build_activity_observed_before"] for row in repeats["repetitions"])
    attempts = data["expanded_runtime_attempts"]
    assert len(attempts) == 3 and attempts[0]["passed"] is False
    assert len(attempts[0]["completed_checks"]) == 5
    assert attempts[0]["primary_close_timeout_observed"] and attempts[0]["failed_evidence_retained"]
    assert {row["diagnostic_logging_enabled"] for row in attempts[1:]} == {True, False}
    assert all(row["passed"] and len(row["checks"]) == 18
               and REQUIRED_RUNTIME_CHECKS.issubset(row["checks"]) for row in attempts[1:])
    shutdown = data["shutdown_diagnosis"]
    assert shutdown["passed"] and shutdown["runs"] == 16
    assert shutdown["reviewed148_cycles"] == shutdown["candidate156_cycles"] == 8
    assert 0 < shutdown["minimum_close_seconds"] <= shutdown["maximum_close_seconds"] < 30
    assert shutdown["all_observed_owned_processes_exited"] and shutdown["postguards_passed"]
    assert shutdown["timeout_changed"] is shutdown["forced_termination"] is False
    assert shutdown["initial_timeout_root_cause_resolved"] is False
    assert shutdown["matched_stock156_control"] is False
    assert data["frozen_build_inputs_unchanged"] == 201 and data["remaining_unverified"]


def test_exact_stock_156_control_and_historical_revision_stamp_are_bound():
    import base64
    import hashlib
    import json
    from urllib.parse import parse_qs, urlsplit
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-156"
    raw = (root / "stock-control-observations.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    manifest = json.loads((root / "manifest.json").read_bytes())
    assert data["schema"] == 1 and data["platform"] == "win32" and data["passed"]
    assert data["target_version"] == data["executable_pe_version"] == manifest["target_version"]
    assert data["target_revision"] == manifest["target_revision"]
    assert data["browser_get_version"]["product"] == "Chrome/" + data["target_version"]
    assert data["browser_get_version"]["revision"] == "@" + data["target_revision"]
    assert data["exact_stock_runtime_source_verified"] and data["official_md5_matched"]
    metadata = data["official_object_metadata"]
    assert metadata["name"] == "156.0.8078.36/win64/chrome-win64.zip"
    assert len(base64.b64decode(metadata["md5Hash"], validate=True)) == 16
    assert int(metadata["size"]) == data["archive_bytes"] == 209126017
    assert len(data["archive_sha256"]) == 64 and metadata["generation"].isdecimal()
    archive = urlsplit(data["archive_url"])
    assert archive.scheme == "https" and archive.netloc == "storage.googleapis.com"
    assert archive.path == "/chrome-for-testing-public/" + metadata["name"]
    assert parse_qs(archive.query) == {"generation": [metadata["generation"]]}
    assert data["version_metadata_http_status"] == 404 and data["exact_asset_head_http_status"] == 200
    assert data["resources_closed"] and data["controlled_page_passed"] and data["postguards_passed"]
    for field in ("production_admitted", "managed_activation_performed", "same_build_flags_verified",
                  "matched_full_surface_calibration_passed", "effective_sandbox_flags_verified"):
        assert data[field] is False
    stamp = data["native_build_revision_stamp"]
    assert stamp["passed"] and stamp["dummy_generation_matches_active_header"]
    assert stamp["real_generation_only_changes_last_change"] and stamp["official_build_remains_false"]
    assert stamp["branding_and_version_preserved"] and stamp["source_and_output_unchanged"]
    assert stamp["real_lastchange"].startswith(data["target_revision"] + "-")
    assert stamp["override_applied"] is stamp["compiled"] is stamp["runtime_real_stamp_verified"] is False
    fragment = (root / stamp["override_file"]).read_bytes()
    assert hashlib.sha256(fragment).hexdigest() == stamp["override_sha256"] and b"\r" not in fragment
    assert [line for line in fragment.decode().splitlines() if line and not line.startswith("#")] == ["use_dummy_lastchange = false"]
    selected_args = (build.ROOT / "native/args.gn").read_text(encoding="utf-8-sig")
    assert [line for line in selected_args.splitlines() if line.startswith("use_dummy_lastchange")] == [
        "use_dummy_lastchange = false"]
    assert data["frozen_inputs_unchanged"] == stamp["frozen_inputs_unchanged"] == 201


def test_same_upstream_156_audio_aba_records_only_unprotected_calibration():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    raw = (root / "matched-stock-observations.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    stock_raw = (root / data["stock_control_file"]).read_bytes()
    stock = json.loads(stock_raw)
    baseline = json.loads((root.parent / "upstream-156/windows-runtime-observations.json").read_bytes())
    assert hashlib.sha256(stock_raw).hexdigest() == data["stock_control_sha256"]
    assert hashlib.sha256((root / "cases.json").read_bytes()).hexdigest() == data["cases_sha256"]
    assert hashlib.sha256((root / "compressor-matrix-control.js").read_bytes()).hexdigest() == data["probe_sha256"]
    assert data["schema"] == 1 and data["passed"] and data["measurement_complete"] and data["postguards_passed"]
    assert data["capture_count"] == 135 and data["case_count"] == 15 and data["repetitions_per_case_per_phase"] == 3
    assert data["native_matches_stock_all_cases"] and data["stock_float32_exact_cases"] == 12
    assert data["native_core_sha256"] == baseline["runtime_core_sha256"]
    assert data["stock_core_sha256"] == stock["stock_core_sha256"]
    assert data["candidate_build_receipt_sha256"] == baseline["build_receipt_sha256"]
    for field in ("native_policy_enabled", "audio_math_included", "float32_backend_runtime_verified",
                  "variant_device_cohort_verified", "privacy_admitted", "production_admitted",
                  "same_build_flags_verified", "native_runtime_revision_self_reported"):
        assert data[field] is False
    assert data["native_dummy_revision_expected"] and data["native_receipt_revision_verified"] and data["stock_runtime_revision_verified"]
    assert [row["label"] for row in data["phases"]] == ["native-before", "stock", "native-after"]
    for phase in data["phases"]:
        assert phase["capture_count"] == 45 and phase["resources_closed"]
        assert phase["all_event_promise_buffers_identical"] and phase["all_audio_contexts_closed"] and phase["all_case_repetitions_bit_exact"]
        assert phase["source_base_revision"] == stock["target_revision"]
        assert phase["observed_runtime_revision"] == (stock["target_revision"] if phase["label"] == "stock" else "0" * 40)
    assert len(data["comparisons"]) == len({row["id"] for row in data["comparisons"]}) == 15
    assert all(row["native_repeat_exact"] and row["native_prototype_exact"] and row["stock_native_prototype_exact"]
               and row["native_and_stock_exact"] and row["native_sha256"] == row["stock_sha256"]
               and row["mismatched_channel_samples"] == row["maximum_ulp"] == row["maximum_absolute_error"] == row["rms_error"] == 0
               for row in data["comparisons"])
    assert sum(not row["stock_float32_prototype_exact"] for row in data["comparisons"]) == 3
    assert [row["passed"] for row in data["prior_incomplete_attempts"]] == [False, False]
    integration = json.loads((root / "context-integration.json").read_bytes())
    calibration = integration["stock_baseline_calibration"]
    assert calibration["file"] == "matched-stock-observations.json"
    assert calibration["sha256"] == hashlib.sha256(raw).hexdigest()
    assert data["frozen_inputs_unchanged"] == 201 and data["remaining_unverified"]


def test_audio_browser_matrix_revision_decoder_and_exact_comparison(tmp_path):
    import argparse
    import base64
    import runpy
    import struct
    from scripts import native_build as build

    module = runpy.run_path(str(build.ROOT / "native/drafts/audio-dsp-math-v2/browser_matrix.py"), run_name="glint_browser_matrix_test")
    from pathlib import PureWindowsPath
    native = PureWindowsPath("D:/checkout/src/out/CamouFlowNative/chrome.exe")
    assert module["inside_compiled_checkout"](PureWindowsPath("D:/checkout/src/new-report"), native)
    assert not module["inside_compiled_checkout"](PureWindowsPath("D:/checkout/src-other/new-report"), native)
    assert not module["inside_compiled_checkout"](PureWindowsPath("D:/reports/new-report"), native)
    revision = "a" * 40
    version = "156.0.8078.36"
    normal = {"product": "Chrome/" + version, "revision": "@" + revision}
    dummy = {**normal, "revision": "@" + "0" * 40}
    module["validate_version"](normal, version, revision, dummy=False)
    module["validate_version"](dummy, version, revision, dummy=True)
    for observed, allow_dummy in ((dummy, False), (normal, True), (None, False),
                                  ({**normal, "product": "Chrome/155.0.0.0"}, False),
                                  ({**normal, "revision": "@" + "b" * 40}, False)):
        with pytest.raises(ValueError):
            module["validate_version"](observed, version, revision, dummy=allow_dummy)
    case = {"id": "owned", "frames": 256, "rate": 44100}
    channel = struct.pack("<256f", *([0.25] * 256))
    encoded = base64.b64encode(channel).decode("ascii")
    observed = {"id": "owned", "frames": 256, "sampleRate": 44100, "channelCount": 2,
                "eventSameBuffer": True, "closed": True, "samplesBase64": [encoded, encoded]}
    assert module["decode_capture"](observed, case) == channel * 2
    nonfinite = base64.b64encode(struct.pack("<256f", *([float("nan")] * 256))).decode("ascii")
    for changes in ({"eventSameBuffer": 1}, {"closed": False}, {"frames": 255}, {"sampleRate": 48000},
                    {"channelCount": 1}, {"samplesBase64": [encoded]}, {"samplesBase64": ["x", "x"]},
                    {"samplesBase64": ["!" + encoded[1:], encoded]}, {"samplesBase64": [nonfinite, encoded]}):
        with pytest.raises(ValueError):
            module["decode_capture"]({**observed, **changes}, case)
    zero, negative_zero = struct.pack("<f", 0), struct.pack("<f", -0.0)
    equal = module["compare"](zero, zero, zero)
    assert equal["native_and_stock_exact"] and equal["native_repeat_exact"]
    differing = module["compare"](zero, negative_zero, zero)
    assert differing["native_and_stock_exact"] is False and differing["mismatched_channel_samples"] == 1
    repeated = module["compare"](zero, zero, negative_zero)
    assert repeated["native_repeat_exact"] is repeated["native_and_stock_exact"] is False
    assert repeated["native_repeat_mismatched_channel_samples"] == 1
    for buffers in ((b"", b"", b""), (b"x", b"x", b"x"), (zero, zero * 2, zero)):
        with pytest.raises(ValueError):
            module["compare"](*buffers)
    forbidden = Path("C:/glint-forbidden-audio-matrix-output")
    existed = forbidden.exists()
    with pytest.raises(ValueError, match="D:"):
        module["verify"](argparse.Namespace(output=forbidden, native_executable=tmp_path / "native.exe",
                                           stock_executable=tmp_path / "stock.exe", allow_native_dummy_revision=False))
    assert forbidden.exists() is existed


def test_public_audio_browser_matrix_cli_evidence_is_bound_and_scoped():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    raw = (root / "browser-cli-observations.json").read_bytes()
    data = json.loads(raw)
    script = (root / data["script"]["file"]).read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in script and not script.startswith(b"\xef\xbb\xbf")
    assert hashlib.sha256(script).hexdigest() == data["script"]["sha256"]
    baseline_raw = (root / data["matched_baseline_file"]).read_bytes()
    baseline = json.loads(baseline_raw)
    assert hashlib.sha256(baseline_raw).hexdigest() == data["matched_baseline_sha256"]
    assert data["schema"] == 1 and data["platform"] == "win32" and data["passed"]
    assert data["measurement_complete"] and data["postguards_passed"]
    assert data["capture_count"] == 135 and data["case_count"] == 15
    assert data["native_matches_stock_all_cases"] and data["native_repeat_stable_all_cases"]
    assert data["all_case_hashes_match_prior_measurement"] and data["measured_input_count"] >= 200
    for field in ("native_core_sha256", "stock_core_sha256", "cases_sha256", "probe_sha256"):
        assert data[field] == baseline[field]
    assert data["native_receipt_sha256"] == baseline["candidate_build_receipt_sha256"]
    assert data["native_dummy_revision_acknowledged"] and data["fixture_profiles_are_fresh_per_phase"]
    for field in ("persistent_profile_restart_verified", "native_policy_enabled", "audio_math_included",
                  "same_build_flags_verified", "variant_device_cohort_verified", "privacy_admitted", "production_admitted"):
        assert data[field] is False
    assert [row["label"] for row in data["phases"]] == ["native-before", "stock", "native-after"]
    assert all(row["capture_count"] == 45 and row["resources_closed"] for row in data["phases"])
    controls = {row["name"]: row for row in data["negative_controls"]}
    assert len(controls) == data["negative_control_count"] == 5
    assert all(row["passed"] and row["exit_code"] == 1 for row in controls.values())
    assert controls["wrong-stock-role"]["browser_phase_started"] is False
    assert controls["dummy-without-acknowledgement"]["native_resources_closed"]
    assert controls["dummy-without-acknowledgement"]["audio_captures"] == 0
    assert controls["dummy-without-acknowledgement"]["stock_phase_started"] is False
    assert controls["existing-output-not-overwritten"]["existing_report_unchanged"]
    assert controls["non-D-output-refused"]["no_directory_created"] and data["remaining_unverified"]
    assert controls["source-checkout-output-refused"]["no_directory_created"]
    assert controls["source-checkout-output-refused"]["synthetic_source_layout"]
    assert controls["source-checkout-output-refused"]["browser_phase_started"] is False
    assert data["compiler_idle_required"] is True
    timeout = data["prior_timeout_attempt"]
    assert timeout["retained"] is True and timeout["passed"] is False
    assert timeout["timeout_increased"] is False and timeout["root_cause_proven"] is False


def test_public_156_runtime_suite_evidence_keeps_release_gates_separate():
    import json
    from scripts import native_build as build

    draft = build.ROOT / "native/drafts/upstream-156"
    raw = (draft / "runtime-suite-observations.json").read_bytes()
    data = json.loads(raw)
    baseline = json.loads((draft / "windows-runtime-observations.json").read_bytes())
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert data["passed"] and data["schema"] == 1 and data["candidate"] == "upstream-156"
    for field in ("candidate_manifest_sha256", "build_receipt_sha256", "runtime_core_sha256"):
        assert data[field] == baseline[field]
    assert [(g["name"], g["checks"]) for g in data["gates"]] == [
        ("runtime", 18), ("hardware", 9), ("webrtc", 7), ("automation", 55),
        ("fonts", 42), ("identity", 18), ("cdp", 6), ("combined", 5)]
    assert sum(g["checks"] for g in data["gates"]) == data["check_count"] == 160
    for row in [data, *data["gates"]]:
        digest = row.get("report_sha256", row.get("suite_report_sha256"))
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
        assert row["passed"] is True
    for field in ("privacy_admitted", "release_admitted", "production_admitted",
                  "third_party_antibot_verified", "audio_math_included"):
        assert data[field] is False
    handoff = baseline["native_identity_handoff"]
    assert handoff["tests"] == 15 and handoff["passed"] and handoff["postguards_passed"]
    assert handoff["baseline_browser_code_unchanged"] and data["remaining_unverified"]
    delivery = baseline["native_delivery_units"]
    assert delivery["tests"] == 34 and delivery["passed"] and delivery["postguards_passed"]
    assert delivery["baseline_browser_code_unchanged"] and delivery["native_source_changed"] is False
    assert delivery["old_draft_comparison_replaced"] and delivery["complete_ordered_chain_guard_retained"]
    assert len(delivery["delivery_source_sha256"]) == 10 and len(delivery["verifier_sha256"]) == 64


def test_audio_fidelity_stock_fixture_preserves_exact_signals_and_rejects_faults():
    import hashlib
    import json
    import struct
    from scripts import native_build as build

    draft = build.ROOT / "native/drafts/audio-dsp-math-v2"
    raw = (draft / "audio-fidelity-observations.json").read_bytes()
    data = json.loads(raw)
    probe = (draft / data["probe"]["file"]).read_bytes()
    assert b"\r" not in raw and b"\r" not in probe
    assert not raw.startswith(b"\xef\xbb\xbf") and not probe.startswith(b"\xef\xbb\xbf")
    assert hashlib.sha256(probe).hexdigest() == data["probe"]["sha256"]
    stock = json.loads((draft.parent / "upstream-156/stock-control-observations.json").read_bytes())
    assert data["stock_core_sha256"] == stock["stock_core_sha256"]
    assert data["browser_get_version"]["revision"] == "@" + stock["target_revision"]
    assert data["passed"] and data["baseline_runs_bit_exact"] and data["resources_closed"] and data["postguards_passed"]
    assert data["baseline_runs"] == 2 and data["renders_per_run"] == 54 and data["repetitions_per_case"] == 3
    kinds = {"silence", "identity", "half-gain", "impulse", "stereo", "constant-positive",
             "constant-negative", "oscillator", "compressor"}
    assert {(row["kind"], row["rate"]) for row in data["cases"]} == {(kind, rate) for kind in kinds for rate in (44100, 48000)}
    assert len(data["cases"]) == 18
    for row in data["cases"]:
        assert row["frames"] == 512 and row["channelCount"] == 2 and len(row["channels"]) == 2
        for channel, observed in enumerate(row["channels"]):
            assert all(observed[key] for key in ("finite", "repeatedExact", "copiedExact", "segmentedExact"))
            kind = row["kind"]
            if kind in ("oscillator", "compressor"):
                assert observed["expectedExact"] is None and observed["nonzero"]
                continue
            values = [((index % 17) - 8) / 32 for index in range(512)]
            if kind == "silence":
                values = [0.0] * 512
            elif kind == "half-gain":
                values = [value / 2 for value in values]
            elif kind == "impulse":
                values = [0.5] + [0.0] * 511
            elif kind == "stereo":
                values = [0.25 if channel == 0 else -0.125] * 512
            elif kind in ("constant-positive", "constant-negative"):
                values = [0.25 if kind == "constant-positive" else -0.25] * 512
            assert observed["expectedExact"] is True
            assert hashlib.sha256(struct.pack("<512f", *values)).hexdigest() == observed["sha256"]
    controls = {row["name"]: row for row in data["negative_controls"]}
    assert {name: row["rejected_rows"] for name, row in controls.items()} == {
        "wrong-constant-reference": 12, "wrong-segment-offset": 48,
        "wrong-mutation-offset": 54, "unstable-oscillator": 0}
    assert all(row["passed"] for row in controls.values())
    assert controls["unstable-oscillator"]["repeat_stable"] is False
    for field in ("glint_policy_execution_verified", "audio_math_execution_verified", "device_cohort_verified",
                  "privacy_admitted", "production_admitted"):
        assert data[field] is False
    assert data["remaining_unverified"]


def test_native_156_baseline_manifest_checkpoint_preserves_exact_public_patch_inputs():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-156"
    raw = (root / "checkpoints/001-065.json").read_bytes()
    manifest = json.loads(raw)
    baseline = json.loads((root / "windows-runtime-observations.json").read_bytes())
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert hashlib.sha256(raw).hexdigest() == baseline["candidate_manifest_sha256"]
    assert len(manifest["patches"]) == baseline["compiled_patch_count"] == 65
    assert manifest["target_revision"] == baseline["target_revision"]
    assert manifest["target_version"] == baseline["target_version"]
    for row in manifest["patches"]:
        assert hashlib.sha256((root / "patches" / row["file"]).read_bytes()).hexdigest() == row["sha256"]
    candidate = build.load_candidate("upstream-156")
    assert candidate["manifest"]["patches"][:65] == manifest["patches"]
    for name in ("audio-dsp-math-v2/context-integration.json", "gpu-transport/optional-query-fixture-observations.json"):
        path = root.parent / name
        descriptor = json.loads(path.read_bytes())
        assert (path.parent / descriptor["required_base_manifest"]).resolve() == root / "checkpoints/001-065.json"
        assert descriptor["required_base_manifest_sha256"] == hashlib.sha256(raw).hexdigest()


def test_selected_gpu_fixture_preserves_baseline_and_requires_negative_case():
    import hashlib
    import json
    from scripts import native_build as build
    from scripts.verify_native_privacy_units import required_tests

    candidate = build.load_candidate("upstream-156")
    root = candidate["directory"]
    checkpoint = json.loads((root / "checkpoints/001-065.json").read_bytes())
    assert candidate["manifest"]["patches"][:65] == checkpoint["patches"]
    row = candidate["manifest"]["patches"][65]
    assert row["file"] == "0066-native-gpu-optional-query-fixture.patch"
    content = (root / "patches" / row["file"]).read_bytes()
    original = (root.parent / "gpu-transport/gpu_readback_metadata_optional_query_fixture.patch").read_bytes()
    assert content == original and hashlib.sha256(content).hexdigest() == row["sha256"]
    assert required_tests("gpu-metadata")["GlintPassthroughWithoutTextureQueryTest"] == {
        "TextureAttachmentRemainsUnavailableWithoutNativeQueryExtension"}
    assert sum(map(len, required_tests("gpu-metadata").values())) == 34


def test_baseline_native_batch_keeps_gpu_failure_and_all_later_results():
    import hashlib
    import json
    from scripts import native_build as build
    from scripts.verify_native_privacy_units import SUPPORTED_TARGETS

    root = build.ROOT / "native/drafts/upstream-156"
    data = json.loads((root / "native-batch65-observations.json").read_bytes())
    assert hashlib.sha256((root / data["required_base_manifest"]).read_bytes()).hexdigest() == data["candidate_manifest_sha256"]
    assert data["passed"] is False and data["postguards_passed"] is True
    assert data["build_invocations"] == 1 and data["jobs"] == 4
    assert [row["target"] for row in data["targets"]] == [target for target in SUPPORTED_TARGETS if target != "audio-math"]
    assert [row["target"] for row in data["targets"] if not row["native_cases_passed"]] == ["gpu-metadata"]
    gpu = next(row for row in data["targets"] if row["target"] == "gpu-metadata")
    assert gpu["tests"] == 33 and gpu["failures"] == 6 and gpu["returncode"] == 1
    assert all(row["failures"] == 0 and row["returncode"] == 0 for row in data["targets"] if row is not gpu)
    baseline = json.loads((root / "windows-runtime-observations.json").read_bytes())
    assert data["runtime_core_sha256_measured"] == baseline["runtime_core_sha256"]
    assert data["build_receipt_sha256"] == baseline["build_receipt_sha256"]
    assert data["browser_runtime_verified"] is data["privacy_admitted"] is data["production_admitted"] is False


def test_native_66_batch_binds_frozen_manifest_and_complete_native_filters():
    import hashlib
    import json
    from scripts import native_build as build
    from scripts.verify_native_privacy_units import SUPPORTED_TARGETS, required_tests

    candidate = build.load_candidate("upstream-156")
    root = candidate["directory"]
    data = json.loads((root / "native-batch66-observations.json").read_bytes())
    raw = (root / data["required_manifest"]).read_bytes()
    manifest = json.loads(raw)
    assert data["candidate_manifest_sha256"] == hashlib.sha256(raw).hexdigest()
    assert len(manifest["patches"]) == data["compiled_patch_count"] == 66
    assert candidate["manifest"]["patches"][:66] == manifest["patches"]
    for row in manifest["patches"]:
        assert hashlib.sha256((root / "patches" / row["file"]).read_bytes()).hexdigest() == row["sha256"]
    assert data["passed"] and data["postguards_passed"] and data["actual_sync_hooks_completed"]
    assert data["build_invocations"] == 1 and data["jobs"] == 4
    assert [row["target"] for row in data["targets"]] == [target for target in SUPPORTED_TARGETS if target != "audio-math"]
    for row in data["targets"]:
        assert row["native_cases_passed"] and row["returncode"] == 0
        assert row["tests"] == sum(map(len, required_tests(row["target"]).values()))
    assert next(row for row in data["targets"] if row["target"] == "gpu-metadata")["tests"] == 34
    baseline = json.loads((root / "windows-runtime-observations.json").read_bytes())
    assert data["browser_core_unchanged_from_baseline65"]
    assert data["runtime_core_sha256_measured"] == baseline["runtime_core_sha256"]
    assert data["build_receipt_sha256"] != baseline["build_receipt_sha256"]
    assert data["unchanged_source_mtimes_restored"] == 256
    assert data["changed_source_files"] == ["gpu/command_buffer/service/gles2_cmd_decoder_passthrough_unittest_framebuffers.cc"]
    assert data["browser_runtime_verified"] is data["privacy_admitted"] is data["production_admitted"] is False


def test_canonical_app66_evidence_keeps_audio_failure_outside_admission():
    import hashlib
    import json
    import re
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-156"
    data = json.loads((root / "canonical-app66-observations.json").read_bytes())
    assert data["schema"] == 1 and data["passed"] is True
    assert hashlib.sha256((root / data["required_manifest"]).read_bytes()).hexdigest() == data["candidate_manifest_sha256"]
    native = json.loads((root / "native-batch66-observations.json").read_bytes())
    assert data["build_receipt_sha256"] == native["build_receipt_sha256"]
    assert data["runtime_core_sha256"] == native["runtime_core_sha256_measured"]
    assert re.fullmatch(r"[0-9a-f]{40}", data["verified_code_commit"])
    assert len(data["source_code_sha256"]) == 6
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in data["source_code_sha256"].values())
    assert data["full_python"]["passed"] == 3862 and data["full_python"]["skipped"] == 1
    assert data["full_python"]["postguards_passed"]
    payload = data["development_payload"]
    assert payload["raw_browser_checks"] == payload["installed_browser_checks"] == 160
    assert payload["activation_performed"] is False
    browser = data["canonical_browser"]
    assert browser["installed_lifecycle_checks"] == 18 and browser["worker_startup_checks"] == 60
    assert browser["profile_identity_phases"] == browser["partitioned_privacy_phases"] == 12
    assert browser["nested_canvas_cases_per_mode"] == 24 and browser["source_postguards_passed"]
    audio = data["audio_v1_fidelity"]
    assert audio["passed"] is False and audio["baseline_passed"] == 54
    assert audio["protected_passed"] == 42 and audio["protected_failed"] == 12
    assert audio["failed_graphs"] == ["half-gain", "identity"]
    assert audio["repeat_stable"] and audio["mutation_controls_passed"] and audio["resources_closed"]
    assert audio["source_postguards_passed"]
    assert data["privacy_admitted"] is data["production_admitted"] is data["device_cohort_verified"] is False
    assert data["compatible_rollback_verified"] is False
    for relative in ("profile-version/windows-profile-version-guard.json", "runtime-verifier/owned-runtime-evidence-retention.json"):
        descriptor = root.parent / relative
        value = json.loads(descriptor.read_bytes())
        assert value["canonical_runtime_verified"] is True
        assert (descriptor.parent / value["canonical_verification_record"]).resolve() == root / "canonical-app66-observations.json"


def test_gpu_optional_query_fixture_evidence_keeps_canonical_admission_separate():
    import hashlib
    import json
    from scripts import native_build as build
    from scripts.verify_native_privacy_units import required_tests

    draft = build.ROOT / "native/drafts/gpu-transport"
    raw = (draft / "optional-query-fixture-observations.json").read_bytes()
    data = json.loads(raw)
    patch = (draft / data["patch"]["file"]).read_bytes()
    assert b"\r" not in raw and b"\r" not in patch
    assert not raw.startswith(b"\xef\xbb\xbf") and not patch.startswith(b"\xef\xbb\xbf")
    assert hashlib.sha256(patch).hexdigest() == data["patch"]["sha256"]
    assert hashlib.sha256((draft / data["required_base_manifest"]).read_bytes()).hexdigest() == data["required_base_manifest_sha256"]
    text = patch.decode("utf-8")
    assert text.count("diff --git ") == 1
    assert data["source_file"] == "gpu/command_buffer/service/gles2_cmd_decoder_passthrough_unittest_framebuffers.cc"
    assert text.startswith("diff --git a/" + data["source_file"] + " b/" + data["source_file"] + "\n")
    added = "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    assert 'glRequestExtensionANGLEFn(' in added and 'ReinitializeDynamicBindings()' in added
    assert 'ASSERT_TRUE(context->HasExtension("GL_ANGLE_get_tex_level_parameter"))' in added
    assert "GlintPassthroughAttachmentTest(false)" in added and "EXPECT_FALSE(QueryAttachment())" in added
    assert "GTEST_SKIP" not in added and "DISABLED_" not in added
    expected = {suite + "." + name for suite, names in required_tests("gpu-metadata").items() for name in names}
    expected.add(data["negative_case"])
    assert data["negative_case"] == "GlintPassthroughWithoutTextureQueryTest.TextureAttachmentRemainsUnavailableWithoutNativeQueryExtension"
    assert len(data["executed_tests"]) == len(expected) == data["native_test_count"] == 34
    assert set(data["executed_tests"]) == expected
    assert data["previous_native_test_count"] == 33 and data["previous_failure_count"] == 6
    assert data["passed"] and data["source_replay_passed"] and data["isolated_fixture_compiled"]
    assert data["isolated_native_tests_passed"] and data["postguards_passed"] and data["frozen_inputs_unchanged"] == 201
    baseline = json.loads((draft.parent / "upstream-156/windows-runtime-observations.json").read_bytes())
    assert data["baseline_runtime_core_sha256"] == baseline["runtime_core_sha256"]
    for field in ("selected_in_manifest", "canonical_verifier_enabled", "production_code_changed", "canonical_checkout_changed",
                  "browser_runtime_admitted", "packaging_admitted", "production_admitted"):
        assert data[field] is False
    assert data["remaining_unverified"]


def test_first_156_audio_calibration_does_not_admit_the_math_variant():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-156"
    data = json.loads((root / "windows-runtime-observations.json").read_text(encoding="utf-8"))
    audio = data["audio_native_baseline"]
    assert audio["passed"] and audio["all_native156_prototype_bit_exact"]
    assert audio["capture_count"] == audio["case_count"] * audio["repetitions_per_case"] == 45
    assert audio["case_count"] == len(audio["cases"]) == 15
    assert audio["matched_stock156_verified"] is audio["float32_backend_runtime_verified"] is False
    assert audio["resources_closed"] and audio["postguards_passed"]
    assert hashlib.sha256((root / audio["probe_file"]).read_bytes()).hexdigest() == audio["probe_sha256"]
    cases_raw = (root / audio["cases_file"]).read_bytes()
    assert hashlib.sha256(cases_raw).hexdigest() == audio["cases_sha256"]
    cases = {row["id"]: row for row in json.loads(cases_raw)["cases"]}
    assert {row["id"] for row in audio["cases"]} == set(cases)
    for row in audio["cases"]:
        assert row["raw_sha256"] == row["reference_sha256"]
        assert row["frames"] == cases[row["id"]]["frames"]
        assert row["sampleRate"] == cases[row["id"]]["rate"] and row["channelCount"] == 2


def test_156_compiled_branding_record_matches_the_project_logo():
    import hashlib
    import json
    from scripts import native_build as build
    from scripts.verify_native_branding import icon_images

    root = build.ROOT / "native/drafts/upstream-156"
    data = json.loads((root / "windows-runtime-observations.json").read_text(encoding="utf-8"))
    branding = data["compiled_branding"]
    logo = (root / branding["logo_file"]).resolve()
    assert logo == build.ROOT / "logo.ico"
    assert hashlib.sha256(logo.read_bytes()).hexdigest() == branding["logo_sha256"]
    assert branding["passed"] and branding["resources_closed"] and branding["postguards_passed"]
    assert branding["resource_pack_postguards_passed"] and branding["resource_pack_count"] >= 4
    assert branding["browser_version"] == data["target_version"]
    assert branding["version_page_product"].strip() == "Glint"
    assert set(branding["icons"]) == {"IDR_MAINFRAME", "IDR_X001_APP_LIST"}
    assert all(images == icon_images(logo.read_bytes()) for images in branding["icons"].values())
    assert set(branding["product_names"]) == {"chrome.exe", "chrome.dll"}
    assert all(names and set(names) == {"Glint"} for names in branding["product_names"].values())
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert branding["branding_patches"] == {row["file"]: row["sha256"] for row in manifest["patches"]
                                            if row["file"].startswith(("0060-", "0061-"))}
    assert set(branding["required_resource_pack_sha256"]) == {
        "resources.pak", "chrome_100_percent.pak", "chrome_200_percent.pak", "locales/en-US.pak"}
    assert data["release_admitted"] is data["production_admitted"] is False


def test_runtime_retention_preserves_original_failure_scope():
    import hashlib
    import json
    from scripts import native_build as build
    from scripts.package_native_windows import REQUIRED_RUNTIME_CHECKS

    root = build.ROOT / "native/drafts/runtime-verifier"
    raw = (root / "owned-runtime-evidence-retention.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["schema"] == 1 and data["source_application_passed"]
    assert data["applied_to_canonical_verifier"] is True
    for field in ("browser_close_timeout_resolved", "timeout_changed",
                  "forced_termination", "release_admitted", "production_admitted"):
        assert data[field] is False
    source = build.ROOT / data["source_file"]
    normalized = source.read_text(encoding="utf-8-sig").encode("utf-8")
    assert hashlib.sha256(normalized).hexdigest() == data["source_after_sha256"]
    patch = (root / data["patch"]["file"]).read_bytes()
    assert hashlib.sha256(patch).hexdigest() == data["patch"]["sha256"]
    observations = json.loads((build.ROOT / "native/drafts/upstream-156/windows-runtime-observations.json").read_text(encoding="utf-8"))
    assert data["captured_source_raw_sha256"] == observations["source_snapshot_sha256"][data["source_file"]]
    controls = {row["case"]: row for row in data["windows_held_file_controls"]}
    assert len(controls) == 5 and all(row["passed"] for row in controls.values())
    assert controls["baseline-locked-file"]["error_type"] == "NotADirectoryError"
    assert controls["candidate-locked-file"]["error_type"] == "TimeoutError"
    assert controls["candidate-log-error-during-failure"]["error_type"] == "TimeoutError"
    assert controls["candidate-success"]["exit_code"] == 0
    assert controls["candidate-cleanup-error"]["exit_code"] == 1
    regression = data["isolated_browser_regression"]
    assert regression["passed"] and regression["version"] == "156.0.8078.36"
    assert len(regression["checks"]) == 18 and REQUIRED_RUNTIME_CHECKS.issubset(regression["checks"])
    assert regression["runtime_core_sha256"] == observations["runtime_core_sha256"]
    assert data["frozen_inputs_unchanged"] == 201 and data["application_gate"]


def test_windows_profile_version_guard_binds_runtime_and_readonly_controls():
    import ast
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/profile-version"
    raw = (root / "windows-profile-version-guard.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["schema"] == 1 and data["platform"] == "win32"
    assert data["applied_to_canonical_runtime"] is True
    for field in ("other_platforms_implemented", "production_admitted",
                  "profile_data_rewritten_by_guard"):
        assert data[field] is False
    assert data["source_application_passed"] and data["no_fallback"]
    runtime = build.ROOT / data["source_file"]
    normalized = runtime.read_text(encoding="utf-8-sig").encode("utf-8")
    assert hashlib.sha256(normalized).hexdigest() == data["source_after_sha256"]
    assert (build.ROOT / "app/core/native/profile_version.py").read_bytes() == (root / data["guard"]["file"]).read_bytes()
    for field in ("guard", "patch"):
        artifact = (root / data[field]["file"]).read_bytes()
        assert hashlib.sha256(artifact).hexdigest() == data[field]["sha256"]
        assert b"\r" not in artifact and not artifact.startswith(b"\xef\xbb\xbf")
    ast.parse((root / data["guard"]["file"]).read_text(encoding="utf-8"))
    controls = data["marker_and_mocked_launch_controls"]
    assert len(controls) == data["control_count"] == len({row["name"] for row in controls}) == 22
    assert all(row["passed"] for row in controls)
    assert {"blocked-before-identity-and-driver", "invalid-pe-version", "missing-marker-existing-data",
            "local-state-without-marker", "invalid-utf8", "directory-marker"}.issubset({row["name"] for row in controls})
    assert data["measured_pe_versions"] == {"reviewed148": [148, 0, 7778, 96], "candidate156": [156, 0, 8078, 36]}
    upgrade = data["real_owned_upgrade"]
    assert upgrade["passed"] and upgrade["real_upgrade_five_stores_preserved"]
    assert upgrade["owned_identity_payload_unchanged"] and upgrade["rejected_profile_files_unchanged"]
    assert upgrade["downgrade_rejected_before_identity_and_driver"]
    assert upgrade["older_browser_started_on_upgraded_profile"] is False
    assert upgrade["resources_closed"] and upgrade["postguards_passed"]
    assert upgrade["after_upgrade_storage"] == {"cookie": "owned=owned-upgrade-control",
        "local": "owned-upgrade-control", "indexed": "owned-upgrade-control", "cached": "owned-upgrade-control", "workers": 1}
    lifecycle = data["isolated_extended_lifecycle"]
    assert lifecycle["passed"] and lifecycle["postguards_passed"] and lifecycle["exit_code"] == 0
    assert lifecycle["canonical_runtime_changed"] is lifecycle["canonical_verifier_changed"] is False
    assert lifecycle["production_admitted"] is False and lifecycle["applied_to_cli_child_processes"]
    assert lifecycle["guard_sha256"] == data["guard"]["sha256"]
    assert lifecycle["runtime_sha256"] == data["source_after_sha256"]
    assert len(lifecycle["checks"]) == len(set(lifecycle["checks"])) == lifecycle["check_count"] == 18
    assert {"native-profile-backup-restore-storage-and-engine-isolation",
            "cancelled-driver-start-cleans-pending-operation-and-restarts-profile",
            "existing-browser-interface-and-scenario-executor"}.issubset(lifecycle["checks"])
    assert data["frozen_inputs_unchanged"] == 201 and data["application_gate"] and data["remaining_unverified"]


def test_windows_resource_reader_draft_preserves_readonly_scope():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/resources"
    raw = (root / "observations.json").read_bytes()
    data = json.loads(raw)
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    reader = (root / data["reader"]["file"]).read_bytes()
    assert hashlib.sha256(reader).hexdigest() == data["reader"]["sha256"]
    assert b"\r" not in reader and not reader.startswith(b"\xef\xbb\xbf")
    assert data["schema"] == 1 and data["platform"] == "win32" and data["passed"]
    assert len(data["controls"]) == data["control_count"] == 24
    assert len({row["name"] for row in data["controls"]}) == 24
    assert all(row["passed"] for row in data["controls"])
    for field in ("manager_integrated", "production_admitted", "memory_limit_changed", "forced_termination_added"):
        assert data[field] is False
    assert data["postguards_passed"] and data["owned_children_exited"] and data["glint_resources_closed"]
    assert data["frozen_inputs_unchanged"] == 201 and data["remaining_unverified"]
    observed = data["glint_observation"]
    assert observed["passed"] and observed["browser_version"] == "156.0.8078.36"
    assert observed["process_count"] == 7 and observed["os_parent_chain_checked"] and observed["creation_identity_checked"]
    assert observed["summed_working_set_bytes"] > observed["root_working_set_bytes"] > 0
    assert observed["summed_private_commit_bytes"] > 0
    assert observed["summed_working_set_is_unique_physical_ram"] is False
    assert observed["all_browser_processes_over_lifetime_accounted"] is False and observed["not_a_performance_benchmark"]
    baseline = json.loads((build.ROOT / "native/drafts/upstream-156/windows-runtime-observations.json").read_text())
    assert data["runtime_core_sha256"] == baseline["runtime_core_sha256"]
    controls = data["owned_child_observations"]
    assert controls["private_commit_increase_bytes"] >= 16 * 1024 * 1024
    assert controls["handle_count_stable"] and controls["cpu_interval"]["cpu_seconds"] > 0
    assert data["initial_control_failure"]["retained"] and data["initial_control_failure"]["reader_defect"] is False


def test_windows_resource_cpu_intervals_and_input_validation(monkeypatch):
    from dataclasses import replace
    import importlib.util
    from types import SimpleNamespace
    from scripts import native_build as build

    path = build.ROOT / "native/drafts/resources/windows_process_resources.py"
    spec = importlib.util.spec_from_file_location("glint_resource_test", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    first = module.ProcessSample(10, 100, 1_000_000_000, 0, 0, 1024, 2048, 3072)
    second = replace(first, measured_ns=3_000_000_000, kernel_100ns=10_000_000, user_100ns=20_000_000)
    assert module.cpu_interval(first, second) == {"elapsed_seconds": 2.0, "cpu_seconds": 3.0, "mean_cpu_cores": 1.5}
    assert module.cpu_interval(first, replace(second, kernel_100ns=0, user_100ns=0))["mean_cpu_cores"] == 0
    for candidate in (replace(second, pid=11), replace(second, created_100ns=101), first,
                      replace(second, measured_ns=first.measured_ns - 1)):
        with pytest.raises(ValueError):
            module.cpu_interval(first, candidate)
    for bad in (True, -1, 2**64):
        with pytest.raises(ValueError):
            replace(first, private_commit_bytes=bad)
    for field in ("kernel_100ns", "user_100ns"):
        with pytest.raises(ValueError):
            module.cpu_interval(replace(first, **{field: 1}), replace(second, **{field: 0}))
    uninitialized = object.__new__(module.WindowsProcessReader)
    for bad in (True, 0, -1, 2**32):
        with pytest.raises(ValueError):
            uninitialized.read(bad)
    with pytest.raises(ValueError):
        uninitialized.read(10, expected_created_100ns=True)
    if sys.platform == "win32":
        import os
        reader = module.WindowsProcessReader()
        sample = reader.read(os.getpid())
        repeated = reader.read(os.getpid(), expected_created_100ns=sample.created_100ns)
        assert repeated.pid == sample.pid == os.getpid()
        assert sample.working_set_bytes > 0 and sample.private_commit_bytes > 0
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="linux"))
    with pytest.raises(OSError, match="not implemented"):
        module.WindowsProcessReader()


def test_windows_resource_tree_selection_and_intervals_are_identity_bound():
    from dataclasses import replace
    from native.drafts.resources import windows_process_tree as tree

    node = tree.ProcessNode
    rows = (node(1, 0, "root"), node(2, 1, "child"), node(3, 2, "grandchild"), node(9, 0, "other"))
    assert tree.descendants(rows, 1) == rows[:3]
    assert tree.descendants(tuple(reversed(rows)), 1) == rows[:3]
    for invalid in (rows + (rows[0],), (node(1, 2, "root"), node(2, 1, "cycle")), (None,)):
        with pytest.raises(ValueError):
            tree.descendants(invalid, 1)
    with pytest.raises(ProcessLookupError):
        tree.descendants(rows, 8)
    with pytest.raises(ValueError, match="bound"):
        tree.descendants((rows[0], *(node(pid, 1, "child") for pid in range(2, tree.MAX_TREE_PROCESSES + 2))), 1)
    with pytest.raises(ValueError):
        node(True, 0, "root")
    with pytest.raises(ValueError):
        node(1, -1, "root")
    with pytest.raises(ValueError):
        node(1, 0, "bad\0image")
    sample = tree.ProcessSample(1, 100, 1_000_000_000, 0, 0, 1024, 2048, 3072)
    child = replace(sample, pid=2, created_100ns=200)
    before = tree.ProcessTreeSample(1, 100, 1, 1_000_000_000, (sample, child))
    after = tree.ProcessTreeSample(1, 100, 2_000_000_000, 3_000_000_000,
        tuple(replace(row, measured_ns=3_000_000_000, user_100ns=10_000_000) for row in (sample, child)))
    assert before.summed_working_set_bytes == 2048 and before.summed_private_commit_bytes == 6144
    assert tree.tree_cpu_interval(before, after) == {"elapsed_seconds": 2.0, "cpu_seconds": 2.0, "mean_cpu_cores": 1.0}
    for invalid in (replace(after, processes=(after.processes[0],)),
                    replace(after, processes=(after.processes[0], replace(after.processes[1], created_100ns=201))),
                    tree.ProcessTreeSample(2, 200, 2_000_000_000, 3_000_000_000, (after.processes[1],)), before):
        with pytest.raises(ValueError):
            tree.tree_cpu_interval(before, invalid)
    for changes in ({"root_pid": []}, {"root_created_100ns": True}, {"processes": ()},
                    {"processes": (sample, sample)}, {"capture_started_ns": 0}, {"capture_started_ns": 2_000_000_000},
                    {"processes": (sample, replace(child, created_100ns=99))}):
        with pytest.raises(ValueError):
            replace(before, **changes)


def test_windows_resource_tree_capture_refuses_churn_reuse_and_partial_samples():
    from dataclasses import replace
    import time
    from native.drafts.resources import windows_process_tree as tree

    rows = (tree.ProcessNode(1, 0, "root"), tree.ProcessNode(2, 1, "child"))
    anchor = tree.ProcessSample(1, 100, time.monotonic_ns(), 0, 0, 1024, 2048, 3072)

    class Model(tree.WindowsProcessTreeReader):
        def __init__(self, after=None, *, before=rows, root_created=100, child_created=200, reused_child=False, denied_child=False):
            self.snapshots = iter((before, before if after is None else after))
            self.created = {1: root_created, 2: child_created, 3: 300}
            self.reads = {}
            self.reused_child = reused_child
            self.denied_child = denied_child

        def snapshot(self):
            return next(self.snapshots)

        def read(self, pid, *, expected_created_100ns=None):
            self.reads[pid] = self.reads.get(pid, 0) + 1
            if pid == 2 and self.denied_child:
                raise PermissionError("Owned child query denied")
            created = self.created[pid] + int(pid == 2 and self.reused_child and self.reads[pid] > 1)
            if expected_created_100ns is not None and created != expected_created_100ns:
                raise ValueError("Process identity changed")
            return replace(anchor, pid=pid, created_100ns=created, measured_ns=time.monotonic_ns())

    stable = Model()
    measured = stable.read_tree(anchor)
    assert len(measured.processes) == 2 and stable.reads == {1: 2, 2: 2}
    assert measured.summed_working_set_bytes == 2048
    for model in (Model(root_created=101), Model(child_created=99), Model(reused_child=True),
                  Model(after=rows[:1]), Model(after=rows + (tree.ProcessNode(3, 1, "new"),)),
                  Model(after=(rows[0], replace(rows[1], image="changed"))),
                  Model(before=rows + (tree.ProcessNode(3, 2, "grandchild"),),
                        after=rows + (tree.ProcessNode(3, 1, "grandchild"),))):
        with pytest.raises(ValueError):
            model.read_tree(anchor)
    with pytest.raises(ProcessLookupError):
        Model(after=()).read_tree(anchor)
    with pytest.raises(PermissionError):
        Model(denied_child=True).read_tree(anchor)
    with pytest.raises(ValueError):
        Model().read_tree(None)


def test_windows_resource_tree_observations_do_not_admit_watchdog_or_limits():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/resources"
    raw = (root / "tree-observations.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["schema"] == 1 and data["passed"] and data["platform"] == "win32"
    for name, digest in data["source_sha256"].items():
        source = (root / name).read_bytes()
        assert hashlib.sha256(source).hexdigest() == digest
        assert b"\r" not in source and not source.startswith(b"\xef\xbb\xbf")
    primitive = json.loads((root / "observations.json").read_text())
    assert data["source_sha256"][primitive["reader"]["file"]] == primitive["reader"]["sha256"]
    assert len(data["controls"]) == data["control_count"] == 18
    assert len({row["name"] for row in data["controls"]}) == 18 and all(row["passed"] for row in data["controls"])
    assert data["postguards_passed"] and data["owned_children_exited"] and data["glint_resources_closed"]
    for field in ("manager_integrated", "production_admitted", "memory_limit_changed", "forced_termination_added",
                  "atomic_process_snapshot", "complete_lifetime_accounting", "summed_working_set_is_unique_physical_ram"):
        assert data[field] is False
    assert data["frozen_inputs_unchanged"] == 201 and data["remaining_unverified"]
    assert len(data["glint_observations"]) == 2
    assert all(row["process_count"] >= 7 and row["browser_version"] == "156.0.8078.36"
               and row["root_identity_from_owned_cdp"] and row["snapshot_membership_stable"]
               and row["not_an_atomic_or_lifetime_snapshot"] and row["not_a_performance_benchmark"]
               and row["cpu_interval"]["cpu_seconds"] >= 0 for row in data["glint_observations"])
    baseline = json.loads((build.ROOT / "native/drafts/upstream-156/windows-runtime-observations.json").read_text())
    assert data["runtime_core_sha256"] == baseline["runtime_core_sha256"]


def test_audio_math_context_draft_binds_source_only_integration():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    raw = (root / "context-integration.json").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    descriptor = json.loads(raw)
    assert descriptor["schema"] == 1
    base = root / descriptor["required_base_manifest"]
    assert hashlib.sha256(base.read_bytes()).hexdigest() == descriptor["required_base_manifest_sha256"]
    manifest = json.loads(base.read_bytes())
    assert len(manifest["patches"]) == 65
    assert descriptor["target_revision"] == manifest["target_revision"]
    assert descriptor["target_version"] == manifest["target_version"] == "156.0.8078.36"
    for field in ("selected_in_manifest", "compiled", "compiled_browser", "native_tests_executed",
                  "runtime_verified", "variant_device_cohort_verified", "production_admitted"):
        assert descriptor[field] is False
    patch = descriptor["patch"]
    body = (root / patch["file"]).read_bytes()
    assert hashlib.sha256(body).hexdigest() == patch["sha256"]
    assert b"\r" not in body and not body.startswith(b"\xef\xbb\xbf")
    assert not any(Path(row["file"]).name == patch["file"] for row in manifest["patches"])
    extra = descriptor["extra_pristine_sources"]
    assert len(extra) == len({row["path"] for row in extra}) == 9
    assert not {row["path"] for row in extra} & {row["path"] for row in manifest["source_files"]}
    evidence = descriptor["source_application"]
    assert evidence["passed"] and evidence["patch_count"] == 66
    assert evidence["pristine_inputs"] == len(extra) + len(manifest["source_files"]) == 194
    assert evidence["frozen_build_inputs_unchanged"] == 201
    assert evidence["source_invariants"] == {
        "gpu_commands": {"preserved": 321, "appended": 577}, "grit_structure_preserved": True}
    assert len(descriptor["source_files"]) == 16 and descriptor["remaining_unverified"]
    objects = descriptor["isolated_object_compilation"]
    assert objects["passed"] and objects["postguards_passed"]
    assert objects["compiled_objects"] == len(objects["objects"]) == 7
    assert objects["serial_compilers"] == 1 and objects["priority"] == "below-normal"
    assert objects["original_flags_preserved"] is True
    for field in ("official_gn_build", "linked", "native_tests_executed"):
        assert objects[field] is False
    assert len(objects["compiler_sha256"]) == 64
    assert len({row["source"] for row in objects["objects"]}) == 7
    assert all(row["exit_code"] == 0 and row["object_created"]
               and len(row["object_sha256"]) == 64 for row in objects["objects"])
    failed = objects["initial_test_object_failure"]
    assert failed["exit_code"] == 1 and failed["compiled_production_objects"] == 6
    assert failed["failed_evidence_retained"] and failed["patch_sha256"] != patch["sha256"]
    assert failed["source"].endswith("/offline_audio_context_test.cc")


def test_audio_math_context_draft_separates_caching_and_readback_pipelines():
    import hashlib
    import hmac
    import json
    import re
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    data = json.loads((root / "context-integration.json").read_text(encoding="utf-8"))
    patch = (root / data["patch"]["file"]).read_text(encoding="utf-8")
    added = "\n".join(line[1:] for line in patch.splitlines()
                      if line.startswith("+") and not line.startswith("+++"))
    policy = data["policy"]
    assert policy["enabled_by_default"] is False and policy["captured_once_per_context"]
    assert policy["math_and_readback_farbling_mutually_exclusive"]
    assert policy["backends"] == ["native", "float32"]
    assert "BASE_FEATURE(kGlintAudioMathCandidate, base::FEATURE_DISABLED_BY_DEFAULT);" in added
    assert policy["capture_time"] == "BaseAudioContext construction"
    assert "glint_audio_math_pipeline_(CaptureGlintAudioMathPipeline(window))" in added
    assert re.search(r"const glint::candidate::AudioMathPipelineResult\s+glint_audio_math_pipeline_;", added)
    assert "glint_audio_math_pipeline_.emplace(" not in added
    assert "GetGlintAudioMathPipeline() const" in added
    assert "CompressorMathPolicy math_policy" in added
    assert "glint_math_policy_(math_policy)" in added
    assert "AudioMathPipeline::kLegacyReadback" in added
    assert re.search(r"SurfaceSeedResult\(\s*std::optional", added)
    assert "OPENSSL_cleanse(key.data(), key.size())" in added
    assert "OPENSSL_cleanse(digest.data(), digest.size())" in added
    assert policy["domain"] in added
    selectors = [hmac.new(bytes([seed]) * 32, policy["domain"].encode("ascii"),
                          hashlib.sha256).digest()[0] & 1 for seed in (3, 4, 5)]
    assert selectors == [1, 0, 0]
    fixtures = re.findall(r"TEST_F\(OfflineAudioContextTest,\s*(GlintMath\w+)\)", added)
    assert set(fixtures) == set(data["prepared_tests"]) and len(fixtures) == 11
    assert "source->offset()->setValue(0.25f)" in added
    assert "source->connect(context->destinationNode(), 0, 0, ASSERT_NO_EXCEPTION)" in added
    assert "GetDynamicsCompressorHandler().glint_math_policy_.backend()" in added
    assert "EXPECT_EQ(sample, 0.25f)" in added
    assert "kNotReadableError" in added and "kUnavailablePolicy" in added


def test_audio_math_lifecycle_baseline_is_not_integration_runtime_admission():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/audio-dsp-math-v2"
    descriptor = json.loads((root / "context-integration.json").read_text(encoding="utf-8"))
    row = descriptor["lifecycle_baseline_calibration"]
    raw = (root / row["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    data = json.loads(raw)
    probe = data["probe"]
    assert hashlib.sha256((root / probe["file"]).read_bytes()).hexdigest() == probe["sha256"]
    assert data["schema"] == 1 and data["version"] == "148.0.7778.96"
    assert data["capture_count"] == 6 and data["repetitions_per_browser"] == 3
    for field in ("native156_runtime_verified", "math_integration_runtime_verified",
                  "native_fixtures_executed", "production_admitted"):
        assert data[field] is False
    assert data["postguards_passed"] and data["all_runtime_resources_closed"]
    assert data["owned_identity_payloads_unchanged"]
    assert {row["phase"] for row in data["captures"]} == {"stock-baseline", "a-native-baseline"}
    expected = {"closedRealtime": {"state": "closed", "node": {"created": True, "error": None}},
                "detachedOffline": {"state": "suspended", "node": {"created": True, "error": None}},
                "frameRemoved": True}
    for capture in data["captures"]:
        assert capture["repetitions"] == 3 and capture["observation"] == expected
        assert capture["sandbox_requested"] and capture["no_sandbox_flag_absent"]
    previous = json.loads((root / "observations.json").read_text(encoding="utf-8"))["browser_baseline_calibration"]
    for field in ("receipt_sha256", "native_core_sha256", "stock_core_sha256"):
        assert data[field] == previous[field]


def test_compressor_browser_calibration_covers_native_baseline_only():
    import json
    from scripts import native_build as build

    data = json.loads((build.ROOT / "native/drafts/audio-dsp-math-v2/observations.json").read_text(encoding="utf-8"))
    baseline = data["browser_baseline_calibration"]
    assert baseline["version"] == "148.0.7778.96" and baseline["capture_count"] == 6
    assert baseline["postguards_passed"] and baseline["all_runtime_resources_closed"]
    assert baseline["sandbox_requested"] and baseline["no_sandbox_flag_absent"]
    assert baseline["owned_identity_payloads_unchanged"]
    previous = json.loads((build.ROOT / "native/drafts/upstream-157-prefix/audio-constant-observations.json").read_text(encoding="utf-8"))
    for field in ("receipt_sha256", "native_core_sha256", "stock_core_sha256"):
        assert baseline[field] == previous[field]
    assert len(baseline["captures"]) == 2
    assert {row["phase"] for row in baseline["captures"]} == {"stock-baseline", "a-native-baseline"}
    for row in baseline["captures"]:
        assert row["repetitions"] == 3
        capture = row["observation"]
        assert capture == {"frames": 8192, "sampleRate": 44100, "channelCount": 2,
                           "eventSameBuffer": True, "closed": True, "prototype_exact": True,
                           "raw_sha256": data["native_samples_sha256"]}
    assert data["variant_device_cohort_verified"] is False


def test_pending_audio_copy_failure_fixtures_require_exact_unselected_prerequisite():
    import hashlib
    import json
    import re
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-157-prefix"
    descriptor = json.loads((root / "audio-copy-failure-tests.json").read_text(encoding="utf-8"))
    previous = json.loads((root / "chunked-audio-tests.json").read_text(encoding="utf-8"))
    manifest_path = root / "full-inputs-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert descriptor["schema"] == 1
    assert descriptor["target_revision"] == manifest["target_revision"]
    assert descriptor["target_version"] == manifest["target_version"]
    assert descriptor["required_base_manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert descriptor["required_patches"] == [previous["patch"]]
    for field in ("selected_in_manifest", "compiled", "native_tests_executed", "runtime_verified", "production_admitted"):
        assert descriptor[field] is False
    row = descriptor["patch"]
    assert row["file"] == "0067-native-audio-copy-failure-tests.patch"
    assert not (root / "patches" / row["file"]).exists()
    assert all(Path(patch["file"]).name != row["file"] for patch in manifest["patches"])
    raw = (root / row["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    patch = raw.decode("utf-8")
    paths = [line[6:] for line in patch.splitlines() if line.startswith("+++ b/")]
    assert paths == [source["path"] for source in descriptor["source_files"]]
    assert {Path(path).name for path in paths} == {
        "offline_audio_context.h", "offline_audio_context_test.cc", "offline_audio_buffer_unittest.cc"}
    assert [source["preserved_tests"] for source in descriptor["source_files"]] == [0, 25, 4]
    for source in descriptor["source_files"]:
        assert len(source["before_sha256"]) == len(source["after_sha256"]) == 64
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    names = [fixture + "." + name for fixture, name in
             re.findall(r"TEST_F\(\s*(\w+),\s*(\w+)\)", additions)]
    assert names == descriptor["expected_tests"] == [
        "OfflineAudioContextTest.GlintProtectedCopyFailureRejectsPendingQueueWithoutRawResult",
        "GlintOfflineAudioBufferTest.DetachedSourceRejectsWithoutRawFallback"]
    assert "FRIEND_TEST_ALL_PREFIXES(" in additions
    assert additions.index("suspended.WaitUntilSettled();") < additions.index(
        "context->pending_render_targets_.front() = invalid_target;")
    assert additions.index("context->OnChunkRendered();") < additions.index("first.WaitUntilSettled();")
    assert 'expect_rejection(first, "NotReadableError")' in additions
    assert 'expect_rejection(second, "AbortError")' in additions
    assert 'expect_rejection(future_suspend, "InvalidStateError")' in additions
    assert "EXPECT_EQ(completion->count(), 0);" in additions
    assert "CopyOfflineAudioBuffer(*source, kSeed), nullptr" in additions
    assert "SetSharedRenderTarget" not in additions and "->Resolve(" not in additions
    assert len(descriptor["api_sources"]) == 7 and descriptor["remaining_unverified"]
    for source in descriptor["api_sources"]:
        assert len(source["git_blob_sha1"]) == 40 and len(source["sha256"]) == 64
        assert 0 < source["bytes"] < 1024 * 1024


def test_audio_detached_buffer_controls_do_not_claim_protected_copy_execution():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-157-prefix"
    descriptor = json.loads((root / "audio-copy-failure-tests.json").read_text(encoding="utf-8"))
    calibration = descriptor["transfer_calibration"]
    assert calibration["file"] == "audio-detached-buffer-observations.json"
    assert calibration["protected_copy_path_executed"] is False
    assert calibration["chunked157_runtime_verified"] is False
    raw = (root / calibration["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == calibration["sha256"]
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["measurement_complete"] and data["buffer_transfer_controls_passed"]
    assert data["postguards_passed"] and data["all_runtime_resources_closed"]
    assert data["owned_identity_payloads_unchanged"] and data["sandbox_requested"] and data["no_sandbox_flag_absent"]
    for field in ("native156_verified", "native157_verified", "protected_copy_path_executed",
                  "privacy_admitted", "production_admitted"):
        assert data[field] is False
    probe = data["probe"]
    assert probe["file"] == "audio-detached-buffer-control.js"
    raw_probe = (root / probe["file"]).read_bytes()
    assert hashlib.sha256(raw_probe).hexdigest() == probe["sha256"]
    assert b"\r" not in raw_probe and not raw_probe.startswith(b"\xef\xbb\xbf")
    previous = json.loads((root / "audio-constant-observations.json").read_text(encoding="utf-8"))
    for field in ("receipt_sha256", "native_core_sha256", "stock_core_sha256"):
        assert data[field] == previous[field]
    assert data["browser_version"] == "148.0.7778.96"
    assert len(data["phases"]) == 5 and {row["phase"] for row in data["phases"]} == {
        "stock-baseline", "a-native-baseline", "a-partitioned", "a-identity", "a-identity-restart"}
    assert sum(row["repetitions"] for row in data["phases"]) == data["capture_count"] == 15
    assert all(row["repetitions"] == 3 for row in data["phases"])
    assert data["identical_observation_for_all_captures"] == {
        "beforeFrames": 128, "afterFrames": 0, "originalBytes": 0,
        "transferredBytes": 512, "sourceFrames": 128, "passed": True}


def test_audio_teardown_controls_preserve_matched_scope_and_dead_realm_semantics():
    import hashlib
    import json
    from scripts import native_build as build

    root = build.ROOT / "native/drafts/upstream-157-prefix"
    descriptor = json.loads((root / "chunked-audio-tests.json").read_text(encoding="utf-8"))
    calibration = descriptor["lifecycle_runtime_calibration"]
    assert calibration["matched_stock_native_version"] == "148.0.7778.96"
    assert calibration["captures"] == 15
    for field in ("chunked157_runtime_verified", "native157_fixtures_executed", "production_gate_passed"):
        assert calibration[field] is False
    observation = calibration["observations"]
    assert observation["file"] == "audio-teardown-observations.json"
    raw = (root / observation["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == observation["sha256"]
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["measurement_complete"] and data["teardown_controls_passed"]
    assert data["postguards_passed"] and data["all_runtime_resources_closed"]
    assert data["owned_identity_payloads_unchanged"]
    for field in ("native156_verified", "native157_verified", "privacy_admitted", "production_admitted"):
        assert data[field] is False
    probe = data["probe"]
    assert probe["file"] == "audio-teardown-control.js"
    raw_probe = (root / probe["file"]).read_bytes()
    assert hashlib.sha256(raw_probe).hexdigest() == probe["sha256"]
    assert b"\r" not in raw_probe and not raw_probe.startswith(b"\xef\xbb\xbf")
    constant = json.loads((root / "audio-constant-observations.json").read_text(encoding="utf-8"))
    for field in ("receipt_sha256", "native_core_sha256", "stock_core_sha256"):
        assert data[field] == constant[field]
    rows = data["captures"]
    assert len(rows) == 5 and {row["phase"] for row in rows} == {
        "stock-baseline", "a-native-baseline", "a-partitioned", "a-identity", "a-identity-restart"}
    assert sum(row["repetitions"] for row in rows) == data["capture_count"] == 15
    for row in rows:
        assert row["repetitions"] == 3 and row["browser_version"] == "148.0.7778.96"
        assert row["resources_closed"] and row["sandbox_requested"] and row["no_sandbox_flag_absent"]
        measured = row["observation"]
        assert measured["passed"] and measured["suspendedBeforeDetach"] and measured["pendingBeforeDetach"]
        assert measured["frameRemoved"] and measured["completionCount"] == 0
        assert measured["renderState"] == measured["futureSuspendState"] == "pending"
        assert measured["stateAfterDetach"] == "suspended" and measured["retryError"] == "InvalidStateError"


def test_audio_kernel_observations_do_not_admit_an_unproven_identity_generator():
    import json
    from scripts import native_build as build

    path = build.ROOT / "native/drafts/upstream-157-prefix/audio-kernel-observations.json"
    raw = path.read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["measurement_complete"] and data["frozen_inputs_unchanged"] and data["source_inputs_unchanged"]
    for field in ("compiled_browser", "runtime_verified", "production_admitted",
                  "identity_variation_observed", "automatic_vectorization"):
        assert data[field] is False
    assert data["functions"] == ["Vadd", "Vsma", "Vsmul"]
    assert "/Od" in data["compiler_flags"] and "/Qvec-" not in data["compiler_flags"]
    assert data["compiler_configuration_verified"] is True
    assert len(data["source_sha256"]) == 6 and len(data["scope_limitations"]) == 4
    assert {row["fp_mode"] for row in data["runs"]} == {"strict", "precise"}
    assert len(data["runs"]) == 2
    for row in data["runs"]:
        assert row["compared_samples"] == 32 * 8192 * 8 * 3
        assert row["gain_one_exact_samples"] == 32 * 8192
        assert row["different_samples"] == row["segmentation_differences"] == 0


def test_audio_matched148_observations_preserve_failed_fidelity_not_admission():
    import json
    from scripts import native_build as build

    path = build.ROOT / "native/drafts/upstream-157-prefix/audio-constant-observations.json"
    raw = path.read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw)
    assert data["measurement_complete"] and data["postguards_passed"]
    assert data["all_runtime_resources_closed"] and data["identity_restart_stable"]
    assert data["owned_identity_payloads_unchanged"] and data["shape_verified_for_all_captures"]
    for field in ("constant_control_compatibility_passed", "privacy_admitted", "production_admitted",
                  "native156_verified", "native157_verified"):
        assert data[field] is False
    expected = {"zero": "00000000", "positive_quarter": "3e800000",
                "negative_quarter": "be800000", "positive_half": "3f000000"}
    assert data["expected_bits"] == expected
    assert data["measurement_shape"] == {"frames": 256, "sample_rate": 44100, "channels": 1,
                                         "event_promise_same_buffer": True, "closed": True}
    rows = {row["phase"]: row for row in data["captures"]}
    assert len(rows) == len(data["captures"]) == 9
    assert set(rows) == {"stock-baseline", "a-native-baseline", "b-native-baseline",
                         "a-partitioned", "b-partitioned", "a-identity", "b-identity",
                         "a-identity-restart", "b-identity-restart"}
    mismatches = 0
    for name, row in rows.items():
        assert row["browser_version"] == "148.0.7778.96"
        assert row["sandbox_requested"] and row["no_sandbox_flag_absent"] and row["resources_closed"]
        assert set(row["observed_bits"]) == set(expected)
        for label, bits in row["observed_bits"].items():
            assert len(bits) == 1 and len(bits[0]) == 8
            assert int(bits[0], 16) in {int(expected[label], 16), int(expected[label], 16) ^ 1}
            if "baseline" in name:
                assert bits == [expected[label]]
            else:
                mismatches += bits != [expected[label]]
    assert mismatches == data["nonexact_protected_capture_count"] == 14
    for profile in ("a", "b"):
        assert rows[profile + "-identity"]["observed_bits"] == rows[profile + "-identity-restart"]["observed_bits"]


@pytest.mark.parametrize("failure", [None, "manifest-only", "patch-directory-only", "bad-source", "bad-patch",
                                    "duplicate-source", "duplicate-patch", "non-string-path", "oversized-manifest",
                                    "bad-schema", "bad-revision", "bad-version", "bad-dependency", "manifest-drift", "patch-drift", "output-in-patches"])
def test_explicit_rebase_manifest_reuses_shared_patches_without_implicit_fallback(tmp_path, monkeypatch, failure):
    import hashlib
    import json
    from scripts import verify_native_rebase_draft as draft

    source = tmp_path / "source"
    source.mkdir()
    original = b"int value = 1;\n"
    (source / "value.cc").write_bytes(original)
    shared = tmp_path / "shared-patches"
    shared.mkdir()
    patch = shared / "change.patch"
    patch.write_bytes(b"diff --git a/value.cc b/value.cc\n--- a/value.cc\n+++ b/value.cc\n@@ -1 +1 @@\n-int value = 1;\n+int value = 2;\n")
    manifest = tmp_path / "forward.json"
    value = {"schema": 1, "target_revision": "a" * 40,
             "source_files": [{"path": "value.cc", "sha256": hashlib.sha256(original).hexdigest()}],
             "patches": [{"file": "change.patch", "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}]}
    if failure == "duplicate-source":
        value["source_files"] *= 2
    elif failure == "duplicate-patch":
        value["patches"] *= 2
    elif failure == "non-string-path":
        value["source_files"][0]["path"] = []
    elif failure == "bad-schema":
        value["schema"] = True
    elif failure == "bad-revision":
        value["target_revision"] = "moving-head"
    elif failure == "bad-version":
        value["target_version"] = True
    elif failure == "bad-dependency":
        value["dependencies"] = []
    manifest.write_text(json.dumps(value), encoding="utf-8")
    if failure == "oversized-manifest":
        manifest.write_bytes(b" " * (4 * 1024**2 + 1))
    elif failure == "bad-source":
        (source / "value.cc").write_bytes(b"changed")
    elif failure == "bad-patch":
        patch.write_bytes(b"changed")
    monkeypatch.setattr(draft, "DRAFT", tmp_path / "must-not-be-used")
    output = shared / "report" if failure == "output-in-patches" else tmp_path / "output"
    arguments = {"manifest_path": manifest, "patch_directory": shared}
    if failure == "manifest-only":
        del arguments["patch_directory"]
    elif failure == "patch-directory-only":
        del arguments["manifest_path"]
    run = draft.subprocess.run

    def wrapped(command, **kwargs):
        result = run(command, **kwargs)
        if "apply" in command and "--check" not in command:
            if failure == "manifest-drift":
                manifest.write_text(json.dumps(value) + " ", encoding="utf-8")
            elif failure == "patch-drift":
                patch.write_bytes(patch.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(draft.subprocess, "run", wrapped)
    if failure not in {None, "manifest-drift", "patch-drift"}:
        with pytest.raises(ValueError):
            draft.verify(source, output, **arguments)
        assert not output.exists()
    else:
        report = draft.verify(source, output, **arguments)
        assert report["passed"] is (failure is None)
        assert report["inputs_unchanged"] is (failure is None)
        assert not report["compiled"] and not report["runtime_verified"] and not report["production_admitted"]
        assert (source / "value.cc").read_bytes() == original
        assert (output / "src/value.cc").read_bytes() == b"int value = 2;\n"


def test_upstream_draft_manifest_binds_registered_sources_and_compact_lf_patches():
    import hashlib
    import json
    from scripts import verify_native_rebase_draft as draft

    manifest = json.loads((draft.DRAFT / "manifest.json").read_text(encoding="utf-8-sig"))
    originals = sorted((draft.ROOT / "native/patches").glob("*.patch"))[:62]
    assert len(originals) == 62 and len(manifest["patches"]) == 67
    assert [row["file"] for row in manifest["patches"][:62]] == [path.name for path in originals]
    assert [row["file"] for row in manifest["patches"][62:]] == [
        "0063-native-safe-buffer-portability.patch", "0064-native-audio-safe-domain-copy.patch",
        "0065-native-fixture-portability.patch", "0066-native-gpu-optional-query-fixture.patch",
        "0067-native-audio-math-context-candidate.patch"]
    for row in manifest["patches"]:
        content = (draft.DRAFT / "patches" / row["file"]).read_bytes()
        assert b"\r" not in content and not content.startswith(b"\xef\xbb\xbf")
        assert hashlib.sha256(content).hexdigest() == row["sha256"]
    for row, original in zip(manifest["patches"][:62], originals, strict=True):
        assert hashlib.sha256(original.read_bytes()).hexdigest() == row["original_sha256"]
    assert manifest["patches"][6]["directory"] == "v8"
    assert manifest["dependencies"]["v8"]["revision"] == "8ce248ef8f7f71c04f7faaac249a37d340279f52"
    assert any(row["path"] == "DEPS" for row in manifest["source_files"])
    inspector = (draft.DRAFT / "patches" / manifest["patches"][6]["file"]).read_text(encoding="utf-8")
    assert "+  if (!isBuiltinGetter(function))" in inspector
    assert "-bool isBuiltinGetter" not in inspector


def test_forward_refresh_manifest_reuses_exact_patch_bytes_without_registering_a_build():
    import hashlib
    import json
    from scripts import native_build, verify_native_rebase_draft as draft

    original = draft.DRAFT / "checkpoints/001-065.json"
    refresh = draft.ROOT / "native/drafts/upstream-156-refresh"
    before = json.loads(original.read_text(encoding="utf-8"))
    value = json.loads((refresh / "manifest.json").read_text(encoding="utf-8"))
    assert value["base_manifest_sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
    assert value["target_version"] == "156.0.8078.75"
    assert value["target_revision"] == "861389936bf33ea77529ee5dcc0605e68f6bb620"
    assert value["dependencies"]["v8"]["revision"] == "235050a0df6db2c9d92a419af2b72fbf3b2dd73b"
    assert value["patches"] == before["patches"] and len(value["patches"]) == 65
    assert not (refresh / "patches").exists()
    assert len(value["source_files"]) == 185
    assert [row["path"] for row in value["source_files"]] == [row["path"] for row in before["source_files"]]
    for row in value["source_files"]:
        if row["path"].startswith("v8/"):
            prefix = "https://chromium.googlesource.com/v8/v8/+/" + value["dependencies"]["v8"]["revision"] + "/"
            name = row["path"][3:]
        else:
            prefix = "https://chromium.googlesource.com/chromium/src/+/" + value["target_revision"] + "/"
            name = row["path"]
        assert row["url"] == prefix + name + "?format=TEXT"
        assert type(row["bytes"]) is int and 0 <= row["bytes"] <= 16 * 1024**2
    assert sum(a["sha256"] != b["sha256"] for a, b in zip(before["source_files"], value["source_files"], strict=True)) == 7
    with pytest.raises(ValueError, match="Unknown Native build candidate"):
        native_build.load_candidate("upstream-156-refresh")


def _sparse_fetch_fixture(tmp_path, count=1):
    import hashlib
    import json
    revision = "a" * 40
    rows, contents = [], {}
    for index in range(count):
        name = f"source/file{index}.cc"
        content = f"int value{index} = 1;\n".encode()
        contents[name] = content
        rows.append({"path": name, "url": f"https://chromium.googlesource.com/chromium/src/+/{revision}/{name}?format=TEXT",
                     "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {"schema": 1, "target_revision": revision, "source_files": rows,
                "patches": [{"file": "not-fetched.patch", "sha256": "b" * 64}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest, contents


@pytest.mark.parametrize("failure", [None, "redirect", "oversized", "bad-base64", "checksum", "429", "503", "manifest-drift"])
def test_sparse_source_fetch_checks_https_payload_and_stops_without_retry(tmp_path, monkeypatch, failure):
    import base64
    import io
    import json
    from types import SimpleNamespace
    import urllib.error
    from unittest.mock import Mock
    from scripts import fetch_native_rebase_sources as fetch

    path, manifest, contents = _sparse_fetch_fixture(tmp_path)
    row = manifest["source_files"][0]

    class Response(io.BytesIO):
        def geturl(self):
            return "https://untrusted.invalid" if failure == "redirect" else row["url"]

    def request(value, timeout):
        assert value.full_url == row["url"] and timeout == 30
        if failure in {"429", "503"}:
            raise urllib.error.HTTPError(row["url"], int(failure), "owned failure", {"Retry-After": "120"}, None)
        if failure == "manifest-drift":
            path.write_text(json.dumps(manifest) + " ", encoding="utf-8")
        encoded = base64.b64encode(contents[row["path"]])
        if failure == "oversized":
            encoded += b"AAAA"
        elif failure == "bad-base64":
            encoded = b"!" * len(encoded)
        elif failure == "checksum":
            encoded = base64.b64encode(b"x" * row["bytes"])
        return Response(encoded)

    network = Mock(side_effect=request)
    monkeypatch.setattr(fetch.urllib.request, "build_opener", lambda *_handlers: SimpleNamespace(open=network))
    output = tmp_path / "output"
    report = fetch.fetch_sources(path, output)
    assert report["passed"] is (failure is None)
    assert report["network_requests"] == network.call_count == 1
    assert not report["compiled"] and not report["runtime_verified"] and not report["production_admitted"]
    assert json.loads((output / fetch.REPORT_NAME).read_text()) == report
    if failure in {"429", "503"}:
        assert report["http_status"] == int(failure) and report["retry_after"] == "120"
    if failure is None:
        assert (output / row["path"]).read_bytes() == contents[row["path"]]
    elif failure != "manifest-drift":
        assert not (output / row["path"]).exists()


@pytest.mark.parametrize("failure", [None, "corrupt", "drift", "linked", "output-in-cache", "existing-output"])
def test_sparse_source_fetch_uses_read_only_cache_and_preserves_evidence(tmp_path, monkeypatch, failure):
    from unittest.mock import Mock
    from scripts import fetch_native_rebase_sources as fetch

    path, manifest, contents = _sparse_fetch_fixture(tmp_path)
    row = manifest["source_files"][0]
    cache = tmp_path / "cache"
    cached = cache / row["path"]
    cached.parent.mkdir(parents=True)
    cached.write_bytes(contents[row["path"]])
    output = cache / "output" if failure == "output-in-cache" else tmp_path / "output"
    if failure == "existing-output":
        output.mkdir()
        (output / "retained").write_bytes(b"retained")
    elif failure == "corrupt":
        cached.write_bytes(b"corrupt cache")
    elif failure == "linked":
        from pathlib import Path
        resolve = Path.resolve
        monkeypatch.setattr(Path, "resolve", lambda self, *a, **kw: tmp_path / "foreign" if self == cached else resolve(self, *a, **kw))
    network = Mock(side_effect=AssertionError("Cache must not issue HTTP or silently replace corrupt bytes"))
    monkeypatch.setattr(fetch.urllib.request, "build_opener", network)
    if failure == "drift":
        read = fetch.read_source

        def drift(root, selected):
            value = read(root, selected)
            if root == cache:
                cached.write_bytes(b"changed after read")
            return value

        monkeypatch.setattr(fetch, "read_source", drift)
    if failure in {"corrupt", "linked", "output-in-cache", "existing-output"}:
        with pytest.raises(ValueError):
            fetch.fetch_sources(path, output, cache=cache)
        if failure == "existing-output":
            assert (output / "retained").read_bytes() == b"retained"
        else:
            assert not output.exists()
    else:
        report = fetch.fetch_sources(path, output, cache=cache)
        assert report["passed"] is (failure is None)
        assert report["network_requests"] == 0 and report["cache_hits"] == 1
    network.assert_not_called()


@pytest.mark.parametrize("limit", ["MAX_FILES", "MAX_TOTAL_BYTES"])
def test_sparse_source_fetch_budget_refusal_does_not_create_evidence_or_issue_http(tmp_path, monkeypatch, limit):
    from unittest.mock import Mock
    from scripts import fetch_native_rebase_sources as fetch

    path, _manifest, _contents = _sparse_fetch_fixture(tmp_path)
    monkeypatch.setattr(fetch, limit, 0)
    network = Mock()
    monkeypatch.setattr(fetch.urllib.request, "build_opener", network)
    with pytest.raises(ValueError):
        fetch.fetch_sources(path, tmp_path / "output")
    network.assert_not_called()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("mutation", ["url", "revision-url", "boolean-size", "too-large", "checksum", "traversal",
                                      "duplicate", "case-alias", "report-collision", "noncanonical", "git-path", "missing-v8-pin"])
def test_sparse_source_fetch_rejects_invalid_plans_before_network_or_output(tmp_path, monkeypatch, mutation):
    import json
    from unittest.mock import Mock
    from scripts import fetch_native_rebase_sources as fetch

    path, manifest, _contents = _sparse_fetch_fixture(tmp_path)
    row = manifest["source_files"][0]
    if mutation == "url":
        row["url"] = "http://127.0.0.1/private"
    elif mutation == "revision-url":
        row["url"] = row["url"].replace("a" * 40, "main")
    elif mutation == "boolean-size":
        row["bytes"] = True
    elif mutation == "too-large":
        row["bytes"] = fetch.MAX_FILE_BYTES + 1
    elif mutation == "checksum":
        row["sha256"] = "invalid"
    elif mutation in {"duplicate", "case-alias"}:
        manifest["source_files"].append({**row, "path": row["path"].upper() if mutation == "case-alias" else row["path"]})
    else:
        row["path"] = {"traversal": "../outside", "report-collision": fetch.REPORT_NAME,
                       "noncanonical": "source//file0.cc", "git-path": ".git/config",
                       "missing-v8-pin": "v8/src/file.cc"}[mutation]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    network = Mock()
    monkeypatch.setattr(fetch.urllib.request, "build_opener", network)
    with pytest.raises(ValueError):
        fetch.fetch_sources(path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
    network.assert_not_called()


def test_sparse_source_fetch_applies_minimum_interval_and_disables_redirects(tmp_path, monkeypatch):
    import base64
    import io
    from types import SimpleNamespace
    from scripts import fetch_native_rebase_sources as fetch

    path, _manifest, contents = _sparse_fetch_fixture(tmp_path, count=3)
    clock, sleeps = [100.0], []
    monkeypatch.setattr(fetch.time, "monotonic", lambda: clock[0])

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(fetch.time, "sleep", sleep)

    class Response(io.BytesIO):
        def __init__(self, url, content):
            super().__init__(base64.b64encode(content))
            self.url = url

        def geturl(self):
            return self.url

    def request(value, timeout):
        name = value.full_url.split("/" + "a" * 40 + "/")[1].split("?")[0]
        clock[0] += .25
        return Response(value.full_url, contents[name])

    monkeypatch.setattr(fetch.urllib.request, "build_opener", lambda *_handlers: SimpleNamespace(open=request))
    report = fetch.fetch_sources(path, tmp_path / "output")
    assert report["passed"] and report["network_requests"] == 3
    assert sleeps == [1.75, 1.75]
    assert fetch.NoRedirect().redirect_request(None, None, 302, "", {}, "https://untrusted.invalid") is None


def test_upstream_privacy_batch_keeps_owned_key_implementations_and_test_bindings():
    import re
    from scripts import verify_native_rebase_draft as draft

    def added_files(text):
        files = {}
        for section in text.split("diff --git ")[1:]:
            if "\n--- /dev/null\n" in section:
                name = re.search(r"^\+\+\+ b/(.+)$", section, re.MULTILINE).group(1)
                files[name] = [line[1:] for line in section.splitlines() if line.startswith("+") and not line.startswith("+++")]
        return files

    candidates = sorted((draft.DRAFT / "patches").glob("*.patch"))[10:17]
    assert len(candidates) == 7
    for candidate in candidates:
        original = draft.ROOT / "native/patches" / candidate.name
        assert added_files(candidate.read_text(encoding="utf-8")) == added_files(original.read_text(encoding="utf-8-sig"))
    batch = "\n".join(path.read_text(encoding="utf-8") for path in candidates)
    for binding in ('source_set("camouflow_native_privacy")', 'test("camouflow_native_privacy_unittests")',
                    '"../browser/camouflow_native/privacy_context_unittest.cc"',
                    '"//content/browser:camouflow_native_privacy"'):
        assert binding in batch


def test_upstream_worker_batch_retains_new_policy_container_and_fixture_contracts():
    from scripts import verify_native_rebase_draft as draft

    def additions(name):
        text = (draft.DRAFT / "patches" / name).read_text(encoding="utf-8")
        return "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))

    dedicated = additions("0021-native-dedicated-worker-startup-gate.patch")
    assert dedicated.count("blink::mojom::PolicyContainerPtr policy_container") == 2
    assert dedicated.count("std::move(policy_container)") == 2
    shared = additions("0023-native-shared-worker-startup-gate.patch")
    assert "WebString::FromUTF8" not in shared and shared.count("WebString::FromUtf8") == 2
    fixture = additions("0026-native-worker-canvas-handoff-tests.patch")
    assert "GlobalScopeCreationParams::CreateForWorkerForTesting(" in fixture
    assert "nullptr, seed" not in fixture
    assert fixture.count("DidEvaluateTopLevelScriptMock") == 4
    commit = additions("0030-native-document-commit-prototype.patch")
    assert commit.count("AddThrottle(std::make_unique<PrivacyNavigationThrottle>(*this))") == 2
    commit_patch = (draft.DRAFT / "patches/0030-native-document-commit-prototype.patch").read_text(encoding="utf-8")
    assert "CreateThrottlesForCommitWithoutUrlLoader(" in commit_patch


def test_upstream_surface_batch_keeps_initiator_token_and_new_worker_mock_signature():
    from scripts import verify_native_rebase_draft as draft

    def additions(name):
        text = (draft.DRAFT / "patches" / name).read_text(encoding="utf-8")
        return "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))

    document = additions("0032-native-document-surface-policy.patch")
    assert "blink.mojom.InitiatorStateToken initiator_state_token" in document
    assert document.count("const blink::InitiatorStateToken& initiator_state_token") == 4
    assert document.count("frame_token, initiator_state_token") >= 3
    worker = additions("0031-native-worker-surface-policy.patch")
    assert "DidEvaluateTopLevelScript(_)" not in worker
    assert "DidEvaluateTopLevelScriptMock(_, _)" in worker
    assert "const JavaScriptFrameworkDetectionResult&" in worker
    assert "nullptr, legacy" not in worker
    metadata = additions("0034-native-gpu-metadata-minimization.patch")
    assert "BASE_FEATURE(kGlintGpuMetadataMinimization, base::FEATURE_DISABLED_BY_DEFAULT)" in metadata
    assert "BASE_FEATURE(kGlintWebGLReadbackCandidate, base::FEATURE_DISABLED_BY_DEFAULT)" in metadata


def test_upstream_final_batch_uses_target_command_id_and_current_identity_fixture_api():
    import re
    from scripts import verify_native_rebase_draft as draft

    transport = (draft.DRAFT / "patches/0055-native-gpu-readback-metadata-transport.patch").read_text(encoding="utf-8")
    assert re.search(r"^\+\s*OP\(GetGlintReadFramebufferMetadataCHROMIUM\)\s*/\*\s*577\s*\*/", transport, re.MULTILINE)
    assert "diff --git a/gpu/command_buffer/build_gles2_cmd_buffer.py" in transport
    for name in ("0052-native-surface-identity-v3-transport.patch", "0053-native-identity-handoff-tests.patch"):
        text = (draft.DRAFT / "patches" / name).read_text(encoding="utf-8")
        additions = "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
        assert "DidEvaluateTopLevelScript(true)" not in additions
        assert not re.search(r'KURL\("http://fake.url/"\),\s*nullptr,', additions)


def test_native_error_patch_covers_console_coercion_and_property_preview_paths():
    from scripts.native_build import ROOT

    patch = (ROOT / "native/patches/0007-native-inspector-error-accessors.patch").read_text(encoding="utf-8-sig")
    assert "+++ b/src/inspector/v8-console-message.cc" in patch
    assert "+++ b/src/inspector/value-mirror.h" in patch
    assert "ValueMirror::getErrorDescription(" in patch
    assert "/*includeStack=*/false" in patch
    assert "? getErrorProperty(context, object, v8Name)" in patch


@pytest.mark.parametrize("phase", ["checkpoint-before-crash", "crashed-profile-cleanup", "round-finalizer"])
def test_restart_close_failure_retains_original_error_and_adds_context(phase):
    import asyncio
    import re
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts.verify_native_runtime import _close_restart_profile

    error = TimeoutError("Native browser context close timed out")
    runtime = SimpleNamespace(close=AsyncMock(side_effect=error))
    with pytest.raises(TimeoutError) as observed:
        asyncio.run(_close_restart_profile(runtime, round_number=2, profile_slot=1, phase=phase))
    assert observed.value is error
    assert str(error) == "Native browser context close timed out"
    assert len(error.__notes__) == 1
    assert error.__notes__[0].startswith(f"Native restart gate: round=2, profile_slot=1, phase={phase}, ")
    assert re.search(r"close_elapsed_seconds=\d+\.\d{3}$", error.__notes__[0])
    runtime.close.assert_awaited_once()


def test_restart_close_success_has_no_extra_shutdown_or_retry():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts.verify_native_runtime import _close_restart_profile

    runtime = SimpleNamespace(close=AsyncMock())
    asyncio.run(_close_restart_profile(runtime, round_number=1, profile_slot=0, phase="round-finalizer"))
    runtime.close.assert_awaited_once()


def test_restart_close_does_not_swallow_or_relabel_cancellation():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts.verify_native_runtime import _close_restart_profile

    error = asyncio.CancelledError()
    runtime = SimpleNamespace(close=AsyncMock(side_effect=error))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_close_restart_profile(runtime, round_number=1, profile_slot=0, phase="round-finalizer"))
    assert not getattr(error, "__notes__", [])
    runtime.close.assert_awaited_once()


def test_restart_finalizer_error_identifies_slot_and_closes_other_profiles(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts import verify_native_runtime as gate

    error = TimeoutError("Native browser context close timed out")
    runtimes = [SimpleNamespace(start=AsyncMock(return_value=SimpleNamespace(pages=[object()])), close=AsyncMock()),
                SimpleNamespace(start=AsyncMock(side_effect=RuntimeError("owned startup failed")), close=AsyncMock(side_effect=error))]
    created = iter(runtimes)
    monkeypatch.setattr(gate, "NativeRuntime", lambda *args: next(created))
    monkeypatch.setattr(gate, "process_snapshot", lambda: {})
    with pytest.raises(TimeoutError) as observed:
        asyncio.run(gate.verify_multi_profile_restarts(tmp_path, tmp_path / "missing", "http://127.0.0.1:1"))
    assert observed.value is error
    assert "round=1, profile_slot=1, phase=round-finalizer" in error.__notes__[0]
    for runtime in runtimes:
        runtime.close.assert_awaited_once()
