// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_RGBA8_READBACK_REGION_H_
#define GLINT_RGBA8_READBACK_REGION_H_

#include <cstddef>
#include <cstdint>
#include <span>

#include "base/types/expected.h"

namespace glint::candidate {
struct Rgba8ReadbackRequest {
  int32_t frame_width;
  int32_t frame_height;
  int32_t x;
  int32_t y;
  int32_t width;
  int32_t height;
};

enum class Rgba8ReadbackMode { kOutsideOnly, kFullFrameInPlace, kHalo };

struct Rgba8ReadbackRegion {
  Rgba8ReadbackMode mode = Rgba8ReadbackMode::kOutsideOnly;
  int32_t x = 0;
  int32_t y = 0;
  int32_t width = 0;
  int32_t height = 0;
  size_t rectangle_bytes = 0;
  size_t tile_bytes = 0;
  bool operator==(const Rgba8ReadbackRegion&) const = default;
};

enum class ReadbackRegionError {
  kInvalidDimensions,
  kBudgetExceeded,
  kInvalidStorage,
  kAliasedStorage,
};

// One-pixel halo around the in-bounds portion of the requested rectangle.
// Only for the edge-colour candidate; coordinate/global algorithms cannot use
// this local-domain optimization. Empty intersection requires no tile read.
// An exact full-frame request may transform its own private rectangle in place,
// so the budget does not include a redundant second full-frame allocation.
base::expected<Rgba8ReadbackRegion, ReadbackRegionError>
PlanRgba8ReadbackRegion(const Rgba8ReadbackRequest& request,
                        size_t additional_memory_limit);

// Overlay already-protected halo pixels into the private driver-read rectangle.
// Preserve every out-of-bounds pixel exactly; never mutate the source tile.
// Reject forged plans, wrong lengths and aliases before writing anything.
// Full-frame-in-place plans must use the transform directly, not this overlay.
base::expected<void, ReadbackRegionError> OverlayProtectedRgba8ReadbackRegion(
    std::span<const uint8_t> protected_tile,
    std::span<uint8_t> private_rectangle,
    const Rgba8ReadbackRequest& request,
    const Rgba8ReadbackRegion& region);
}  // namespace glint::candidate
#endif
