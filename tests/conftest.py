import hashlib
import json
from pathlib import Path
import subprocess

import pytest


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
