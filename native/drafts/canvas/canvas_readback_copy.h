// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_CANVAS_READBACK_COPY_H_
#define GLINT_CANVAS_READBACK_COPY_H_

#include <array>
#include <cstddef>
#include <cstdint>

#include "base/types/expected.h"
#include "third_party/skia/include/core/SkBitmap.h"
#include "third_party/skia/include/core/SkPixmap.h"

namespace glint::candidate {
enum class CanvasCopyError {
  kUnsupportedFormat,
  kInvalidLayout,
  kMemoryLimit,
  kAllocationFailed,
  kReadFailed,
  kTransformFailed,
};

// Full raster snapshot only, after the caller's native access checks.
// Returns an owned immutable RGBA8/unpremultiplied/sRGB copy. Never writes source.
// Crop/encoding must retain this result; errors are not unprotected fallback.
base::expected<SkBitmap, CanvasCopyError> CreateProtectedCanvasCopy(
    const SkPixmap& source,
    const std::array<uint8_t, 32>& partition_seed,
    size_t memory_limit_bytes);
}  // namespace glint::candidate
#endif
