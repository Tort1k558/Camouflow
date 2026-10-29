import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from scripts import verify_native_privacy_batch as batch


@pytest.fixture
def owned(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    source = workspace / "chromium/src"
    output = source / "out/CamouFlowNative"
    output.mkdir(parents=True)
    candidate = batch.build.load_candidate("upstream-156")
    args = (batch.ROOT / "native/args.gn").read_bytes()
    (output / "args.gn").write_bytes(args)
    core = {"chrome.exe": "a" * 64}
    receipt = {"owned": True, "runtime_core_sha256_measured": core,
               "binary_sha256_measured": core["chrome.exe"], "args_sha256": hashlib.sha256(args).hexdigest(),
               "local_windows_toolchain_sha256": "a" * 64}
    (output / "camouflow-build.json").write_text(json.dumps(receipt), encoding="utf-8")
    watched = tmp_path / "watched.py"
    watched.write_bytes(b"owned\n")
    state = {"builds": [], "cases": [], "source_calls": 0, "env_calls": 0, "sdk_calls": 0,
             "failure": None, "executed": False, "inputs": {watched}}
    monkeypatch.setattr(batch.sys, "platform", "win32")
    monkeypatch.setattr(batch, "ARTIFACT_VOLUME", tmp_path.drive.upper())
    monkeypatch.setattr(batch.build, "preflight", lambda *args, **kwargs: None)
    monkeypatch.setattr(batch.build, "candidate_workspace", lambda *args, **kwargs: None)
    monkeypatch.setattr(batch.units, "require_idle_builder", lambda *args: None)
    monkeypatch.setattr(batch, "source_inputs", lambda selected: set(state["inputs"]))

    def environment(*args):
        state["env_calls"] += 1
        return {"GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": "a" * 64}

    def sources(*args):
        state["source_calls"] += 1
        if state["failure"] == "invalid-source":
            raise ValueError("Unrecognized source changes")
        rows = [{"name": row["file"], "sha256": row["sha256"]} for row in candidate["manifest"]["patches"]]
        if state["failure"] == "late-source" and state["executed"]:
            rows[0]["sha256"] = "b" * 64
        return rows

    def sdk(*args):
        state["sdk_calls"] += 1
        return {"GLINT_LOCAL_WINDOWS_TOOLCHAIN_SHA256": ("b" if state["failure"] == "late-sdk" else "a") * 64}

    def validate(value, lock, *, candidate):
        assert lock == candidate["lock"]
        if state["failure"] == "invalid-receipt":
            raise ValueError("Invalid compiled receipt")
        assert value["owned"] is True

    def core_sample(*args):
        return {"chrome.exe": ("b" if state["failure"] == "late-core" and state["executed"] else "a") * 64}

    monkeypatch.setattr(batch.units, "verification_environment", environment)
    monkeypatch.setattr(batch.units, "verified_source_chain", sources)
    monkeypatch.setattr(batch.build, "local_windows_toolchain", sdk)
    monkeypatch.setattr(batch, "validate_build_receipt", validate)
    monkeypatch.setattr(batch, "measure_runtime_core", core_sample)
    monkeypatch.setattr(batch.build, "check_patch_dependencies", lambda *args: None)
    monkeypatch.setattr(batch.build, "depot_command", lambda *args: ["autoninja"])
    for name, relative in batch.units.DELIVERY_SOURCE_FILES.items():
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((batch.ROOT / "native/drafts/document_delivery" / name).read_bytes())

    def run(command, **kwargs):
        assert kwargs["env"]["TEMP"] == kwargs["env"]["TMP"] == kwargs["env"]["TMPDIR"]
        assert Path(kwargs["env"]["TEMP"]).is_dir()
        with pytest.raises(ValueError, match="owns this workspace"):
            with batch.build.workspace_lock(workspace):
                pytest.fail("Batch released its owner lock")
        kwargs["stdout"].write("Owned subprocess output\n")
        if command[0] == "autoninja":
            state["builds"].append(command)
            if state["failure"] == "compiler":
                raise subprocess.CalledProcessError(1, command)
            for name in command[5:]:
                (output / (name + ".exe")).write_bytes(name.encode("ascii"))
            return subprocess.CompletedProcess(command, 0)
        results = Path(next(arg.removeprefix("--gtest_output=json:") for arg in command if arg.startswith("--gtest_output=")))
        target = results.name.removesuffix("-tests.json")
        state["cases"].append(target)
        assert kwargs["timeout"] == 300
        assert set(command[1].removeprefix("--gtest_filter=").split(":")) == {
            suite + "." + name for suite, names in batch.units.required_tests(target).items() for name in names}
        state["executed"] = True
        if state["failure"] == "timeout" and target == "keys":
            raise subprocess.TimeoutExpired(command, 300)
        required = batch.units.required_tests(target)
        result = {"tests": sum(map(len, required.values())), "failures": 0, "disabled": 0,
                  "testsuites": [{"name": suite, "testsuite": [
                      {"name": name, "status": "RUN", "result": "COMPLETED"} for name in sorted(names)]}
                      for suite, names in required.items()]}
        if state["failure"] == "empty-results" and target == "keys":
            result.update(tests=0, testsuites=[])
        if state["failure"] == "late-input":
            watched.write_bytes(b"changed\n")
        if state["failure"] == "added-input":
            added = tmp_path / "added.py"
            added.write_bytes(b"new\n")
            state["inputs"].add(added)
        if state["failure"] == "late-binary":
            Path(command[0]).write_bytes(b"changed executable")
        if state["failure"] == "late-receipt":
            (output / "camouflow-build.json").write_bytes(b"changed receipt")
        if state["failure"] == "late-args":
            (output / "args.gn").write_bytes(b"changed GN arguments")
        if state["failure"] == "late-delivery":
            (source / batch.units.DELIVERY_SOURCE_FILES["privacy_worker_service.cc"]).write_bytes(b"changed delivery")
        results.write_text(json.dumps(result), encoding="utf-8")
        return subprocess.CompletedProcess(command, 1 if state["failure"] == "native-failure" and target == "keys" else 0)

    monkeypatch.setattr(batch.subprocess, "run", run)
    return SimpleNamespace(workspace=workspace, reports=tmp_path / "reports", state=state)


def test_batch_audio_math_reuses_blink_binary_and_requires_all_context_cases(owned):
    result = batch.verify(owned.workspace, owned.reports, ("worker-handoff", "audio-math"),
                          candidate_name="upstream-156", local_toolchain=True)
    assert result["passed"] and result["postguards_passed"]
    assert owned.state["builds"][0][5:] == ["blink_unittests"]
    assert owned.state["cases"] == ["worker-handoff", "audio-math"]
    assert len(batch.units.required_tests("audio-math")["OfflineAudioContextTest"]) == 12
    assert not result["privacy_admitted"] and not result["production_admitted"]


def test_audio_math_single_verifier_requires_explicit_candidate_before_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(batch.build, "preflight", lambda *args, **kwargs: pytest.fail("Unexpected preflight"))
    with pytest.raises(ValueError, match="explicit upstream-156"):
        batch.units.verify(tmp_path, tmp_path / "report.json", target="audio-math")


def test_audio_math_requires_selected_patch_and_matches_native_test_inventory(tmp_path):
    import re

    candidate = batch.build.load_candidate("upstream-156")
    patches = [{"name": row["file"]} for row in candidate["manifest"]["patches"]]
    assert batch.units.require_target_sources(tmp_path, patches, "audio-math") is None
    with pytest.raises(ValueError, match="patches are required"):
        batch.units.require_target_sources(tmp_path,
            [row for row in patches if row["name"] != "0068-native-audio-math-fixture-readiness.patch"], "audio-math")
    patch = "\n".join((candidate["directory"] / "patches" / row["name"]).read_text(encoding="utf-8-sig")
                      for row in patches if row["name"] in {
                          "0067-native-audio-math-context-candidate.patch", "0068-native-audio-math-fixture-readiness.patch"})
    resulting_lines = "\n".join(line[1:] for line in patch.splitlines()
                                if line.startswith(("+", " ")) and not line.startswith("+++"))
    names = set(re.findall(r"TEST_F\(OfflineAudioContextTest,\s*(GlintMath\w+)\)", resulting_lines))
    assert names == batch.units.required_tests("audio-math")["OfflineAudioContextTest"]


def test_screen_metrics_requires_explicit_candidate_before_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(batch.build, "preflight", lambda *args, **kwargs: pytest.fail("Unexpected preflight"))
    with pytest.raises(ValueError, match="explicit upstream-156"):
        batch.units.verify(tmp_path, tmp_path / "report.json", target="screen-metrics")


def test_screen_metrics_native_gate_matches_selected_source_inventory(tmp_path):
    import re

    candidate = batch.build.load_candidate("upstream-156")
    patches = [{"name": row["file"]} for row in candidate["manifest"]["patches"]]
    name = "0069-native-logical-screen-inheritance.patch"
    assert batch.units.require_target_sources(tmp_path, patches, "screen-metrics") is None
    with pytest.raises(ValueError, match="patches are required"):
        batch.units.require_target_sources(tmp_path, [row for row in patches if row["name"] != name], "screen-metrics")
    raw = (candidate["directory"] / "patches" / name).read_text(encoding="utf-8-sig")
    added = "\n".join(line[1:] for line in raw.splitlines() if line.startswith("+") and not line.startswith("+++"))
    cases = set(re.findall(r"TEST\(GlintLogicalScreenTest,\s*(\w+)\)", added))
    assert cases == batch.units.required_tests("screen-metrics")["GlintLogicalScreenTest"]
    assert len(cases) == 9
    assert batch.units.unit_binary_target("screen-metrics") == "blink_common_unittests"


def test_batch_screen_metrics_builds_common_binary_without_claiming_browser_admission(owned):
    result = batch.verify(owned.workspace, owned.reports, ("screen-metrics",),
                          candidate_name="upstream-156", local_toolchain=True)
    assert result["passed"] and result["postguards_passed"]
    assert owned.state["builds"][0][5:] == ["blink_common_unittests"]
    assert owned.state["cases"] == ["screen-metrics"]
    assert not result["browser_runtime_verified"] and not result["privacy_admitted"]


def test_batch_builds_shared_executables_once_and_checks_final_source_sdk_state(owned):
    result = batch.verify(owned.workspace, owned.reports, ("keys", "document-partition", "contexts"),
                          candidate_name="upstream-156", local_toolchain=True)
    assert result["passed"] and result["postguards_passed"]
    assert result["source_chromium_revision"] == batch.build.load_candidate("upstream-156")["lock"]["chromium_revision"]
    assert result["chromium_version"] == batch.build.load_candidate("upstream-156")["lock"]["chromium_version"]
    assert len(owned.state["builds"]) == result["build_invocations"] == 1
    assert owned.state["builds"][0][1:] == ["-C", "out/CamouFlowNative", "-j", "4", "camouflow_native_privacy_unittests", "content_unittests"]
    assert owned.state["cases"] == ["keys", "document-partition", "contexts"]
    assert owned.state["source_calls"] == 2 and owned.state["env_calls"] == owned.state["sdk_calls"] == 1
    assert json.loads((owned.reports / "batch.json").read_bytes()) == result
    assert all(row["native_cases_passed"] for row in result["targets"])
    assert result["privacy_admitted"] is result["production_admitted"] is result["browser_runtime_verified"] is False
    with pytest.raises(ValueError, match="fresh"):
        batch.verify(owned.workspace, owned.reports, ("keys",), candidate_name="upstream-156")


@pytest.mark.parametrize("failure", ["native-failure", "empty-results", "timeout"])
def test_batch_collects_later_targets_after_an_individual_failure(owned, failure):
    owned.state["failure"] = failure
    result = batch.verify(owned.workspace, owned.reports, ("keys", "document-partition", "contexts"), candidate_name="upstream-156")
    assert not result["passed"] and result["postguards_passed"]
    assert owned.state["cases"] == ["keys", "document-partition", "contexts"]
    assert [row["native_cases_passed"] for row in result["targets"]] == [False, True, True]
    assert len(owned.state["builds"]) == 1 and result["targets"][0]["error"]


@pytest.mark.parametrize("failure", ["late-source", "late-sdk", "late-core", "late-input", "added-input", "late-binary", "late-receipt", "late-args", "late-delivery"])
def test_batch_rejects_mutations_in_shared_postguards(owned, failure):
    owned.state["failure"] = failure
    result = batch.verify(owned.workspace, owned.reports, ("keys", "delivery"),
                          candidate_name="upstream-156", local_toolchain=True)
    assert not result["passed"] and not result["postguards_passed"] and result["postguard_error"]
    assert all(row["native_cases_passed"] for row in result["targets"])


@pytest.mark.parametrize("failure", ["compiler", "invalid-source", "invalid-receipt"])
def test_batch_never_starts_cases_after_failed_shared_preconditions(owned, failure):
    owned.state["failure"] = failure
    result = batch.verify(owned.workspace, owned.reports, ("keys",), candidate_name="upstream-156")
    assert not result["passed"] and result["error"] and not owned.state["cases"]
    assert len(owned.state["builds"]) == (1 if failure == "compiler" else 0)


@pytest.mark.parametrize("targets", [(), ("unknown",), ("keys", "keys"), "keys", (True,)])
def test_batch_requires_distinct_explicit_supported_targets(owned, targets):
    with pytest.raises(ValueError, match="distinct"):
        batch.verify(owned.workspace, owned.reports, targets, candidate_name="upstream-156")
    assert not owned.reports.exists() and not owned.state["builds"]


@pytest.mark.parametrize("jobs,timeout", [(True, 300), (0, 300), (5, 300), (4, 0), (4, 901), (4, True)])
def test_batch_rejects_invalid_resource_and_deadline_limits(owned, jobs, timeout):
    with pytest.raises(ValueError):
        batch.verify(owned.workspace, owned.reports, ("keys",), candidate_name="upstream-156", jobs=jobs, timeout_seconds=timeout)
    assert not owned.reports.exists() and not owned.state["builds"]
