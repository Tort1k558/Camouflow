// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_WEBGPU_READBACK_LAYOUT_H_
#define GLINT_WEBGPU_READBACK_LAYOUT_H_

#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>

namespace glint::candidate {
enum class WebGpuPixelFormat { kRgba8Unorm, kBgra8Unorm };

// One already validated 2D copy, one layer; offsets are buffer-relative.
// A zero row pitch represents the omitted bytesPerRow of a single-row copy.
struct WebGpuReadbackLayout {
  uint64_t offset = 0;
  uint32_t row_pitch = 0;
  uint32_t width = 0;
  uint32_t height = 0;
  WebGpuPixelFormat format = WebGpuPixelFormat::kRgba8Unorm;
};

std::optional<size_t> WebGpuPackedPixelBytes(const WebGpuReadbackLayout& layout);

// Detached non-overlapping storage only. Partial mappings and invalid layouts
// fail before writing any output. These helpers do not select or protect data.
bool ExtractWebGpuRgba8(std::span<const uint8_t> mapped,
                       uint64_t mapping_offset,
                       const WebGpuReadbackLayout& layout,
                       std::span<uint8_t> rgba);
bool StoreWebGpuRgba8(std::span<const uint8_t> rgba,
                     const WebGpuReadbackLayout& layout,
                     uint64_t mapping_offset,
                     std::span<uint8_t> mapped);
}  // namespace glint::candidate
#endif
