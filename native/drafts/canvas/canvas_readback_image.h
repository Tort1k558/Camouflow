// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_CANVAS_READBACK_IMAGE_H_
#define GLINT_CANVAS_READBACK_IMAGE_H_

#include "canvas_readback_copy.h"
#include "base/memory/scoped_refptr.h"
#include "third_party/blink/renderer/platform/graphics/static_bitmap_image.h"

namespace glint::candidate {
// Full Blink snapshot, after taint/layer/context checks. Readback only, not a
// replacement for GetImage/Snapshot used by drawing or presentation.
// Additional pixel memory is bounded across both raster copies.
base::expected<scoped_refptr<blink::StaticBitmapImage>, CanvasCopyError>
CreateProtectedCanvasImage(
    scoped_refptr<blink::StaticBitmapImage> source,
    const std::array<uint8_t, 32>& partition_seed,
    size_t memory_limit_bytes);
}  // namespace glint::candidate
#endif
