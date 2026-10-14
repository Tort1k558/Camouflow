import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from scripts import stage_native_windows as staging


@pytest.fixture
def staging_fixture(tmp_path, monkeypatch):
    root = tmp_path / "public"
    (root / "native").mkdir(parents=True)
    arguments = b"is_debug=false\n"
    (root / "native/args.gn").write_bytes(arguments)
    workspace = tmp_path / "workspace"
    output = workspace / "chromium/src/out/CamouFlowNative"
    output.mkdir(parents=True)
    (output / "args.gn").write_bytes(arguments)
    core = {name: hashlib.sha256(name.encode()).hexdigest()
            for name in ("chrome.exe", "chrome.dll", "chrome_elf.dll")}
    receipt = {"schema": 1, "platform": "win32", "binary": "chrome.exe",
               "native_version": staging.build.LOCK["native_version"],
               "chromium_revision": staging.build.LOCK["chromium_revision"],
               "depot_tools_revision": staging.build.LOCK["depot_tools_revision"],
               "runtime_core_sha256_measured": core, "binary_sha256_measured": core["chrome.exe"],
               "args_sha256": hashlib.sha256(arguments).hexdigest(), "patches": []}
    (output / "camouflow-build.json").write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(staging, "ROOT", root)
    monkeypatch.setattr(staging.sys, "platform", "win32")
    monkeypatch.setattr(staging, "require_idle_builder", lambda: None)
    monkeypatch.setattr(staging.build, "preflight", lambda _: None)
    monkeypatch.setattr(staging.build, "environment", lambda _: {})
    monkeypatch.setattr(staging.build, "require_stage", lambda *args: None)
    monkeypatch.setattr(staging.build, "check_patch_dependencies", lambda *args: None)
    monkeypatch.setattr(staging.build, "run", lambda *args, **kwargs: staging.build.LOCK["chromium_revision"])
    monkeypatch.setattr(staging.build, "source_patches", lambda *args: [])
    monkeypatch.setattr(staging.build, "v8_source_patches", lambda *args: [])
    monkeypatch.setattr(staging.build, "measure_runtime_core", lambda *args: dict(core))
    monkeypatch.setattr(staging.build, "depot_command", lambda *args: ["owned-autoninja"])
    return workspace, output, tmp_path / "stage-proof.json", receipt


@pytest.mark.parametrize("failure", [None, "public-line-endings", "build", "staged-core", "core", "args", "public-args", "receipt", "patches"])
def test_official_staging_preserves_failures_and_postguards(staging_fixture, monkeypatch, failure):
    workspace, output, report, _ = staging_fixture
    calls = []
    measure = staging.build.measure_runtime_core
    if failure == "public-line-endings":
        (staging.ROOT / "native/args.gn").write_bytes(b"is_debug=false\r\n")

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] == workspace / "chromium/src"
        assert kwargs["env"]["GOMEMLIMIT"] == "3GiB"
        if failure == "build":
            raise subprocess.CalledProcessError(1, command)
        if failure == "staged-core":
            monkeypatch.setattr(staging.build, "measure_runtime_core", lambda exe, *args:
                                {**measure(exe), "chrome.dll": "a" * 64} if args else measure(exe))
        elif failure == "core":
            monkeypatch.setattr(staging.build, "measure_runtime_core", lambda *args: {"chrome.exe": "a" * 64})
        elif failure in {"args", "receipt"}:
            (output / ("args.gn" if failure == "args" else "camouflow-build.json")).write_bytes(b"changed")
        elif failure == "public-args":
            (staging.ROOT / "native/args.gn").write_bytes(b"changed")
        elif failure == "patches":
            monkeypatch.setattr(staging.build, "source_patches", lambda *args: [{"name": "changed"}])

    monkeypatch.setattr(staging.subprocess, "run", run)
    proof = staging.stage(workspace, report, jobs=4)
    assert proof["passed"] is (failure in {None, "public-line-endings"})
    assert proof["inputs_unchanged"] is (failure in {None, "public-line-endings", "build", "staged-core"})
    assert calls == [["owned-autoninja", "-C", "out/CamouFlowNative", "-j", "4", staging.TARGET]]
    assert json.loads(report.read_text(encoding="utf-8")) == proof
    with pytest.raises(ValueError, match="overwrite"):
        staging.stage(workspace, report)


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("platform", "linux"), ("binary", "other.exe"),
    ("binary_sha256_measured", "a" * 64), ("runtime_core_sha256_measured", {}),
    ("args_sha256", "a" * 64), ("patches", [{"name": "missing"}]),
    ("native_version", "other"), ("chromium_revision", "a" * 40),
    ("depot_tools_revision", "a" * 40),
])
def test_official_staging_rejects_receipt_mismatch_before_builder(staging_fixture, monkeypatch, field, value):
    workspace, output, report, receipt = staging_fixture
    receipt[field] = value
    (output / "camouflow-build.json").write_text(json.dumps(receipt), encoding="utf-8")
    from unittest.mock import Mock
    builder = Mock()
    monkeypatch.setattr(staging.subprocess, "run", builder)
    with pytest.raises(ValueError, match="matching pinned"):
        staging.stage(workspace, report)
    builder.assert_not_called()
    assert not report.exists()


@pytest.mark.parametrize("jobs", [True, 0, 5, 1.5])
def test_official_staging_rejects_invalid_concurrency(jobs, monkeypatch):
    monkeypatch.setattr(staging.sys, "platform", "win32")
    with pytest.raises(ValueError, match="jobs"):
        staging.stage(Path("D:/unused"), Path("D:/unused.json"), jobs=jobs)
