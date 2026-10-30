// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "webgpu_readback_provenance.h"

#include <algorithm>
#include <limits>

namespace glint::candidate {
namespace {
WebGpuReadbackRegion Clip(const WebGpuReadbackRegion& region,
                          uint64_t begin,
                          uint64_t end) {
  auto result = region;
  result.buffer_offset = begin;
  result.size = end - begin;
  result.snapshot_offset += begin - region.buffer_offset;
  return result;
}

bool ContainsPixels(const WebGpuReadbackRegion& region) {
  const auto end = WebGpuReadbackEnd(region.snapshot_layout,
                                    std::numeric_limits<size_t>::max());
  if (!end || region.size == 0 ||
      region.snapshot_offset > std::numeric_limits<uint64_t>::max() - region.size) {
    return false;
  }
  const auto& layout = region.snapshot_layout;
  const uint64_t begin = std::max(layout.offset, region.snapshot_offset);
  const uint64_t finish = std::min(*end, region.snapshot_offset + region.size);
  if (begin >= finish) {
    return false;
  }
  const uint64_t row_bytes = static_cast<uint64_t>(layout.width) * 4;
  const uint64_t pitch = layout.row_pitch == 0 ? row_bytes : layout.row_pitch;
  const uint64_t position = begin - layout.offset;
  const uint64_t row = position / pitch;
  if (position % pitch < row_bytes) {
    return true;
  }
  return row + 1 < layout.height &&
         layout.offset + (row + 1) * pitch < finish;
}
}  // namespace

WebGpuReadbackProvenance::WebGpuReadbackProvenance(size_t buffer_bytes,
                                                 uint64_t device_epoch)
    : buffer_bytes_(buffer_bytes),
      device_epoch_(device_epoch),
      reliable_(device_epoch != 0) {}

bool WebGpuReadbackProvenance::Poison() {
  reliable_ = false;
  count_ = 0;
  return false;
}

bool WebGpuReadbackProvenance::Fits(uint64_t offset, uint64_t size) const {
  return offset <= buffer_bytes_ && size <= buffer_bytes_ - offset;
}

bool WebGpuReadbackProvenance::Advance(uint64_t sequence) {
  if (destroyed_ || !reliable_) {
    return false;
  }
  if (sequence == 0 || sequence <= sequence_) {
    return Poison();
  }
  sequence_ = sequence;
  return true;
}

bool WebGpuReadbackProvenance::Append(const WebGpuReadbackRegion& region) {
  if (!ContainsPixels(region)) {
    return true;
  }
  if (count_ == regions_.size()) {
    return Poison();
  }
  regions_[count_++] = region;
  return true;
}

bool WebGpuReadbackProvenance::Erase(uint64_t offset, uint64_t size) {
  if (size == 0) {
    return true;
  }
  const auto old = regions_;
  const size_t previous_count = count_;
  count_ = 0;
  const uint64_t end = offset + size;
  for (size_t i = 0; i < previous_count; ++i) {
    const auto& region = old[i];
    const uint64_t region_end = region.buffer_offset + region.size;
    if (offset >= region_end || end <= region.buffer_offset) {
      if (!Append(region)) {
        return false;
      }
    } else {
      if (region.buffer_offset < offset &&
          !Append(Clip(region, region.buffer_offset, offset))) {
        return false;
      }
      if (end < region_end && !Append(Clip(region, end, region_end))) {
        return false;
      }
    }
  }
  return true;
}

bool WebGpuReadbackProvenance::RecordTextureCopy(
    uint64_t sequence,
    const WebGpuReadbackLayout& layout,
    const WebGpuSnapshotToken& snapshot,
    const WebGpuSourceRect& source_rect) {
  if (!Advance(sequence)) {
    return false;
  }
  if (layout.width == 0 || layout.height == 0) {
    return Fits(layout.offset, 0) || Poison();
  }
  const auto end = WebGpuReadbackEnd(layout, buffer_bytes_);
  if (!end || snapshot.device_epoch != device_epoch_ ||
      snapshot.snapshot_id == 0 || snapshot.source_version == 0 ||
      snapshot.policy_generation == 0 ||
      source_rect.x > source_rect.full_width ||
      source_rect.y > source_rect.full_height ||
      layout.width > source_rect.full_width - source_rect.x ||
      layout.height > source_rect.full_height - source_rect.y ||
      !WebGpuPackedPixelBytes({0, 0, source_rect.full_width,
                               source_rect.full_height, layout.format})) {
    return Poison();
  }
  const uint64_t row_bytes = static_cast<uint64_t>(layout.width) * 4;
  for (uint32_t row = 0; row < layout.height && count_ != 0; ++row) {
    if (!Erase(layout.offset + static_cast<uint64_t>(row) * layout.row_pitch,
               row_bytes)) {
      return false;
    }
  }
  return Append({layout.offset, *end - layout.offset, layout.offset,
                 layout, snapshot, source_rect});
}

bool WebGpuReadbackProvenance::RecordFullTextureCopy(
    uint64_t sequence,
    const WebGpuReadbackLayout& layout,
    const WebGpuSnapshotToken& snapshot) {
  return RecordTextureCopy(sequence, layout, snapshot,
      {0, 0, layout.width, layout.height});
}

bool WebGpuReadbackProvenance::RecordBufferCopy(
    uint64_t sequence,
    uint64_t destination_offset,
    const WebGpuReadbackProvenance& source,
    uint64_t source_offset,
    uint64_t size) {
  const auto previous = source;
  if (!Advance(sequence)) {
    return false;
  }
  if (!previous.reliable_ || previous.destroyed_ ||
      previous.device_epoch_ != device_epoch_ || previous.sequence_ >= sequence ||
      !Fits(destination_offset, size) || !previous.Fits(source_offset, size) ||
      destination_offset % 4 != 0 || source_offset % 4 != 0 || size % 4 != 0) {
    return Poison();
  }
  if (size == 0) {
    return true;
  }
  if (this == &source && destination_offset < source_offset + size &&
      source_offset < destination_offset + size) {
    return Poison();
  }
  if (!Erase(destination_offset, size)) {
    return false;
  }
  for (size_t i = 0; i < previous.count_; ++i) {
    const auto& region = previous.regions_[i];
    const uint64_t begin = std::max(source_offset, region.buffer_offset);
    const uint64_t end = std::min(source_offset + size,
                                  region.buffer_offset + region.size);
    if (begin < end) {
      auto copied = Clip(region, begin, end);
      copied.buffer_offset = destination_offset + begin - source_offset;
      if (!Append(copied)) {
        return false;
      }
    }
  }
  return true;
}

bool WebGpuReadbackProvenance::InvalidateWrite(uint64_t sequence,
                                             uint64_t offset,
                                             uint64_t size) {
  if (!Advance(sequence)) {
    return false;
  }
  if (!Fits(offset, size)) {
    return Poison();
  }
  return Erase(offset, size);
}

WebGpuReadbackPlan WebGpuReadbackProvenance::PlanMap(uint64_t offset,
                                                   uint64_t size) const {
  WebGpuReadbackPlan plan;
  plan.mapping_offset = offset;
  plan.mapping_size = size;
  if (destroyed_) {
    plan.status = WebGpuMapProvenance::kDestroyed;
  } else if (!reliable_ || !Fits(offset, size)) {
    plan.status = WebGpuMapProvenance::kUnreliable;
  } else if (size != 0) {
    for (size_t i = 0; i < count_; ++i) {
      const auto& region = regions_[i];
      const uint64_t begin = std::max(offset, region.buffer_offset);
      const uint64_t end = std::min(offset + size,
                                    region.buffer_offset + region.size);
      if (begin < end) {
        auto clipped = Clip(region, begin, end);
        if (ContainsPixels(clipped)) {
          plan.regions[plan.count++] = clipped;
        }
      }
    }
    if (plan.count != 0) {
      plan.status = WebGpuMapProvenance::kReadback;
    }
  }
  return plan;
}

void WebGpuReadbackProvenance::Destroy() {
  destroyed_ = true;
  reliable_ = false;
  count_ = 0;
}

std::optional<size_t> WebGpuCanonicalByte(
    const WebGpuReadbackRegion& region,
    uint64_t buffer_offset) {
  if (buffer_offset < region.buffer_offset ||
      buffer_offset - region.buffer_offset >= region.size ||
      region.snapshot_offset > std::numeric_limits<uint64_t>::max() -
                                   (buffer_offset - region.buffer_offset)) {
    return std::nullopt;
  }
  const auto& layout = region.snapshot_layout;
  const auto& rectangle = region.source_rect;
  if (rectangle.x > rectangle.full_width || rectangle.y > rectangle.full_height ||
      layout.width > rectangle.full_width - rectangle.x ||
      layout.height > rectangle.full_height - rectangle.y ||
      !WebGpuPackedPixelBytes({0, 0, rectangle.full_width,
                               rectangle.full_height, layout.format})) {
    return std::nullopt;
  }
  const auto end = WebGpuReadbackEnd(layout,
                                    std::numeric_limits<size_t>::max());
  const uint64_t original = region.snapshot_offset +
                            (buffer_offset - region.buffer_offset);
  if (!end || original < layout.offset || original >= *end) {
    return std::nullopt;
  }
  const uint64_t row_bytes = static_cast<uint64_t>(layout.width) * 4;
  const uint64_t pitch = layout.row_pitch == 0 ? row_bytes : layout.row_pitch;
  const uint64_t relative = original - layout.offset;
  const uint64_t row = relative / pitch;
  const uint64_t column = relative % pitch;
  if (row >= layout.height || column >= row_bytes) {
    return std::nullopt;
  }
  uint64_t channel = column % 4;
  if (layout.format == WebGpuPixelFormat::kBgra8Unorm && channel % 2 == 0) {
    channel = 2 - channel;
  }
  return static_cast<size_t>(
      ((row + rectangle.y) * rectangle.full_width + column / 4 + rectangle.x) * 4 +
      channel);
}
}  // namespace glint::candidate
