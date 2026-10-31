// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#ifndef GLINT_BUFFER_SCATTER_PARAMETERS_H_
#define GLINT_BUFFER_SCATTER_PARAMETERS_H_
#include <cstdint>
namespace glint::candidate {
struct BufferScatterParameters {
    uint32_t destination_offset, region_bytes, prefix_bytes, initial_row;
    uint32_t initial_column, source_pitch, copy_width, copy_height;
    uint32_t source_x, source_y, full_width, full_height;
    uint32_t bgra, destination_bytes, protected_bytes, reserved;
};
static_assert(sizeof(BufferScatterParameters) == 64);
constexpr uint64_t kBufferScatterByteLimit = 64 * 1024 * 1024;
constexpr uint32_t kBufferScatterThreadsPerRow = 4096;

}  // namespace glint::candidate

#endif
