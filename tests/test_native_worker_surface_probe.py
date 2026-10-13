from __future__ import annotations

import copy
import hashlib
import json

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
