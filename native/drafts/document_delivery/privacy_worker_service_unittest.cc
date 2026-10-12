// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_worker_service.h"

#include <memory>
#include <vector>

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/run_loop.h"
#include "base/test/bind.h"
#include "base/test/scoped_feature_list.h"
#include "base/time/time.h"
#include "content/browser/worker_host/worker_util.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/browser_task_environment.h"
#include "content/public/test/test_browser_context.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "mojo/public/cpp/bindings/unique_receiver_set.h"
#include "net/base/features.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/public/common/features.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace content {
namespace {
using Status = blink::mojom::NativePrivacyDeliveryStatus;
using Policy = blink::mojom::NativePrivacyCanvasPolicyPtr;
using Kind = PrivacyWorkerService::Kind;
constexpr char kIdentity[] =
    R"({"schema":1,"seed":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"})";

class NativePrivacyWorkerServiceTest : public testing::Test {
 protected:
  void SetUp() override {
    features_.InitAndEnableFeature(net::features::kThirdPartyStoragePartitioning);
    ASSERT_TRUE(owned_.CreateUniqueTempDir());
    ASSERT_TRUE(base::WriteFile(
        owned_.GetPath().AppendASCII("camouflow-native-privacy.json"), kIdentity));
    context_ = std::make_unique<TestBrowserContext>();
  }

  void Initialize() {
    ASSERT_TRUE(InitializeNativePrivacyContext(context_.get(), owned_.GetPath()));
  }

  blink::StorageKey Partition() {
    return blink::StorageKey::CreateFirstParty(
        url::Origin::Create(GURL("https://worker.test")));
  }

  mojo::Remote<blink::mojom::NativePrivacyWorker> Connect(
      Kind kind = Kind::kDedicated) {
    const auto partition = Partition();
    return ConnectForPartition(partition, partition.origin(), kind);
  }

  mojo::Remote<blink::mojom::NativePrivacyWorker> ConnectForPartition(
      const blink::StorageKey& partition,
      const url::Origin& worker_origin,
      Kind kind = Kind::kDedicated) {
    mojo::Remote<blink::mojom::NativePrivacyWorker> remote;
    receivers_.Add(std::make_unique<PrivacyWorkerService>(
                       *context_, partition, kind, worker_origin),
                   remote.BindNewPipeAndPassReceiver());
    return remote;
  }

  BrowserTaskEnvironment tasks_{
      base::test::TaskEnvironment::TimeSource::MOCK_TIME,
      base::test::TaskEnvironment::ThreadPoolExecutionMode::QUEUED};
  base::test::ScopedFeatureList features_;
  base::ScopedTempDir owned_;
  std::unique_ptr<TestBrowserContext> context_;
  mojo::UniqueReceiverSet<blink::mojom::NativePrivacyWorker> receivers_;
};

TEST_F(NativePrivacyWorkerServiceTest, MissingServiceReturnsUnavailable) {
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

TEST_F(NativePrivacyWorkerServiceTest, ReadyPolicyMatchesTrustedPartition) {
  Initialize();
  tasks_.RunUntilIdle();
  const auto expected = DeriveNativePrivacyKey(context_.get(), Partition(), "canvas");
  ASSERT_TRUE(expected);
  for (auto kind : {Kind::kDedicated, Kind::kShared, Kind::kService}) {
    auto remote = Connect(kind);
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
}

TEST_F(NativePrivacyWorkerServiceTest, LoadingDoesNotReplyBeforeReadiness) {
  Initialize();
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status status, Policy policy) {
        ++replies;
        EXPECT_EQ(status, Status::kReady);
        EXPECT_TRUE(policy);
      }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 0);
  tasks_.RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyWorkerServiceTest, ShutdownSettlesLoadingOnce) {
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
  ShutdownNativePrivacyContext(context_.get());
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
  tasks_.RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyWorkerServiceTest, DeadlineRejectsLateReadiness) {
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
  tasks_.AdvanceClock(base::Seconds(11));
  base::RunLoop().RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
  tasks_.RunUntilIdle();
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}

TEST_F(NativePrivacyWorkerServiceTest, ReceiverOwnerDestructionDropsLoadingReply) {
  Initialize();
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status, Policy) { ++replies; }));
  remote.FlushForTesting();
  receivers_.Clear();
  tasks_.RunUntilIdle();
  EXPECT_EQ(replies, 0);
  EXPECT_FALSE(remote.is_connected());
}

TEST_F(NativePrivacyWorkerServiceTest, PipeDisconnectDropsLoadingReply) {
  Initialize();
  auto remote = Connect();
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status, Policy) { ++replies; }));
  remote.FlushForTesting();
  remote.reset();
  base::RunLoop().RunUntilIdle();
  tasks_.RunUntilIdle();
  EXPECT_EQ(replies, 0);
  EXPECT_TRUE(receivers_.empty());
}

TEST_F(NativePrivacyWorkerServiceTest, DestroyedContextCannotDeliverSeed) {
  auto remote = Connect();
  context_.reset();
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

TEST_F(NativePrivacyWorkerServiceTest, UnpartitionedSharedAndServiceWorkersFail) {
  Initialize();
  tasks_.RunUntilIdle();
  base::test::ScopedFeatureList disabled;
  disabled.InitAndDisableFeature(net::features::kThirdPartyStoragePartitioning);
  for (auto kind : {Kind::kShared, Kind::kService}) {
    auto remote = Connect(kind);
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
}

TEST_F(NativePrivacyWorkerServiceTest, LegacyDataWorkerOriginMismatchIsRejected) {
  Initialize();
  tasks_.RunUntilIdle();
  base::test::ScopedFeatureList legacy;
  legacy.InitAndDisableFeature(blink::features::kDataUrlWorkerOpaqueOrigin);
  const GURL script_url("data:text/javascript,void(0)");
  const auto partition = CalculateWorkerStorageKey(script_url, Partition());
  const auto origin = CalculateWorkerRendererOrigin(script_url, partition);
  ASSERT_NE(partition.origin(), origin);
  auto remote = ConnectForPartition(partition, origin);
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

TEST_F(NativePrivacyWorkerServiceTest, MatchingOpaqueDataWorkerUsesOwnedPartition) {
  Initialize();
  tasks_.RunUntilIdle();
  base::test::ScopedFeatureList opaque;
  opaque.InitAndEnableFeature(blink::features::kDataUrlWorkerOpaqueOrigin);
  const GURL script_url("data:text/javascript,void(0)");
  const auto partition = CalculateWorkerStorageKey(script_url, Partition());
  const auto origin = CalculateWorkerRendererOrigin(script_url, partition);
  ASSERT_TRUE(origin.opaque());
  ASSERT_EQ(partition.origin(), origin);
  const auto expected = DeriveNativePrivacyKey(context_.get(), partition, "canvas");
  ASSERT_TRUE(expected);
  auto remote = ConnectForPartition(partition, origin);
  int replies = 0;
  remote->GetCanvasPolicy(base::BindLambdaForTesting(
      [&](Status status, Policy policy) {
        ++replies;
        EXPECT_EQ(status, Status::kReady);
        ASSERT_TRUE(policy);
        EXPECT_EQ(policy->partition_seed,
                  std::vector<uint8_t>(expected->begin(), expected->end()));
      }));
  remote.FlushForTesting();
  EXPECT_EQ(replies, 1);
}
}  // namespace
}  // namespace content
