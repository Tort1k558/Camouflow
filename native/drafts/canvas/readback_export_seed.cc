// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "readback_export_seed.h"

namespace glint::candidate {
bool ProtectWebGLCanonicalPixels(
    std::span<uint8_t> rgba,
    uint32_t width,
    uint32_t height,
    const std::array<uint8_t, 32>& partition_seed) {
  return TransformEdgeCoherentCanvas(rgba, width, height, partition_seed);
}
}  // namespace glint::candidate
