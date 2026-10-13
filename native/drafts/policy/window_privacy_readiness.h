// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_WINDOW_PRIVACY_READINESS_H_
#define GLINT_WINDOW_PRIVACY_READINESS_H_

#include "base/functional/callback.h"
#include "base/memory/weak_ptr.h"
#include "base/timer/timer.h"
#include "content/common/content_export.h"
#include "content/public/browser/browser_context.h"

namespace glint::candidate {
// Owned by the requesting RFH. Destruction cancels rather than invoking a
// callback on a destroyed frame; terminal completion may destroy this object.
class CONTENT_EXPORT WindowPrivacyReadiness {
 public:
  WindowPrivacyReadiness(content::BrowserContext* context,
                         base::OnceCallback<void(bool)> callback);
  ~WindowPrivacyReadiness();
  WindowPrivacyReadiness(const WindowPrivacyReadiness&) = delete;
  WindowPrivacyReadiness& operator=(const WindowPrivacyReadiness&) = delete;

  void Start();

 private:
  void Complete(bool ready);

  base::WeakPtr<content::BrowserContext> context_;
  base::OnceCallback<void(bool)> callback_;
  bool started_ = false;
  base::OneShotTimer timer_;
  base::WeakPtrFactory<WindowPrivacyReadiness> weak_factory_{this};
};
}  // namespace glint::candidate

#endif
