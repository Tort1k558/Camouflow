import re
from pathlib import Path

import pytest

from scripts import verify_native_next_batch as batch
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
                                 "content/test/BUILD.gn", "content/browser/BUILD.gn",
                                 "third_party/blink/renderer/core/workers/worker_global_scope.h",
                                 "third_party/blink/renderer/core/loader/document_loader_test.cc",
                                 "content/renderer/render_frame_impl.cc",
                                 "content/browser/renderer_host/render_frame_host_impl.h",
                                 "content/common/frame.mojom",
                                 "third_party/blink/renderer/modules/BUILD.gn",
                                 "third_party/blink/public/common/features.h",
                                 "third_party/blink/common/features.cc",
                                 "third_party/blink/renderer/core/html/build.gni",
                                 "third_party/blink/renderer/core/html/canvas/html_canvas_element.cc",
                                 "third_party/blink/renderer/core/offscreencanvas/offscreen_canvas.cc",
                                 "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.h",
                                 "third_party/blink/renderer/modules/webgl/webgl_rendering_context_base.cc",
                                 "third_party/blink/renderer/modules/webgl/webgl2_rendering_context_base.cc",
                                 "content/browser/renderer_host/render_frame_host_impl.cc",
                                 "third_party/blink/renderer/core/loader/document_loader.cc",
                                 "third_party/blink/renderer/core/workers/worker_thread_test.cc"})
        paths.update(current_paths)
        additions.update(added_sources(text))
    assert paths == EXISTING_PATHS | set(CANONICAL.values())
    assert set(additions) == set(CANONICAL.values())
    for name, relative in CANONICAL.items():
        assert additions[relative] == (DRAFTS / name).read_text(encoding="utf-8-sig")


def test_owned_replay_disables_machine_specific_crlf_conversion():
    text = Path(batch.__file__).read_text(encoding="utf-8-sig")
    configure = 'build.run(["git", "config", "core.autocrlf", "false"], overlay, env)'
    apply = 'build.run(["git", "apply", "--check", str(DRAFTS / name)], overlay, env)'
    assert text.index(configure) < text.index(apply)


@pytest.mark.parametrize("followups", [(), batch.FOLLOWUPS[:1], batch.FOLLOWUPS])
def test_registered_replay_preserves_reviewed_successor_order(followups):
    names = (*batch.PROMOTED, *followups)
    assert batch.registered_replay_chain([{"name": name} for name in reversed(names)]) == names


@pytest.mark.parametrize("names", [batch.PROMOTED[:2], batch.FOLLOWUPS,
                                   (*batch.PROMOTED, "0042-unreviewed.patch")])
def test_registered_replay_rejects_incomplete_or_unreviewed_chains(names):
    with pytest.raises(ValueError):
        batch.registered_replay_chain([{"name": name} for name in names])


def test_unpromoted_baseline_has_no_registered_reversal():
    assert batch.registered_replay_chain([{"name": "0030-native-document-commit-prototype.patch"}]) == ()


def test_webgl_compile_fix_uses_expected_and_gc_owned_stateless_cleanup():
    patch = (batch.ROOT / "native/patches/0037-native-webgl-readback-compilation.patch").read_text(encoding="utf-8-sig")
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "GetPackPixelStoreParams()).has_value()" in additions
    assert "[](WebGLRenderingContextBase* context)" in additions
    assert "WrapPersistent(this)" in additions
    assert "context->DrawingBufferClientRestorePixelPackParameters();" in additions
    assert "context->DrawingBufferClientRestorePixelPackBufferBinding();" in additions
    assert "[this]" not in additions


def test_renderer_presence_fix_uses_actual_mojo_pointer_api():
    patch = (batch.ROOT / "native/patches/0038-native-renderer-struct-pointer-presence.patch").read_text(encoding="utf-8-sig")
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "!commit_params->glint_document_canvas_commit.is_null()" in additions
    assert "!= nullptr" not in additions
    assert "DecodeOwnedDocumentSurfacePolicy" in patch


