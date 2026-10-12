// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_document_service.h"

#include <vector>

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/run_loop.h"
#include "base/test/bind.h"
#include "base/time/time.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/test_renderer_host.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "url/gurl.h"

namespace content {
namespace {
using Status = blink::mojom::NativePrivacyDeliveryStatus;
using Policy = blink::mojom::NativePrivacyCanvasPolicyPtr;
constexpr char kIdentity[] =
    R"({"schema":1,"seed":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"})";

class NativePrivacyDocumentServiceTest : public RenderViewHostTestHarness {
 public:
  NativePrivacyDocumentServiceTest()
      : RenderViewHostTestHarness(
            base::test::TaskEnvironment::TimeSource::MOCK_TIME,
            base::test::TaskEnvironment::ThreadPoolExecutionMode::QUEUED) {}

 protected:
  void SetUp() override {
    RenderViewHostTestHarness::SetUp();
    ASSERT_TRUE(owned_.CreateUniqueTempDir());
    ASSERT_TRUE(base::WriteFile(
        owned_.GetPath().AppendASCII("camouflow-native-privacy.json"),
        kIdentity));
    NavigateAndCommit(GURL("https://canvas.test/first"));
  }

  void Initialize() {
    ASSERT_TRUE(InitializeNativePrivacyContext(browser_context(),
                                               owned_.GetPath()));
  }

  mojo::Remote<blink::mojom::NativePrivacyDocument> Connect() {
    mojo::Remote<blink::mojom::NativePrivacyDocument> remote;
    PrivacyDocumentService::Create(main_rfh(),
                                    remote.BindNewPipeAndPassReceiver());
    return remote;
  }

  base::ScopedTempDir owned_;
};

TEST_F(NativePrivacyDocumentServiceTest, MissingServiceReturnsUnavailable) {
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status status, Policy policy) {
        ++replies;
        EXPECT_EQ(status, Status::kUnavailable);
        EXPECT_FALSE(policy);
      }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyDocumentServiceTest, ReadyContextDeliversOnlyCanvasSubkey) {
  Initialize();
  task_environment()->RunUntilIdle();
  const auto expected = DeriveNativePrivacyKey(
      browser_context(), main_rfh()->GetStorageKey(), "canvas");
  ASSERT_TRUE(expected);
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status status, Policy policy) {
        ++replies;
        EXPECT_EQ(status, Status::kReady);
        ASSERT_TRUE(policy);
        EXPECT_EQ(policy->version, 1u);
        EXPECT_EQ(policy->partition_seed,
                  std::vector<uint8_t>(expected->begin(), expected->end()));
      }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyDocumentServiceTest, LoadingDoesNotReplyBeforeReadiness) {
  Initialize();
  ASSERT_FALSE(IsNativePrivacyContextReady(browser_context()));
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status status, Policy policy) {
        ++replies;
        EXPECT_EQ(status, Status::kReady);
        ASSERT_TRUE(policy);
        EXPECT_EQ(policy->partition_seed.size(), 32u);
      }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 0);
  task_environment()->RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyDocumentServiceTest, ShutdownSettlesOnceWithoutSeed) {
  Initialize();
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status status, Policy policy) {
        ++replies;
        EXPECT_EQ(status, Status::kUnavailable);
        EXPECT_FALSE(policy);
      }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 0);
  ShutdownNativePrivacyContext(browser_context());
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
  task_environment()->RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyDocumentServiceTest, TimeoutRejectsLateReadyReply) {
  Initialize();
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status status, Policy policy) {
        ++replies;
        EXPECT_EQ(status, Status::kTimedOut);
        EXPECT_FALSE(policy);
      }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 0);
  // Do not run queued ThreadPool loading before the deadline.
  task_environment()->AdvanceClock(base::Seconds(11));
  base::RunLoop().RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
  task_environment()->RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyDocumentServiceTest, PipeDisconnectDropsLoadingReply) {
  Initialize();
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status, Policy) { ++replies; }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 0);
  remote.reset();
  base::RunLoop().RunUntilIdle();
  task_environment()->RunUntilIdle();
  EXPECT_EQ(replies, 0);
}

TEST_F(NativePrivacyDocumentServiceTest, DocumentDestructionDropsLoadingReply) {
  Initialize();
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status, Policy) { ++replies; }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 0);
  DeleteContents();
  task_environment()->RunUntilIdle();
  EXPECT_EQ(replies, 0);
  EXPECT_FALSE(remote.is_connected());
}

}  // namespace
}  // namespace content
