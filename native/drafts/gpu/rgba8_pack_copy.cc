// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "rgba8_pack_copy.h"

#include <algorithm>
#include <functional>

#include "base/numerics/checked_math.h"

namespace glint::candidate {
base::expected<void, Rgba8PackCopyError> CopyRgba8ReadbackToPackLayout(
    std::span<const uint8_t> source,
    std::span<uint8_t> destination,
    GLsizei width,
    GLsizei height,
    size_t destination_offset,
    const blink::WebGLImageConversion::PixelStoreParams& params) {
  if (width < 0 || height < 0 ||
      (params.alignment != 1 && params.alignment != 2 &&
       params.alignment != 4 && params.alignment != 8) ||
      params.row_length < 0 || params.skip_rows < 0 || params.skip_pixels < 0 ||
      params.image_height != 0 || params.skip_images != 0) {
    return base::unexpected(Rgba8PackCopyError::kInvalidLayout);
  }
  if (destination_offset > destination.size()) {
    return base::unexpected(Rgba8PackCopyError::kDestinationTooSmall);
  }
  unsigned image_bytes = 0, padding = 0, skip_bytes = 0;
  if (blink::WebGLImageConversion::ComputeImageSizeInBytes(
          GL_RGBA, GL_UNSIGNED_BYTE, width, height, 1, params, &image_bytes,
          &padding, &skip_bytes) != GL_NO_ERROR) {
    return base::unexpected(Rgba8PackCopyError::kInvalidLayout);
  }
  if (!width || !height) {
    return {};
  }
  base::CheckedNumeric<size_t> tight_bytes = width;
  tight_bytes *= height;
  tight_bytes *= 4;
  if (!tight_bytes.IsValid() || source.size() != tight_bytes.ValueOrDie()) {
    return base::unexpected(Rgba8PackCopyError::kInvalidSource);
  }
  base::CheckedNumeric<size_t> end = destination_offset;
  end += skip_bytes;
  end += image_bytes;
  if (!end.IsValid() || end.ValueOrDie() > destination.size()) {
    return base::unexpected(Rgba8PackCopyError::kDestinationTooSmall);
  }
  const std::less<const uint8_t*> less;
  if (less(source.data(), destination.last(0).data()) &&
      less(destination.data(), source.last(0).data())) {
    return base::unexpected(Rgba8PackCopyError::kAliasedStorage);
  }
  // Reuse upstream's padding and skip calculation, including overlapping
  // row layouts. Do not demand padding after the last row or invent GL errors.
  const size_t row_bytes = static_cast<size_t>(width) * 4;
  const size_t row_pixels = params.row_length > 0 ? params.row_length : width;
  const size_t stride = row_pixels * 4 + padding;
  const size_t start = destination_offset + skip_bytes;
  for (size_t row = 0; row < static_cast<size_t>(height); ++row) {
    const auto input = source.subspan(row * row_bytes, row_bytes);
    auto output = destination.subspan(start + row * stride, row_bytes);
    std::copy(input.begin(), input.end(), output.begin());
  }
  return {};
}
}  // namespace glint::candidate
