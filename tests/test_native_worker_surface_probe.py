from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import verify_native_worker_startup as startup


def nested_observation(mode):
    if mode == "unavailable":
        return {"status": "worker-error", "executions": {"parent": 0, "child": 0},
                "script_requests": {"parent": 1, "child": 0}}
    return {"status": "reply", "id": "owned-child", "executions": {"parent": 1, "child": 1},
            "script_requests": {"parent": 1, "child": 1}}


@pytest.mark.parametrize("mode", startup.PHASES)
def test_nested_worker_validator_accepts_exact_calibrated_counts(mode):
    startup.validate_nested_observation(nested_observation(mode), mode=mode, child_identifier="owned-child")


@pytest.mark.parametrize("mode", startup.PHASES)
@pytest.mark.parametrize("field", ["executions", "script_requests"])
@pytest.mark.parametrize("counter", ["parent", "child"])
def test_nested_worker_validator_rejects_boolean_or_missing_counters(mode, field, counter):
    observed = nested_observation(mode)
    for value in (True, -1, "1", None):
        invalid = copy.deepcopy(observed)
        invalid[field][counter] = value
        with pytest.raises(ValueError):
            startup.validate_nested_observation(invalid, mode=mode, child_identifier="owned-child")
    del observed[field][counter]
    with pytest.raises(ValueError):
        startup.validate_nested_observation(observed, mode=mode, child_identifier="owned-child")


@pytest.mark.parametrize("status", ["timeout", "nested-worker-error", "reply"])
def test_nested_unavailable_policy_never_accepts_timeout_or_child_reply(status):
    observed = nested_observation("unavailable")
    observed["status"] = status
    with pytest.raises(ValueError):
        startup.validate_nested_observation(observed, mode="unavailable", child_identifier="owned-child")


@pytest.mark.parametrize("field,counter", [("executions", "parent"), ("executions", "child"),
                                          ("script_requests", "child")])
def test_nested_unavailable_policy_rejects_any_body_execution_or_child_fetch(field, counter):
    observed = nested_observation("unavailable")
    observed[field][counter] = 1
    with pytest.raises(ValueError):
        startup.validate_nested_observation(observed, mode="unavailable", child_identifier="owned-child")


@pytest.mark.parametrize("field,counter", [("executions", "parent"), ("executions", "child"),
                                          ("script_requests", "parent"), ("script_requests", "child")])
def test_nested_ready_policy_rejects_duplicate_or_missing_execution_and_fetch(field, counter):
    for count in (0, 2):
        observed = nested_observation("ready")
        observed[field][counter] = count
        with pytest.raises(ValueError):
            startup.validate_nested_observation(observed, mode="ready", child_identifier="owned-child")


def test_nested_worker_validator_rejects_reply_from_parent_or_other_worker():
    observed = nested_observation("ready")
    observed["id"] = "owned-parent"
    with pytest.raises(ValueError):
        startup.validate_nested_observation(observed, mode="ready", child_identifier="owned-child")


@pytest.mark.parametrize("parent,child", startup.NESTED_CASES)
def test_nested_worker_source_preserves_explicit_types_and_independent_child_identity(parent, child):
    source = startup.nested_worker_source("owned-parent", "owned-child", parent, child)
    assert source.startswith("import {moduleMarker}") is (parent == "module")
    assert 'id=owned-child&type=' + child in source
    assert 'type: ' + json.dumps(child) in source
    assert "encodeURIComponent(\"owned-parent\")" in source
    assert "child.terminate()" in source
    assert "self.postMessage({id: event.data.id})" in source


@pytest.mark.parametrize("arguments", [("same", "same", "classic", "classic"),
                                       ("", "child", "classic", "classic"),
                                       ("parent", "child", "unknown", "classic")])
def test_nested_worker_source_rejects_ambiguous_inputs(arguments):
    with pytest.raises(ValueError):
        startup.nested_worker_source(*arguments)


@pytest.mark.parametrize("mode", ["baseline", "ready", "unavailable"])
def test_surface_probe_does_not_request_canvas_fallback(mode):
    arguments = startup.StartupConfiguration(probe_mode=mode, bootstrap_policy="surfaces").launch_arguments()
    assert startup.BOOTSTRAP_ARGUMENT not in arguments
    assert (startup.SURFACE_BOOTSTRAP_ARGUMENT in arguments) is (mode != "baseline")
    assert (startup.KEY_ARGUMENT in arguments) is (mode == "ready")


