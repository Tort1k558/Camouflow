// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "webgpu_readback_layout.h"

#include <limits>

namespace glint::candidate {
namespace {
bool Overlaps(std::span<const uint8_t> first,
              std::span<const uint8_t> second) {
  if (first.empty() || second.empty()) {
    return false;
  }
  const auto a = reinterpret_cast<uintptr_t>(first.data());
  const auto b = reinterpret_cast<uintptr_t>(second.data());
  return a <= b ? b - a < first.size() : a - b < second.size();
}

std::optional<size_t> MappingStart(const WebGpuReadbackLayout& layout,
                                   uint64_t mapping_offset,
                                   size_t mapped_bytes,
                                   size_t packed_bytes) {
  const auto required = WebGpuPackedPixelBytes(layout);
  if (!required || *required != packed_bytes || layout.offset % 4 != 0 ||
      mapped_bytes > std::numeric_limits<uint64_t>::max() - mapping_offset ||
      mapping_offset > layout.offset) {
    return std::nullopt;
  }
  const uint64_t row_bytes = static_cast<uint64_t>(layout.width) * 4;
  if ((layout.row_pitch == 0 && layout.height != 1) ||
      (layout.row_pitch != 0 &&
       (layout.row_pitch % 256 != 0 || layout.row_pitch < row_bytes))) {
    return std::nullopt;
  }
  const uint64_t start = layout.offset - mapping_offset;
  const uint64_t previous_rows =
      static_cast<uint64_t>(layout.height - 1) * layout.row_pitch;
  if (start > mapped_bytes || previous_rows > mapped_bytes - start ||
      row_bytes > mapped_bytes - start - previous_rows) {
    return std::nullopt;
  }
  return static_cast<size_t>(start);
}
}  // namespace

std::optional<size_t> WebGpuPackedPixelBytes(
    const WebGpuReadbackLayout& layout) {
  if (layout.width == 0 || layout.height == 0 ||
      (layout.format != WebGpuPixelFormat::kRgba8Unorm &&
       layout.format != WebGpuPixelFormat::kBgra8Unorm)) {
    return std::nullopt;
  }
  const uint64_t row_bytes = static_cast<uint64_t>(layout.width) * 4;
  if (row_bytes > std::numeric_limits<size_t>::max() / layout.height) {
    return std::nullopt;
  }
  return static_cast<size_t>(row_bytes * layout.height);
}

bool ExtractWebGpuRgba8(std::span<const uint8_t> mapped,
                       uint64_t mapping_offset,
                       const WebGpuReadbackLayout& layout,
                       std::span<uint8_t> rgba) {
  const auto start = MappingStart(layout, mapping_offset, mapped.size(), rgba.size());
  if (!start || Overlaps(mapped, rgba)) {
    return false;
  }
  const size_t row_bytes = static_cast<size_t>(layout.width) * 4;
  const size_t red = layout.format == WebGpuPixelFormat::kBgra8Unorm ? 2 : 0;
  for (uint32_t y = 0; y < layout.height; ++y) {
    const auto source = mapped.subspan(*start + static_cast<size_t>(y) * layout.row_pitch, row_bytes);
    auto destination = rgba.subspan(static_cast<size_t>(y) * row_bytes, row_bytes);
    for (size_t x = 0; x < row_bytes; x += 4) {
      destination[x] = source[x + red];
      destination[x + 1] = source[x + 1];
      destination[x + 2] = source[x + 2 - red];
      destination[x + 3] = source[x + 3];
    }
  }
  return true;
}

bool StoreWebGpuRgba8(std::span<const uint8_t> rgba,
                     const WebGpuReadbackLayout& layout,
                     uint64_t mapping_offset,
                     std::span<uint8_t> mapped) {
  const auto start = MappingStart(layout, mapping_offset, mapped.size(), rgba.size());
  if (!start || Overlaps(mapped, rgba)) {
    return false;
  }
  const size_t row_bytes = static_cast<size_t>(layout.width) * 4;
  const size_t red = layout.format == WebGpuPixelFormat::kBgra8Unorm ? 2 : 0;
  for (uint32_t y = 0; y < layout.height; ++y) {
    const auto source = rgba.subspan(static_cast<size_t>(y) * row_bytes, row_bytes);
    auto destination = mapped.subspan(*start + static_cast<size_t>(y) * layout.row_pitch, row_bytes);
    for (size_t x = 0; x < row_bytes; x += 4) {
      destination[x + red] = source[x];
      destination[x + 1] = source[x + 1];
      destination[x + 2 - red] = source[x + 2];
      destination[x + 3] = source[x + 3];
    }
  }
  return true;
}
}  // namespace glint::candidate
