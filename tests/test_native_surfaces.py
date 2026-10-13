import copy
import hashlib
import json
import struct
import sys
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from scripts import verify_native_surfaces as surfaces
from scripts.verify_native_canvas import ERRORS_EXPECTED, GEOMETRY_EXPECTED


def denial_observation():
    frame = {"id": "owned-frame", "loaderId": "original-loader", "url": "about:blank"}
    return {"url": "http://127.0.0.1/owned", "counts": {"requests": 1, "executions": 0},
        "before_frame": frame, "after_frame": copy.deepcopy(frame),
        "before_history": {"currentIndex": 0, "entries": [{"url": "about:blank"}]},
        "after_history": {"currentIndex": 0, "entries": [{"url": "about:blank"}]},
        "events": [
            {"method": "Network.requestWillBeSent", "requestId": "owned-request", "type": "Document",
             "frameId": "owned-frame", "url": "http://127.0.0.1/owned"},
            {"method": "Network.loadingFailed", "requestId": "owned-request", "type": "Document",
             "errorText": "net::ERR_ABORTED", "canceled": True}]}


def test_document_denial_requires_exact_document_abort_and_unchanged_commit():
    surfaces.validate_denial_navigation(denial_observation(), denied=True)


@pytest.mark.parametrize("mutation", ["wrong_request", "fetch_abort", "wrong_error", "not_canceled",
    "foreign_frame", "loader_changed", "url_changed", "history_changed", "commit_event",
    "missing_abort", "script_executed", "not_fetched", "boolean_count", "overflow"])
def test_document_denial_cannot_pass_with_incomplete_or_unrelated_evidence(mutation):
    observed = denial_observation()
    if mutation == "wrong_request":
        observed["events"][1]["requestId"] = "unrelated"
    elif mutation == "fetch_abort":
        observed["events"][1]["type"] = "Fetch"
    elif mutation == "wrong_error":
        observed["events"][1]["errorText"] = "net::ERR_FAILED"
    elif mutation == "not_canceled":
        observed["events"][1]["canceled"] = False
    elif mutation == "foreign_frame":
        observed["events"][0]["frameId"] = "unrelated"
    elif mutation == "loader_changed":
        observed["after_frame"]["loaderId"] = "new-loader"
    elif mutation == "url_changed":
        observed["after_frame"]["url"] = observed["url"]
    elif mutation == "history_changed":
        observed["after_history"]["currentIndex"] = 1
    elif mutation == "commit_event":
        observed["events"].append({"method": "Page.frameNavigated", "url": observed["url"]})
    elif mutation == "missing_abort":
        observed["events"].pop()
    elif mutation == "script_executed":
        observed["counts"]["executions"] = 1
    elif mutation == "not_fetched":
        observed["counts"]["requests"] = 0
    elif mutation == "boolean_count":
        observed["counts"]["requests"] = True
    elif mutation == "overflow":
        observed["events"].append({"method": "overflow"})
    with pytest.raises(ValueError):
        surfaces.validate_denial_navigation(observed, denied=True)


def test_document_denial_calibration_requires_executed_committed_control():
    observed = denial_observation()
    observed["counts"]["executions"] = 1
    observed["after_frame"]["url"] = observed["url"]
    surfaces.validate_denial_navigation(observed, denied=False)
    observed["after_frame"]["url"] = "about:blank"
    with pytest.raises(ValueError, match="did not commit"):
        surfaces.validate_denial_navigation(observed, denied=False)


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


@pytest.mark.parametrize("mode", surfaces.DERIVATION_MODES)
@pytest.mark.parametrize("failure", [None, "start-a", "start-b", "survivor-changed", "restart-changed", "cleanup",
                                    "missing-argument", "duplicate-mode"])
