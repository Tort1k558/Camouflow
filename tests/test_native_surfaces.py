import copy
import hashlib
import json
import struct
import sys
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from scripts import verify_native_surfaces as surfaces
from scripts.verify_native_canvas import ERRORS_EXPECTED, GEOMETRY_EXPECTED


def observation(digest="a", cross=None):
    rows = {}
    for name in surfaces.CONTEXTS:
        value = (cross if name == "cross_origin_frame" and cross else digest) * 64
        worker = name not in surfaces.DOCUMENT_CONTEXTS
        canvas = {key: value for key in ("pixels", "repeat", "blob", "htmlBlob", "htmlDataUrl")}
        canvas.update(htmlCapture=None if worker else True, geometry=copy.deepcopy(GEOMETRY_EXPECTED),
                      errors=copy.deepcopy(ERRORS_EXPECTED))
        if worker:
            canvas.update(htmlBlob=None, htmlDataUrl=None)
            audio = {"available": False, "reason": "API unavailable"}
        else:
            samples = [0x3e800000 + int(value[0], 16) * 2] * 4096
            sample_hash = hashlib.sha256(struct.pack("<4096I", *samples)).hexdigest()
            silent_hash = hashlib.sha256(bytes(4096 * 4)).hexdigest()
            signal = {"hash": sample_hash, "copiedHash": sample_hash, "rightHash": sample_hash,
                "sampleBits": samples, "renderMilliseconds": 1.0,
                "finite": True, "silence": None, "signal": True, "eventSameBuffer": True,
                "liveMutation": True, "copyFromSeesMutation": True, "copyToSeesMutation": True,
                "invalidChannel": "IndexSizeError", "sampleRate": 44100, "channels": 2,
                "frames": 4096, "closed": True}
            silence = {**signal, "hash": silent_hash, "copiedHash": silent_hash,
                       "rightHash": silent_hash, "silence": True, "signal": None,
                       "sampleBits": [0] * 4096}
            audio = {"available": True, "completionMutationVisible": True,
                     "signal": signal, "repeat": copy.deepcopy(signal),
                     "silence": silence}
        rows[name] = {"canvas": canvas, "audio": audio}
    return rows


def test_combined_baseline_protected_restart_and_isolation():
    baseline, first, second = observation(), observation("b", "c"), observation("d", "e")
    surfaces.validate_combined(first, copy.deepcopy(first), protected=True)
    surfaces.validate_isolation(baseline, first, second)


@pytest.mark.parametrize("context", sorted(surfaces.CONTEXTS))
def test_missing_context_cannot_pass(context):
    observed = observation("b", "c")
    del observed[context]
    with pytest.raises(ValueError):
        surfaces.validate_combined(observed, protected=True)


@pytest.mark.parametrize("surface", ["canvas", "audio"])
def test_same_partition_disagreement_cannot_pass(surface):
    observed = observation("b", "c")
    observed["same_origin_frame"][surface] = observation("d", "e")["document"][surface]
    with pytest.raises(ValueError, match="Same-partition"):
        surfaces.validate_combined(observed, protected=True)


def test_cross_origin_without_isolation_cannot_pass():
    with pytest.raises(ValueError, match="Cross-origin"):
        surfaces.validate_combined(observation(), protected=True)


def test_restart_drift_and_reused_profile_cannot_pass():
    first = observation("b", "c")
    with pytest.raises(ValueError, match="restart"):
        surfaces.validate_combined(first, observation("d", "e"), protected=True)
    with pytest.raises(ValueError, match="both profiles"):
        surfaces.validate_isolation(observation(), first, first)


def test_restart_durations_are_measured_not_fingerprint_identity():
    previous = observation("b", "c")
    observed = copy.deepcopy(previous)
    observed["document"]["audio"]["signal"]["renderMilliseconds"] = 2.5
    surfaces.validate_combined(observed, previous, protected=True)


def test_first_parser_script_matches_settled_policy_without_timing_identity():
    document = observation("b", "c")["document"]
    first = copy.deepcopy(document)
    first["audio"]["signal"]["renderMilliseconds"] = 100.0
    result = {"parserState": "loading", "observed": first, "initialChild": copy.deepcopy(first),
              "initialChildURL": "about:blank"}
    surfaces.validate_first_script(result, document,
                                  {"requests": 1, "executions": 1})


