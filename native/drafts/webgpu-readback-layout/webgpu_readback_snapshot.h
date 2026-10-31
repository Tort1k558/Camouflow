// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_WEBGPU_READBACK_SNAPSHOT_H_
#define GLINT_WEBGPU_READBACK_SNAPSHOT_H_

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <span>

#include "webgpu_readback_provenance.h"

namespace glint::candidate {
struct WebGpuMappedShadow {
  std::unique_ptr<uint8_t[]> bytes;
  size_t size = 0;
};

// Whole-surface snapshots from a trusted native execution boundary only. Seeds
// are supplied by that context's policy and are not retained. Call under the
// owning device lock. Returned shadows still need native mapped-buffer lifetime
// integration; this class never installs JavaScript hooks or owns GPU resources.
class WebGpuReadbackSnapshots {
 public:
  WebGpuReadbackSnapshots(uint64_t device_epoch,
                          uint64_t policy_generation,
                          size_t snapshot_limit_bytes,
                          size_t shadow_limit_bytes);
  // Issue in native execution order; completion may arrive in any order.
  bool BeginCapture(const WebGpuSnapshotToken& token,
                     const WebGpuReadbackLayout& full_surface);
  bool CompleteCapture(const WebGpuSnapshotToken& token,
                        const WebGpuReadbackLayout& full_surface,
                        uint64_t mapping_offset,
                        std::span<const uint8_t> mapped,
                        const std::array<uint8_t, 32>& seed);
  bool Capture(const WebGpuSnapshotToken& token,
                const WebGpuReadbackLayout& full_surface,
                uint64_t mapping_offset,
                std::span<const uint8_t> mapped,
                const std::array<uint8_t, 32>& seed);
  std::optional<WebGpuMappedShadow> BuildProtectedShadow(
      const WebGpuReadbackPlan& plan,
      uint64_t mapping_offset,
      std::span<const uint8_t> mapped) const;
  bool Release(const WebGpuSnapshotToken& token);
  void Destroy();
  size_t retained_bytes() const { return retained_bytes_; }
  size_t reserved_bytes() const { return reserved_bytes_; }
  size_t pending_count() const;

 private:
  struct Snapshot {
    enum class State { kFree, kPending, kReady };
    State state = State::kFree;
    WebGpuSnapshotToken token;
    WebGpuReadbackLayout capture_layout;
    uint32_t width = 0;
    uint32_t height = 0;
    WebGpuPixelFormat format = WebGpuPixelFormat::kRgba8Unorm;
    size_t size = 0;
    std::unique_ptr<uint8_t[]> original;
    std::unique_ptr<uint8_t[]> protected_pixels;
  };
  const Snapshot* Find(const WebGpuSnapshotToken& token) const;

  uint64_t device_epoch_;
  uint64_t policy_generation_;
  uint64_t last_snapshot_id_ = 0;
  size_t snapshot_limit_bytes_;
  size_t shadow_limit_bytes_;
  size_t retained_bytes_ = 0;
  size_t reserved_bytes_ = 0;
  bool destroyed_ = false;
  std::array<Snapshot, kWebGpuReadbackRegionLimit> snapshots_{};
};
}  // namespace glint::candidate
#endif
