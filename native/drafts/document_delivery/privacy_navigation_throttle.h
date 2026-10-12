// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_NAVIGATION_THROTTLE_H_
#define CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_NAVIGATION_THROTTLE_H_

#include "base/memory/weak_ptr.h"
#include "base/timer/timer.h"
#include "content/public/browser/navigation_throttle.h"

namespace content {
class BrowserContext;
class NavigationThrottleRegistry;

inline constexpr char kGlintDocumentPrivacyBootstrapSwitch[] =
    "glint-document-canvas-bootstrap-test";

class CONTENT_EXPORT PrivacyNavigationThrottle final : public NavigationThrottle {
 public:
  explicit PrivacyNavigationThrottle(NavigationThrottleRegistry& registry);
  ~PrivacyNavigationThrottle() override;

  ThrottleCheckResult WillProcessResponse() override;
  ThrottleCheckResult WillCommitWithoutUrlLoader() override;
  const char* GetNameForLogging() override;

 private:
  ThrottleCheckResult CheckReadiness();
  void BeginReadinessWait();
  void Complete(bool ready);

  base::WeakPtr<BrowserContext> context_;
  bool pending_ = false;
  base::OneShotTimer timer_;
  base::WeakPtrFactory<PrivacyNavigationThrottle> weak_factory_{this};
};

}  // namespace content
#endif  // CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_NAVIGATION_THROTTLE_H_
