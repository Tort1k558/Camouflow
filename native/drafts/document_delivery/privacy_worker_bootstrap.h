// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CONTENT_RENDERER_WORKER_PRIVACY_WORKER_BOOTSTRAP_H_
#define CONTENT_RENDERER_WORKER_PRIVACY_WORKER_BOOTSTRAP_H_

#include <array>
#include <cstdint>

#include "base/functional/callback.h"
#include "base/memory/weak_ptr.h"
#include "base/sequence_checker.h"
#include "base/timer/timer.h"
#include "base/types/expected.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "third_party/blink/public/mojom/native_privacy/native_privacy_document.mojom.h"

namespace content {

enum class PrivacyWorkerBootstrapError {
  kUnavailable,
  kTimedOut,
  kDisconnected,
  kMalformedPolicy,
};

// The caller must bind the worker host's broker, never its creator's document
// broker. Hold script startup until success; destruction cancels the request.
class PrivacyWorkerBootstrap final {
 public:
  using Result = base::expected<std::array<uint8_t, 32>, PrivacyWorkerBootstrapError>;
  using Callback = base::OnceCallback<void(Result)>;

  explicit PrivacyWorkerBootstrap(
      mojo::PendingRemote<blink::mojom::NativePrivacyWorker> endpoint);
  ~PrivacyWorkerBootstrap();
  PrivacyWorkerBootstrap(const PrivacyWorkerBootstrap&) = delete;
  PrivacyWorkerBootstrap& operator=(const PrivacyWorkerBootstrap&) = delete;

  // Call once on the creating sequence. A missing pipe may complete inline.
  void Start(Callback callback);

 private:
  void OnReply(blink::mojom::NativePrivacyDeliveryStatus status,
               blink::mojom::NativePrivacyCanvasPolicyPtr policy);
  void Fail(PrivacyWorkerBootstrapError error);
  void Complete(Result result);

  mojo::Remote<blink::mojom::NativePrivacyWorker> endpoint_;
  bool started_ = false;
  Callback callback_;
  base::OneShotTimer timer_;
  SEQUENCE_CHECKER(sequence_checker_);
  base::WeakPtrFactory<PrivacyWorkerBootstrap> weak_factory_{this};
};

}  // namespace content
#endif
