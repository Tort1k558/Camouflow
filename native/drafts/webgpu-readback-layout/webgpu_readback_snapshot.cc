// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "webgpu_readback_snapshot.h"

#include <algorithm>
#include <limits>
#include <new>

#include "third_party/blink/renderer/core/html/canvas/glint/canvas_readback_candidate.h"

namespace glint::candidate {
WebGpuReadbackSnapshots::WebGpuReadbackSnapshots(uint64_t device_epoch,
                                                 uint64_t policy_generation,
                                                 size_t snapshot_limit_bytes,
                                                 size_t shadow_limit_bytes)
    : device_epoch_(device_epoch),
      policy_generation_(policy_generation),
      snapshot_limit_bytes_(snapshot_limit_bytes),
      shadow_limit_bytes_(shadow_limit_bytes),
      destroyed_(device_epoch == 0 || policy_generation == 0) {}

bool WebGpuReadbackSnapshots::BeginCapture(
    const WebGpuSnapshotToken& token,
    const WebGpuReadbackLayout& full_surface) {
  if (destroyed_ || token.device_epoch != device_epoch_ ||
      token.policy_generation != policy_generation_ || token.source_version == 0 ||
      token.snapshot_id <= last_snapshot_id_) {
    return false;
  }
  const auto packed = WebGpuPackedPixelBytes(full_surface);
  if (!packed || !WebGpuReadbackEnd(full_surface, std::numeric_limits<size_t>::max()) ||
      *packed > (snapshot_limit_bytes_ - reserved_bytes_) / 2) {
    return false;
  }
  auto slot = std::find_if(snapshots_.begin(), snapshots_.end(),
      [](const Snapshot& value) { return value.state == Snapshot::State::kFree; });
  if (slot == snapshots_.end()) {
    return false;
  }
  slot->state = Snapshot::State::kPending;
  slot->token = token;
  slot->capture_layout = full_surface;
  slot->width = full_surface.width;
  slot->height = full_surface.height;
  slot->format = full_surface.format;
  slot->size = *packed;
  reserved_bytes_ += *packed * 2;
  last_snapshot_id_ = token.snapshot_id;
  return true;
}

bool WebGpuReadbackSnapshots::CompleteCapture(
    const WebGpuSnapshotToken& token,
    const WebGpuReadbackLayout& full_surface,
    uint64_t mapping_offset,
    std::span<const uint8_t> mapped,
    const std::array<uint8_t, 32>& seed) {
  if (destroyed_ || token.snapshot_id == 0) {
    return false;
  }
  auto slot = std::find_if(snapshots_.begin(), snapshots_.end(),
      [&token](const Snapshot& value) {
        return value.state == Snapshot::State::kPending && value.token == token;
      });
  if (slot == snapshots_.end()) {
    return false;
  }
  const auto cancel = [&]() {
    const auto abandoned = slot->token;
    Release(abandoned);
    return false;
  };
  const auto& expected = slot->capture_layout;
  if (full_surface.offset != expected.offset || full_surface.row_pitch != expected.row_pitch ||
      full_surface.width != expected.width || full_surface.height != expected.height ||
      full_surface.format != expected.format) {
    return cancel();
  }
  const size_t packed = slot->size;
  auto original = std::unique_ptr<uint8_t[]>(new (std::nothrow) uint8_t[packed]);
  auto protected_pixels = std::unique_ptr<uint8_t[]>(new (std::nothrow) uint8_t[packed]);
  if (!original || !protected_pixels ||
      !ExtractWebGpuRgba8(mapped, mapping_offset, full_surface,
                         {original.get(), packed})) {
    return cancel();
  }
  std::copy_n(original.get(), packed, protected_pixels.get());
  if (!TransformEdgeCoherentCanvas({protected_pixels.get(), packed},
                                   full_surface.width, full_surface.height, seed)) {
    return cancel();
  }
  slot->original = std::move(original);
  slot->protected_pixels = std::move(protected_pixels);
  slot->state = Snapshot::State::kReady;
  retained_bytes_ += packed * 2;
  return true;
}

bool WebGpuReadbackSnapshots::Capture(
    const WebGpuSnapshotToken& token,
    const WebGpuReadbackLayout& full_surface,
    uint64_t mapping_offset,
    std::span<const uint8_t> mapped,
    const std::array<uint8_t, 32>& seed) {
  return BeginCapture(token, full_surface) &&
         CompleteCapture(token, full_surface, mapping_offset, mapped, seed);
}

size_t WebGpuReadbackSnapshots::pending_count() const {
  return static_cast<size_t>(std::count_if(snapshots_.begin(), snapshots_.end(),
      [](const Snapshot& value) { return value.state == Snapshot::State::kPending; }));
}

const WebGpuReadbackSnapshots::Snapshot* WebGpuReadbackSnapshots::Find(
    const WebGpuSnapshotToken& token) const {
  for (const auto& snapshot : snapshots_) {
    if (snapshot.state == Snapshot::State::kReady && snapshot.token == token) {
      return &snapshot;
    }
  }
  return nullptr;
}

std::optional<WebGpuMappedShadow> WebGpuReadbackSnapshots::BuildProtectedShadow(
    const WebGpuReadbackPlan& plan,
    uint64_t mapping_offset,
    std::span<const uint8_t> mapped) const {
  if (destroyed_ || plan.status != WebGpuMapProvenance::kReadback ||
      plan.count == 0 || plan.count > plan.regions.size() ||
      plan.mapping_offset != mapping_offset || plan.mapping_size != mapped.size() ||
      mapped.empty() || mapped.size() > shadow_limit_bytes_ ||
      mapped.size() > std::numeric_limits<uint64_t>::max() - mapping_offset) {
    return std::nullopt;
  }
  const size_t marker_bytes = mapped.size() / 8 + (mapped.size() % 8 != 0);
  if (marker_bytes > shadow_limit_bytes_ - mapped.size()) {
    return std::nullopt;
  }
  WebGpuMappedShadow shadow;
  shadow.bytes.reset(new (std::nothrow) uint8_t[mapped.size()]);
  auto written = std::unique_ptr<uint8_t[]>(new (std::nothrow) uint8_t[marker_bytes]());
  if (!shadow.bytes || !written) {
    return std::nullopt;
  }
  shadow.size = mapped.size();
  std::copy(mapped.begin(), mapped.end(), shadow.bytes.get());
  bool observed_pixel = false;
  for (size_t index = 0; index < plan.count; ++index) {
    const auto& region = plan.regions[index];
    const auto* snapshot = Find(region.snapshot);
    const auto source_end = WebGpuReadbackEnd(region.snapshot_layout,
        std::numeric_limits<size_t>::max());
    if (!snapshot || !source_end || region.size == 0 ||
        region.buffer_offset < mapping_offset ||
        region.buffer_offset - mapping_offset > mapped.size() ||
        region.size > mapped.size() - (region.buffer_offset - mapping_offset) ||
        region.snapshot_offset < region.snapshot_layout.offset ||
        region.snapshot_offset > *source_end || region.size > *source_end - region.snapshot_offset ||
        region.source_rect.full_width != snapshot->width ||
        region.source_rect.full_height != snapshot->height ||
        region.source_rect.x > snapshot->width || region.source_rect.y > snapshot->height ||
        region.snapshot_layout.width > snapshot->width - region.source_rect.x ||
        region.snapshot_layout.height > snapshot->height - region.source_rect.y ||
        region.snapshot_layout.format != snapshot->format) {
      return std::nullopt;
    }
    const auto& layout = region.snapshot_layout;
    const uint64_t row_bytes = static_cast<uint64_t>(layout.width) * 4;
    const uint64_t pitch = layout.row_pitch == 0 ? row_bytes : layout.row_pitch;
    const uint64_t begin = region.snapshot_offset;
    const uint64_t end = begin + region.size;
    const uint64_t first_row = (begin - layout.offset) / pitch;
    const uint64_t last_row = (end - 1 - layout.offset) / pitch;
    for (uint64_t row = first_row; row <= last_row; ++row) {
      const uint64_t row_start = layout.offset + row * pitch;
      const uint64_t pixel_begin = std::max(begin, row_start);
      const uint64_t pixel_end = std::min(end, row_start + row_bytes);
      const uint64_t canonical_row =
          ((row + region.source_rect.y) * snapshot->width + region.source_rect.x) * 4;
      for (uint64_t byte = pixel_begin; byte < pixel_end; ++byte) {
        const uint64_t column = byte - row_start;
        uint64_t channel = column % 4;
        if (layout.format == WebGpuPixelFormat::kBgra8Unorm && channel % 2 == 0) {
          channel = 2 - channel;
        }
        const size_t canonical = static_cast<size_t>(canonical_row + (column / 4) * 4 + channel);
        const size_t local = static_cast<size_t>(region.buffer_offset - mapping_offset + byte - begin);
        const uint8_t bit = static_cast<uint8_t>(1u << (local % 8));
        if (canonical >= snapshot->size || (written[local / 8] & bit) != 0 ||
            mapped[local] != snapshot->original[canonical]) {
          return std::nullopt;
        }
        written[local / 8] |= bit;
        observed_pixel = true;
        shadow.bytes[local] = snapshot->protected_pixels[canonical];
      }
    }
  }
  if (!observed_pixel) {
    return std::nullopt;
  }
  return shadow;
}

bool WebGpuReadbackSnapshots::Release(const WebGpuSnapshotToken& token) {
  for (auto& snapshot : snapshots_) {
    if (snapshot.state != Snapshot::State::kFree && snapshot.token == token) {
      reserved_bytes_ -= snapshot.size * 2;
      if (snapshot.state == Snapshot::State::kReady) {
        retained_bytes_ -= snapshot.size * 2;
      }
      snapshot = Snapshot{};
      return true;
    }
  }
  return false;
}

void WebGpuReadbackSnapshots::Destroy() {
  destroyed_ = true;
  for (auto& snapshot : snapshots_) {
    snapshot = Snapshot{};
  }
  retained_bytes_ = 0;
  reserved_bytes_ = 0;
}
}  // namespace glint::candidate
