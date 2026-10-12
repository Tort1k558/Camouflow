// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_WORKER_SERVICE_H_
#define CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_WORKER_SERVICE_H_

#include "base/memory/weak_ptr.h"
#include "base/timer/timer.h"
#include "third_party/blink/public/common/storage_key/storage_key.h"
#include "third_party/blink/public/mojom/native_privacy/native_privacy_document.mojom.h"

namespace content {
class BrowserContext;

// Owned by a worker host's UniqueReceiverSet, never a self-owned receiver.
class PrivacyWorkerService final : public blink::mojom::NativePrivacyWorker {
 public:
  enum class Kind { kDedicated, kShared, kService };
  PrivacyWorkerService(BrowserContext& context,
                       const blink::StorageKey& browser_partition,
                       Kind kind);
  ~PrivacyWorkerService() override;
  PrivacyWorkerService(const PrivacyWorkerService&) = delete;
  PrivacyWorkerService& operator=(const PrivacyWorkerService&) = delete;

  void GetCanvasPolicy(GetCanvasPolicyCallback callback) override;

 private:
  void OnReady(bool ready);
  void OnTimeout();
  void Complete(blink::mojom::NativePrivacyDeliveryStatus status,
                blink::mojom::NativePrivacyCanvasPolicyPtr policy);

  const base::WeakPtr<BrowserContext> context_;
  const blink::StorageKey partition_;
  const Kind kind_;
  bool requested_ = false;
  GetCanvasPolicyCallback pending_reply_;
  base::OneShotTimer timer_;
  base::WeakPtrFactory<PrivacyWorkerService> weak_factory_{this};
};
}  // namespace content
#endif
