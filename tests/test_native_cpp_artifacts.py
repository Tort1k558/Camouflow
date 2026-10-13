from pathlib import Path

import pytest

from scripts.verify_native_gpu_cpp import evidence_directory


@pytest.mark.parametrize("existing", ["log", "directory", "file"])
def test_cpp_artifact_creation_never_overwrites_existing_evidence(tmp_path, existing):
    log = tmp_path / "check.log"
    artifacts = log.with_name(log.name + ".artifacts")
    retained = log if existing == "log" else artifacts
    if existing == "directory":
        retained.mkdir()
        retained = retained / "crash.cpp"
    retained.write_text("retain", encoding="utf-8")
    with pytest.raises(ValueError):
        evidence_directory(log)
    assert retained.read_text(encoding="utf-8") == "retain"


def test_cpp_artifacts_live_beside_private_log_not_disposable_overlay(tmp_path):
    log = tmp_path / "new.log"
    directory = evidence_directory(log)
    assert directory == Path(str(log) + ".artifacts")
    assert directory.is_dir() and not log.exists()


def test_cpp_artifacts_reject_missing_parent(tmp_path):
    with pytest.raises(ValueError):
        evidence_directory(tmp_path / "absent/log")
    assert not (tmp_path / "absent").exists()