def test_document_policy_abort_uses_ready_request_owner_without_state_rewind():
    patch = (batch.ROOT / "native/patches/0039-native-document-ready-commit-cancellation.patch").read_text(encoding="utf-8-sig")
    additions = "\n".join(line[1:] for line in patch.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "net_error_ = net::ERR_ABORTED;" in additions
    assert "FrameTreeNode* node = frame_tree_node_;" in additions
    assert "GetRenderFrameHost()->NavigationRequestCancelled(" in additions
    assert "node->render_manager()->DiscardSpeculativeRFHIfUnused(" in additions
    assert additions.count("abort_privacy_commit();") == 3
    assert "OnRequestFailedInternal" not in additions
    assert "SetState(" not in additions
    assert "DCHECK" not in additions
    assert additions.index("FrameTreeNode* node") < additions.index("NavigationRequestCancelled(")


def test_ready_cancellation_followup_reacquires_frame_tree_after_finish_observers():
    text = (DRAFTS / "policy/document_ready_commit_observer_guard.patch").read_text(encoding="utf-8-sig")
    additions = "\n".join(line[1:] for line in text.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "const auto node_id = frame_tree_node_->frame_tree_node_id();" in additions
    assert "if (auto* node = FrameTreeNode::GloballyFindByID(node_id))" in additions
    assert "FrameTreeNode* node = frame_tree_node_;" not in additions
    assert "NavigationRequestCancelled(" in text


def test_late_document_policy_loss_fixtures_cover_both_modes_recovery_and_destruction():
    text = (DRAFTS / "policy/document_ready_commit_observer_tests.patch").read_text(encoding="utf-8-sig")
    names = re.findall(r"\+TEST_P\(NativeDocumentNavigationTest, (Late\w+)\)", text)
    assert set(names) == {
        f"Late{mode}PolicyLoss{outcome}" for mode in ("Canvas", "Surface")
        for outcome in ("CancelsAndAllowsNextNavigation", "ObserverMayDestroyWebContents")}
    assert len(names) == 4
    assert "+  void ReadyToCommitNavigation(NavigationHandle*) override {" in text
    assert "+      ShutdownNativePrivacyContext(browser_context());" in text
    assert text.count("+  shutdown_policy_at_ready_ = true;") == 4
    assert text.count("+  EXPECT_EQ(error_, net::ERR_ABORTED);") == 4
    assert text.count("+  destroy_contents_on_finish_ = true;") == 2
    assert text.count('+  NavigateAndCommit(GURL("https://canvas.test/recovery"));') == 2


def test_promoted_observer_patch_and_unit_gate_include_all_eight_late_cases():
    from scripts.verify_native_privacy_units import REQUIRED_SURFACE_NAVIGATION_TESTS

    expected = "".join((DRAFTS / "policy" / name).read_text(encoding="utf-8-sig") for name in (
        "document_ready_commit_observer_guard.patch", "document_ready_commit_observer_tests.patch"))
    patch = batch.ROOT / "native/patches/0040-native-ready-commit-observer-lifetime.patch"
    assert patch.read_text(encoding="utf-8-sig") == expected
    names = re.findall(r"\+TEST_P\(NativeDocumentNavigationTest, (Late\w+)\)", expected)
    suite = REQUIRED_SURFACE_NAVIGATION_TESTS["WithAndWithoutUrlLoader/NativeDocumentNavigationTest"]
    assert {f"{case}/{index}" for case in names for index in range(2)}.issubset(suite)
    assert sum(map(len, REQUIRED_SURFACE_NAVIGATION_TESTS.values())) == 42


def test_child_transport_fixture_uses_public_mojo_dispatch_without_widening_rfh_api():
    from scripts.verify_native_document_drafts import patch_paths

    patch = batch.ROOT / "native/patches/0041-native-child-transport-fixture-interface.patch"
    text = patch.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == {"content/browser/camouflow_native/glint/child_surface_transport_unittest.cc"}
    additions = "\n".join(line[1:] for line in text.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert '#include "content/common/frame.mojom.h"' in additions
    assert "mojom::FrameHost::CreateChildFrameWithGlintPolicyCallback" in additions
    assert "static_cast<mojom::FrameHost*>(parent)->CreateChildFrameWithGlintPolicy(" in additions
    assert "friend" not in additions and "public:" not in additions


def test_webgl_readback_is_disabled_by_default_and_uses_owned_surface_seed():
    text = (DRAFTS / "gpu/webgl_default_readback_candidate.patch").read_text(encoding="utf-8-sig")
    assert "+BASE_FEATURE(kGlintWebGLReadbackCandidate, base::FEATURE_DISABLED_BY_DEFAULT);" in text
    assert "GetExecutionContext(), glint::candidate::SurfaceSeedKind::kWebGL" in text
    assert "if (!seed.has_value() || !seed.value())" in text
    assert "framebuffer || format != GL_RGBA || type != GL_UNSIGNED_BYTE" in text
    assert "kCandidateAdditionalPixelBudget" in text
    assert "total_bytes.IsValid()" in text
    assert "ContextGL()->CheckFramebufferStatus(" in text
    assert "SynthesizeGLError(GL_INVALID_FRAMEBUFFER_OPERATION" in text
    assert "(pack.row_length > 0 ? pack.row_length : width)" in text


def test_webgl_readback_keeps_intermediate_pixels_private_and_restores_pack_state():
    text = (DRAFTS / "gpu/webgl_default_readback_candidate.patch").read_text(encoding="utf-8-sig")
    assert "base::ScopedClosureRunner restore(base::BindOnce([this]" in text
    assert "DrawingBufferClientRestorePixelPackParameters();" in text
    assert "DrawingBufferClientRestorePixelPackBufferBinding();" in text
    assert "ContextGL()->BindBuffer(GL_PIXEL_PACK_BUFFER, 0);" in text
    assert "rectangle.data());" in text and "canonical.data());" in text
    assert "ProtectWebGLCanonicalPixels(" in text
    assert "CopyRgba8ReadbackToPackLayout(" in text
    assert "BufferSubDataImpl(GL_PIXEL_PACK_BUFFER, destination, row_bytes," in text
    additions = "\n".join(line[1:] for line in text.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "ContextGL()->GetError(" not in additions
    assert "ContextGL()->Draw" not in additions


def test_webgl_exports_share_surface_domain_without_changing_2d_policy():
    text = (DRAFTS / "canvas/readback_export_seed.h").read_text(encoding="utf-8-sig")
    assert "!webgl_context ||" in text
    assert "return CanvasPartitionSeed(context);" in text
    assert "SurfacePartitionSeed(context, SurfaceSeedKind::kWebGL)" in text
    assert "CORE_EXPORT bool ProtectWebGLCanonicalPixels(" in text
    assert "base::unexpected(SurfaceSeedError::kInvalidPolicy)" in text
    patch = (DRAFTS / "gpu/webgl_default_readback_candidate.patch").read_text(encoding="utf-8-sig")
    assert patch.count("+    const auto seed = glint::candidate::CanvasExportPartitionSeed(") == 3


def test_renderbuffer_readback_uses_selected_native_attachment_extent():
    text = (DRAFTS / "gpu/renderbuffer_readback_candidate.patch").read_text(encoding="utf-8-sig")
    assert "framebuffer->GetAttachmentObject(framebuffer->GetReadBuffer())" in text
    assert "!attachment || !attachment->IsRenderbuffer()" in text
    assert "renderbuffer->IsMultisampled()" in text
    assert "+    storage = renderbuffer->InternalFormat();" in text
    assert "+    frame_width = renderbuffer->Width();" in text
    assert "+    frame_height = renderbuffer->Height();" in text
    assert "+  bool IsMultisampled() const { return is_multisampled_; }" in text
    assert "PrepareGlintRgba8Readback" in text
    additions = "\n".join(line[1:] for line in text.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
    assert "GL_VIEWPORT" not in additions and "GetError(" not in additions


def test_document_policy_producers_bind_exact_final_wire_origin():
    registered = (DRAFTS.parents[1] / "native/patches/0030-native-document-commit-prototype.patch").read_text(encoding="utf-8-sig")
    future = (DRAFTS / "policy/document_surface_transport.patch").read_text(encoding="utf-8-sig")
    assert "commit_params_->origin_to_commit));" in registered
    assert "+        commit_params_->origin_to_commit);" in future
    assert "ReuseRequestNavigationClientForCommitIfNeeded();" in registered


def test_gpu_shader_debug_metadata_is_gated_at_extension_support_boundary():
    text = (DRAFTS / "gpu/gpu_shader_metadata_minimization.patch").read_text(encoding="utf-8-sig")
    assert "+  if (base::FeatureList::IsEnabled(features::kGlintGpuMetadataMinimization)) {" in text
    assert "+    return false;" in text
    assert "GL_ANGLE_translated_shader_source" in text
    assert not any(line.startswith("+") and "getTranslatedShaderSource" in line for line in text.splitlines())


def test_rgba8_pack_copy_reuses_upstream_layout_and_validates_before_writes():
    text = (DRAFTS / "gpu/rgba8_pack_copy.cc").read_text(encoding="utf-8-sig")
    assert "WebGLImageConversion::ComputeImageSizeInBytes(" in text
    assert "GL_RGBA, GL_UNSIGNED_BYTE" in text
    assert "std::less<const uint8_t*>" in text
    assert "destination.last(0).data()" in text
    assert text.index("Rgba8PackCopyError::kAliasedStorage") < text.index("std::copy(")
    assert text.index("Rgba8PackCopyError::kDestinationTooSmall") < text.index("std::copy(")
    assert "GetBufferSubData" not in text
    assert "HMAC" not in text
    fixtures = (DRAFTS / "gpu/rgba8_pack_copy_unittest.cc").read_text(encoding="utf-8-sig")
    names = re.findall(r"TEST\(\s*GlintRgba8PackCopyTest,\s*(\w+)\s*\)", fixtures)
    assert len(names) == len(set(names)) == 14
    assert "AliasedStorageCannotMutateCanonicalSource" in names
    assert "ShortDestinationRejectsBeforeAnyWrite" in names


def test_startup_preload_settles_before_profile_publication_without_event_loop():
    text = (DRAFTS / "policy/startup_privacy_preload.patch").read_text(encoding="utf-8-sig")
    assert "+      ScopedAllowBlockingForProfile allow_native_identity_read;" in text
    assert '+      TRACE_EVENT0("browser", "Glint.ReadOnlyStartupIdentityPreload");' in text
    assert '+        !native_command->HasSwitch("glint-document-canvas-bootstrap-test")) {' in text
    assert "+  service->Loaded(PrivacyProfileKey::LoadOwnedProfile(owned_profile));" in text
    assert text.index("+  service->Loaded(") < text.index("+  owner.SetUserData(")
    assert "+    return owned_root.empty() && PrivacyKeyService::InstallEphemeral(*context);" in text
    assert "+  if (!context || context->ShutdownStarted()) {" in text
    production = text.split("diff --git a/content/browser/camouflow_native/privacy_context_unittest.cc", 1)
    assert "RunLoop" not in production[0]
    fixtures = re.findall(r"\+TEST_F\(NativePrivacyBrowserContextTest, (Startup\w+)\)", text)
    assert len(fixtures) == len(set(fixtures)) == 6


def test_child_policy_is_authenticated_before_local_initial_document_creation():
    text = (DRAFTS / "policy/child_surface_transport.patch").read_text(encoding="utf-8-sig")
    assert "+  [Sync] CreateChildFrameWithGlintPolicy(" in text
    assert "+  auto requesting_frame = render_frame_scoped_weak_ptr_factory_.GetWeakPtr();" in text
    assert "+    std::move(callback).Run(false, nullptr);" in text
    assert "+  if (!child || child->GetParent() != requesting_frame.get() ||" in text
    assert "+      child->GetBrowserContext() != requesting_frame->GetBrowserContext() ||" in text
    assert "+      !child->frame_tree_node()->is_on_initial_empty_document()) {" in text
    assert "+        child->GetBrowserContext(), child->GetStorageKey()," in text
    assert "+        child->GetLastCommittedOrigin());" in text
    assert "+  child_render_frame->glint_initial_surface_required_ = glint_child_required;" in text
    assert "CloneGlint" not in text
    renderer = text.split("diff --git a/content/renderer/render_frame_impl.cc", 1)[1]
    assert renderer.index("+    if (!GetFrameHost()->CreateChildFrameWithGlintPolicy(") < renderer.index(
        "   RenderFrameImpl* child_render_frame = RenderFrameImpl::Create(")
    fixtures = (DRAFTS / "policy/child_surface_transport_unittest.cc").read_text(encoding="utf-8-sig")
    names = re.findall(r"TEST_F\(\s*GlintChildSurfaceTransportTest,\s*(\w+)\s*\)", fixtures)
    assert len(names) == len(set(names)) == 5
    assert "bool created, auto policy" not in fixtures
    assert "FeatureOffCallbackCanDestroyFrameOwner" in names
    assert "+    *created = false;" in text
    assert "+    policy->reset();" in text
    assert "+    // No synthetic policy or fallback to ordinary asynchronous creation." in text


def test_initial_main_policy_is_browser_owned_and_consumed_before_frame_creation():
    text = (DRAFTS / "policy/initial_main_surface_transport.patch").read_text(encoding="utf-8-sig")
    assert text.count("+  blink.mojom.GlintSurfacePolicyCommit? glint_initial_surface_commit;") == 2
    assert "+              main_rfh->GetBrowserContext(), main_rfh->GetStorageKey()," in text
    assert "+            new_main_rfh->GetBrowserContext(), new_main_rfh->GetStorageKey()," in text
    assert "+    render_frame->glint_initial_surface_policy_ =" in text
    assert "+  params.glint_document_surface_policy = std::move(glint_initial_surface_policy_);" in text
    assert "+  glint_initial_surface_policy_.reset();" in text
    assert "+  Client()->PopulateGlintInitialDocument(*navigation_params);" in text
    assert "+    CHECK(" not in text


def test_initial_policy_origin_guard_precedes_upstream_calculation_and_cannot_borrow():
    text = (DRAFTS / "policy/initial_main_surface_transport.patch").read_text(encoding="utf-8-sig")
    assert "+      glint_document_surface_payload_required_) {" in text
    assert "+      glint_document_surface_policy_.reset();" in text
    assert "+      origin_to_commit_ = SecurityOrigin::CreateFromUrlOrigin(" in text
    assert "+      storage_key_ = glint_document_surface_policy_->partition;" in text
    helper = (DRAFTS / "policy/initial_document_surface_policy.h").read_text(encoding="utf-8-sig")
    assert "return origin.opaque();" in helper
    assert "return !owner_origin || origin == *owner_origin;" in helper
    fixtures = (DRAFTS / "policy/initial_document_surface_policy_unittest.cc").read_text(encoding="utf-8-sig")
    names = re.findall(r"TEST\(GlintInitialDocumentSurfacePolicyTest, (\w+)\)", fixtures)
    assert len(names) == len(set(names)) == 14
    assert "FinalDifferentKeyStillRejectsAdoptedPolicy" in names


def test_popup_wait_keeps_request_and_revalidates_frame_and_document():
    text = (DRAFTS / "policy/window_privacy_readiness.patch").read_text(encoding="utf-8-sig")
    assert "+                           render_frame_scoped_weak_ptr_factory_.GetWeakPtr()," in text
    assert "+                           GetDocumentTokenIgnoringSafetyRestrictions()," in text
    assert "+      requesting_document != GetDocumentTokenIgnoringSafetyRestrictions()) {" in text
    assert "+  glint_window_privacy_readiness_.reset();" in text
    assert "+  CreateNewWindow(std::move(params), std::move(callback));" in text
    assert "+    if (glint_window_privacy_readiness_) {" in text
    assert "GetAgentSchedulingGroup().CreateView" not in text


def test_popup_readiness_settles_once_before_destructive_callback():
    text = (DRAFTS / "policy/window_privacy_readiness.cc").read_text(encoding="utf-8-sig")
    assert "base::Seconds(10)" in text
    assert text.index("timer_.Stop();") < text.index("std::move(callback).Run(ready);")
    assert text.index("weak_factory_.InvalidateWeakPtrs();") < text.index("std::move(callback).Run(ready);")
    assert "content::IsNativePrivacyContextReady(context_.get())" in text
    fixtures = (DRAFTS / "policy/window_privacy_readiness_unittest.cc").read_text(encoding="utf-8-sig")
    names = re.findall(r"TEST_F\(GlintWindowPrivacyReadinessTest, (\w+)\)", fixtures)
    assert len(names) == len(set(names)) == 8
    assert "InlineCallbackMayDestroyRequest" in names


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


def test_surface_bootstrap_flags_are_forwarded_to_renderer_processes():
    text = (DRAFTS / "policy/surface_bootstrap_switches.patch").read_text(encoding="utf-8-sig")
    for flag in ("glint-worker-canvas-bootstrap-test", "glint-worker-surface-bootstrap-test",
                 "glint-document-canvas-bootstrap-test", "glint-document-surface-bootstrap-test"):
        assert f'+      "{flag}"' in text
    assert "renderer_cmd->CopySwitchesFrom(browser_cmd, glint_bootstrap_test_switches);" in text


def test_document_surface_transport_is_explicit_and_rejects_before_lifecycle_mutation():
    text = (DRAFTS / "policy/document_surface_transport.patch").read_text(encoding="utf-8-sig")
    assert "+  GlintSurfacePolicyCommit? glint_document_surface_commit;" in text
    assert "+  bool glint_document_surface_policy_required = false;" in text
    assert text.count("+          nullptr /* glint_document_surface_commit */,") == 4
    assert text.count("+          false /* glint_document_surface_policy_required */,") == 4
    assert "CreateDocumentSurfacePolicyCommit(" in text
    assert "+  std::optional<glint::candidate::DocumentSurfacePolicy> document_surface_policy;" in text
    assert "+    if (!document_surface_policy) {" in text
    assert "+      AbortClientNavigationImpl(/*for_new_navigation=*/false);" in text
    assert "+  navigation_params->glint_document_surface_policy = std::move(document_surface_policy);" in text
    assert "+         !request->commit_params().glint_document_surface_policy_required)) {" in text
    assert "+  const auto node_id = rejected->frame_tree_node()->frame_tree_node_id();" in text
    assert "+  if (auto* node = FrameTreeNode::GloballyFindByID(node_id)) {" in text


def test_document_surface_handoff_keeps_final_origin_semantics_and_has_no_new_check():
    text = (DRAFTS / "policy/document_surface_handoff.patch").read_text(encoding="utf-8-sig")
    assert "+          glint::candidate::ValidateDocumentSurfacePolicy(" in text
    assert "+              initializer.GlintSurfacePolicy(), initializer.GetWindow()->GetStorageKey()," in text
    assert "+  if (document_ && !document_->GlintSurfacePolicyReady()) {" in text
    assert "+    if (!policy && !glint_document_surface_payload_required_ &&" in text
    assert "+    document_init.WithGlintSurfacePolicy(std::move(policy), true);" in text
    assert "+  if (frame_->GetDocument()->GlintSurfacePolicyRequired()) {" in text
    assert "+    params->glint_document_surface_policy = frame_->GetDocument()->GlintSurfacePolicy();" in text
    additions = "\n".join(line[1:] for line in text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    assert "CHECK(" not in additions and "CalculateOrigin(" not in additions


def test_document_surface_first_script_and_inheritance_fixture_definitions_are_complete():
    text = (DRAFTS / "policy/document_surface_handoff_tests.patch").read_text(encoding="utf-8-sig")
    names = re.findall(r"\+TEST_P\(DocumentLoaderTest, (\w+)\)", text)
    assert len(names) == len(set(names)) == 15
    for name in ("GlintSurfacesOwnAllSeedsBeforeFirstInlineScript",
                 "GlintSurfacesInitialBlankChildInheritsExactParentPartition",
                 "GlintSurfacesSrcdocChildInheritsBeforeItsFirstScript",
                 "GlintSurfacesSandboxedSrcdocCannotBorrowParentIdentity",
                 "GlintSurfacesLateRejectionIsInertReplacementNotRollback"):
        assert name in names
    assert "+  EXPECT_FALSE(frame->GetFrame()->DomWindow()->CanExecuteScripts(kAboutToExecuteScript));" in text


def test_document_surface_navigation_fixtures_cover_readiness_and_selected_tokens():
    text = (DRAFTS / "policy/document_surface_navigation_tests.patch").read_text(encoding="utf-8-sig")
    readiness = re.findall(r"\+TEST_F\(NativeDocumentSurfaceReadinessTest, (\w+)\)", text)
    navigation = re.findall(r"\+TEST_P\(NativeDocumentNavigationTest, (Surface\w+)\)", text)
    assert len(readiness) == len(set(readiness)) == 6
    assert len(navigation) == len(set(navigation)) == 8
    assert "DeadlineRejectsLateReplyWithoutCanvasFallback" in readiness
    assert "SurfaceStaleRejectedTokenCannotCancelNextNavigation" in navigation
    assert "SurfaceConflictingFlagsRejectEvenReadyContext" in navigation
    assert "SurfaceFlagOffCannotCarryPriorNavigationEnvelope" in navigation
    assert "SurfaceRejectionObserverMayDestroyWebContents" in navigation


def test_worker_surface_consumers_can_distinguish_flag_off_from_missing_required_policy():
    text = (DRAFTS / "policy/worker_surface_scope_state.patch").read_text(encoding="utf-8-sig")
    assert "+  bool GlintSurfacePolicyRequired() const {" in text
    assert "+  bool GlintSurfacePolicyReady() const {" in text
    assert "+    return !glint_surface_policy_required_ || glint_surface_policy_.has_value();" in text
    assert text.count("+    DCHECK(IsContextThread());") == 3


def test_canvas_seed_consumer_distinguishes_unavailable_from_flag_off_for_every_surface():
    header = (DRAFTS / "canvas/canvas_partition_seed.h").read_text(encoding="utf-8-sig")
    source = (DRAFTS / "canvas/canvas_partition_seed.cc").read_text(encoding="utf-8-sig")
    assert "base::expected<std::optional<std::array<uint8_t, 32>>, SurfaceSeedError>" in header
    for kind in ("Canvas", "WebGL", "WebGPU", "Audio"):
        assert "SurfaceSeedKind::k" + kind in source
        assert "Glint" + kind + "PartitionSeed()" in source
    assert "if (!scope.GlintSurfacePolicyReady())" in source
    assert "base::unexpected(SurfaceSeedError::kInvalidPolicy)" in source
    assert "base::unexpected(SurfaceSeedError::kUnavailableContext)" in source
    assert "value_or(" not in source


def test_all_four_canvas_api_hooks_reject_seed_errors_without_raw_fallback():
    count = 0
    for name in ("get_image_data_candidate_hook.patch", "html_export_candidate_hook.patch",
                 "offscreen_candidate_hook.patch"):
        text = (DRAFTS / "canvas" / name).read_text(encoding="utf-8-sig")
        count += text.count('+          "Glint Canvas policy is unavailable.");')
        assert "+    if (!seed.has_value()) {" in text
        assert "+    if (const auto& partition_seed = seed.value()) {" in text
        assert "+          " in text
        assert "if (const auto seed = glint::candidate::CanvasPartitionSeed(" not in text
    assert count == 4


def test_surface_seed_reader_fixtures_use_actual_scope_creation_and_keep_bounded_cleanup():
    text = (DRAFTS / "canvas/surface_seed_reader_tests.patch").read_text(encoding="utf-8-sig")
    document = re.findall(r"\+TEST_P\(DocumentLoaderTest, (GlintSurfaceSeedReader\w+)\)", text)
    worker = re.findall(r"\+TEST_F\(GlintWorkerSurfaceThreadTest, (SurfaceReader\w+)\)", text)
    assert len(document) == len(set(document)) == 6
    assert len(worker) == len(set(worker)) == 2
    assert "SetGlintScopeObserverForTesting" not in text
    assert "+  EXPECT_CALL(*reporting_proxy_, DidCreateWorkerGlobalScope(_))" in text
    assert "+  ExpectRejectedSurface(std::nullopt, std::nullopt," in text


def test_offline_audio_hook_captures_before_allocation_and_exposes_one_detached_result():
    text = (DRAFTS / "audio/offline_audio_surface_hook.patch").read_text(encoding="utf-8-sig")
    assert "+  const auto seed = glint::candidate::SurfacePartitionSeed(" in text
    assert "+  glint_audio_partition_seed_ = seed.value();" in text
    assert text.index("glint_audio_partition_seed_ = seed.value()") < text.index(
        "complete_resolver_ = MakeGarbageCollected<ScriptPromiseResolver<AudioBuffer>>")
    assert "+      !glint::candidate::CanCopyOfflineAudio(number_of_channels, total_render_frames_)) {" in text
    assert "+      rendered_buffer = glint::candidate::CopyOfflineAudioBuffer(" in text
    assert "+      DispatchEvent(*OfflineAudioCompletionEvent::Create(rendered_buffer));" in text
    assert "+      complete_resolver_->Resolve(rendered_buffer);" in text
    assert "+      complete_resolver_->Reject(MakeGarbageCollected<DOMException>(" in text


def test_offline_audio_guard_fixtures_cannot_allocate_a_resolver_on_early_failure():
    text = (DRAFTS / "audio/offline_audio_surface_guard_tests.patch").read_text(encoding="utf-8-sig")
    names = re.findall(r"\+TEST_F\(OfflineAudioContextTest, (Glint\w+)\)", text)
    assert len(names) == len(set(names)) == 2
    assert "GlintMissingPolicyRejectsBeforeResolverOrRenderThread" in names
    assert "GlintCopyBudgetRejectsBeforeAllocationOrRenderThread" in names
    assert text.count("+  auto promise = context->startOfflineRendering(nullptr, exception);") == 2
    assert text.count("+  EXPECT_TRUE(promise.IsEmpty());") == 2
def test_initial_origin_compile_repair_preserves_immutable_member_and_header_abi():
    from scripts.native_build import ROOT
    from scripts.verify_native_document_drafts import patch_paths

    patch = ROOT / "native/patches/0035-native-initial-origin-calculation.patch"
    text = patch.read_text(encoding="utf-8-sig")
    assert patch_paths(text) == {"third_party/blink/renderer/core/loader/document_loader.cc"}
    assert "+  scoped_refptr<SecurityOrigin> effective_origin_to_commit = origin_to_commit_;" in text
    assert "-      origin_to_commit_ = SecurityOrigin::CreateFromUrlOrigin(" in text
    normalized = " ".join(text.replace("\n+", "\n").split())
    assert "glint_document_surface_payload_required_ && glint_document_surface_policy_" in normalized
    assert "CHECK(sandbox_origin->IsOpaque());" in text
    assert "CHECK(origin->IsSameOriginWith(effective_origin_to_commit.get()));" in text
    assert '"effective_origin_to_commit' not in text


def test_worker_complete_type_repair_supplies_definition_without_changing_service_abi():
    from scripts.native_build import ROOT
    from scripts.verify_native_document_drafts import patch_paths

    text = (ROOT / "native/patches/0036-native-worker-complete-surface-type.patch").read_text(encoding="utf-8-sig")
    assert patch_paths(text) == {"content/browser/camouflow_native/privacy_worker_service.h"}
    added = [line for line in text.splitlines() if line.startswith("+") and not line.startswith("+++")]
    assert added == [
        '+#include "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom.h"']
