// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_readback_image.h"

#include <limits>
#include <utility>

#include "third_party/blink/renderer/platform/graphics/unaccelerated_static_bitmap_image.h"
#include "third_party/skia/include/core/SkColorSpace.h"
#include "third_party/skia/include/core/SkImage.h"

namespace glint::candidate {

base::expected<scoped_refptr<blink::StaticBitmapImage>, CanvasCopyError>
CreateProtectedCanvasImage(
    scoped_refptr<blink::StaticBitmapImage> source,
    const std::array<uint8_t, 32>& partition_seed,
    size_t memory_limit_bytes) {
  if (!source) {
    return base::unexpected(CanvasCopyError::kInvalidLayout);
  }
  const auto paint_image = source->PaintImageForCurrentFrame();
  if (!paint_image || paint_image.IsPaintWorklet()) {
    return base::unexpected(CanvasCopyError::kUnsupportedFormat);
  }
  const auto source_info = paint_image.GetSkImageInfo();
  if (source_info.isEmpty()) {
    return base::unexpected(CanvasCopyError::kInvalidLayout);
  }
  if ((source_info.colorType() != kRGBA_8888_SkColorType &&
       source_info.colorType() != kBGRA_8888_SkColorType) ||
      (source_info.alphaType() != kOpaque_SkAlphaType &&
       source_info.alphaType() != kUnpremul_SkAlphaType &&
       source_info.alphaType() != kPremul_SkAlphaType) ||
      !source_info.colorSpace() || !source_info.colorSpace()->isSRGB()) {
    return base::unexpected(CanvasCopyError::kUnsupportedFormat);
  }
  const auto info = source_info.makeColorType(kRGBA_8888_SkColorType)
                        .makeAlphaType(source_info.alphaType() == kOpaque_SkAlphaType
                                           ? kOpaque_SkAlphaType
                                           : kUnpremul_SkAlphaType);
  const size_t row_bytes = info.minRowBytes();
  const size_t bytes = info.computeByteSize(row_bytes);
  if (bytes == std::numeric_limits<size_t>::max()) {
    return base::unexpected(CanvasCopyError::kInvalidLayout);
  }
  // Two detached buffers coexist before the input raster is released.
  if (bytes > memory_limit_bytes / 2) {
    return base::unexpected(CanvasCopyError::kMemoryLimit);
  }
  SkBitmap raster;
  if (!raster.tryAllocPixels(info, row_bytes)) {
    return base::unexpected(CanvasCopyError::kAllocationFailed);
  }
  // Same pinned PaintImage readPixels path used by ImageDataBuffer; do not
  // substitute a guessed GPU buffer or alter the live render target.
  if (!paint_image.readPixels(info, raster.getPixels(), row_bytes, 0, 0)) {
    return base::unexpected(CanvasCopyError::kReadFailed);
  }
  auto copy = CreateProtectedCanvasCopy(raster.pixmap(), partition_seed,
                                         memory_limit_bytes - bytes);
  if (!copy.has_value()) {
    return base::unexpected(copy.error());
  }
  raster.reset();
  auto image = SkImages::RasterFromBitmap(copy.value());
  if (!image) {
    return base::unexpected(CanvasCopyError::kAllocationFailed);
  }
  scoped_refptr<blink::StaticBitmapImage> result =
      blink::UnacceleratedStaticBitmapImage::Create(std::move(image),
                                                    source->Orientation());
  if (!result) {
    return base::unexpected(CanvasCopyError::kAllocationFailed);
  }
  return result;
}
}  // namespace glint::candidate