def test_probe_rejects_unknown_policy():
    with pytest.raises(ValueError):
        startup.StartupConfiguration(bootstrap_policy="unknown").launch_arguments()
    with pytest.raises(ValueError):
        startup.validate_receipt(None, {}, bootstrap_policy="unknown")


@pytest.mark.parametrize("state", ["absent", "unreceipted", "wrong-hash", "matching"])
def test_surface_receipt_requires_registered_compiled_patch(tmp_path, monkeypatch, state):
    root = tmp_path / "public"
    patches = root / "native/patches"
    patches.mkdir(parents=True)
    entries = []
    for number in range(15, 28):
        original, = (startup.ROOT / "native/patches").glob(f"{number:04d}-*.patch")
        path = patches / original.name
        path.write_bytes(original.read_bytes())
        entries.append({"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if state != "absent":
        patch = patches / startup.SURFACE_PATCH
        patch.write_bytes(b"controlled fixture; not actual compiled evidence\n")
        if state != "unreceipted":
            entries.append({"name": patch.name, "sha256": "bad" if state == "wrong-hash"
                            else hashlib.sha256(patch.read_bytes()).hexdigest()})
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"controlled fixture")
    receipt = executable.parent / "camouflow-build.json"
    raw = json.dumps({"chromium_revision": startup.LOCK["chromium_revision"],
                      "binary_sha256_measured": "a" * 64, "patches": entries}).encode()
    receipt.write_bytes(raw)
    monkeypatch.setattr(startup, "ROOT", root)
    if state == "matching":
        assert startup.validate_receipt(executable, {"chrome.exe": "a" * 64}, bootstrap_policy="surfaces") == raw
    else:
        with pytest.raises(ValueError):
            startup.validate_receipt(executable, {"chrome.exe": "a" * 64}, bootstrap_policy="surfaces")


CANDIDATE_RECEIPT_CASES = ("worker-canvas", "worker-surfaces", "surfaces-privacy", "surfaces-identity", "gpu-privacy", "gpu-identity")


def _candidate_receipt_fixture(tmp_path):
    from scripts import native_build as build

    candidate = build.load_candidate("upstream-156")
    lock = candidate["lock"]
    executable = tmp_path / "chrome.exe"
    executable.write_bytes(b"owned fake executable; validator only, no process launch")
    core = {"chrome.exe": "a" * 64, "chrome.dll": "b" * 64, "chrome_elf.dll": "c" * 64}
    patches = [{"name": row["file"], "sha256": row["sha256"],
                **({"repository": "v8", "revision": candidate["manifest"]["dependencies"]["v8"]["revision"]}
                   if repository == "v8" else {})}
               for repository in (".", "v8") for row in candidate["manifest"]["patches"]
               if row.get("directory", ".") == repository]
    arguments = (build.ROOT / "native/args.gn").read_bytes()
    (tmp_path / "args.gn").write_bytes(arguments)
    receipt = {"schema": 1, "platform": "win32", "binary": "chrome.exe", "native_version": lock["native_version"],
               "chromium_revision": lock["chromium_revision"], "depot_tools_revision": lock["depot_tools_revision"],
               "candidate_manifest_sha256": candidate["manifest_sha256"], "patches": patches,
               "binary_sha256_measured": core["chrome.exe"], "runtime_core_sha256_measured": dict(core),
               "args_sha256": hashlib.sha256(arguments).hexdigest()}
    return executable, core, receipt


def _validate_candidate_receipt(case, executable, core, candidate="upstream-156"):
    from scripts import verify_native_surfaces as surfaces
    from scripts import verify_native_gpu_readback as gpu

    selected = {} if candidate is None else {"candidate_name": candidate}
    if case.startswith("worker-"):
        return startup.validate_receipt(executable, core, bootstrap_policy=case.split("-", 1)[1], **selected)
    mode = "profile-identity" if case.endswith("identity") else "partitioned-privacy"
    module = surfaces if case.startswith("surfaces-") else gpu
    return module.validate_receipt(executable, core, derivation_mode=mode, **selected)


@pytest.mark.parametrize("case", CANDIDATE_RECEIPT_CASES)
@pytest.mark.parametrize("mutation", [None, "crlf", "manifest", "first-patch-hash", "missing-tail", "reordered",
    "v8-revision", "executable-hash", "dll-hash", "partial-core", "gn-hash", "rehashed-recipe",
    "missing-args", "oversized-args", "malformed", "oversized-receipt", "legacy-without-explicit",
    "unknown-candidate", "wrong-platform", "wrong-native-version", "wrong-chromium",
    "receipt-grows-after-stat", "args-grow-after-stat"])
def test_candidate_receipt_binding(tmp_path, monkeypatch, case, mutation):
    executable, core, receipt = _candidate_receipt_fixture(tmp_path)
    arguments = tmp_path / "args.gn"
    if mutation == "manifest":
        receipt["candidate_manifest_sha256"] = "d" * 64
    elif mutation == "first-patch-hash":
        receipt["patches"][0]["sha256"] = "d" * 64
    elif mutation == "missing-tail":
        receipt["patches"].pop()
    elif mutation == "reordered":
        receipt["patches"][0], receipt["patches"][1] = receipt["patches"][1], receipt["patches"][0]
    elif mutation == "v8-revision":
        next(row for row in receipt["patches"] if row.get("repository") == "v8")["revision"] = "0" * 40
    elif mutation == "executable-hash":
        receipt["binary_sha256_measured"] = "d" * 64
    elif mutation == "dll-hash":
        receipt["runtime_core_sha256_measured"]["chrome.dll"] = "d" * 64
    elif mutation == "partial-core":
        core.pop("chrome.dll")
        receipt["runtime_core_sha256_measured"] = dict(core)
    elif mutation == "gn-hash":
        receipt["args_sha256"] = "d" * 64
    elif mutation in {"crlf", "rehashed-recipe", "oversized-args"}:
        if mutation == "crlf":
            arguments.write_bytes(arguments.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        elif mutation == "rehashed-recipe":
            arguments.write_bytes(arguments.read_bytes() + b"\n# unselected recipe\n")
        else:
            arguments.write_bytes(b" " * 65537)
        receipt["args_sha256"] = hashlib.sha256(arguments.read_bytes()).hexdigest()
    elif mutation == "missing-args":
        arguments.unlink()
    elif mutation == "wrong-platform":
        receipt["platform"] = "linux"
    elif mutation == "wrong-native-version":
        receipt["native_version"] = "0.0.0"
    elif mutation == "wrong-chromium":
        receipt["chromium_revision"] = "0" * 40
    elif mutation == "args-grow-after-stat":
        arguments.write_bytes(b" " * 65537)
        receipt["args_sha256"] = hashlib.sha256(arguments.read_bytes()).hexdigest()
    if mutation == "receipt-grows-after-stat":
        receipt["owned_padding"] = "x" * (8 * 1024**2)
    raw = json.dumps(receipt).encode("utf-8")
    if mutation == "malformed":
        raw = b"{"
    elif mutation == "oversized-receipt":
        raw = b" " * (8 * 1024**2 + 1)
    (tmp_path / "camouflow-build.json").write_bytes(raw)
    reads = []
    if mutation in {"receipt-grows-after-stat", "args-grow-after-stat"}:
        target = arguments if mutation == "args-grow-after-stat" else tmp_path / "camouflow-build.json"
        original_stat, original_open = Path.stat, Path.open
        def stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            return SimpleNamespace(st_size=1, st_mode=result.st_mode) if path == target else result
        class ObservedRead:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def read(self, size=-1):
                reads.append(size)
                return self.stream.read(size)
        def opened(path, mode="r", *args, **kwargs):
            stream = original_open(path, mode, *args, **kwargs)
            return ObservedRead(stream) if path == target and mode == "rb" else stream
        monkeypatch.setattr(Path, "stat", stat)
        monkeypatch.setattr(Path, "open", opened)
    candidate = None if mutation == "legacy-without-explicit" else ("unknown" if mutation == "unknown-candidate" else "upstream-156")
    if mutation in {None, "crlf"}:
        assert _validate_candidate_receipt(case, executable, core, candidate) == raw
    else:
        with pytest.raises((ValueError, OSError)):
            _validate_candidate_receipt(case, executable, core, candidate)
    if mutation in {"receipt-grows-after-stat", "args-grow-after-stat"}:
        assert reads == [65537 if mutation == "args-grow-after-stat" else 8 * 1024**2 + 1]
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted([
        "chrome.exe", "camouflow-build.json", *([] if mutation == "missing-args" else ["args.gn"])])
