// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "rgba8_pack_copy.h"

#include <array>
#include <limits>
#include <vector>

#include "testing/gtest/include/gtest/gtest.h"

namespace glint::candidate {
namespace {
constexpr std::array<uint8_t, 16> kPixels{1, 2, 3, 255, 4,  5,  6,  255,
                                          7, 8, 9, 255, 10, 11, 12, 255};

TEST(GlintRgba8PackCopyTest, TightLayoutCopiesRowsWithoutSourceMutation) {
  auto source = kPixels;
  std::array<uint8_t, 16> destination{};
  blink::WebGLImageConversion::PixelStoreParams params;
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(source, destination, 2, 2, 0, params));
  EXPECT_EQ(destination, kPixels);
  EXPECT_EQ(source, kPixels);
}

TEST(GlintRgba8PackCopyTest, NonzeroOffsetPreservesPrefixAndSuffix) {
  std::array<uint8_t, 28> destination;
  destination.fill(165);
  blink::WebGLImageConversion::PixelStoreParams params;
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, 2, 8, params));
  for (size_t i = 0; i < destination.size(); ++i) {
    EXPECT_EQ(destination[i], i >= 8 && i < 24 ? kPixels[i - 8] : 165);
  }
}

TEST(GlintRgba8PackCopyTest, SkipsAndPaddingAreNotWritten) {
  std::array<uint8_t, 68> destination;
  destination.fill(165);
  blink::WebGLImageConversion::PixelStoreParams params;
  params.row_length = 4;
  params.skip_rows = 1;
  params.skip_pixels = 1;
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, 2, 8, params));
  auto expected = destination;
  expected.fill(165);
  for (size_t row = 0; row < 2; ++row) {
    for (size_t byte = 0; byte < 8; ++byte) {
      expected[28 + row * 16 + byte] = kPixels[row * 8 + byte];
    }
  }
  EXPECT_EQ(destination, expected);
}

TEST(GlintRgba8PackCopyTest, AlignmentEightPreservesInterRowPadding) {
  std::array<uint8_t, 24> destination;
  destination.fill(165);
  blink::WebGLImageConversion::PixelStoreParams params;
  params.alignment = 8;
  const auto source = std::span(kPixels).first(12);
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(source, destination, 1, 3, 0, params));
  for (size_t i = 0; i < destination.size(); ++i) {
    EXPECT_EQ(destination[i],
              i % 8 < 4 && i < 20 ? source[(i / 8) * 4 + i % 8] : 165);
  }
}

TEST(GlintRgba8PackCopyTest, LastRowDoesNotRequireTrailingPadding) {
  std::array<uint8_t, 12> destination{};
  blink::WebGLImageConversion::PixelStoreParams params;
  params.alignment = 8;
  ASSERT_TRUE(CopyRgba8ReadbackToPackLayout(std::span(kPixels).first(8),
                                            destination, 1, 2, 0, params));
  EXPECT_EQ(destination[8], kPixels[4]);
  EXPECT_EQ(destination[11], kPixels[7]);
}

TEST(GlintRgba8PackCopyTest, OverlappingRowsUseUpstreamLayout) {
  std::array<uint8_t, 12> destination{};
  blink::WebGLImageConversion::PixelStoreParams params;
  params.row_length = 1;
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, 2, 0, params));
  EXPECT_EQ(destination, (std::array<uint8_t, 12>{1, 2, 3, 255, 7, 8, 9, 255,
                                                  10, 11, 12, 255}));
}

TEST(GlintRgba8PackCopyTest, ShortDestinationRejectsBeforeAnyWrite) {
  std::array<uint8_t, 15> destination;
  destination.fill(165);
  const auto before = destination;
  blink::WebGLImageConversion::PixelStoreParams params;
  auto result =
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, 2, 0, params);
  ASSERT_FALSE(result);
  EXPECT_EQ(result.error(), Rgba8PackCopyError::kDestinationTooSmall);
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8PackCopyTest, WrongSourceSizeRejectsBeforeAnyWrite) {
  std::array<uint8_t, 16> destination;
  destination.fill(165);
  const auto before = destination;
  blink::WebGLImageConversion::PixelStoreParams params;
  auto result = CopyRgba8ReadbackToPackLayout(std::span(kPixels).first(15),
                                              destination, 2, 2, 0, params);
  ASSERT_FALSE(result);
  EXPECT_EQ(result.error(), Rgba8PackCopyError::kInvalidSource);
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8PackCopyTest, AliasedStorageCannotMutateCanonicalSource) {
  auto data = kPixels;
  blink::WebGLImageConversion::PixelStoreParams params;
  auto result = CopyRgba8ReadbackToPackLayout(data, data, 2, 2, 0, params);
  ASSERT_FALSE(result);
  EXPECT_EQ(result.error(), Rgba8PackCopyError::kAliasedStorage);
  EXPECT_EQ(data, kPixels);
}

TEST(GlintRgba8PackCopyTest, NegativeDimensionsRejectBeforeAnyWrite) {
  std::array<uint8_t, 16> destination{};
  const auto before = destination;
  blink::WebGLImageConversion::PixelStoreParams params;
  EXPECT_FALSE(
      CopyRgba8ReadbackToPackLayout(kPixels, destination, -1, 2, 0, params));
  EXPECT_FALSE(
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, -1, 0, params));
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8PackCopyTest, InvalidPackFieldsRejectWithoutUpstreamDcheck) {
  std::array<uint8_t, 16> destination{};
  const auto before = destination;
  for (int field = 0; field < 6; ++field) {
    blink::WebGLImageConversion::PixelStoreParams params;
    if (field == 0)
      params.alignment = 3;
    if (field == 1)
      params.row_length = -1;
    if (field == 2)
      params.skip_rows = -1;
    if (field == 3)
      params.skip_pixels = -1;
    if (field == 4)
      params.skip_images = 1;
    if (field == 5)
      params.image_height = 1;
    auto result =
        CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, 2, 0, params);
    ASSERT_FALSE(result);
    EXPECT_EQ(result.error(), Rgba8PackCopyError::kInvalidLayout);
  }
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8PackCopyTest, RowStrideOverflowRejectsBeforeAnyWrite) {
  std::array<uint8_t, 16> destination{};
  const auto before = destination;
  blink::WebGLImageConversion::PixelStoreParams params;
  params.row_length = std::numeric_limits<int>::max();
  auto result =
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, 2, 0, params);
  ASSERT_FALSE(result);
  EXPECT_EQ(result.error(), Rgba8PackCopyError::kInvalidLayout);
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8PackCopyTest, OversizedOffsetRejectsBeforeAnyWrite) {
  std::array<uint8_t, 16> destination{};
  const auto before = destination;
  blink::WebGLImageConversion::PixelStoreParams params;
  auto result = CopyRgba8ReadbackToPackLayout(
      kPixels, destination, 2, 2, std::numeric_limits<size_t>::max(), params);
  ASSERT_FALSE(result);
  EXPECT_EQ(result.error(), Rgba8PackCopyError::kDestinationTooSmall);
  EXPECT_EQ(destination, before);
}

TEST(GlintRgba8PackCopyTest, EmptyReadsDoNotTouchSourceOrDestination) {
  std::array<uint8_t, 16> destination;
  destination.fill(165);
  const auto before = destination;
  blink::WebGLImageConversion::PixelStoreParams params;
  params.skip_rows = 5;
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 0, 2, 16, params));
  ASSERT_TRUE(
      CopyRgba8ReadbackToPackLayout(kPixels, destination, 2, 0, 16, params));
  EXPECT_EQ(destination, before);
}
}  // namespace
}  // namespace glint::candidate
