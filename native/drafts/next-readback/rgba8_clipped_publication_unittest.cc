// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "rgba8_pack_copy.h"

#include <array>
#include <vector>

#include "testing/gtest/include/gtest/gtest.h"

namespace glint::candidate {
namespace {
TEST(GlintRgba8ClippedPublicationTest,
     PreservesClippedPixelsPaddingAndOffsets) {
  std::array<uint8_t, 64> source;
  for (size_t index = 0; index < source.size(); ++index)
    source[index] = static_cast<uint8_t>(index);
  std::vector<uint8_t> destination(200, 165), expected = destination;
  blink::WebGLImageConversion::PixelStoreParams pack;
  pack.alignment = 8;
  pack.row_length = 6;
  pack.skip_pixels = 1;
  pack.skip_rows = 1;
  for (size_t row = 1; row < 3; ++row)
    for (size_t byte = 0; byte < 8; ++byte)
      expected[12 + 28 + row * 24 + 4 + byte] = source[row * 16 + 4 + byte];
  EXPECT_TRUE(CopyRgba8ReadbackToPackLayout(source, destination, 4, 4, 12, pack,
                                            gfx::Rect(1, 1, 2, 2))
                  .has_value());
  EXPECT_EQ(destination, expected);
}

TEST(GlintRgba8ClippedPublicationTest, EntirelyOutsideDestinationRemainsExact) {
  std::array<uint8_t, 64> source{};
  std::array<uint8_t, 64> destination;
  destination.fill(165);
  const auto before = destination;
  EXPECT_TRUE(CopyRgba8ReadbackToPackLayout(source, destination, 4, 4, 0, {},
                                            gfx::Rect())
                  .has_value());
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8ClippedPublicationTest, InvalidCopyRegionNeverWrites) {
  std::array<uint8_t, 64> source{};
  std::array<uint8_t, 64> destination;
  destination.fill(165);
  const auto before = destination;
  for (const auto& region :
       {gfx::Rect(-1, 0, 1, 1), gfx::Rect(3, 0, 2, 1), gfx::Rect(0, 3, 1, 2)}) {
    EXPECT_FALSE(
        CopyRgba8ReadbackToPackLayout(source, destination, 4, 4, 0, {}, region)
            .has_value());
    EXPECT_EQ(destination, before);
  }
}

TEST(GlintRgba8ClippedPublicationTest,
     ClipDoesNotRelaxOriginalBufferValidation) {
  std::array<uint8_t, 64> source{};
  std::array<uint8_t, 4> destination{165, 165, 165, 165};
  const auto before = destination;
  EXPECT_FALSE(CopyRgba8ReadbackToPackLayout(source, destination, 4, 4, 0, {},
                                             gfx::Rect(0, 0, 1, 1))
                   .has_value());
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8ClippedPublicationTest, AliasesRejectBeforeClippedWrites) {
  std::array<uint8_t, 80> storage;
  storage.fill(165);
  const auto before = storage;
  EXPECT_FALSE(CopyRgba8ReadbackToPackLayout(std::span(storage).first(64),
                                             std::span(storage).subspan(8, 64),
                                             4, 4, 0, {}, gfx::Rect(1, 1, 2, 2))
                   .has_value());
  EXPECT_EQ(storage, before);
}

TEST(GlintRgba8ClippedPublicationTest, FullRegionRetainsExistingPackContract) {
  std::array<uint8_t, 64> source;
  for (size_t index = 0; index < source.size(); ++index)
    source[index] = static_cast<uint8_t>(index);
  std::array<uint8_t, 64> legacy{}, clipped{};
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(source, legacy, 4, 4, 0, {}).has_value());
  ASSERT_TRUE(CopyRgba8ReadbackToPackLayout(source, clipped, 4, 4, 0, {},
                                            gfx::Rect(0, 0, 4, 4))
                  .has_value());
  EXPECT_EQ(clipped, legacy);
}
}  // namespace
}  // namespace glint::candidate
