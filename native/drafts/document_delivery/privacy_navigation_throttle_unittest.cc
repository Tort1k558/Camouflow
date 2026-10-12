// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_navigation_throttle.h"

#include <memory>

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/run_loop.h"
#include "base/test/bind.h"
#include "base/test/scoped_command_line.h"
#include "base/time/time.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/mock_navigation_handle.h"
#include "content/public/test/mock_navigation_throttle_registry.h"
#include "content/public/test/test_renderer_host.h"
#include "testing/gtest/include/gtest/gtest.h"

namespace content {
namespace {
constexpr char kIdentity[] =
    R"({"schema":1,"seed":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"})";

class NativeDocumentReadinessThrottleTest : public RenderViewHostTestHarness {
 public:
  NativeDocumentReadinessThrottleTest()
      : RenderViewHostTestHarness(
            base::test::TaskEnvironment::TimeSource::MOCK_TIME,
            base::test::TaskEnvironment::ThreadPoolExecutionMode::QUEUED) {}

 protected:
  void SetUp() override {
    RenderViewHostTestHarness::SetUp();
    command_line_.GetProcessCommandLine()->RemoveSwitch(
        kGlintDocumentPrivacyBootstrapSwitch);
    ASSERT_TRUE(owned_.CreateUniqueTempDir());
    ASSERT_TRUE(base::WriteFile(
        owned_.GetPath().AppendASCII("camouflow-native-privacy.json"), kIdentity));
    handle_ = std::make_unique<MockNavigationHandle>(web_contents());
    registry_ = std::make_unique<MockNavigationThrottleRegistry>(handle_.get());
    throttle_ = std::make_unique<PrivacyNavigationThrottle>(*registry_);
    throttle_->set_resume_callback_for_testing(
        base::BindLambdaForTesting([this] { ++resumed_; }));
    throttle_->set_cancel_deferred_navigation_callback_for_testing(
        base::BindLambdaForTesting([this](NavigationThrottle::ThrottleCheckResult result) {
          EXPECT_EQ(NavigationThrottle::CANCEL_AND_IGNORE, result);
          ++cancelled_;
        }));
  }

  void TearDown() override {
    throttle_.reset();
    registry_.reset();
    handle_.reset();
    ShutdownNativePrivacyContext(browser_context());
    task_environment()->RunUntilIdle();
    RenderViewHostTestHarness::TearDown();
  }

  void Enable() {
    command_line_.GetProcessCommandLine()->AppendSwitch(
        kGlintDocumentPrivacyBootstrapSwitch);
  }

  void Initialize() {
    ASSERT_TRUE(InitializeNativePrivacyContext(browser_context(), owned_.GetPath()));
  }

  base::ScopedTempDir owned_;
  base::test::ScopedCommandLine command_line_;
  std::unique_ptr<MockNavigationHandle> handle_;
  std::unique_ptr<MockNavigationThrottleRegistry> registry_;
  std::unique_ptr<PrivacyNavigationThrottle> throttle_;
  int resumed_ = 0;
  int cancelled_ = 0;
};