def test_concurrent_profile_probe_requires_stability_and_closes_both_owners(monkeypatch, mode, failure):
    import asyncio
    from types import SimpleNamespace

    events = []
    class Runtime:
        def __init__(self, name):
            self.name = name
            self.context = None
            self.starts = self.closes = 0
            self.configuration = surfaces.SurfaceConfiguration(probe_mode="ready", derivation_mode=mode,
                disabled_features_argument="--disable-features=Example",
                ignored_driver_argument="--disable-features=Example,ThirdPartyStoragePartitioning")

        async def start(self, **kwargs):
            self.starts += 1
            events.append(("start", self.name))
            if failure == ("start-a" if self.name == "profile-a" else "start-b"):
                raise ValueError("owned startup failure")
            self.context = SimpleNamespace(name=self.name)

        async def close(self):
            self.closes += 1
            events.append(("close", self.name))
            if failure == "cleanup" and self.name == "profile-a":
                raise ValueError("owned cleanup failure")
            self.context = None

    profiles = {name: Runtime(name) for name in ("profile-a", "profile-b")}
    results = {"baseline": observation(),
               "profile-a": observation("b", "c" if mode == "partitioned-privacy" else "b"),
               "profile-b": observation("d", "e" if mode == "partitioned-privacy" else "d")}
    async def observe(context, *args, **kwargs):
        if ((failure == "survivor-changed" and profiles["profile-a"].context is None)
                or (failure == "restart-changed" and profiles[context.name].starts > 1)):
            return observation("f", "a" if mode == "partitioned-privacy" else "f")
        return copy.deepcopy(results[context.name])
    monkeypatch.setattr(surfaces, "observe", observe)
    async def arguments(context):
        values = profiles[context.name].configuration.launch_arguments()
        if failure == "missing-argument":
            values.remove(surfaces.KEY_ARGUMENT)
        elif failure == "duplicate-mode":
            values.append(surfaces.IDENTITY_ARGUMENT)
        return values
    monkeypatch.setattr(surfaces, "browser_arguments", arguments)
    report = {"checks": []}
    operation = surfaces.verify_concurrent_profiles(profiles, "http://owned", results, report, derivation_mode=mode)
    if failure is None:
        asyncio.run(operation)
        assert [check["name"] for check in report["checks"]] == list(surfaces.CONCURRENT_PHASES)
        assert all(check["passed"] for check in report["checks"])
        assert [check["active_profiles"] for check in report["checks"]] == [
            ["profile-a", "profile-b"], ["profile-b"], ["profile-a", "profile-b"],
            ["profile-a"], ["profile-a", "profile-b"]]
    else:
        with pytest.raises((ValueError, RuntimeError)):
            asyncio.run(operation)
    assert events[-2:] == [("close", "profile-a"), ("close", "profile-b")]


def test_combined_profile_identity_is_stable_across_sites_restart_and_independent_profiles():
    baseline, first, second = observation(), observation("b"), observation("d")
    surfaces.validate_combined(first, copy.deepcopy(first), protected=True,
                               derivation_mode="profile-identity")
    surfaces.validate_isolation(baseline, first, second, derivation_mode="profile-identity")
    with pytest.raises(ValueError, match="Cross-origin"):
        surfaces.validate_combined(first, protected=True)


@pytest.mark.parametrize("surface", ["canvas", "audio"])
@pytest.mark.parametrize("context", sorted(surfaces.DOCUMENT_CONTEXTS))
def test_profile_identity_rejects_inconsistent_document_surfaces(surface, context):
    first = observation("b")
    first[context][surface] = observation("d")["document"][surface]
    with pytest.raises(ValueError):
        surfaces.validate_combined(first, protected=True, derivation_mode="profile-identity")


@pytest.mark.parametrize("context", sorted(surfaces.CONTEXTS - surfaces.DOCUMENT_CONTEXTS))
def test_profile_identity_rejects_worker_canvas_disagreement(context):
    first = observation("b")
    first[context]["canvas"] = observation("d")[context]["canvas"]
    with pytest.raises(ValueError):
        surfaces.validate_combined(first, protected=True, derivation_mode="profile-identity")


def test_profile_identity_rejects_partitioned_entropy_restart_drift_and_reused_root():
    with pytest.raises(ValueError):
        surfaces.validate_combined(observation("b", "c"), protected=True,
                                   derivation_mode="profile-identity")
    with pytest.raises(ValueError, match="restart"):
        surfaces.validate_combined(observation("b"), observation("d"), protected=True,
                                   derivation_mode="profile-identity")
    with pytest.raises(ValueError, match="both profiles"):
        surfaces.validate_isolation(observation(), observation("b"), observation("b"),
                                    derivation_mode="profile-identity")


