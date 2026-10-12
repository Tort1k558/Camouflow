// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_SURFACE_POLICY_PRODUCER_H_
#define GLINT_SURFACE_POLICY_PRODUCER_H_

#include <optional>

#include "third_party/blink/public/common/native_privacy/glint/surface_policy.h"

namespace blink {
class StorageKey;
}
namespace content {
class BrowserContext;
}

namespace glint::candidate {
// UI-sequence only. Unready, failed and shutting-down contexts produce nothing.
std::optional<SurfacePolicy> CreateSurfacePolicy(
    content::BrowserContext* context,
    const blink::StorageKey& trusted_partition);
}  // namespace glint::candidate

#endif
