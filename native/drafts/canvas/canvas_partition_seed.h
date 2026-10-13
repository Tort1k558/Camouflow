// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_CANVAS_PARTITION_SEED_H_
#define GLINT_CANVAS_PARTITION_SEED_H_

#include <array>
#include <cstdint>
#include <optional>

#include "base/types/expected.h"
#include "third_party/blink/renderer/core/core_export.h"

namespace blink {
class ExecutionContext;
}

namespace glint::candidate {
enum class SurfaceSeedKind { kCanvas, kWebGL, kWebGPU, kAudio };
enum class SurfaceSeedError { kUnavailableContext, kInvalidPolicy, kUnsupportedKind };
using SurfaceSeedResult =
    base::expected<std::optional<std::array<uint8_t, 32>>, SurfaceSeedError>;

// Only consumes the owned native bootstrap; never a page-provided seed.
// A successful empty result means flag-off. Required missing/invalid data is
// an error, and must never be interpreted as permission for raw readback.
CORE_EXPORT SurfaceSeedResult SurfacePartitionSeed(
    blink::ExecutionContext* context,
    SurfaceSeedKind kind);
CORE_EXPORT SurfaceSeedResult CanvasPartitionSeed(
    blink::ExecutionContext* context);
}

#endif