@pytest.mark.parametrize("mode", ["", "unknown", "PROFILE-IDENTITY", None, [], True])
def test_combined_unknown_derivation_mode_cannot_downgrade_validation(mode):
    with pytest.raises(ValueError, match="derivation mode"):
        surfaces.validate_combined(observation("b"), protected=True, derivation_mode=mode)
    with pytest.raises(ValueError, match="derivation mode"):
        surfaces.validate_isolation(observation(), observation("b"), observation("d"),
                                    derivation_mode=mode)


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


@pytest.mark.parametrize("mode", surfaces.DERIVATION_MODES)
@pytest.mark.parametrize("phase", ["baseline", "ready", "unavailable"])
def test_profile_identity_switch_requires_ready_full_surface_configuration(mode, phase):
    arguments = surfaces.SurfaceConfiguration(probe_mode=phase, derivation_mode=mode).launch_arguments()
    assert (surfaces.IDENTITY_ARGUMENT in arguments) is (mode == "profile-identity" and phase == "ready")
    if surfaces.IDENTITY_ARGUMENT in arguments:
        assert surfaces.KEY_ARGUMENT in arguments
        assert surfaces.DOCUMENT_ARGUMENT in arguments
        assert "--glint-worker-surface-bootstrap-test" in arguments
        assert not any("canvas-bootstrap-test" in argument for argument in arguments)


@pytest.mark.parametrize("mode", [None, [], "random"])
def test_profile_identity_configuration_rejects_unknown_mode(mode):
    with pytest.raises(ValueError, match="derivation mode"):
        surfaces.SurfaceConfiguration(derivation_mode=mode).launch_arguments()


@pytest.mark.parametrize("missing", [None, *surfaces.IDENTITY_PATCHES])
def test_profile_identity_receipt_requires_each_exact_compiled_patch(tmp_path, monkeypatch, missing):
    import hashlib

    core = {"chrome.exe": "a", "chrome.dll": "b", "chrome_elf.dll": "c"}
    receipt = {"runtime_core_sha256_measured": core, "patches": [
        {"name": name, "sha256": hashlib.sha256((surfaces.ROOT / "native/patches" / name).read_bytes()).hexdigest()}
        for name in (*surfaces.REQUIRED_PATCHES, *surfaces.IDENTITY_PATCHES) if name != missing]}
    raw = json.dumps(receipt).encode()
    monkeypatch.setattr(surfaces, "validate_worker_receipt", lambda *args, **kwargs: raw)
    if missing is None:
        assert surfaces.validate_receipt(tmp_path / "chrome.exe", core, derivation_mode="profile-identity") == raw
    else:
        with pytest.raises(ValueError, match="exact compiled surface patch"):
            surfaces.validate_receipt(tmp_path / "chrome.exe", core, derivation_mode="profile-identity")
        assert surfaces.validate_receipt(tmp_path / "chrome.exe", core) == raw


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


def test_identity_launch_candidate_requires_full_surfaces_and_keeps_renderer_selection_closed():
    from scripts.verify_native_document_drafts import patch_paths
    from scripts.verify_native_profile_identity_draft import LAUNCH_FIXTURES, LAUNCH_PATCH, LAUNCH_PATHS

    text = LAUNCH_PATCH.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == LAUNCH_PATHS
    assert all(name in text for name in LAUNCH_FIXTURES)
    assert text.count("+TEST_F(NativePrivacyBrowserContextTest,") == len(LAUNCH_FIXTURES)
    assert "glint-fingerprint-derivation-mode" in text
    assert "!command.HasSwitch(kNativePrivacyKeyServiceSwitch)" in text
    assert '!command.HasSwitch("glint-document-surface-bootstrap-test")' in text
    assert '!command.HasSwitch("glint-worker-surface-bootstrap-test")' in text
    assert text.count("CHECK(native_mode.has_value());") == 2
    assert "render_process_host_impl.cc" not in text
    added = " ".join(line[1:].strip() for line in text.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))
    assert "this, base::FilePath(), *native_mode" in added


def test_identity_readback_batch_rejects_conflicting_sources_instead_of_picking_a_winner():
    from scripts.verify_native_identity_readback_batch import _merge_composed_sources

    assert _merge_composed_sources({"owned.cc": "one", "same.h": "same"},
                                   {"gpu.cc": "two", "same.h": "same"}) == {
        "owned.cc": "one", "gpu.cc": "two", "same.h": "same"}
    with pytest.raises(ValueError, match="overlapping source edits"):
        _merge_composed_sources({"shared.h": "identity"}, {"shared.h": "gpu"})


