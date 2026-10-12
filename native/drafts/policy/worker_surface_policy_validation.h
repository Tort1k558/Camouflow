// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_WORKER_SURFACE_POLICY_VALIDATION_H_
#define GLINT_WORKER_SURFACE_POLICY_VALIDATION_H_

#include <optional>
#include <utility>

#include "surface_policy_validation.h"
#include "worker_surface_policy.h"

namespace glint::candidate {
// The partition is browser-owned. Blink independently selects the actual worker
// origin; a mismatch rejects startup rather than normalizing away its identity.
inline std::optional<WorkerSurfacePolicy> ValidateWorkerSurfacePolicy(
    std::optional<WorkerSurfacePolicy> incoming,
    const url::Origin& final_worker_origin,
    bool has_legacy_canvas_seed) {
  if (!incoming || has_legacy_canvas_seed ||
      incoming->partition.origin() != final_worker_origin ||
      !ValidateSurfacePolicy(incoming->policy, incoming->partition)) {
    return std::nullopt;
  }
  return incoming;
}
}  // namespace glint::candidate

#endif
