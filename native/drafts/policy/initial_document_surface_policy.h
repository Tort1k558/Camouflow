// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_INITIAL_DOCUMENT_SURFACE_POLICY_H_
#define GLINT_INITIAL_DOCUMENT_SURFACE_POLICY_H_

#include <optional>

#include "document_surface_policy.h"

namespace glint::candidate {
// Check before CalculateOrigin: a tuple origin in an origin-sandboxed window
// would violate upstream invariants rather than merely failing final policy.
inline bool CanAdoptInitialDocumentSurfacePolicy(
    const std::optional<DocumentSurfacePolicy>& owned,
    const std::optional<url::Origin>& owner_origin,
    bool origin_sandboxed) {
  if (!owned ||
      !ValidateDocumentSurfacePolicy(owned, owned->partition, true, false)) {
    return false;
  }
  const auto& origin = owned->partition.origin();
  if (origin_sandboxed) {
    return origin.opaque();
  }
  return !owner_origin || origin == *owner_origin;
}
}  // namespace glint::candidate

#endif
