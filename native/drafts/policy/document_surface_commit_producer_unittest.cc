// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "document_surface_commit_producer.h"

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/unguessable_token.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/test_renderer_host.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/public/common/native_privacy/glint/document_surface_policy.h"
#include "url/gurl.h"

namespace glint::candidate {
namespace {
class GlintDocumentSurfaceProducerTest : public content::RenderViewHostTestHarness {
 public:
  GlintDocumentSurfaceProducerTest()
      : RenderViewHostTestHarness(
            base::test::TaskEnvironment::TimeSource::MOCK_TIME,
            base::test::TaskEnvironment::ThreadPoolExecutionMode::QUEUED) {}

 protected:
  void SetUp() override {
    RenderViewHostTestHarness::SetUp();
    ASSERT_TRUE(owned_.CreateUniqueTempDir());
    ASSERT_TRUE(base::WriteFile(owned_.GetPath().AppendASCII("camouflow-native-privacy.json"),
        R"({"schema":1,"seed":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"})"));
  }
  void TearDown() override {
    content::ShutdownNativePrivacyContext(browser_context());
    task_environment()->RunUntilIdle();
    RenderViewHostTestHarness::TearDown();
  }
  void Initialize() {
    ASSERT_TRUE(content::InitializeNativePrivacyContext(browser_context(), owned_.GetPath()));
  }
  const url::Origin origin_ = url::Origin::Create(GURL("https://document.test/"));
  const blink::StorageKey partition_ = blink::StorageKey::CreateFirstParty(origin_);
  base::ScopedTempDir owned_;
};

TEST_F(GlintDocumentSurfaceProducerTest, NullAndAbsentContextsCannotProduceCommit) {
  EXPECT_FALSE(CreateDocumentSurfacePolicyCommit(nullptr, partition_, origin_));
  EXPECT_FALSE(CreateDocumentSurfacePolicyCommit(browser_context(), partition_, origin_));
}

TEST_F(GlintDocumentSurfaceProducerTest, LoadingCannotProduceCommit) {
  Initialize();
  EXPECT_FALSE(CreateDocumentSurfacePolicyCommit(browser_context(), partition_, origin_));
}

TEST_F(GlintDocumentSurfaceProducerTest, ReadyCommitUsesExactFourDomainDerivations) {
  Initialize();
  task_environment()->RunUntilIdle();
  auto wire = CreateDocumentSurfacePolicyCommit(browser_context(), partition_, origin_);
  ASSERT_TRUE(wire);
  auto owned = DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false);
  ASSERT_TRUE(owned);
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(owned, partition_, true, false));
  EXPECT_EQ(owned->policy.canvas, content::DeriveNativePrivacyKey(browser_context(), partition_, "canvas"));
  EXPECT_EQ(owned->policy.webgl, content::DeriveNativePrivacyKey(browser_context(), partition_, "webgl"));
  EXPECT_EQ(owned->policy.webgpu, content::DeriveNativePrivacyKey(browser_context(), partition_, "webgpu"));
  EXPECT_EQ(owned->policy.audio, content::DeriveNativePrivacyKey(browser_context(), partition_, "audio"));
}

TEST_F(GlintDocumentSurfaceProducerTest, InheritedOriginUsesResolvedBrowserPartition) {
  Initialize();
  task_environment()->RunUntilIdle();
  const auto provisional = blink::StorageKey::CreateFirstParty(url::Origin());
  auto wire = CreateDocumentSurfacePolicyCommit(browser_context(), provisional, origin_);
  ASSERT_TRUE(wire);
  EXPECT_EQ(wire->partition, partition_);
  EXPECT_TRUE(DecodeOwnedDocumentSurfacePolicy(*wire, provisional, origin_, false));
}

TEST_F(GlintDocumentSurfaceProducerTest, NonceCannotBecomeFirstParty) {
  Initialize();
  task_environment()->RunUntilIdle();
  const auto key = blink::StorageKey::CreateWithNonce(origin_, base::UnguessableToken::Create());
  auto wire = CreateDocumentSurfacePolicyCommit(browser_context(), key, origin_);
  ASSERT_TRUE(wire);
  EXPECT_TRUE(DecodeOwnedDocumentSurfacePolicy(*wire, key, origin_, false));
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
}

TEST_F(GlintDocumentSurfaceProducerTest, ReturnedWireMutationCannotChangeNextCommit) {
  Initialize();
  task_environment()->RunUntilIdle();
  auto first = CreateDocumentSurfacePolicyCommit(browser_context(), partition_, origin_);
  ASSERT_TRUE(first);
  const auto expected = first->audio_seed;
  first->audio_seed.assign(32, 255);
  first->partition_encoding.clear();
  auto next = CreateDocumentSurfacePolicyCommit(browser_context(), partition_, origin_);
  ASSERT_TRUE(next);
  EXPECT_EQ(next->audio_seed, expected);
  EXPECT_TRUE(DecodeOwnedDocumentSurfacePolicy(*next, partition_, origin_, false));
}

TEST_F(GlintDocumentSurfaceProducerTest, ShutdownCannotProduceCommit) {
  Initialize();
  task_environment()->RunUntilIdle();
  content::ShutdownNativePrivacyContext(browser_context());
  EXPECT_FALSE(CreateDocumentSurfacePolicyCommit(browser_context(), partition_, origin_));
}

TEST_F(GlintDocumentSurfaceProducerTest, MalformedIdentityCannotProduceOrRegenerateCommit) {
  const auto identity = owned_.GetPath().AppendASCII("camouflow-native-privacy.json");
  ASSERT_TRUE(base::WriteFile(identity, "malformed"));
  Initialize();
  task_environment()->RunUntilIdle();
  EXPECT_FALSE(CreateDocumentSurfacePolicyCommit(browser_context(), partition_, origin_));
  std::string stored;
  ASSERT_TRUE(base::ReadFileToString(identity, &stored));
  EXPECT_EQ(stored, "malformed");
}
}  // namespace
}  // namespace glint::candidate
