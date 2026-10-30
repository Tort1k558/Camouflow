// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_WEBGPU_READBACK_PROVENANCE_H_
#define GLINT_WEBGPU_READBACK_PROVENANCE_H_

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

#include "webgpu_readback_layout.h"

namespace glint::candidate {
struct WebGpuSnapshotToken {
  uint64_t device_epoch = 0;
  uint64_t snapshot_id = 0;
  uint64_t source_version = 0;
  uint64_t policy_generation = 0;
  bool operator==(const WebGpuSnapshotToken&) const = default;
};

struct WebGpuSourceRect {
  uint32_t x = 0;
  uint32_t y = 0;
  uint32_t full_width = 0;
  uint32_t full_height = 0;
};

struct WebGpuReadbackRegion {
  uint64_t buffer_offset = 0;
  uint64_t size = 0;
  uint64_t snapshot_offset = 0;
  WebGpuReadbackLayout snapshot_layout;
  WebGpuSnapshotToken snapshot;
  WebGpuSourceRect source_rect;
};

enum class WebGpuMapProvenance { kUnrelated, kReadback, kUnreliable, kDestroyed };
constexpr size_t kWebGpuReadbackRegionLimit = 16;

struct WebGpuReadbackPlan {
  WebGpuMapProvenance status = WebGpuMapProvenance::kUnrelated;
  uint64_t mapping_offset = 0;
  uint64_t mapping_size = 0;
  size_t count = 0;
  std::array<WebGpuReadbackRegion, kWebGpuReadbackRegionLimit> regions{};
};

// Native validated/executed writes only, under the device's queue lock. A sequence
// is a strictly increasing device execution order, not a renderer encoding ID.
// Tokens refer to retained full-surface snapshots owned by the future native hook.
// No pixels, keys, GPU resources or JavaScript state are owned by this tracker.
class WebGpuReadbackProvenance {
 public:
  WebGpuReadbackProvenance(size_t buffer_bytes, uint64_t device_epoch);
  bool RecordTextureCopy(uint64_t sequence,
                         const WebGpuReadbackLayout& layout,
                         const WebGpuSnapshotToken& snapshot,
                         const WebGpuSourceRect& source_rect);
  bool RecordFullTextureCopy(uint64_t sequence,
                             const WebGpuReadbackLayout& layout,
                             const WebGpuSnapshotToken& snapshot);
  bool RecordBufferCopy(uint64_t sequence,
                        uint64_t destination_offset,
                        const WebGpuReadbackProvenance& source,
                        uint64_t source_offset,
                        uint64_t size);
  bool InvalidateWrite(uint64_t sequence, uint64_t offset, uint64_t size);
  WebGpuReadbackPlan PlanMap(uint64_t offset, uint64_t size) const;
  void Destroy();

 private:
  bool Advance(uint64_t sequence);
  bool Poison();
  bool Erase(uint64_t offset, uint64_t size);
  bool Append(const WebGpuReadbackRegion& region);
  bool Fits(uint64_t offset, uint64_t size) const;

  size_t buffer_bytes_;
  uint64_t device_epoch_;
  uint64_t sequence_ = 0;
  bool reliable_;
  bool destroyed_ = false;
  size_t count_ = 0;
  std::array<WebGpuReadbackRegion, kWebGpuReadbackRegionLimit> regions_{};
};

// Maps one copied byte to a full snapshot's packed RGBA8 coordinate; padding and
// out-of-range bytes have no coordinate. BGRA channels map without changing alpha.
std::optional<size_t> WebGpuCanonicalByte(
    const WebGpuReadbackRegion& region,
    uint64_t buffer_offset);
}  // namespace glint::candidate
#endif
