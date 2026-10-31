// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#ifndef GLINT_WEBGPU_BUFFER_SCATTER_MAPPING_H_
#define GLINT_WEBGPU_BUFFER_SCATTER_MAPPING_H_
#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <optional>
#include "gpu/command_buffer/common/glint/webgpu_readback_provenance.h"
namespace glint::candidate {
constexpr uint64_t kWebGpuBufferScatterByteLimit = 64 * 1024 * 1024;
// Sixteen DWORDs match the native scatter ABI. This carries geometry, not authorization.
// Structural mapping only. Native policy/epoch, immutable GPU snapshot
// ownership, binding routing and alias/copyback authorization remain the
// caller's duties.
inline std::optional<std::array<uint32_t, 16>> BuildWebGpuBufferScatterWords(
    const WebGpuReadbackRegion& region,
    uint64_t destination_bytes, bool source_bgra = false) {
  const auto& layout = region.snapshot_layout;
  const auto& rectangle = region.source_rect;
  if (region.kind != WebGpuReadbackRegionKind::kPixels || !region.size ||
      !region.snapshot.device_epoch || !region.snapshot.snapshot_id ||
      !region.snapshot.source_version || !region.snapshot.policy_generation ||
      !destination_bytes || destination_bytes > kWebGpuBufferScatterByteLimit ||
      region.buffer_offset > destination_bytes ||
      region.size > destination_bytes - region.buffer_offset ||
      region.snapshot_offset >
          std::numeric_limits<uint64_t>::max() - region.size ||
      !rectangle.full_width || !rectangle.full_height ||
      rectangle.full_width > 8192 || rectangle.full_height > 8192 ||
      rectangle.x > rectangle.full_width ||
      rectangle.y > rectangle.full_height ||
      layout.width > rectangle.full_width - rectangle.x ||
      layout.height > rectangle.full_height - rectangle.y) {
    return std::nullopt;
  }
  const auto end =
      WebGpuReadbackEnd(layout, std::numeric_limits<size_t>::max());
  const auto packed = WebGpuPackedPixelBytes(
      {0, 0, rectangle.full_width, rectangle.full_height, layout.format});
  if (!end || !packed || *packed > kWebGpuBufferScatterByteLimit) {
    return std::nullopt;
  }
  const uint64_t begin = std::max(layout.offset, region.snapshot_offset);
  const uint64_t finish = std::min(*end, region.snapshot_offset + region.size);
  if (begin >= finish) {
    return std::nullopt;
  }
  const uint64_t pitch =
      layout.row_pitch ? layout.row_pitch : uint64_t{layout.width} * 4;
  const uint64_t relative = begin - layout.offset;
  const uint64_t row = relative / pitch, column = relative % pitch;
  const uint64_t prefix = begin - region.snapshot_offset;
  const uint64_t first_pixel_delta =
      column < uint64_t{layout.width} * 4 ? 0 : pitch - column;
  if (first_pixel_delta >= finish - begin ||
      !WebGpuCanonicalByte(region,
                           region.buffer_offset + prefix + first_pixel_delta)) {
    return std::nullopt;
  }
  return std::array<uint32_t, 16>{
      static_cast<uint32_t>(region.buffer_offset),
      static_cast<uint32_t>(region.size),
      static_cast<uint32_t>(prefix),
      static_cast<uint32_t>(row),
      static_cast<uint32_t>(column),
      static_cast<uint32_t>(pitch),
      layout.width,
      layout.height,
      rectangle.x,
      rectangle.y,
      rectangle.full_width,
      rectangle.full_height,
      (layout.format == WebGpuPixelFormat::kBgra8Unorm) != source_bgra ? 1u : 0u,
      static_cast<uint32_t>(destination_bytes),
      static_cast<uint32_t>(*packed),
      0};
}
}  // namespace glint::candidate
#endif
