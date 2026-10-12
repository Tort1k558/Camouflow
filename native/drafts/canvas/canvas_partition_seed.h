// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_CANVAS_PARTITION_SEED_H_
#define GLINT_CANVAS_PARTITION_SEED_H_

#include <array>
#include <cstdint>
#include <optional>

#include "third_party/blink/renderer/core/core_export.h"

namespace blink {
class ExecutionContext;
}

namespace glint::candidate {
// Only consumes the owned native bootstrap; never a page-provided seed.
CORE_EXPORT std::optional<std::array<uint8_t, 32>> CanvasPartitionSeed(
    blink::ExecutionContext* context);
}

#endif
