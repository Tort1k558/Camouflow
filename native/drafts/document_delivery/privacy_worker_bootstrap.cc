// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/renderer/worker/privacy_worker_bootstrap.h"

#include <algorithm>
#include <utility>

#include "base/check.h"
#include "base/functional/bind.h"
#include "base/time/time.h"

namespace content {
namespace {
using Status = blink::mojom::NativePrivacyDeliveryStatus;
using Error = PrivacyWorkerBootstrapError;
constexpr uint32_t kSupportedCanvasPolicyVersion = 1;
constexpr base::TimeDelta kBootstrapDeadline = base::Seconds(10);
}  // namespace

PrivacyWorkerBootstrap::PrivacyWorkerBootstrap(
    mojo::PendingRemote<blink::mojom::NativePrivacyWorker> endpoint) {
  if (endpoint.is_valid()) {
    endpoint_.Bind(std::move(endpoint));
  }
}

PrivacyWorkerBootstrap::~PrivacyWorkerBootstrap() {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
}

void PrivacyWorkerBootstrap::Start(Callback callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  CHECK(!started_);
  CHECK(callback);
  started_ = true;
  callback_ = std::move(callback);
  if (!endpoint_.is_bound()) {
    Fail(Error::kDisconnected);
    return;
  }
  endpoint_.set_disconnect_handler(base::BindOnce(
      &PrivacyWorkerBootstrap::Fail, weak_factory_.GetWeakPtr(),
      Error::kDisconnected));
  timer_.Start(FROM_HERE, kBootstrapDeadline,
               base::BindOnce(&PrivacyWorkerBootstrap::Fail,
                              weak_factory_.GetWeakPtr(), Error::kTimedOut));
  endpoint_->GetCanvasPolicy(base::BindOnce(
      &PrivacyWorkerBootstrap::OnReply, weak_factory_.GetWeakPtr()));
}

void PrivacyWorkerBootstrap::OnReply(
    Status status, blink::mojom::NativePrivacyCanvasPolicyPtr policy) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if ((status != Status::kReady && policy) ||
      (status == Status::kReady &&
       (!policy || policy->version != kSupportedCanvasPolicyVersion ||
        policy->partition_seed.size() != 32))) {
    Fail(Error::kMalformedPolicy);
    return;
  }
  if (status == Status::kUnavailable) {
    Fail(Error::kUnavailable);
    return;
  }
  if (status == Status::kTimedOut) {
    Fail(Error::kTimedOut);
    return;
  }
  if (status != Status::kReady) {
    Fail(Error::kMalformedPolicy);
    return;
  }
  std::array<uint8_t, 32> seed;
  std::copy(policy->partition_seed.begin(), policy->partition_seed.end(),
            seed.begin());
  Complete(seed);
}

void PrivacyWorkerBootstrap::Fail(Error error) {
  Complete(base::unexpected(error));
}

void PrivacyWorkerBootstrap::Complete(Result result) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  timer_.Stop();
  weak_factory_.InvalidateWeakPtrs();
  endpoint_.reset();
  if (callback_) {
    // The owner may destroy this object from its startup continuation.
    std::move(callback_).Run(std::move(result));
  }
}

}  // namespace content
