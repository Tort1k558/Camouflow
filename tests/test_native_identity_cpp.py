from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import verify_native_identity_cpp as checker


def prepare_inputs(tmp_path):
    source = tmp_path / "source"
    output = source / "out/CamouFlowNative"
    overlay = tmp_path / "owned"
    for relative in checker.TARGETS:
        path = overlay / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("candidate source", encoding="utf-8")
    for relative in checker.GENERATED_TARGETS:
        path = overlay / "bindings-gen" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fresh v3 source", encoding="utf-8")
    paths = [source / "third_party/llvm-build/Release+Asserts/bin/clang-cl.exe",
             output / "toolchain.ninja", output / "args.gn"]
    paths.extend(output / "obj" / (target + ".ninja") for target in (checker.TARGETS | checker.GENERATED_TARGETS).values())
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("actual target input fixture", encoding="utf-8")
    return source, overlay, tmp_path / "syntax.log"


@pytest.mark.parametrize("failure", [None, "compiler", "timeout", "changed-input", "missing-generated"])
def test_identity_cpp_checker_is_complete_and_fail_closed(tmp_path, monkeypatch, failure):
    source, overlay, log = prepare_inputs(tmp_path)
    monkeypatch.setattr(checker.sys, "platform", "win32")
    monkeypatch.setattr(checker, "measure_runtime_core", lambda executable: {"chrome.exe": "a" * 64})
    flags = []
    commands = []
    def syntax_flags(ninja, toolchain, relative, *, generated=False):
        flags.append((relative, generated))
        return "ACTUAL_TARGET_FLAGS"
    def run(command, **kwargs):
        commands.append(command)
        response = Path(command[1].removeprefix("@")).read_text(encoding="utf-8")
        assert "-fsyntax-only" in response and "/Yu" not in response
        assert response.index('-I"' + str(overlay / "cpp-checks/gen")) < response.index("ACTUAL_TARGET_FLAGS")
        assert kwargs["cwd"] == source / "out/CamouFlowNative"
        if len(commands) == 3:
            if failure == "compiler":
                return SimpleNamespace(returncode=1)
            if failure == "timeout":
                raise checker.subprocess.TimeoutExpired(command, 180)
            if failure == "changed-input":
                (source / "out/CamouFlowNative/args.gn").write_text("changed", encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(checker, "syntax_flags", syntax_flags)
    monkeypatch.setattr(checker.subprocess, "run", run)
    if failure == "missing-generated":
        missing = next(iter(checker.GENERATED_TARGETS))
        (overlay / "bindings-gen" / missing).unlink()
        stale = source / "out/CamouFlowNative/gen" / missing
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("stale v2 source", encoding="utf-8")
        with pytest.raises(ValueError, match="fresh generated"):
            checker.verify_cpp(source, overlay, log, {})
        assert commands == []
        return
    proof = checker.verify_cpp(source, overlay, log, {})
    assert proof["passed"] is (failure is None)
    assert proof["compiled"] is False and proof["privacy_admitted"] is False
    assert len(proof["units"]) == (3 if failure in {"compiler", "timeout"} else 22)
    if failure is None:
        assert set(proof["units"]) == set(checker.TARGETS | checker.GENERATED_TARGETS)
        assert {relative for relative, generated in flags if generated} == set(checker.GENERATED_TARGETS)
    if failure == "changed-input":
        assert proof["active_core_and_inputs_unchanged"] is False


def test_identity_cpp_sources_include_consumers_and_generated_implementations():
    assert len(checker.TARGETS) == 20 and len(checker.GENERATED_TARGETS) == 2
    assert "content/renderer/render_frame_impl.cc" in checker.TARGETS
    assert "third_party/blink/renderer/modules/service_worker/service_worker_global_scope.cc" in checker.TARGETS
    assert any(name.endswith(".mojom.cc") for name in checker.GENERATED_TARGETS)
    assert any(name.endswith(".mojom-shared.cc") for name in checker.GENERATED_TARGETS)
