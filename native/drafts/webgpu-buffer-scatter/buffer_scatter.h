// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#ifndef GLINT_BUFFER_SCATTER_H_
#define GLINT_BUFFER_SCATTER_H_
#include <bit>
#include "buffer_scatter_parameters.h"
#include "buffer_scatter_mapping.h"
namespace glint::candidate {
static_assert(kBufferScatterByteLimit == kWebGpuBufferScatterByteLimit);
inline std::optional<BufferScatterParameters> BuildBufferScatterParameters(
    const WebGpuReadbackRegion& region, uint64_t destination_bytes) {
    const auto words = BuildWebGpuBufferScatterWords(region, destination_bytes);
    if (!words) return std::nullopt;
    return std::bit_cast<BufferScatterParameters>(*words);
}
}  // namespace glint::candidate
#endif
