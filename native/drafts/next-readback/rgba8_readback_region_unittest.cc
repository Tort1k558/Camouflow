// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "rgba8_readback_region.h"

#include <array>
#include <limits>
#include <vector>

#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/renderer/core/html/canvas/glint/readback_export_seed.h"

namespace glint::candidate {
namespace {
TEST(GlintRgba8ReadbackRegionTest, TinyCropUsesHaloNotWholeLargeFramebuffer) {
  const auto region = PlanRgba8ReadbackRegion({4096, 4096, 100, 100, 1, 1}, 40);
  ASSERT_TRUE(region.has_value());
  EXPECT_EQ(region->mode, Rgba8ReadbackMode::kHalo);
  EXPECT_EQ(region->x, 99);
  EXPECT_EQ(region->y, 99);
  EXPECT_EQ(region->width, 3);
  EXPECT_EQ(region->height, 3);
  EXPECT_EQ(region->rectangle_bytes, 4u);
  EXPECT_EQ(region->tile_bytes, 36u);
  EXPECT_FALSE(PlanRgba8ReadbackRegion({4096, 4096, 100, 100, 1, 1}, 39));
}

TEST(GlintRgba8ReadbackRegionTest, ExactFullFrameNeedsOnePrivateAllocation) {
  constexpr size_t kBudget = 64U * 1024U * 1024U;
  const auto region =
      PlanRgba8ReadbackRegion({4096, 4096, 0, 0, 4096, 4096}, kBudget);
  ASSERT_TRUE(region.has_value());
  EXPECT_EQ(region->mode, Rgba8ReadbackMode::kFullFrameInPlace);
  EXPECT_EQ(region->rectangle_bytes, kBudget);
  EXPECT_EQ(region->tile_bytes, 0u);
  EXPECT_FALSE(
      PlanRgba8ReadbackRegion({4096, 4096, 0, 0, 4096, 4096}, kBudget - 1));
}

TEST(GlintRgba8ReadbackRegionTest, CanvasBoundaryClipsHalo) {
  const auto region = PlanRgba8ReadbackRegion({8, 6, -1, -2, 3, 4}, 1024);
  ASSERT_TRUE(region.has_value());
  EXPECT_EQ(region->x, 0);
  EXPECT_EQ(region->y, 0);
  EXPECT_EQ(region->width, 3);
  EXPECT_EQ(region->height, 3);
}

TEST(GlintRgba8ReadbackRegionTest, OutsideOnlyKeepsPrivateDriverPixels) {
  const Rgba8ReadbackRequest request{8, 6, -20, -20, 2, 2};
  const auto region = PlanRgba8ReadbackRegion(request, 16);
  ASSERT_TRUE(region.has_value());
  EXPECT_EQ(region->mode, Rgba8ReadbackMode::kOutsideOnly);
  std::array<uint8_t, 16> rectangle;
  rectangle.fill(165);
  const auto before = rectangle;
  EXPECT_TRUE(
      OverlayProtectedRgba8ReadbackRegion({}, rectangle, request, *region));
  EXPECT_EQ(rectangle, before);
}

TEST(GlintRgba8ReadbackRegionTest, ExtremeCoordinatesDoNotOverflowClipping) {
  const auto high = PlanRgba8ReadbackRegion(
      {8, 6, std::numeric_limits<int32_t>::max(), 0, 1, 1}, 4);
  const auto low = PlanRgba8ReadbackRegion(
      {8, 6, std::numeric_limits<int32_t>::min(), 0, 1, 1}, 4);
  ASSERT_TRUE(high.has_value());
  ASSERT_TRUE(low.has_value());
  EXPECT_EQ(high->tile_bytes, 0u);
  EXPECT_EQ(low->tile_bytes, 0u);
}

TEST(GlintRgba8ReadbackRegionTest, InvalidDimensionsAndUnboundedMemoryReject) {
  EXPECT_FALSE(PlanRgba8ReadbackRegion({0, 6, 0, 0, 1, 1}, 1024));
  EXPECT_FALSE(PlanRgba8ReadbackRegion({8, 6, 0, 0, -1, 1}, 1024));
  const auto max = std::numeric_limits<int32_t>::max();
  EXPECT_FALSE(PlanRgba8ReadbackRegion({max, max, 1, 1, max, max}, 1024));
}

TEST(GlintRgba8ReadbackRegionTest, EmptyReadHasNoTileOrStorage) {
  const Rgba8ReadbackRequest request{8, 6, 2, 2, 0, 4};
  const auto region = PlanRgba8ReadbackRegion(request, 0);
  ASSERT_TRUE(region.has_value());
  EXPECT_EQ(region->rectangle_bytes, 0u);
  EXPECT_EQ(region->tile_bytes, 0u);
  EXPECT_TRUE(OverlayProtectedRgba8ReadbackRegion({}, {}, request, *region));
}

TEST(GlintRgba8ReadbackRegionTest,
     OverlayCannotSilentlySkipFullFrameTransform) {
  const Rgba8ReadbackRequest request{1, 1, 0, 0, 1, 1};
  const auto region = PlanRgba8ReadbackRegion(request, 4);
  ASSERT_TRUE(region.has_value());
  std::array<uint8_t, 4> rectangle{1, 2, 3, 255};
  const auto before = rectangle;
  EXPECT_FALSE(
      OverlayProtectedRgba8ReadbackRegion({}, rectangle, request, *region));
  EXPECT_EQ(rectangle, before);
}

TEST(GlintRgba8ReadbackRegionTest, ForgedPlanAndWrongStorageNeverWrite) {
  const Rgba8ReadbackRequest request{4, 4, 1, 1, 1, 1};
  auto region = PlanRgba8ReadbackRegion(request, 40);
  ASSERT_TRUE(region.has_value());
  std::array<uint8_t, 36> tile{};
  std::array<uint8_t, 4> rectangle{165, 165, 165, 165};
  const auto before = rectangle;
  EXPECT_FALSE(OverlayProtectedRgba8ReadbackRegion(
      std::span(tile).first(32), rectangle, request, *region));
  region->x = 1;
  EXPECT_FALSE(
      OverlayProtectedRgba8ReadbackRegion(tile, rectangle, request, *region));
  EXPECT_EQ(rectangle, before);
}

TEST(GlintRgba8ReadbackRegionTest, AliasedStorageRejectsBeforeWrite) {
  const Rgba8ReadbackRequest request{4, 4, 1, 1, 1, 1};
  const auto region = PlanRgba8ReadbackRegion(request, 40);
  ASSERT_TRUE(region.has_value());
  std::array<uint8_t, 36> tile{};
  const auto before = tile;
  EXPECT_FALSE(OverlayProtectedRgba8ReadbackRegion(
      tile, std::span(tile).subspan(8, 4), request, *region));
  EXPECT_EQ(tile, before);
}

TEST(GlintRgba8ReadbackRegionTest, HaloMatchesFullCanvasForEverySmallCrop) {
  constexpr int kWidth = 7, kHeight = 6;
  std::array<uint8_t, 32> seed;
  seed.fill(17);
  std::vector<uint8_t> original(kWidth * kHeight * 4);
  for (int y = 0; y < kHeight; ++y) {
    for (int x = 0; x < kWidth; ++x) {
      const size_t offset = (y * kWidth + x) * 4;
      original[offset] = (x * 31 + y * 7) % 256;
      original[offset + 1] = (x * 3 + y * 33) % 256;
      original[offset + 2] = ((x + y) / 2) * 19;
      original[offset + 3] = (x + y) % 5 == 0   ? 0
                             : (x + y) % 7 == 0 ? 127
                                                : 255;
    }
  }
  auto full = original;
  ASSERT_TRUE(ProtectWebGLCanonicalPixels(full, kWidth, kHeight, seed));
  for (int y = -2; y < kHeight + 2; ++y) {
    for (int x = -2; x < kWidth + 2; ++x) {
      for (int height = 0; height <= 4; ++height) {
        for (int width = 0; width <= 5; ++width) {
          const Rgba8ReadbackRequest request{kWidth, kHeight, x,
                                             y,      width,   height};
          const auto region = PlanRgba8ReadbackRegion(request, 1024);
          ASSERT_TRUE(region.has_value());
          std::vector<uint8_t> tile(region->tile_bytes);
          for (int row = 0; row < region->height; ++row) {
            for (int column = 0; column < region->width; ++column) {
              const size_t input =
                  ((row + region->y) * kWidth + column + region->x) * 4;
              const size_t output = (row * region->width + column) * 4;
              for (int channel = 0; channel < 4; ++channel)
                tile[output + channel] = original[input + channel];
            }
          }
          if (!tile.empty())
            ASSERT_TRUE(ProtectWebGLCanonicalPixels(tile, region->width,
                                                    region->height, seed));
          const auto protected_tile = tile;
          std::vector<uint8_t> rectangle(region->rectangle_bytes, 165);
          auto expected = rectangle;
          for (int row = 0; row < height; ++row) {
            for (int column = 0; column < width; ++column) {
              if (x + column < 0 || x + column >= kWidth || y + row < 0 ||
                  y + row >= kHeight)
                continue;
              const size_t input = ((y + row) * kWidth + x + column) * 4;
              const size_t output = (row * width + column) * 4;
              for (int channel = 0; channel < 4; ++channel) {
                rectangle[output + channel] = original[input + channel];
                expected[output + channel] = full[input + channel];
              }
            }
          }
          ASSERT_TRUE(OverlayProtectedRgba8ReadbackRegion(tile, rectangle,
                                                          request, *region));
          EXPECT_EQ(rectangle, expected);
          EXPECT_EQ(tile, protected_tile);
        }
      }
    }
  }
}
}  // namespace
}  // namespace glint::candidate