@pytest.mark.parametrize("mutation", ["late", "missing", "canvas", "audio", "unbound_bits", "beacon",
                                      "child_navigation", "child_missing", "child_canvas", "child_audio"])
def test_first_parser_script_rejects_late_incomplete_or_changed_policy(mutation):
    document = observation("b", "c")["document"]
    result = {"parserState": "loading", "observed": copy.deepcopy(document),
              "initialChild": copy.deepcopy(document), "initialChildURL": "about:blank"}
    counts = {"requests": 1, "executions": 1}
    if mutation == "late":
        result["parserState"] = "complete"
    elif mutation == "missing":
        del result["observed"]["audio"]
    elif mutation in {"canvas", "audio"}:
        result["observed"][mutation] = observation("d", "e")["document"][mutation]
    elif mutation == "unbound_bits":
        result["observed"]["audio"]["signal"]["sampleBits"][0] ^= 1
    elif mutation == "child_navigation":
        result["initialChildURL"] = "https://child.test/"
    elif mutation == "child_missing":
        del result["initialChild"]
    elif mutation in {"child_canvas", "child_audio"}:
        surface = mutation.removeprefix("child_")
        result["initialChild"][surface] = observation("d", "e")["document"][surface]
    else:
        counts["executions"] = 0
    with pytest.raises(ValueError):
        surfaces.validate_first_script(result, document, counts)


def test_unavailable_document_audio_cannot_pass():
    observed = observation("b", "c")
    observed["srcdoc_frame"]["audio"] = {"available": False, "reason": "API unavailable"}
    with pytest.raises(ValueError, match="all five"):
        surfaces.validate_combined(observed, protected=True)


def test_prelaunch_failure_creates_no_profile_and_no_admission(tmp_path, monkeypatch):
    executable = tmp_path / "chrome.exe"
    executable.touch()
    report = tmp_path / "failed.json"
    owned = tmp_path / "owned"
    monkeypatch.setattr(surfaces, "measure_runtime_core", lambda path: {"chrome.exe": "a" * 64})

    def reject(*args, **kwargs):
        raise ValueError("Uncompiled source")

    monkeypatch.setattr(surfaces, "validate_receipt", reject)
    monkeypatch.setattr(sys, "argv", ["probe", "--executable", str(executable),
                                      "--work-dir", str(owned), "--report", str(report)])
    assert surfaces.main() == 1
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert evidence["error"] == "Uncompiled source"
    assert evidence["privacy_admitted"] is False and evidence["passed"] is False
    assert evidence["checks"] == [] and not owned.exists()


def test_receipt_requires_dll_binding(tmp_path, monkeypatch):
    monkeypatch.setattr(surfaces, "validate_worker_receipt", lambda *args, **kwargs:
                        json.dumps({"patches": []}).encode())
    with pytest.raises(ValueError, match="every runtime core file"):
        surfaces.validate_receipt(tmp_path / "chrome.exe", {"chrome.exe": "a", "chrome.dll": "b"})


def test_surface_flags_do_not_enable_protection_in_baseline():
    assert surfaces.DOCUMENT_ARGUMENT not in surfaces.SurfaceConfiguration().launch_arguments()
    assert surfaces.DOCUMENT_ARGUMENT in surfaces.SurfaceConfiguration(probe_mode="ready").launch_arguments()


def test_owned_denial_fixture_counts_requests_and_execution_separately():
    server = surfaces.SurfaceFixtureServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    identifier = "a" * 32
    try:
        with urlopen(f"{origin}/surface-startup?id={identifier}", timeout=5) as response:
            assert b"surface-executed" in response.read()
        assert server.counts(identifier) == {"requests": 1, "executions": 0}
        with urlopen(f"{origin}/surface-executed?id={identifier}", timeout=5) as response:
            assert response.status == 204
        assert server.counts(identifier) == {"requests": 1, "executions": 1}
        with pytest.raises(HTTPError) as failure:
            urlopen(f"{origin}/surface-startup?id=invalid", timeout=5)
        assert failure.value.code == 400
        assert server.counts("invalid") == {"requests": 0, "executions": 0}
        first_identifier = "b" * 32
        with urlopen(f"{origin}/surface-first-script?id={first_identifier}", timeout=5) as response:
            body = response.read().decode("utf-8")
            assert "const glintParserState = document.readyState;" in body
            assert f"({surfaces.COMBINED_READ})()" in body
            assert "glintFirstChild.contentWindow.eval(" in body
            assert "glintInitialChildURL" in body
            assert "window.__glintFirstSurfaceRead" in body
        assert server.counts(first_identifier) == {"requests": 1, "executions": 0}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_profile_identity_candidate_keeps_privacy_api_and_prepares_native_lifecycle_fixtures():
    from scripts.verify_native_document_drafts import patch_paths
    from scripts.verify_native_profile_identity_draft import PATCH, PATHS, reference_vectors

    text = PATCH.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == PATHS
    assert text.count("+TEST(NativeProfileIdentityKeyTest,") == 7
    assert text.count("+TEST_F(NativePrivacyKeyServiceTest,") == 4
    assert 'std::string_view("canvas\\0audio", 12)' in text
    assert "+  if (!IsNativePrivacyContextReady(context)) {" in text
    assert '+  message.push_back(\'\\0\');' in text
    assert '+  std::string message("Glint/profile-identity/v1");' in text
    assert all(value in text for value in reference_vectors().values())


