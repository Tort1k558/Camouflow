// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "window_privacy_readiness.h"

#include <utility>

#include "base/functional/bind.h"
#include "base/time/time.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/native_privacy_context.h"

namespace glint::candidate {
WindowPrivacyReadiness::WindowPrivacyReadiness(
    content::BrowserContext* context,
    base::OnceCallback<void(bool)> callback)
    : context_(context ? context->GetWeakPtr() : nullptr),
      callback_(std::move(callback)) {}

WindowPrivacyReadiness::~WindowPrivacyReadiness() = default;

void WindowPrivacyReadiness::Start() {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (started_ || !callback_) {
    return;
  }
  started_ = true;
  if (!context_ || context_->ShutdownStarted()) {
    Complete(false);
    return;
  }
  timer_.Start(FROM_HERE, base::Seconds(10),
               base::BindOnce(&WindowPrivacyReadiness::Complete,
                              weak_factory_.GetWeakPtr(), false));
  // Ready/failed/shutdown may settle inline. Do not access members afterwards.
  content::WhenNativePrivacyContextReady(
      context_.get(), base::BindOnce(&WindowPrivacyReadiness::Complete,
                                     weak_factory_.GetWeakPtr()));
}

void WindowPrivacyReadiness::Complete(bool ready) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!callback_) {
    return;
  }
  ready = ready && context_ && !context_->ShutdownStarted() &&
          content::IsNativePrivacyContextReady(context_.get());
  timer_.Stop();
  weak_factory_.InvalidateWeakPtrs();
  auto callback = std::move(callback_);
  std::move(callback).Run(ready);
}
}  // namespace glint::candidate
