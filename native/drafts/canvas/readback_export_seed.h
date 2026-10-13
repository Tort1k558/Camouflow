// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_READBACK_EXPORT_SEED_H_
#define GLINT_READBACK_EXPORT_SEED_H_

#include "base/feature_list.h"
#include "canvas_partition_seed.h"
#include "canvas_readback_candidate.h"
#include "third_party/blink/public/common/features.h"

namespace glint::candidate {
// Component-safe bridge: the transform implementation belongs to blink_core.
CORE_EXPORT bool ProtectWebGLCanonicalPixels(
    std::span<uint8_t> rgba,
    uint32_t width,
    uint32_t height,
    const std::array<uint8_t, 32>& partition_seed);

inline SurfaceSeedResult CanvasExportPartitionSeed(
    blink::ExecutionContext* context,
    bool webgl_context) {
  if (!webgl_context || !base::FeatureList::IsEnabled(
                            blink::features::kGlintWebGLReadbackCandidate)) {
    return CanvasPartitionSeed(context);
  }
  auto seed = SurfacePartitionSeed(context, SurfaceSeedKind::kWebGL);
  if (seed.has_value() && !seed.value()) {
    return base::unexpected(SurfaceSeedError::kInvalidPolicy);
  }
  return seed;
}
}  // namespace glint::candidate
#endif
