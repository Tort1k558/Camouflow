from __future__ import annotations

import json

import pytest

from scripts import verify_native_gpu_cpp as gpu_cpp
from scripts import verify_native_identity_cpp as identity_cpp
from scripts import verify_native_identity_readback_batch as batch


@pytest.mark.parametrize("failure", [None, "identity", "gpu", "consumer-drift"])
def test_combined_cpp_checks_share_exact_composition_and_fail_closed(tmp_path, monkeypatch, failure):
    workspace = tmp_path / "workspace"
    source = workspace / "chromium/src"
    names = {"candidate.cc", ".clang-format", "gpu/command_buffer/build_cmd_buffer_lib.py"}
    for name in names | {"consumer.cc"}:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("baseline", encoding="utf-8")
    monkeypatch.setattr(batch, "patch_paths", lambda text: {"candidate.cc"})
    monkeypatch.setattr(batch.gpu, "FIXTURE_PATHS", set())
    monkeypatch.setattr(batch.build, "environment", lambda workspace: {})
    monkeypatch.setattr(batch.build, "run", lambda *args: None)
    monkeypatch.setattr(batch.gpu, "restore_registered_baseline", lambda *args: None)
    monkeypatch.setattr(batch.gpu, "apply_registered_fixture_followup", lambda *args: None)
    monkeypatch.setattr(identity_cpp, "source_paths", lambda source: {"consumer.cc"})
    proof = {"registered_patches": [], "composed_source": {name: batch.digest(source / name) for name in names}}
    monkeypatch.setattr(batch.identity, "verify", lambda *args, **kwargs: proof)
    monkeypatch.setattr(batch.gpu, "verify", lambda *args, **kwargs: proof)
    calls = []

    def bindings(source, overlay, env):
        calls.append(("bindings", overlay))
        return {"passed": True}

    def commands(overlay, formatter, env):
        assert overlay.name == "src"
        calls.append(("commands", overlay))
        return 3

    def cpp(kind, source, overlay, log, env):
        calls.append((kind, overlay))
        assert (overlay / "consumer.cc").read_text(encoding="utf-8") == "baseline"
        if failure == "consumer-drift" and kind == "identity":
            (source / "consumer.cc").write_text("changed", encoding="utf-8")
        return {"passed": failure != kind, "compiled": False, "units": {kind: {"exit_code": 0}}}

    monkeypatch.setattr(batch.identity, "verify_bindings", bindings)
    monkeypatch.setattr(batch.gpu, "verify_codegen", commands)
    monkeypatch.setattr(identity_cpp, "verify_cpp", lambda *args: cpp("identity", *args))
    monkeypatch.setattr(gpu_cpp, "verify_cpp", lambda *args: cpp("gpu", *args))
    report = tmp_path / "proof.json"
    if failure == "consumer-drift":
        with pytest.raises(ValueError, match=r"Active C\+\+ consumers"):
            batch.verify(workspace, report, check_cpp=True)
        assert not report.exists()
    else:
        result = batch.verify(workspace, report, check_cpp=True)
        assert result["passed"] is (failure is None)
        assert result["compiled"] is False and result["privacy_admitted"] is False
        assert json.loads(report.read_text(encoding="utf-8"))["passed"] is (failure is None)
    assert [kind for kind, _ in calls] == ["bindings", "commands", "identity", "gpu"]
    assert len({overlay for _, overlay in calls}) == 1
