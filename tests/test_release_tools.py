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
