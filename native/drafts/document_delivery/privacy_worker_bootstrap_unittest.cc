// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/renderer/worker/privacy_worker_bootstrap.h"

#include <memory>
#include <optional>

#include "base/test/bind.h"
#include "base/test/task_environment.h"
#include "base/time/time.h"
#include "mojo/public/cpp/bindings/receiver.h"
#include "testing/gtest/include/gtest/gtest.h"

namespace content {
namespace {
using Status = blink::mojom::NativePrivacyDeliveryStatus;
using Policy = blink::mojom::NativePrivacyCanvasPolicyPtr;
using Error = PrivacyWorkerBootstrapError;

class NativePrivacyWorkerBootstrapTest
    : public testing::Test,
      public blink::mojom::NativePrivacyWorker {
 protected:
  void GetCanvasPolicy(GetCanvasPolicyCallback callback) override {
    ++requests_;
    reply_ = std::move(callback);
  }

  void Start() {
    mojo::PendingRemote<blink::mojom::NativePrivacyWorker> endpoint;
    receiver_.Bind(endpoint.InitWithNewPipeAndPassReceiver());
    bootstrap_ = std::make_unique<PrivacyWorkerBootstrap>(std::move(endpoint));
    bootstrap_->Start(base::BindLambdaForTesting(
        [&](PrivacyWorkerBootstrap::Result result) {
          ++completions_;
          result_ = std::move(result);
        }));
    tasks_.RunUntilIdle();
    ASSERT_EQ(requests_, 1);
    ASSERT_EQ(completions_, 0);
  }

  Policy ValidPolicy() {
    auto policy = blink::mojom::NativePrivacyCanvasPolicy::New();
    policy->version = 1;
    for (uint8_t i = 0; i < 32; ++i) {
      policy->partition_seed.push_back(i);
    }
    return policy;
  }

  void Reply(Status status, Policy policy) {
    ASSERT_TRUE(reply_);
    std::move(reply_).Run(status, std::move(policy));
    tasks_.RunUntilIdle();
  }

  void ExpectError(Error error) {
    ASSERT_EQ(completions_, 1);
    ASSERT_TRUE(result_);
    ASSERT_FALSE(result_->has_value());
    EXPECT_EQ(result_->error(), error);
  }

  base::test::SingleThreadTaskEnvironment tasks_{
      base::test::TaskEnvironment::TimeSource::MOCK_TIME};
  mojo::Receiver<blink::mojom::NativePrivacyWorker> receiver_{this};
  GetCanvasPolicyCallback reply_;
  std::unique_ptr<PrivacyWorkerBootstrap> bootstrap_;
  int requests_ = 0;
  int completions_ = 0;
  std::optional<PrivacyWorkerBootstrap::Result> result_;
};

TEST_F(NativePrivacyWorkerBootstrapTest, ReadyPolicyReturnsOwnedSurfaceSeedOnce) {
  Start();
  Reply(Status::kReady, ValidPolicy());
  ASSERT_EQ(completions_, 1);
  ASSERT_TRUE(result_);
  ASSERT_TRUE(result_->has_value());
  for (uint8_t i = 0; i < 32; ++i) {
    EXPECT_EQ(result_->value()[i], i);
  }
  tasks_.FastForwardBy(base::Seconds(11));
  EXPECT_EQ(completions_, 1);
  EXPECT_EQ(requests_, 1);
}

TEST_F(NativePrivacyWorkerBootstrapTest, UnavailableDoesNotReturnSeed) {
  Start();
  Reply(Status::kUnavailable, nullptr);
  ExpectError(Error::kUnavailable);
}

TEST_F(NativePrivacyWorkerBootstrapTest, BrowserTimeoutDoesNotReturnSeed) {
  Start();
  Reply(Status::kTimedOut, nullptr);
  ExpectError(Error::kTimedOut);
}

TEST_F(NativePrivacyWorkerBootstrapTest, UnknownVersionIsRejected) {
  Start();
  auto policy = ValidPolicy();
  policy->version = 2;
  Reply(Status::kReady, std::move(policy));
  ExpectError(Error::kMalformedPolicy);
}

TEST_F(NativePrivacyWorkerBootstrapTest, ReadyWithoutPolicyIsRejected) {
  Start();
  Reply(Status::kReady, nullptr);
  ExpectError(Error::kMalformedPolicy);
}

TEST_F(NativePrivacyWorkerBootstrapTest, FailureWithSeedIsRejected) {
  Start();
  Reply(Status::kUnavailable, ValidPolicy());
  ExpectError(Error::kMalformedPolicy);
}

TEST_F(NativePrivacyWorkerBootstrapTest, PeerDisconnectSettlesOnce) {
  Start();
  receiver_.reset();
  tasks_.RunUntilIdle();
  ExpectError(Error::kDisconnected);
  tasks_.FastForwardBy(base::Seconds(11));
  EXPECT_EQ(completions_, 1);
}

TEST_F(NativePrivacyWorkerBootstrapTest, DeadlineRejectsLateReadyReply) {
  Start();
  tasks_.FastForwardBy(base::Seconds(11));
  ExpectError(Error::kTimedOut);
  Reply(Status::kReady, ValidPolicy());
  EXPECT_EQ(completions_, 1);
}

TEST_F(NativePrivacyWorkerBootstrapTest, DestructionDropsPendingReply) {
  Start();
  bootstrap_.reset();
  Reply(Status::kReady, ValidPolicy());
  tasks_.FastForwardBy(base::Seconds(11));
  EXPECT_EQ(completions_, 0);
}

TEST_F(NativePrivacyWorkerBootstrapTest, MissingPipeReturnsTypedFailure) {
  PrivacyWorkerBootstrap bootstrap{
      mojo::PendingRemote<blink::mojom::NativePrivacyWorker>()};
  bootstrap.Start(base::BindLambdaForTesting(
      [&](PrivacyWorkerBootstrap::Result result) {
        ++completions_;
        result_ = std::move(result);
      }));
  ExpectError(Error::kDisconnected);
  EXPECT_EQ(requests_, 0);
}

}  // namespace
}  // namespace content
