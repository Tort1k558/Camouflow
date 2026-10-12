// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_SURFACE_POLICY_VALIDATION_H_
#define GLINT_SURFACE_POLICY_VALIDATION_H_

#include "surface_policy.h"
#include "third_party/blink/public/common/storage_key/storage_key.h"

namespace glint::candidate {
// Must be checked against the final Blink-selected partition before installation.
// IPC sender authentication and safe pre-teardown cancellation are separate gates.
inline bool ValidateSurfacePolicy(const SurfacePolicy& policy,
                                  const blink::StorageKey& selected_partition) {
  if (policy.version != kSurfacePolicyVersion || policy.partition_encoding.empty() ||
      policy.partition_encoding.size() > 8192 || !HasIndependentSurfaceSeeds(policy)) {
    return false;
  }
  const auto encoding = selected_partition.SerializeForNativePrivacy();
  return encoding && *encoding == policy.partition_encoding;
}
}  // namespace glint::candidate

#endif
