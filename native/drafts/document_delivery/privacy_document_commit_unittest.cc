// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_document_commit.h"

#include <vector>

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/test_renderer_host.h"
#include "net/base/schemeful_site.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/public/common/storage_key/storage_key.h"
#include "third_party/blink/public/mojom/navigation/navigation_params.mojom.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace content {
namespace {

constexpr char kIdentity[] =
    R"({"schema":1,"seed":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"})";

class NativeDocumentCanvasCommitTest : public RenderViewHostTestHarness {
 public:
  NativeDocumentCanvasCommitTest()
      : RenderViewHostTestHarness(
            base::test::TaskEnvironment::TimeSource::MOCK_TIME,
            base::test::TaskEnvironment::ThreadPoolExecutionMode::QUEUED) {}

 protected:
  void SetUp() override {
    RenderViewHostTestHarness::SetUp();
    ASSERT_TRUE(owned_.CreateUniqueTempDir());
    ASSERT_TRUE(base::WriteFile(
        owned_.GetPath().AppendASCII("camouflow-native-privacy.json"), kIdentity));
  }

  void TearDown() override {
    ShutdownNativePrivacyContext(browser_context());
    task_environment()->RunUntilIdle();
    RenderViewHostTestHarness::TearDown();
  }

  void Initialize() {
    ASSERT_TRUE(InitializeNativePrivacyContext(browser_context(), owned_.GetPath()));
  }

  blink::StorageKey Partition() {
    return blink::StorageKey::CreateFirstParty(
        url::Origin::Create(GURL("https://canvas.test/")));
  }

  base::ScopedTempDir owned_;
};

TEST_F(NativeDocumentCanvasCommitTest, MissingContextDoesNotCreatePolicy) {
  EXPECT_FALSE(CreatePrivacyDocumentCanvasCommit(nullptr, Partition()));
  EXPECT_FALSE(CreatePrivacyDocumentCanvasCommit(browser_context(), Partition()));
}

TEST_F(NativeDocumentCanvasCommitTest, LoadingDoesNotProducePrematureCommit) {
  Initialize();
  EXPECT_FALSE(CreatePrivacyDocumentCanvasCommit(browser_context(), Partition()));
  task_environment()->RunUntilIdle();
  EXPECT_TRUE(CreatePrivacyDocumentCanvasCommit(browser_context(), Partition()));
}

TEST_F(NativeDocumentCanvasCommitTest, ReadyCommitOwnsExactCanvasSubkeyAndEncoding) {
  Initialize();
  task_environment()->RunUntilIdle();
  const auto key = Partition();
  const auto expected_seed = DeriveNativePrivacyKey(browser_context(), key, "canvas");
  const auto expected_encoding = key.SerializeForNativePrivacy();
  ASSERT_TRUE(expected_seed);
  ASSERT_TRUE(expected_encoding);
  auto policy = CreatePrivacyDocumentCanvasCommit(browser_context(), key);
  ASSERT_TRUE(policy);
  EXPECT_EQ(policy->version, 1u);
  EXPECT_EQ(policy->partition_encoding, *expected_encoding);
  EXPECT_EQ(policy->partition_seed,
            std::vector<uint8_t>(expected_seed->begin(), expected_seed->end()));
  policy->partition_seed.assign(32, 0);
  auto second = CreatePrivacyDocumentCanvasCommit(browser_context(), key);
  ASSERT_TRUE(second);
  EXPECT_EQ(second->partition_seed,
            std::vector<uint8_t>(expected_seed->begin(), expected_seed->end()));
}

TEST_F(NativeDocumentCanvasCommitTest, ShutdownDoesNotProduceCommit) {
  Initialize();
  task_environment()->RunUntilIdle();
  ShutdownNativePrivacyContext(browser_context());
  EXPECT_FALSE(CreatePrivacyDocumentCanvasCommit(browser_context(), Partition()));
}

TEST_F(NativeDocumentCanvasCommitTest, FailedIdentityDoesNotProduceReplacement) {
  ASSERT_TRUE(base::WriteFile(
      owned_.GetPath().AppendASCII("camouflow-native-privacy.json"), "not-json"));
  Initialize();
  task_environment()->RunUntilIdle();
  EXPECT_FALSE(CreatePrivacyDocumentCanvasCommit(browser_context(), Partition()));
  std::string stored;
  ASSERT_TRUE(base::ReadFileToString(
      owned_.GetPath().AppendASCII("camouflow-native-privacy.json"), &stored));
  EXPECT_EQ(stored, "not-json");
}

TEST_F(NativeDocumentCanvasCommitTest, RetainedPartitionStateSelectsDistinctPolicy) {
  Initialize();
  task_environment()->RunUntilIdle();
  const auto origin = url::Origin::Create(GURL("https://canvas.test/"));
  const auto first = blink::StorageKey::Create(
      origin, net::SchemefulSite(GURL("https://first.test/")),
      blink::mojom::AncestorChainBit::kCrossSite, false);
  const auto second = blink::StorageKey::Create(
      origin, net::SchemefulSite(GURL("https://second.test/")),
      blink::mojom::AncestorChainBit::kCrossSite, false);
  ASSERT_EQ(first, second);
  auto first_policy = CreatePrivacyDocumentCanvasCommit(browser_context(), first);
  auto second_policy = CreatePrivacyDocumentCanvasCommit(browser_context(), second);
  ASSERT_TRUE(first_policy);
  ASSERT_TRUE(second_policy);
  EXPECT_NE(first_policy->partition_encoding, second_policy->partition_encoding);
  EXPECT_NE(first_policy->partition_seed, second_policy->partition_seed);
}

}  // namespace
}  // namespace content
