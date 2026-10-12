// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "surface_policy_producer.h"

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/test_renderer_host.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/public/common/native_privacy/glint/surface_policy_validation.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace glint::candidate {
namespace {
class GlintSurfacePolicyProducerTest : public content::RenderViewHostTestHarness {
 public:
  GlintSurfacePolicyProducerTest()
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
  blink::StorageKey Partition() {
    return blink::StorageKey::CreateFirstParty(url::Origin::Create(GURL("https://policy.test/")));
  }
  base::ScopedTempDir owned_;
};

TEST_F(GlintSurfacePolicyProducerTest, MissingAndUnreadyContextRejectsSnapshot) {
  EXPECT_FALSE(CreateSurfacePolicy(nullptr, Partition()));
  EXPECT_FALSE(CreateSurfacePolicy(browser_context(), Partition()));
  Initialize();
  EXPECT_FALSE(CreateSurfacePolicy(browser_context(), Partition()));
}
TEST_F(GlintSurfacePolicyProducerTest, ReadySnapshotUsesFourIndependentDomains) {
  Initialize();
  task_environment()->RunUntilIdle();
  auto policy = CreateSurfacePolicy(browser_context(), Partition());
  ASSERT_TRUE(policy);
  EXPECT_TRUE(ValidateSurfacePolicy(*policy, Partition()));
  EXPECT_EQ(policy->canvas, content::DeriveNativePrivacyKey(browser_context(), Partition(), "canvas"));
  EXPECT_EQ(policy->webgl, content::DeriveNativePrivacyKey(browser_context(), Partition(), "webgl"));
  EXPECT_EQ(policy->webgpu, content::DeriveNativePrivacyKey(browser_context(), Partition(), "webgpu"));
  EXPECT_EQ(policy->audio, content::DeriveNativePrivacyKey(browser_context(), Partition(), "audio"));
}
TEST_F(GlintSurfacePolicyProducerTest, ChangingReturnedSnapshotDoesNotChangeIdentity) {
  Initialize();
  task_environment()->RunUntilIdle();
  auto first = CreateSurfacePolicy(browser_context(), Partition());
  ASSERT_TRUE(first);
  const auto expected = first->audio;
  first->audio.fill(0);
  auto second = CreateSurfacePolicy(browser_context(), Partition());
  ASSERT_TRUE(second);
  EXPECT_EQ(second->audio, expected);
}
TEST_F(GlintSurfacePolicyProducerTest, ShutdownRejectsSnapshot) {
  Initialize();
  task_environment()->RunUntilIdle();
  content::ShutdownNativePrivacyContext(browser_context());
  EXPECT_FALSE(CreateSurfacePolicy(browser_context(), Partition()));
}
}  // namespace
}  // namespace glint::candidate
