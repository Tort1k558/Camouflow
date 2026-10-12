// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_navigation_throttle.h"

#include "base/check.h"
#include "base/command_line.h"
#include "base/functional/bind.h"
#include "base/task/sequenced_task_runner.h"
#include "base/time/time.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/native_privacy_context.h"
#include "content/public/browser/navigation_handle.h"
#include "content/public/browser/navigation_throttle_registry.h"
#include "content/public/browser/web_contents.h"

namespace content {

PrivacyNavigationThrottle::PrivacyNavigationThrottle(
    NavigationThrottleRegistry& registry)
    : NavigationThrottle(registry),
      context_(registry.GetNavigationHandle().GetWebContents()->GetBrowserContext()->GetWeakPtr()) {}

PrivacyNavigationThrottle::~PrivacyNavigationThrottle() = default;

NavigationThrottle::ThrottleCheckResult
PrivacyNavigationThrottle::WillProcessResponse() {
  return CheckReadiness();
}

NavigationThrottle::ThrottleCheckResult
PrivacyNavigationThrottle::WillCommitWithoutUrlLoader() {
  return CheckReadiness();
}

const char* PrivacyNavigationThrottle::GetNameForLogging() {
  return "GlintDocumentPrivacyReadinessThrottle";
}

NavigationThrottle::ThrottleCheckResult
PrivacyNavigationThrottle::CheckReadiness() {
  if (!base::CommandLine::ForCurrentProcess()->HasSwitch(
          kGlintDocumentPrivacyBootstrapSwitch)) {
    return PROCEED;
  }
  CHECK(!pending_);
  if (!context_ || context_->ShutdownStarted()) {
    return CANCEL_AND_IGNORE;
  }
  if (IsNativePrivacyContextReady(context_.get())) {
    return PROCEED;
  }
  pending_ = true;
  // Terminal readiness can reply inline; defer must be installed first.
  base::SequencedTaskRunner::GetCurrentDefault()->PostTask(
      FROM_HERE, base::BindOnce(&PrivacyNavigationThrottle::BeginReadinessWait,
                                weak_factory_.GetWeakPtr()));
  return DEFER;
}

void PrivacyNavigationThrottle::BeginReadinessWait() {
  if (!context_ || context_->ShutdownStarted()) {
    Complete(false);
    return;
  }
  timer_.Start(FROM_HERE, base::Seconds(10),
               base::BindOnce(&PrivacyNavigationThrottle::Complete,
                              weak_factory_.GetWeakPtr(), false));
  WhenNativePrivacyContextReady(
      context_.get(), base::BindOnce(&PrivacyNavigationThrottle::Complete,
                                     weak_factory_.GetWeakPtr()));
}

void PrivacyNavigationThrottle::Complete(bool ready) {
  if (!pending_) {
    return;
  }
  pending_ = false;
  timer_.Stop();
  weak_factory_.InvalidateWeakPtrs();
  if (!ready || !context_ || context_->ShutdownStarted()) {
    CancelDeferredNavigation(CANCEL_AND_IGNORE);
    return;
  }
  Resume();
}

}  // namespace content
