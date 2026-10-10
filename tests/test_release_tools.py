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
