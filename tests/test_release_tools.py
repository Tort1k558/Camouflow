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
    assert env["CIPD_CACHE_DIR"] == str(tmp_path / "cipd-cache")


def test_native_build_rejects_relative_workspace():
    from scripts.native_build import preflight

    with pytest.raises(ValueError, match="absolute"):
        preflight(Path("relative-native-build"))


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
