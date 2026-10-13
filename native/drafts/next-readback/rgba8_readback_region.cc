// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "rgba8_readback_region.h"

#include <algorithm>
#include <functional>
#include <limits>

#include "base/numerics/checked_math.h"

namespace glint::candidate {
base::expected<Rgba8ReadbackRegion, ReadbackRegionError>
PlanRgba8ReadbackRegion(const Rgba8ReadbackRequest& request,
                        size_t additional_memory_limit) {
  if (request.frame_width <= 0 || request.frame_height <= 0 ||
      request.width < 0 || request.height < 0) {
    return base::unexpected(ReadbackRegionError::kInvalidDimensions);
  }
  Rgba8ReadbackRegion region;
  base::CheckedNumeric<size_t> rectangle_bytes = request.width;
  rectangle_bytes *= request.height;
  rectangle_bytes *= 4;
  if (!rectangle_bytes.IsValid()) {
    return base::unexpected(ReadbackRegionError::kBudgetExceeded);
  }
  region.rectangle_bytes = rectangle_bytes.ValueOrDie();
  if (request.x == 0 && request.y == 0 &&
      request.width == request.frame_width &&
      request.height == request.frame_height) {
    region.mode = Rgba8ReadbackMode::kFullFrameInPlace;
  } else if (request.width != 0 && request.height != 0) {
    const int64_t left = std::max<int64_t>(0, request.x);
    const int64_t bottom = std::max<int64_t>(0, request.y);
    const int64_t right = std::min<int64_t>(
        request.frame_width, static_cast<int64_t>(request.x) + request.width);
    const int64_t top = std::min<int64_t>(
        request.frame_height, static_cast<int64_t>(request.y) + request.height);
    if (right > left && top > bottom) {
      region.mode = Rgba8ReadbackMode::kHalo;
      const int64_t halo_left = std::max<int64_t>(0, left - 1);
      const int64_t halo_bottom = std::max<int64_t>(0, bottom - 1);
      const int64_t halo_right =
          std::min<int64_t>(request.frame_width, right + 1);
      const int64_t halo_top = std::min<int64_t>(request.frame_height, top + 1);
      region.x = static_cast<int32_t>(halo_left);
      region.y = static_cast<int32_t>(halo_bottom);
      region.width = static_cast<int32_t>(halo_right - halo_left);
      region.height = static_cast<int32_t>(halo_top - halo_bottom);
    }
  }
  base::CheckedNumeric<size_t> tile_bytes = region.width;
  tile_bytes *= region.height;
  tile_bytes *= 4;
  auto total = rectangle_bytes + tile_bytes;
  if (!total.IsValid() || total.ValueOrDie() > additional_memory_limit) {
    return base::unexpected(ReadbackRegionError::kBudgetExceeded);
  }
  region.tile_bytes = tile_bytes.ValueOrDie();
  return region;
}

base::expected<void, ReadbackRegionError> OverlayProtectedRgba8ReadbackRegion(
    std::span<const uint8_t> protected_tile,
    std::span<uint8_t> private_rectangle,
    const Rgba8ReadbackRequest& request,
    const Rgba8ReadbackRegion& region) {
  const auto expected =
      PlanRgba8ReadbackRegion(request, std::numeric_limits<size_t>::max());
  if (!expected.has_value() || *expected != region ||
      region.mode == Rgba8ReadbackMode::kFullFrameInPlace ||
      protected_tile.size() != region.tile_bytes ||
      private_rectangle.size() != region.rectangle_bytes) {
    return base::unexpected(ReadbackRegionError::kInvalidStorage);
  }
  if (region.tile_bytes == 0) {
    return {};
  }
  const std::less<const uint8_t*> less;
  if (less(protected_tile.data(), private_rectangle.last(0).data()) &&
      less(private_rectangle.data(), protected_tile.last(0).data())) {
    return base::unexpected(ReadbackRegionError::kAliasedStorage);
  }
  const int64_t left = std::max<int64_t>(0, request.x);
  const int64_t bottom = std::max<int64_t>(0, request.y);
  const int64_t right = std::min<int64_t>(
      request.frame_width, static_cast<int64_t>(request.x) + request.width);
  const int64_t top = std::min<int64_t>(
      request.frame_height, static_cast<int64_t>(request.y) + request.height);
  const size_t bytes_per_row = static_cast<size_t>(right - left) * 4;
  for (int64_t y = bottom; y < top; ++y) {
    const size_t input = (static_cast<size_t>(y - region.y) * region.width +
                          static_cast<size_t>(left - region.x)) *
                         4;
    const size_t output = (static_cast<size_t>(y - request.y) * request.width +
                           static_cast<size_t>(left - request.x)) *
                          4;
    const auto row = protected_tile.subspan(input, bytes_per_row);
    auto destination = private_rectangle.subspan(output, bytes_per_row);
    std::copy(row.begin(), row.end(), destination.begin());
  }
  return {};
}
}  // namespace glint::candidate
