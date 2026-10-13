from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.verify_native_gpu_cpp import compiler_failure_is_fatal, evidence_directory
from scripts import verify_native_gpu_cpp as gpu


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


@pytest.mark.parametrize("diagnostic,exit_code,fatal", [
    ("error: invalid expression", 1, False), ("LLVM ERROR: out of memory", 1, True),
    ("Allocation failed", 1, True), ("Exception Code: 0xC000001D", 1, True),
    ("clang frontend command failed due to signal", 1, True), ("", None, True), ("", -1, True)])
def test_cpp_batch_aborts_on_crash_timeout_or_oom(tmp_path, diagnostic, exit_code, fatal):
    log = tmp_path / "syntax.log"
    prior = b"LLVM ERROR: unrelated previous unit\n"
    log.write_bytes(prior + diagnostic.encode("utf-8"))
    assert compiler_failure_is_fatal(log, len(prior), exit_code) is fatal


@pytest.mark.parametrize("padding", [65530, 200000])
def test_cpp_batch_detects_fatal_diagnostics_after_large_output_and_across_read_boundaries(tmp_path, padding):
    log = tmp_path / "long.log"
    log.write_bytes(b"x" * padding + b"LLVM ERROR: out of memory\n")
    assert compiler_failure_is_fatal(log, 0, 1)


@pytest.mark.parametrize("failure", ["syntax", "oom", "timeout"])
def test_gpu_cpp_batch_collects_each_ordinary_error_and_stops_fatal_failures(tmp_path, monkeypatch, failure):
    source, overlay = tmp_path / "source", tmp_path / "owned"
    output = source / "out/CamouFlowNative"
    files = [source / "third_party/llvm-build/Release+Asserts/bin/clang-cl.exe",
             output / "toolchain.ninja", output / "args.gn"]
    for unit, target in gpu.TARGETS.values():
        files += [output / "obj/gpu" / (target + ".ninja"), overlay / "gpu/command_buffer" / unit]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("controlled fixture", encoding="utf-8")
    monkeypatch.setattr(gpu.sys, "platform", "win32")
    monkeypatch.setattr(gpu, "measure_runtime_core", lambda executable: {"chrome.exe": "a" * 64})
    monkeypatch.setattr(gpu, "syntax_flags", lambda *args, **kwargs: "ACTUAL_TARGET_FLAGS")
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if len(commands) in {3, 5}:
            if failure == "timeout":
                raise gpu.subprocess.TimeoutExpired(command, 180)
            kwargs["stdout"].write("LLVM ERROR: out of memory\n" if failure == "oom" else "error: undeclared symbol\n")
            return SimpleNamespace(returncode=1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(gpu.subprocess, "run", run)
    proof = gpu.verify_cpp(source, overlay, tmp_path / "gpu.log", {}, collect_errors=True)
    assert not proof["passed"] and proof["compiled"] is False
    assert len(commands) == (6 if failure == "syntax" else 3)
    assert proof["aborted"] is (failure != "syntax")
    assert len(proof["not_checked"]) == (0 if failure == "syntax" else 3)
