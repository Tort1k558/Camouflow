import re
from pathlib import Path

import pytest

from scripts.verify_native_next_batch import (
    CANONICAL,
    DRAFTS,
    EXISTING_PATHS,
    PATCHES,
    validate_patch_paths,
)


def added_sources(text):
    result = {}
    relative = None
    added = False
    body = []
    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if added:
                result[relative] = "".join(body)
            relative = line.rstrip().split(" b/", 1)[1]
            added = False
            body = []
        elif line.startswith("new file mode "):
            added = True
        elif added and line.startswith("+") and not line.startswith("+++ "):
            body.append(line[1:])
    if added:
        result[relative] = "".join(body)
    return result


def test_next_batch_patch_coverage_and_canonical_sources():
    paths = set()
    additions = {}
    for name in PATCHES:
        text = (DRAFTS / name).read_text(encoding="utf-8-sig")
        current_paths = validate_patch_paths(text)
        # Endpoint/consumer follow-ups intentionally extend the same legacy mock.
        overlap = paths & current_paths
        assert overlap.issubset({"content/renderer/worker/privacy_worker_bootstrap_unittest.cc",
                                 "content/test/BUILD.gn", "content/browser/BUILD.gn"})
        paths.update(current_paths)
        additions.update(added_sources(text))
    assert paths == EXISTING_PATHS | set(CANONICAL.values())
    assert set(additions) == set(CANONICAL.values())
    for name, relative in CANONICAL.items():
        assert additions[relative] == (DRAFTS / name).read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("relative", [
    "../outside.cc", "unrelated/source.cc", "content/browser/unknown.cc",
    "C:/outside.cc", "third_party\\blink\\fake.cc",
])
def test_next_batch_refuses_unknown_or_unsafe_paths(relative):
    with pytest.raises(ValueError):
        validate_patch_paths(f"diff --git a/{relative} b/{relative}\n")


def test_gpu_metadata_candidate_does_not_drop_subgroup_capabilities():
    text = (DRAFTS / "gpu/gpu_metadata_minimization.patch").read_text(encoding="utf-8-sig")
    assert "+    info = MakeGarbageCollected<GPUAdapterInfo>(" in text
    assert "+    return MakeGarbageCollected<GPUAdapterInfo>(" not in text
    assert "base::FEATURE_DISABLED_BY_DEFAULT" in text
    assert "is_fallback_adapter);" in text


def test_audio_and_surface_helpers_do_not_enable_api_hooks():
    audio = validate_patch_paths((DRAFTS / PATCHES[1]).read_text(encoding="utf-8-sig"))
    assert not any(Path(path).name == "offline_audio_context.cc" for path in audio)
    policy = validate_patch_paths((DRAFTS / PATCHES[2]).read_text(encoding="utf-8-sig"))
    assert not any(path.endswith(".mojom") for path in policy)
    producer = (DRAFTS / "policy/surface_policy_producer.cc").read_text(encoding="utf-8-sig")
    for surface in ("canvas", "webgl", "webgpu", "audio"):
        assert f'DeriveNativePrivacyKey(context, trusted_partition, "{surface}")' in producer


def test_worker_endpoint_reuses_readiness_and_preserves_canvas_only_fixture():
    text = (DRAFTS / "policy/surface_worker_endpoint.patch").read_text(encoding="utf-8-sig")
    assert "+  void GetSurfacePolicy(GetSurfacePolicyCallback callback) override;" in text
    assert "+void PrivacyWorkerService::WaitForReadiness() {" in text
    assert text.count("+  WaitForReadiness();") == 2
    assert "+    ADD_FAILURE() << \"Canvas-only fixture must not request a surface bundle\";" in text
    names = re.findall(r"\+TEST_F\(NativePrivacyWorkerSurfaceServiceTest, (\w+)\)", text)
    assert len(names) == len(set(names)) == 8
    assert "SurfaceThenCanvasCannotRequestTwice" in names
    assert "CanvasThenSurfaceCannotRequestTwice" in names


def test_worker_surface_bootstrap_is_explicit_and_owns_its_browser_partition():
    text = (DRAFTS / "policy/surface_worker_bootstrap.patch").read_text(encoding="utf-8-sig")
    assert "+  endpoint_->GetSurfacePolicy(base::BindOnce(" in text
    assert "+  auto owned = glint::candidate::DecodeOwnedWorkerSurfacePolicy(" in text
    assert "+  selected_worker_partition_.reset();" in text
    assert "+  browser_worker_origin_.reset();" in text
    assert "+    ADD_FAILURE() << \"Surface bootstrap must not fall back to Canvas-only delivery\";" in text
    names = re.findall(r"\+TEST_F\(NativePrivacyWorkerSurfaceBootstrapTest, (\w+)\)", text)
    assert len(names) == len(set(names)) == 22
    assert "OriginOnlyRequestOwnsBrowserPartition" in names


