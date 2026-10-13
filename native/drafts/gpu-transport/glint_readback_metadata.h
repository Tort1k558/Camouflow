// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GPU_COMMAND_BUFFER_COMMON_GLINT_READBACK_METADATA_H_
#define GPU_COMMAND_BUFFER_COMMON_GLINT_READBACK_METADATA_H_

#include <array>
#include <cstddef>
#include <limits>
#include <optional>
#include <span>

#include "gpu/command_buffer/common/gl2_types.h"

namespace gpu::gles2 {
inline constexpr std::size_t kGlintReadbackMetadataValues = 7;
using GlintReadbackMetadataWire =
    std::array<GLint, kGlintReadbackMetadataValues>;
inline constexpr GlintReadbackMetadataWire kGlintReadbackMetadataUnavailable{
    1, 0, 0, 0, 0, 0, 0};

struct GlintReadbackMetadata {
  GLsizei width;
  GLsizei height;
  GLenum internal_format;
  GLsizei samples;
  bool rgba8_compatible;
};

inline constexpr bool CanBeGlintByteColourFormat(GLenum format) {
  // OpenGL wire enum values; keep API-specific GL headers out of the codec.
  switch (format) {
    case 0x1907:  // GL_RGB
    case 0x1908:  // GL_RGBA
    case 0x8051:  // GL_RGB8
    case 0x8058:  // GL_RGBA8
      return true;
    default:
      return false;
  }
}

inline std::optional<GlintReadbackMetadata> DecodeGlintReadbackMetadata(
    std::span<const GLint> values) {
  if (values.size() != kGlintReadbackMetadataValues || values[0] != 1 ||
      values[1] != 1 || values[2] <= 0 || values[3] <= 0 || values[4] <= 0 ||
      values[5] < 0 || (values[6] != 0 && values[6] != 1) ||
      (values[6] == 1 &&
       !CanBeGlintByteColourFormat(static_cast<GLenum>(values[4])))) {
    return std::nullopt;
  }
  return GlintReadbackMetadata{values[2], values[3],
                               static_cast<GLenum>(values[4]), values[5],
                               values[6] == 1};
}

inline GlintReadbackMetadataWire EncodeGlintReadbackMetadata(
    GLsizei width,
    GLsizei height,
    GLenum internal_format,
    GLsizei samples,
    bool rgba8_compatible) {
  if (width <= 0 || height <= 0 || internal_format == 0 ||
      internal_format >
          static_cast<GLenum>(std::numeric_limits<GLint>::max()) ||
      samples < 0 ||
      (rgba8_compatible && !CanBeGlintByteColourFormat(internal_format))) {
    return kGlintReadbackMetadataUnavailable;
  }
  return {1,
          1,
          width,
          height,
          static_cast<GLint>(internal_format),
          samples,
          rgba8_compatible ? 1 : 0};
}
}  // namespace gpu::gles2
#endif