def test_immutable_identity_mode_candidate_preserves_default_and_rejects_invalid_modes():
    from scripts.verify_native_document_drafts import patch_paths
    from scripts.verify_native_profile_identity_draft import MODE_FIXTURES, MODE_PATCH, MODE_PATHS

    text = MODE_PATCH.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == MODE_PATHS
    assert text.count("+TEST_F(NativePrivacyKeyServiceTest,") == len(MODE_FIXTURES)
    assert all(name in text for name in MODE_FIXTURES)
    assert "+  const content::NativeFingerprintDerivationMode derivation_mode_;" in text
    assert "kPartitionedPrivacy" in text
    assert "return key_->Derive(trusted_partition, surface);" in text
    assert "return key_->DeriveProfileIdentity(trusted_partition, surface);" in text
    assert text.count("IsValidNativeFingerprintDerivationMode(derivation_mode_)") == 2
    assert "+  struct Owner : base::SupportsUserData {};" in text


def test_identity_context_fixtures_cover_owner_lifecycle_and_incognito_without_source_edits():
    from scripts.verify_native_document_drafts import patch_paths
    from scripts.verify_native_profile_identity_draft import (
        CONTEXT_FIXTURES, CONTEXT_PATCH, CONTEXT_PATH,
    )

    text = CONTEXT_PATCH.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == {CONTEXT_PATH}
    assert text.count("+TEST_F(NativePrivacyBrowserContextTest,") == len(CONTEXT_FIXTURES)
    assert all(name in text for name in CONTEXT_FIXTURES)
    assert "+  context->NotifyWillBeDestroyed();" in text
    assert "+  first->set_is_off_the_record(true);" in text
    assert "+  second->set_is_off_the_record(true);" in text


def test_identity_transport_v3_carries_mode_without_weakening_partition_validation():
    from scripts.verify_native_document_drafts import patch_paths
    from scripts.verify_native_profile_identity_draft import (
        TRANSPORT_FIXTURES, TRANSPORT_PATCH, TRANSPORT_PATHS,
    )

    text = TRANSPORT_PATCH.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == TRANSPORT_PATHS
    assert "+constexpr uint32_t kSurfacePolicyVersion = 3;" in text
    assert "+  uint32 identity_mode;" in text
    assert "wire->identity_mode = static_cast<uint32_t>(policy.identity_mode);" in text
    added = " ".join(line[1:].strip() for line in text.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))
    assert "owned.identity_mode = static_cast<SurfaceIdentityMode>(incoming.identity_mode);" in added
    assert added.count("content::DeriveNativeSelectedFingerprintKey( context,") == 4
    assert "IsValidSurfaceIdentityMode" in text
    assert all(name in text for names in TRANSPORT_FIXTURES.values() for name in names)


def test_identity_blink_handoff_fixtures_cover_first_script_clone_and_rejection():
    from scripts.verify_native_document_drafts import patch_paths
    from scripts.verify_native_profile_identity_draft import HANDOFF_FIXTURES, HANDOFF_PATCH

    text = HANDOFF_PATCH.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == set(HANDOFF_FIXTURES)
    assert text.count("+TEST_P(DocumentLoaderTest,") == 3
    assert text.count("+TEST_F(GlintWorkerSurfaceThreadTest,") == 3
    assert all(name in text for names in HANDOFF_FIXTURES.values() for name in names)
    assert "+    EXPECT_TRUE(client.titles[i].empty());" in text
    assert "clone->glint_document_surface_policy->policy.identity_mode" in text