def test_worker_scope_rejects_before_first_script_without_renderer_check():
    text = (DRAFTS / "policy/worker_surface_handoff.patch").read_text(encoding="utf-8-sig")
    assert "+      script_state && !privacy_rejected) {" in text
    assert "+    worker_script_.Clear();" in text and "+    close();" in text
    assert "+    CHECK(" not in text
    assert "GetSecurityOrigin()->ToUrlOrigin(), glint_canvas_partition_seed_.has_value()" in text
    names = re.findall(r"\+TEST_F\(GlintWorkerSurfaceThreadTest, (\w+)\)", text)
    assert len(names) == len(set(names)) == 4


def test_wire_bounds_precede_partition_serialization():
    text = (DRAFTS / "policy/surface_policy_wire.h").read_text(encoding="utf-8-sig")
    assert text.index("!HasValidSurfacePolicyPayload") < text.index("wire.partition.SerializeForNativePrivacy")


def test_all_worker_launchers_use_explicit_surface_delivery_and_forward_required_flag():
    text = (DRAFTS / "policy/worker_surface_launchers.patch").read_text(encoding="utf-8-sig")
    for path in ("dedicated_worker_host_factory_client.cc", "embedded_shared_worker_stub.cc",
                 "embedded_worker_instance_client_impl.cc", "dedicated_worker.cc",
                 "web_shared_worker_impl.cc", "web_embedded_worker_impl.cc"):
        assert any(relative.endswith("/" + path) for relative in validate_patch_paths(text))
    assert text.count("+      privacy_bootstrap_mode_ == WorkerPrivacyBootstrapMode::kSurfaces;") == 1
    assert "+    const auto partition = params->storage_key;" in text
    assert "+    privacy_bootstrap_->StartSurfacePolicy(partition, base::BindOnce(" in text
    assert "+    privacy_bootstrap_->StartSurfacePolicy(origin, base::BindOnce(" in text
    assert "+  worker_main_script_load_params->glint_surface_policy = surface_policy_;" in text
    assert "+  start_data->glint_surface_policy = std::move(surface_policy);" in text
    assert text.count("creation_params->glint_surface_policy_required") == 3
    assert "+  privacy_bootstrap_failed_ = true;" in text


def test_document_bundle_retains_browser_partition_and_requires_final_validation():
    text = (DRAFTS / "policy/document_surface_policy.h").read_text(encoding="utf-8-sig")
    assert "return DocumentSurfacePolicy{wire.partition, std::move(*policy)};" in text
    assert "ValidateSurfacePolicy(owned->policy, owned->partition) &&" in text
    assert "ValidateSurfacePolicy(owned->policy, final_partition);" in text
    assert "return !required;" in text
    assert "!legacy_canvas_present" in text
    assert "CHECK(" not in text
    fixture = (DRAFTS / "policy/document_surface_policy_unittest.cc").read_text(encoding="utf-8-sig")
    names = re.findall(r"TEST_F\(GlintDocumentSurfacePolicyTest, (\w+)\)", fixture)
    assert len(names) == len(set(names)) == 22
    assert "RetainedTopLevelSiteSurvivesDisabledPartitioning" in names
    assert "MissingRequiredPolicyCannotInstall" in names
    assert "UnknownModeCannotAdmitAnyPayload" in names


def test_document_surface_producer_reuses_selected_partition_and_existing_key_service():
    text = (DRAFTS / "policy/document_surface_commit_producer.cc").read_text(encoding="utf-8-sig")
    assert "blink::ResolveGlintDocumentStorageKey(" in text
    assert "CreateSurfacePolicy(context, partition);" in text
    assert "EncodeSurfacePolicyCommit(*policy, partition) : nullptr;" in text
    assert "InitializeNativePrivacyContext" not in text
    fixture = (DRAFTS / "policy/document_surface_commit_producer_unittest.cc").read_text(encoding="utf-8-sig")
    names = re.findall(r"TEST_F\(GlintDocumentSurfaceProducerTest, (\w+)\)", fixture)
    assert len(names) == len(set(names)) == 8
    assert "MalformedIdentityCannotProduceOrRegenerateCommit" in names
