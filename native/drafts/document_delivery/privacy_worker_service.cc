// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_worker_service.h"

#include <utility>

#include "base/functional/bind.h"
#include "base/time/time.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/native_privacy_context.h"
#include "mojo/public/cpp/bindings/message.h"

namespace content {
namespace {
using Status = blink::mojom::NativePrivacyDeliveryStatus;
constexpr uint32_t kCanvasPolicyVersion = 1;
constexpr base::TimeDelta kReadinessDeadline = base::Seconds(10);
}  // namespace

PrivacyWorkerService::PrivacyWorkerService(
    BrowserContext& context,
    const blink::StorageKey& browser_partition,
    Kind kind)
    : context_(context.GetWeakPtr()),
      partition_(browser_partition),
      kind_(kind) {}

PrivacyWorkerService::~PrivacyWorkerService() = default;

void PrivacyWorkerService::GetCanvasPolicy(GetCanvasPolicyCallback callback) {
  if (requested_) {
    mojo::ReportBadMessage("Glint worker policy requested twice on one pipe");
    return;
  }
  requested_ = true;
  pending_reply_ = std::move(callback);
  // Unpartitioned shared/service workers can serve multiple top-level sites.
  // Do not invent a single client's site or silently use its document identity.
  if (!context_ || context_->ShutdownStarted() ||
      (kind_ != Kind::kDedicated &&
       !blink::StorageKey::IsThirdPartyStoragePartitioningEnabled())) {
    Complete(Status::kUnavailable, nullptr);
    return;
  }
  timer_.Start(FROM_HERE, kReadinessDeadline,
               base::BindOnce(&PrivacyWorkerService::OnTimeout,
                              weak_factory_.GetWeakPtr()));
  WhenNativePrivacyContextReady(
      context_.get(), base::BindOnce(&PrivacyWorkerService::OnReady,
                                     weak_factory_.GetWeakPtr()));
}

void PrivacyWorkerService::OnReady(bool ready) {
  if (!pending_reply_) {
    return;
  }
  if (!ready || !context_ || context_->ShutdownStarted() ||
      (kind_ != Kind::kDedicated &&
       !blink::StorageKey::IsThirdPartyStoragePartitioningEnabled())) {
    Complete(Status::kUnavailable, nullptr);
    return;
  }
  auto seed = DeriveNativePrivacyKey(context_.get(), partition_, "canvas");
  if (!seed) {
    Complete(Status::kUnavailable, nullptr);
    return;
  }
  auto policy = blink::mojom::NativePrivacyCanvasPolicy::New();
  policy->version = kCanvasPolicyVersion;
  policy->partition_seed.assign(seed->begin(), seed->end());
  Complete(Status::kReady, std::move(policy));
}

void PrivacyWorkerService::OnTimeout() {
  Complete(Status::kTimedOut, nullptr);
}

void PrivacyWorkerService::Complete(
    Status status, blink::mojom::NativePrivacyCanvasPolicyPtr policy) {
  timer_.Stop();
  weak_factory_.InvalidateWeakPtrs();
  if (pending_reply_) {
    std::move(pending_reply_).Run(status, std::move(policy));
  }
}
}  // namespace content
