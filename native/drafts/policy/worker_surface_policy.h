// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_WORKER_SURFACE_POLICY_H_
#define GLINT_WORKER_SURFACE_POLICY_H_

#include "surface_policy.h"
#include "third_party/blink/public/common/storage_key/storage_key.h"

namespace glint::candidate {
// The browser endpoint owns the authoritative worker partition. Never derive it
// from a creator document URL or deserialize the commitment as a StorageKey.
struct WorkerSurfacePolicy {
  blink::StorageKey partition;
  SurfacePolicy policy;
};
}  // namespace glint::candidate

#endif
