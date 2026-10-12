// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_readback_copy.h"

#include <array>
#include <cstring>

#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/skia/include/core/SkColorSpace.h"

namespace glint::candidate {
namespace {
constexpr std::array<uint8_t, 32> kFixtureSeed{};

SkImageInfo RGBA(int width, int height) {
  return SkImageInfo::Make(width, height, kRGBA_8888_SkColorType,
                           kUnpremul_SkAlphaType, SkColorSpace::MakeSRGB());
}

TEST(GlintCanvasCopyTest, OwnsImmutableCopyWithoutChangingSource) {
  std::array<uint8_t, 16> source{30, 50, 70, 255, 200, 100, 80, 255,
                                30, 50, 70, 255, 200, 100, 80, 255};
  const auto original = source;
  const SkPixmap pixmap(RGBA(2, 2), source.data(), 8);
  auto copy = CreateProtectedCanvasCopy(pixmap, kFixtureSeed, source.size());
  ASSERT_TRUE(copy.has_value());
  EXPECT_TRUE(copy->isImmutable());
  EXPECT_NE(copy->getPixels(), source.data());
  EXPECT_EQ(source, original);
}

TEST(GlintCanvasCopyTest, UniformRGBAValuesRemainExact) {
  const std::array<uint8_t, 8> source{71, 91, 111, 255, 71, 91, 111, 255};
  auto copy = CreateProtectedCanvasCopy(
      SkPixmap(RGBA(2, 1), source.data(), 8), kFixtureSeed, source.size());
  ASSERT_TRUE(copy.has_value());
  EXPECT_EQ(std::memcmp(copy->getPixels(), source.data(), source.size()), 0);
}

TEST(GlintCanvasCopyTest, BGRAInputIsCanonicalizedExplicitly) {
  const std::array<uint8_t, 4> bgra{33, 22, 11, 255};
  const auto info = SkImageInfo::Make(1, 1, kBGRA_8888_SkColorType,
                                     kUnpremul_SkAlphaType,
                                     SkColorSpace::MakeSRGB());
  auto copy = CreateProtectedCanvasCopy(SkPixmap(info, bgra.data(), 4),
                                         kFixtureSeed, 4);
  ASSERT_TRUE(copy.has_value());
  const std::array<uint8_t, 4> expected{11, 22, 33, 255};
  EXPECT_EQ(copy->colorType(), kRGBA_8888_SkColorType);
  EXPECT_EQ(std::memcmp(copy->getPixels(), expected.data(), 4), 0);
}

TEST(GlintCanvasCopyTest, PremultipliedReadMatchesSkiaCanonicalConversion) {
  const std::array<uint8_t, 4> source{64, 32, 16, 128};
  const auto info = RGBA(1, 1).makeAlphaType(kPremul_SkAlphaType);
  const SkPixmap pixmap(info, source.data(), 4);
  std::array<uint8_t, 4> baseline{};
  ASSERT_TRUE(pixmap.readPixels(SkPixmap(RGBA(1, 1), baseline.data(), 4)));
  auto copy = CreateProtectedCanvasCopy(pixmap, kFixtureSeed, 4);
  ASSERT_TRUE(copy.has_value());
  EXPECT_EQ(copy->alphaType(), kUnpremul_SkAlphaType);
  EXPECT_EQ(std::memcmp(copy->getPixels(), baseline.data(), 4), 0);
}

TEST(GlintCanvasCopyTest, CopyMemoryLimitFailsWithoutChangingSource) {
  const std::array<uint8_t, 4> source{71, 91, 111, 255};
  auto copy = CreateProtectedCanvasCopy(
      SkPixmap(RGBA(1, 1), source.data(), 4), kFixtureSeed, 3);
  ASSERT_FALSE(copy.has_value());
  EXPECT_EQ(copy.error(), CanvasCopyError::kMemoryLimit);
}

TEST(GlintCanvasCopyTest, OpaqueMetadataProducesCanonicalOpaqueAlpha) {
  const std::array<uint8_t, 4> source{71, 91, 111, 0};
  auto copy = CreateProtectedCanvasCopy(
      SkPixmap(RGBA(1, 1).makeAlphaType(kOpaque_SkAlphaType), source.data(), 4),
      kFixtureSeed, 4);
  ASSERT_TRUE(copy.has_value());
  const std::array<uint8_t, 4> expected{71, 91, 111, 255};
  EXPECT_EQ(std::memcmp(copy->getPixels(), expected.data(), 4), 0);
}

TEST(GlintCanvasCopyTest, UntaggedColourSpaceHasNoImplicitFallback) {
  const std::array<uint8_t, 4> source{};
  auto copy = CreateProtectedCanvasCopy(
      SkPixmap(RGBA(1, 1).makeColorSpace(nullptr), source.data(), 4),
      kFixtureSeed, 4);
  ASSERT_FALSE(copy.has_value());
  EXPECT_EQ(copy.error(), CanvasCopyError::kUnsupportedFormat);
}

TEST(GlintCanvasCopyTest, Float16IsRejectedRatherThanClaimedProtected) {
  const std::array<uint16_t, 4> source{};
  auto copy = CreateProtectedCanvasCopy(
      SkPixmap(RGBA(1, 1).makeColorType(kRGBA_F16_SkColorType),
               source.data(), 8), kFixtureSeed, 8);
  ASSERT_FALSE(copy.has_value());
  EXPECT_EQ(copy.error(), CanvasCopyError::kUnsupportedFormat);
}

TEST(GlintCanvasCopyTest, MissingPixelsCannotBeRead) {
  auto copy = CreateProtectedCanvasCopy(SkPixmap(RGBA(1, 1), nullptr, 4),
                                         kFixtureSeed, 4);
  ASSERT_FALSE(copy.has_value());
  EXPECT_EQ(copy.error(), CanvasCopyError::kInvalidLayout);
}

TEST(GlintCanvasCopyTest, CropReadsFromTheSameProtectedFullCopy) {
  const std::array<uint8_t, 16> source{30, 50, 70, 255, 200, 100, 80, 255,
                                      30, 50, 70, 255, 200, 100, 80, 255};
  auto copy = CreateProtectedCanvasCopy(
      SkPixmap(RGBA(2, 2), source.data(), 8), kFixtureSeed, source.size());
  ASSERT_TRUE(copy.has_value());
  std::array<uint8_t, 4> crop{};
  ASSERT_TRUE(copy->pixmap().readPixels(SkPixmap(RGBA(1, 1), crop.data(), 4),
                                        1, 1));
  EXPECT_EQ(std::memcmp(crop.data(), copy->pixmap().addr(1, 1), 4), 0);
}
}  // namespace
}  // namespace glint::candidate