def test_gpu_passthrough_attachment_fixtures_enable_feature_and_cover_native_state():
    from scripts.verify_native_document_drafts import patch_paths
    from scripts.verify_native_gpu_transport_draft import (
        PASSTHROUGH_ATTACHMENT_PATCH, PASSTHROUGH_ATTACHMENT_PATHS,
    )
    from scripts.verify_native_identity_readback_batch import PATCHES

    text = PASSTHROUGH_ATTACHMENT_PATCH.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == PASSTHROUGH_ATTACHMENT_PATHS
    assert text.count("+TEST_F(GlintPassthroughAttachmentTest,") == 14
    assert "InitAndEnableFeature(features::kGlintReadbackMetadataCandidate)" in text
    assert "ActualRgba8ExtentsPreserveRenderbufferBinding" in text
    assert "RedefinedAttachmentUsesCurrentNativeDimensions" in text
    assert "IntegerAttachmentIsNotByteColourCompatible" in text
    assert "MetadataQueryPreservesPendingClientError" in text
    assert "TextureAttachmentUsesNativeExtentsAndPreservesBinding" in text
    assert "TextureReattachmentUsesSelectedObjectNotBoundTexture" in text
    assert "TextureMipAttachmentReportsSelectedLevel" in text
    assert "CubeFaceAttachmentReportsNativeExtentsAndPreservesBinding" in text
    assert "ArrayLayerAttachmentReportsNativeExtentsAndPreservesBinding" in text
    assert "ThreeDimensionalLayerReportsNativeExtentsAndPreservesBinding" in text
    assert "SelectedReadAttachmentControlsNativeMetadata" in text
    assert "NoReadBufferRemainsUnavailableWithoutClientErrors" in text
    assert "IncompleteFramebufferRemainsUnavailableWithoutClientErrors" in text
    assert "MultisampleMetadataMatchesActualRenderbufferSamples" in text
    assert "storage.Init(GL_RENDERBUFFER, 1, GL_RGBA8, 8, 4);" in text
    assert "query.Init(GL_RENDERBUFFER, GL_RENDERBUFFER_SAMPLES, shared_memory_id_," in text
    assert "ASSERT_GT(native_samples, 0);" in text
    assert "EXPECT_EQ(metadata->samples, native_samples);" in text
    assert "select.Init(GL_COLOR_ATTACHMENT1);" in text
    assert "select.Init(GL_NONE);" in text
    assert "EXPECT_FALSE(QueryAttachment());" in text
    assert "attachment.Init(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, kClientTextureId," in text
    assert "DoGetIntegerv(GL_TEXTURE_BINDING_2D_ARRAY, &after, 1);" in text
    assert "DoGetIntegerv(GL_TEXTURE_BINDING_3D, &after, 1);" in text
    assert "max_level.Init(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 1);" in text
    assert "GL_TEXTURE_CUBE_MAP_POSITIVE_Y, kClientTextureId, 0);" in text
    assert "DoGetIntegerv(GL_TEXTURE_BINDING_CUBE_MAP, &after, 1);" in text
    assert "DoGetIntegerv(GL_TEXTURE_BINDING_2D, &before, 1);" in text
    assert "DoGetIntegerv(GL_TEXTURE_BINDING_2D, &after, 1);" in text
    assert "DoFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D," in text
    assert "EXPECT_EQ(second->width, 4);" in text
    assert "EXPECT_EQ(second->height, 7);" in text
    assert "GTEST_SKIP" not in text
    assert PATCHES[-1] == PASSTHROUGH_ATTACHMENT_PATCH


@pytest.mark.parametrize("destination", ["relative", "existing", "source", "public"])
def test_identity_readback_batch_rejects_unsafe_evidence_before_source_validation(tmp_path, destination):
    from scripts.verify_native_identity_readback_batch import ROOT, verify

    workspace = tmp_path / "workspace"
    source = workspace / "chromium/src"
    source.mkdir(parents=True)
    existing = tmp_path / "existing.json"
    existing.write_text("retain", encoding="utf-8")
    reports = {"relative": Path("relative.json"), "existing": existing,
               "source": source / "report.json", "public": ROOT / "report.json"}
    with pytest.raises(ValueError, match="new private report"):
        verify(workspace, reports[destination])
    assert existing.read_text(encoding="utf-8") == "retain"
    assert not list(source.iterdir())
