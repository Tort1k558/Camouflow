from __future__ import annotations

import hashlib
import json

import pytest

from scripts import verify_native_worker_startup as startup


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
