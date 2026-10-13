// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "window_privacy_readiness.h"

#include <memory>

#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/test/bind.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/test/test_renderer_host.h"
#include "testing/gtest/include/gtest/gtest.h"

namespace glint::candidate {
namespace {
class GlintWindowPrivacyReadinessTest : public content::RenderViewHostTestHarness {
 public:
  GlintWindowPrivacyReadinessTest()
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
  base::ScopedTempDir owned_;
};
}  // namespace

TEST_F(GlintWindowPrivacyReadinessTest, MissingContextRejectsInline) {
  int calls = 0;
  WindowPrivacyReadiness request(nullptr, base::BindLambdaForTesting([&](bool ready) {
    EXPECT_FALSE(ready);
    ++calls;
  }));
  request.Start();
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintWindowPrivacyReadinessTest, UninitializedContextRejectsInline) {
  int calls = 0;
  WindowPrivacyReadiness request(browser_context(), base::BindLambdaForTesting([&](bool ready) {
    EXPECT_FALSE(ready);
    ++calls;
  }));
  request.Start();
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintWindowPrivacyReadinessTest, LoadingWaitsForActualProfileReadiness) {
  Initialize();
  int calls = 0;
  WindowPrivacyReadiness request(browser_context(), base::BindLambdaForTesting([&](bool ready) {
    EXPECT_TRUE(ready);
    ++calls;
  }));
  request.Start();
  EXPECT_EQ(calls, 0);
  task_environment()->RunUntilIdle();
  EXPECT_EQ(calls, 1);
  task_environment()->FastForwardBy(base::Seconds(20));
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintWindowPrivacyReadinessTest, DuplicateStartDoesNotRequestTwice) {
  Initialize();
  int calls = 0;
  WindowPrivacyReadiness request(browser_context(), base::BindLambdaForTesting([&](bool ready) {
    EXPECT_TRUE(ready);
    ++calls;
  }));
  request.Start();
  request.Start();
  task_environment()->RunUntilIdle();
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintWindowPrivacyReadinessTest, DestructionCancelsBeforeServiceReply) {
  Initialize();
  int calls = 0;
  auto request = std::make_unique<WindowPrivacyReadiness>(browser_context(),
      base::BindLambdaForTesting([&](bool) { ++calls; }));
  request->Start();
  request.reset();
  task_environment()->RunUntilIdle();
  task_environment()->FastForwardBy(base::Seconds(20));
  EXPECT_EQ(calls, 0);
}

TEST_F(GlintWindowPrivacyReadinessTest, ShutdownSettlesFailureOnce) {
  Initialize();
  int calls = 0;
  WindowPrivacyReadiness request(browser_context(), base::BindLambdaForTesting([&](bool ready) {
    EXPECT_FALSE(ready);
    ++calls;
  }));
  request.Start();
  content::ShutdownNativePrivacyContext(browser_context());
  task_environment()->RunUntilIdle();
  task_environment()->FastForwardBy(base::Seconds(20));
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintWindowPrivacyReadinessTest, MalformedIdentityDoesNotOpenWindow) {
  ASSERT_TRUE(base::WriteFile(owned_.GetPath().AppendASCII("camouflow-native-privacy.json"), "invalid"));
  Initialize();
  int calls = 0;
  WindowPrivacyReadiness request(browser_context(), base::BindLambdaForTesting([&](bool ready) {
    EXPECT_FALSE(ready);
    ++calls;
  }));
  request.Start();
  task_environment()->RunUntilIdle();
  EXPECT_EQ(calls, 1);
}

TEST_F(GlintWindowPrivacyReadinessTest, InlineCallbackMayDestroyRequest) {
  Initialize();
  task_environment()->RunUntilIdle();
  std::unique_ptr<WindowPrivacyReadiness> request;
  int calls = 0;
  request = std::make_unique<WindowPrivacyReadiness>(browser_context(),
      base::BindLambdaForTesting([&](bool ready) {
        EXPECT_TRUE(ready);
        ++calls;
        request.reset();
      }));
  request->Start();
  EXPECT_FALSE(request);
  EXPECT_EQ(calls, 1);
}
}  // namespace glint::candidate
