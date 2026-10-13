// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_RGBA8_PACK_COPY_H_
#define GLINT_RGBA8_PACK_COPY_H_

#include <cstddef>
#include <cstdint>
#include <span>

#include "base/types/expected.h"
#include "third_party/blink/renderer/platform/graphics/gpu/webgl_image_conversion.h"
#include "ui/gfx/geometry/rect.h"

namespace glint::candidate {
enum class Rgba8PackCopyError {
  kInvalidLayout,
  kInvalidSource,
  kDestinationTooSmall,
  kAliasedStorage,
};

// Scatter an already protected, tightly packed RGBA8 read rectangle into its
// validated WebGL destination layout. No allocation, masking or GPU access.
// Preserve row order, skips, padding and bytes outside the requested rectangle.
// All validation precedes writes; source and destination must not overlap.
base::expected<void, Rgba8PackCopyError> CopyRgba8ReadbackToPackLayout(
    std::span<const uint8_t> source,
    std::span<uint8_t> destination,
    GLsizei width,
    GLsizei height,
    size_t destination_offset,
    const blink::WebGLImageConversion::PixelStoreParams& params);

// Copy only the in-bounds part of the read rectangle. Preserve all clipped
// destination pixels, row padding, skips and offset bytes exactly.
base::expected<void, Rgba8PackCopyError> CopyRgba8ReadbackToPackLayout(
    std::span<const uint8_t> source,
    std::span<uint8_t> destination,
    GLsizei width,
    GLsizei height,
    size_t destination_offset,
    const blink::WebGLImageConversion::PixelStoreParams& params,
    const gfx::Rect& copy_region);
}  // namespace glint::candidate
#endif
