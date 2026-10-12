// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_readback_copy.h"

#include <limits>
#include <span>

#include "canvas_readback_candidate.h"
#include "third_party/skia/include/core/SkColorSpace.h"

namespace glint::candidate {

base::expected<SkBitmap, CanvasCopyError> CreateProtectedCanvasCopy(
    const SkPixmap& source,
    const std::array<uint8_t, 32>& partition_seed,
    size_t memory_limit_bytes) {
  if ((source.colorType() != kRGBA_8888_SkColorType &&
       source.colorType() != kBGRA_8888_SkColorType) ||
      (source.alphaType() != kOpaque_SkAlphaType &&
       source.alphaType() != kUnpremul_SkAlphaType &&
       source.alphaType() != kPremul_SkAlphaType) ||
      !source.colorSpace() || !source.colorSpace()->isSRGB()) {
    return base::unexpected(CanvasCopyError::kUnsupportedFormat);
  }
  if (source.width() <= 0 || source.height() <= 0 || !source.addr()) {
    return base::unexpected(CanvasCopyError::kInvalidLayout);
  }
  const size_t width = source.width();
  const size_t height = source.height();
  if (width > std::numeric_limits<size_t>::max() / 4 / height ||
      source.rowBytes() < width * 4 ||
      source.computeByteSize() == std::numeric_limits<size_t>::max()) {
    return base::unexpected(CanvasCopyError::kInvalidLayout);
  }
  const size_t bytes = width * height * 4;
  if (bytes > memory_limit_bytes) {
    return base::unexpected(CanvasCopyError::kMemoryLimit);
  }
  const auto info = SkImageInfo::Make(source.width(), source.height(),
                                     kRGBA_8888_SkColorType,
                                     kUnpremul_SkAlphaType,
                                     source.refColorSpace());
  SkBitmap copy;
  if (!copy.tryAllocPixels(info, width * 4)) {
    return base::unexpected(CanvasCopyError::kAllocationFailed);
  }
  if (!source.readPixels(copy.pixmap(), 0, 0)) {
    return base::unexpected(CanvasCopyError::kReadFailed);
  }
  auto pixels = std::span(static_cast<uint8_t*>(copy.getPixels()), bytes);
  if (source.alphaType() == kOpaque_SkAlphaType) {
    // Opaque metadata makes the stored alpha byte semantically irrelevant.
    for (size_t offset = 3; offset < pixels.size(); offset += 4) {
      pixels[offset] = 255;
    }
  }
  if (!TransformEdgeCoherentCanvas(pixels, source.width(), source.height(),
                                   partition_seed)) {
    return base::unexpected(CanvasCopyError::kTransformFailed);
  }
  copy.setImmutable();
  return copy;
}
}  // namespace glint::candidate