TEST_F(NativeDocumentReadinessThrottleTest, FlagOffDoesNotRequirePolicy) {
  EXPECT_EQ(NavigationThrottle::PROCEED, throttle_->WillProcessResponse());
  EXPECT_EQ(NavigationThrottle::PROCEED, throttle_->WillCommitWithoutUrlLoader());
  task_environment()->RunUntilIdle();
  EXPECT_EQ(resumed_, 0);
  EXPECT_EQ(cancelled_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, ReadyContextProceedsSynchronously) {
  Enable();
  Initialize();
  task_environment()->RunUntilIdle();
  ASSERT_TRUE(IsNativePrivacyContextReady(browser_context()));
  EXPECT_EQ(NavigationThrottle::PROCEED, throttle_->WillProcessResponse());
  EXPECT_EQ(NavigationThrottle::PROCEED, throttle_->WillCommitWithoutUrlLoader());
  EXPECT_EQ(resumed_, 0);
  EXPECT_EQ(cancelled_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, TerminalFailureWaitsUntilDeferInstalled) {
  Enable();
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  EXPECT_EQ(cancelled_, 0);
  base::RunLoop().RunUntilIdle();
  EXPECT_EQ(cancelled_, 1);
  EXPECT_EQ(resumed_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, NoUrlLoaderUsesSupportedCancellation) {
  Enable();
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillCommitWithoutUrlLoader());
  EXPECT_EQ(cancelled_, 0);
  base::RunLoop().RunUntilIdle();
  EXPECT_EQ(cancelled_, 1);
  EXPECT_EQ(resumed_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, LoadingDefersThenResumesOnce) {
  Enable();
  Initialize();
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  base::RunLoop().RunUntilIdle();
  EXPECT_EQ(resumed_, 0);
  EXPECT_EQ(cancelled_, 0);
  task_environment()->RunUntilIdle();
  EXPECT_EQ(resumed_, 1);
  EXPECT_EQ(cancelled_, 0);
  task_environment()->FastForwardBy(base::Seconds(20));
  EXPECT_EQ(resumed_, 1);
}

TEST_F(NativeDocumentReadinessThrottleTest, DeadlineRejectsLateReadyReply) {
  Enable();
  Initialize();
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  base::RunLoop().RunUntilIdle();
  task_environment()->AdvanceClock(base::Seconds(11));
  base::RunLoop().RunUntilIdle();
  EXPECT_EQ(cancelled_, 1);
  task_environment()->RunUntilIdle();
  EXPECT_EQ(cancelled_, 1);
  EXPECT_EQ(resumed_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, DestructionCancelsPostedRegistration) {
  Enable();
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  throttle_.reset();
  task_environment()->RunUntilIdle();
  EXPECT_EQ(cancelled_, 0);
  EXPECT_EQ(resumed_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, DestructionCancelsPendingReadyReply) {
  Enable();
  Initialize();
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  base::RunLoop().RunUntilIdle();
  throttle_.reset();
  task_environment()->RunUntilIdle();
  EXPECT_EQ(cancelled_, 0);
  EXPECT_EQ(resumed_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, ShutdownCancelsPendingNavigationOnce) {
  Enable();
  Initialize();
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  base::RunLoop().RunUntilIdle();
  ShutdownNativePrivacyContext(browser_context());
  EXPECT_EQ(cancelled_, 1);
  task_environment()->RunUntilIdle();
  EXPECT_EQ(cancelled_, 1);
  EXPECT_EQ(resumed_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, CancellationCallbackMayDestroyThrottle) {
  Enable();
  throttle_->set_cancel_deferred_navigation_callback_for_testing(
      base::BindLambdaForTesting([this](NavigationThrottle::ThrottleCheckResult result) {
        EXPECT_EQ(NavigationThrottle::CANCEL_AND_IGNORE, result);
        ++cancelled_;
        throttle_.reset();
      }));
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  base::RunLoop().RunUntilIdle();
  EXPECT_FALSE(throttle_);
  EXPECT_EQ(cancelled_, 1);
  EXPECT_EQ(resumed_, 0);
}

TEST_F(NativeDocumentReadinessThrottleTest, ResumeCallbackMayDestroyThrottle) {
  Enable();
  Initialize();
  throttle_->set_resume_callback_for_testing(base::BindLambdaForTesting([this] {
    ++resumed_;
    throttle_.reset();
  }));
  EXPECT_EQ(NavigationThrottle::DEFER, throttle_->WillProcessResponse());
  base::RunLoop().RunUntilIdle();
  task_environment()->RunUntilIdle();
  EXPECT_FALSE(throttle_);
  EXPECT_EQ(resumed_, 1);
  EXPECT_EQ(cancelled_, 0);
}

}  // namespace
}  // namespace content
