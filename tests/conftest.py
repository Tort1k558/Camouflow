import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def native_units_before_orientation(tmp_path, monkeypatch):
    """Reconstruct the measured 001-070 verifier, without rewriting old evidence."""
    root = Path(__file__).resolve().parents[1]
    directory = root / "native/drafts/environment"
    record = json.loads((directory / "screen-orientation71-gate-preparation.json").read_bytes())
    path = tmp_path / record["base_source"]
    path.parent.mkdir(parents=True)
    path.write_text((root / record["base_source"]).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(directory / record["patch"])], cwd=tmp_path, check=True, capture_output=True)
    value = hashlib.sha256(path.read_bytes()).hexdigest()
    assert value == record["base_source_sha256"]
    monkeypatch.setattr(sys, "path", sys.path.copy())
    namespace = {"__file__": str(root / record["base_source"]), "__name__": "_native_units_before_orientation"}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return {"path": path, "source_sha256": value, "namespace": namespace}


@pytest.fixture
def release_tools_before_72_sha256(tmp_path):
    root = Path(__file__).resolve().parents[1]
    relative = Path("tests/test_release_tools.py")
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text((root / relative).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/linked72-test-contract.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def recorder_before_document_open_sha256(tmp_path):
    """Reconstruct the measured historical source, without rewriting old evidence."""
    root = Path(__file__).resolve().parents[1]
    relative = Path("app/services/scenario_recorder.py")
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    target.write_text((root / relative).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/recorder-document-open.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    record = json.loads((root / "native/drafts/environment/recorder-document-open70-observations.json").read_bytes())
    result = hashlib.sha256(target.read_bytes()).hexdigest()
    assert result == record["source_before"]["normalized_utf8_lf_sha256"] == "b41dc9a12865a0eecf73749b1f69adc70e587f87c14a93973eeff18f60872c8e"
    assert record["source_before"]["raw_sha256"] == "cf37b1e51facc4cf807e0588c2da4869756cbcd170754a3071df261a1817574c"
    return record["source_before"]["raw_sha256"]


@pytest.fixture
def stage_before_python_overlay_sources(tmp_path):
    """Reconstruct the source-bound JS-only build inputs without rewriting evidence."""
    root = Path(__file__).resolve().parents[1]
    names = ("camouflow.spec", "scripts/native_driver_stage.py")
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((root / name).read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--reverse", "--whitespace=error",
                    str(root / "native/drafts/environment/driver-stage-python-integration.patch")],
                   cwd=tmp_path, check=True, capture_output=True)
    return {name: (tmp_path / name).read_text(encoding="utf-8") for name in names}
