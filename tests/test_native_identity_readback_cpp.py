from __future__ import annotations

import json

import pytest

from scripts import verify_native_gpu_cpp as gpu_cpp
from scripts import verify_native_identity_cpp as identity_cpp
from scripts import verify_native_identity_readback_batch as batch


@pytest.mark.parametrize("failure", [None, "identity", "gpu", "consumer-drift", "identity-abort", "identity-input-drift"])
@pytest.mark.parametrize("collect_errors", [False, True])
def test_combined_cpp_checks_share_exact_composition_and_fail_closed(tmp_path, monkeypatch, failure, collect_errors):
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

    def cpp(kind, source, overlay, log, env, **options):
        assert options == ({"collect_errors": True} if collect_errors else {})
        calls.append((kind, overlay))
        assert (overlay / "consumer.cc").read_text(encoding="utf-8") == "baseline"
        if failure == "consumer-drift" and kind == "identity":
            (source / "consumer.cc").write_text("changed", encoding="utf-8")
        failed = failure == kind or kind == "identity" and failure in {"identity-abort", "identity-input-drift"}
        return {"passed": not failed, "compiled": False, "units": {kind: {"exit_code": 1 if failed else 0}},
                "aborted": kind == "identity" and failure == "identity-abort",
                "active_core_and_inputs_unchanged": failure != "identity-input-drift"}

    monkeypatch.setattr(batch.identity, "verify_bindings", bindings)
    monkeypatch.setattr(batch.gpu, "verify_codegen", commands)
    monkeypatch.setattr(identity_cpp, "verify_cpp", lambda *args, **kwargs: cpp("identity", *args, **kwargs))
    monkeypatch.setattr(gpu_cpp, "verify_cpp", lambda *args, **kwargs: cpp("gpu", *args, **kwargs))
    report = tmp_path / "proof.json"
    if failure == "consumer-drift":
        with pytest.raises(ValueError, match=r"Active C\+\+ consumers"):
            batch.verify(workspace, report, check_cpp=True, collect_cpp_errors=collect_errors)
        assert not report.exists()
    else:
        result = batch.verify(workspace, report, check_cpp=True, collect_cpp_errors=collect_errors)
        assert result["passed"] is (failure is None)
        assert result["compiled"] is False and result["privacy_admitted"] is False
        assert json.loads(report.read_text(encoding="utf-8"))["passed"] is (failure is None)
    skipped = collect_errors and failure in {"identity-abort", "identity-input-drift"}
    assert [kind for kind, _ in calls] == ["bindings", "commands", "identity"] + ([] if skipped else ["gpu"])
    if skipped:
        assert result["cpp_syntax"]["gpu"]["units"] == {}
        assert len(result["cpp_syntax"]["gpu"]["not_checked"]) == 6
    assert len({overlay for _, overlay in calls}) == 1
