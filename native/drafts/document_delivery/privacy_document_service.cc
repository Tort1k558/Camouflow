// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_document_service.h"

#include <utility>

#include "base/check.h"
#include "base/functional/bind.h"
#include "base/time/time.h"
#include "content/public/browser/native_privacy_context.h"

namespace content {
namespace {
using Status = blink::mojom::NativePrivacyDeliveryStatus;
constexpr uint32_t kCanvasPolicyVersion = 1;
constexpr base::TimeDelta kReadinessDeadline = base::Seconds(10);
}  // namespace

void PrivacyDocumentService::Create(
    RenderFrameHost* frame,
    mojo::PendingReceiver<blink::mojom::NativePrivacyDocument> receiver) {
  CHECK(frame);
  new PrivacyDocumentService(*frame, std::move(receiver));
}

PrivacyDocumentService::PrivacyDocumentService(
    RenderFrameHost& frame,
    mojo::PendingReceiver<blink::mojom::NativePrivacyDocument> receiver)
    : DocumentService(frame, std::move(receiver)),
      partition_(frame.GetStorageKey()) {}

PrivacyDocumentService::~PrivacyDocumentService() = default;

void PrivacyDocumentService::GetCanvasPolicy(GetCanvasPolicyCallback callback) {
  if (requested_) {
    ReportBadMessageAndDeleteThis("Glint policy requested twice on one pipe");
    return;
  }
  requested_ = true;
  pending_reply_ = std::move(callback);
  if (!render_frame_host().IsActive() ||
      render_frame_host().GetStorageKey() != partition_) {
    Complete(Status::kUnavailable, nullptr);
    return;
  }
  timer_.Start(FROM_HERE, kReadinessDeadline,
               base::BindOnce(&PrivacyDocumentService::OnTimeout,
                              weak_factory_.GetWeakPtr()));
  // Terminal readiness invokes inline. Do not access members after registering.
  WhenNativePrivacyContextReady(
      render_frame_host().GetBrowserContext(),
      base::BindOnce(&PrivacyDocumentService::OnReady,
                     weak_factory_.GetWeakPtr()));
}

void PrivacyDocumentService::OnReady(bool ready) {
  if (!pending_reply_) {
    return;
  }
  if (!ready || !render_frame_host().IsActive() ||
      render_frame_host().GetStorageKey() != partition_) {
    Complete(Status::kUnavailable, nullptr);
    return;
  }
  auto seed = DeriveNativePrivacyKey(render_frame_host().GetBrowserContext(),
                                     partition_, "canvas");
  if (!seed) {
    Complete(Status::kUnavailable, nullptr);
    return;
  }
  auto policy = blink::mojom::NativePrivacyCanvasPolicy::New();
  policy->version = kCanvasPolicyVersion;
  policy->partition_seed.assign(seed->begin(), seed->end());
  Complete(Status::kReady, std::move(policy));
}

void PrivacyDocumentService::OnTimeout() {
  Complete(Status::kTimedOut, nullptr);
}

void PrivacyDocumentService::Complete(
    Status status, blink::mojom::NativePrivacyCanvasPolicyPtr policy) {
  timer_.Stop();
  weak_factory_.InvalidateWeakPtrs();
  if (pending_reply_) {
    std::move(pending_reply_).Run(status, std::move(policy));
  }
}
}  // namespace content
