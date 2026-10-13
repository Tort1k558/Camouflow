// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/renderer_host/render_frame_host_impl.h"

#include <utility>

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/test/bind.h"
#include "base/test/scoped_command_line.h"
#include "content/browser/camouflow_native/glint/document_surface_commit_producer.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/test_renderer_host.h"
#include "content/test/test_render_frame_host.h"
#include "services/metrics/public/cpp/ukm_source_id.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/public/common/native_privacy/glint/document_surface_policy.h"
#include "url/gurl.h"

namespace content {
namespace {
class GlintChildSurfaceTransportTest : public RenderViewHostTestHarness {
 protected:
  void SetUp() override {
    command_line_.GetProcessCommandLine()->RemoveSwitch(
        "glint-document-surface-bootstrap-test");
    command_line_.GetProcessCommandLine()->RemoveSwitch(
        "glint-document-canvas-bootstrap-test");
    RenderViewHostTestHarness::SetUp();
    NavigateAndCommit(GURL("https://child.test/"));
    ASSERT_TRUE(owned_.CreateUniqueTempDir());
    ASSERT_TRUE(base::WriteFile(
        owned_.GetPath().AppendASCII("camouflow-native-privacy.json"),
        R"({"schema":1,"seed":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"})"));
  }
  void TearDown() override {
    ShutdownNativePrivacyContext(browser_context());
    task_environment()->RunUntilIdle();
    RenderViewHostTestHarness::TearDown();
  }
  void Initialize() {
    ASSERT_TRUE(InitializeNativePrivacyContextBeforeFirstFrame(
        browser_context(), owned_.GetPath()));
    ASSERT_TRUE(IsNativePrivacyContextReady(browser_context()));
  }
  void RequestFeatureOff(
      RenderFrameHostImpl::CreateChildFrameWithGlintPolicyCallback callback) {
    auto* parent = static_cast<RenderFrameHostImpl*>(main_rfh());
    parent->CreateChildFrameWithGlintPolicy(
        blink::LocalFrameToken(), TestRenderFrameHost::CreateStubFrameRemote(),
        TestRenderFrameHost::CreateStubBrowserInterfaceBrokerReceiver(),
        TestRenderFrameHost::CreateStubPolicyContainerBindParams(),
        TestRenderFrameHost::CreateStubAssociatedInterfaceProviderReceiver(),
        blink::mojom::TreeScopeType::kDocument, "child", "child-unique", false,
        blink::FramePolicy(), blink::mojom::FrameOwnerProperties::New(),
        blink::FrameOwnerElementType::kIframe, ukm::kInvalidSourceId,
        std::move(callback));
  }
  base::test::ScopedCommandLine command_line_;
  base::ScopedTempDir owned_;
};

TEST_F(GlintChildSurfaceTransportTest,
       FeatureOffRejectsBeforeTokenConsumption) {
  int calls = 0;
  RequestFeatureOff(base::BindLambdaForTesting(
      [&](bool created, blink::mojom::GlintSurfacePolicyCommitPtr policy) {
        EXPECT_FALSE(created);
        EXPECT_FALSE(policy);
        ++calls;
      }));
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintChildSurfaceTransportTest,
       FeatureOffNeverExposesReadyProfilePolicy) {
  Initialize();
  int calls = 0;
  RequestFeatureOff(base::BindLambdaForTesting(
      [&](bool created, blink::mojom::GlintSurfacePolicyCommitPtr policy) {
        EXPECT_FALSE(created);
        EXPECT_FALSE(policy);
        ++calls;
      }));
  EXPECT_EQ(calls, 1);
  EXPECT_TRUE(IsNativePrivacyContextReady(browser_context()));
}

TEST_F(GlintChildSurfaceTransportTest, FeatureOffCallbackCanDestroyFrameOwner) {
  int calls = 0;
  RequestFeatureOff(base::BindLambdaForTesting(
      [&](bool created, blink::mojom::GlintSurfacePolicyCommitPtr policy) {
        EXPECT_FALSE(created);
        EXPECT_FALSE(policy);
        ++calls;
        DeleteContents();
      }));
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintChildSurfaceTransportTest,
       ActualInitialChildKeyMatchesItsFourBrowserDerivations) {
  Initialize();
  auto* child = RenderFrameHostTester::For(main_rfh())->AppendChild("child");
  ASSERT_TRUE(child);
  auto* selected = static_cast<RenderFrameHostImpl*>(child);
  auto wire = glint::candidate::CreateDocumentSurfacePolicyCommit(
      browser_context(), selected->GetStorageKey(),
      selected->GetLastCommittedOrigin());
  ASSERT_TRUE(wire);
  auto policy = glint::candidate::DecodeOwnedDocumentSurfacePolicy(
      *wire, selected->GetStorageKey(), selected->GetLastCommittedOrigin(),
      false);
  ASSERT_TRUE(policy);
  EXPECT_TRUE(glint::candidate::ValidateDocumentSurfacePolicy(
      policy, selected->GetStorageKey(), true, false));
  EXPECT_EQ(policy->policy.canvas,
            DeriveNativePrivacyKey(browser_context(), selected->GetStorageKey(),
                                   "canvas"));
  EXPECT_EQ(policy->policy.webgl,
            DeriveNativePrivacyKey(browser_context(), selected->GetStorageKey(),
                                   "webgl"));
  EXPECT_EQ(policy->policy.webgpu,
            DeriveNativePrivacyKey(browser_context(), selected->GetStorageKey(),
                                   "webgpu"));
  EXPECT_EQ(policy->policy.audio,
            DeriveNativePrivacyKey(browser_context(), selected->GetStorageKey(),
                                   "audio"));
}

TEST_F(GlintChildSurfaceTransportTest,
       SamePartitionParentAndChildUseSamePolicyNotCopiedState) {
  Initialize();
  auto* parent = static_cast<RenderFrameHostImpl*>(main_rfh());
  auto* child = static_cast<RenderFrameHostImpl*>(
      RenderFrameHostTester::For(parent)->AppendChild("child"));
  ASSERT_TRUE(child);
  ASSERT_EQ(parent->GetStorageKey(), child->GetStorageKey());
  auto first = glint::candidate::CreateDocumentSurfacePolicyCommit(
      browser_context(), parent->GetStorageKey(),
      parent->GetLastCommittedOrigin());
  auto second = glint::candidate::CreateDocumentSurfacePolicyCommit(
      browser_context(), child->GetStorageKey(),
      child->GetLastCommittedOrigin());
  ASSERT_TRUE(first);
  ASSERT_TRUE(second);
  EXPECT_EQ(first->partition_encoding, second->partition_encoding);
  EXPECT_EQ(first->canvas_seed, second->canvas_seed);
  EXPECT_EQ(first->audio_seed, second->audio_seed);
}
}  // namespace
}  // namespace content
