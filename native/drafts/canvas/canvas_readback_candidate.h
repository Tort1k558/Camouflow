// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_CANVAS_READBACK_CANDIDATE_H_
#define GLINT_CANVAS_READBACK_CANDIDATE_H_

#include <array>
#include <cstdint>
#include <span>

namespace glint::candidate {

// Detached unpremultiplied RGBA8/sRGB copies only. No live render target writes.
// On failure the caller must discard the copy, never export a partial result.
bool TransformCanvasReadback(std::span<uint8_t> rgba,
                             uint32_t read_width,
                             uint32_t read_height,
                             int64_t origin_x,
                             int64_t origin_y,
                             uint32_t canvas_width,
                             uint32_t canvas_height,
                             const std::array<uint8_t, 32>& partition_seed);

// Alternative research candidate: identical quantized colours stay identical.
// This is not an automatic fallback or an approved browser policy.
bool TransformContentCoherentReadback(
    std::span<uint8_t> rgba,
    uint32_t read_width,
    uint32_t read_height,
    int64_t origin_x,
    int64_t origin_y,
    uint32_t canvas_width,
    uint32_t canvas_height,
    const std::array<uint8_t, 32>& partition_seed);

}  // namespace glint::candidate
#endif
