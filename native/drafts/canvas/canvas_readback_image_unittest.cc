// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_readback_image.h"

#include <algorithm>
#include <array>

#include "base/test/task_environment.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/renderer/platform/graphics/image_data_buffer.h"
#include "third_party/blink/renderer/platform/graphics/unaccelerated_static_bitmap_image.h"
#include "third_party/blink/renderer/platform/image-encoders/image_encoder.h"
#include "third_party/skia/include/core/SkColorSpace.h"
#include "third_party/skia/include/core/SkImage.h"

namespace glint::candidate {
namespace {
constexpr std::array<uint8_t, 32> kFixtureSeed{};
constexpr size_t kPixelBytes = 4 * 4 * 4;
constexpr size_t kPeakCopyBudget = kPixelBytes * 2;

class GlintCanvasImageTest : public testing::Test {
 protected:
  SkBitmap FixtureBitmap() {
    SkBitmap bitmap;
    const auto info = SkImageInfo::Make(4, 4, kRGBA_8888_SkColorType,
                                       kUnpremul_SkAlphaType,
                                       SkColorSpace::MakeSRGB());
    if (!bitmap.tryAllocPixels(info, 16)) {
      ADD_FAILURE() << "Cannot allocate fixture bitmap";
      return bitmap;
    }
    for (int y = 0; y < 4; ++y) {
      for (int x = 0; x < 4; ++x) {
        const int pixel = y * 4 + x;
        auto* rgba = static_cast<uint8_t*>(bitmap.pixmap().writable_addr(x, y));
        rgba[0] = static_cast<uint8_t>(20 + pixel * 7);
        rgba[1] = static_cast<uint8_t>(40 + pixel * 5);
        rgba[2] = static_cast<uint8_t>(80 + pixel * 3);
        rgba[3] = 255;
      }
    }
    bitmap.setImmutable();
    return bitmap;
  }

  scoped_refptr<blink::StaticBitmapImage> FixtureImage() {
    auto bitmap = FixtureBitmap();
    auto image = SkImages::RasterFromBitmap(bitmap);
    if (!image) {
      ADD_FAILURE() << "Cannot create fixture image";
      return nullptr;
    }
    return blink::UnacceleratedStaticBitmapImage::Create(std::move(image));
  }

  base::test::SingleThreadTaskEnvironment tasks_;
};

TEST_F(GlintCanvasImageTest, MissingSnapshotReturnsTypedFailure) {
  auto result = CreateProtectedCanvasImage(nullptr, kFixtureSeed, kPeakCopyBudget);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error(), CanvasCopyError::kInvalidLayout);
}

TEST_F(GlintCanvasImageTest, ReturnsSeparateRasterWithoutChangingSource) {
  auto source = FixtureImage();
  ASSERT_TRUE(source);
  auto before = blink::ImageDataBuffer::Create(source);
  ASSERT_TRUE(before);
  const auto original = before->ToDataURL(blink::kMimeTypePng, 1.0);
  auto result = CreateProtectedCanvasImage(source, kFixtureSeed, kPeakCopyBudget);
  ASSERT_TRUE(result.has_value());
  EXPECT_NE(result->get(), source.get());
  EXPECT_FALSE(result.value()->IsTextureBacked());
  auto after = blink::ImageDataBuffer::Create(source);
  ASSERT_TRUE(after);
  EXPECT_EQ(after->ToDataURL(blink::kMimeTypePng, 1.0), original);
}

TEST_F(GlintCanvasImageTest, OutputOwnsPixelsAfterOriginalRelease) {
  auto source = FixtureImage();
  ASSERT_TRUE(source);
  auto result = CreateProtectedCanvasImage(source, kFixtureSeed, kPeakCopyBudget);
  ASSERT_TRUE(result.has_value());
  source.reset();
  auto data = blink::ImageDataBuffer::Create(result.value());
  ASSERT_TRUE(data);
  EXPECT_EQ(data->PixelData().size(), kPixelBytes);
  EXPECT_FALSE(data->ToDataURL(blink::kMimeTypePng, 1.0).empty());
}

TEST_F(GlintCanvasImageTest, PeakBudgetAccountsForBothDetachedCopies) {
  auto source = FixtureImage();
  ASSERT_TRUE(source);
  auto result = CreateProtectedCanvasImage(source, kFixtureSeed, kPeakCopyBudget - 1);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error(), CanvasCopyError::kMemoryLimit);
}

TEST_F(GlintCanvasImageTest, RetainsSourceOrientationMetadata) {
  auto source = FixtureImage();
  ASSERT_TRUE(source);
  source->SetOrientation(blink::ImageOrientationEnum::kOriginRightTop);
  auto result = CreateProtectedCanvasImage(source, kFixtureSeed, kPeakCopyBudget);
  ASSERT_TRUE(result.has_value());
  EXPECT_EQ(result.value()->Orientation(), source->Orientation());
}

TEST_F(GlintCanvasImageTest, PNGExportMatchesProtectedCanonicalRaster) {
  auto bitmap = FixtureBitmap();
  ASSERT_FALSE(bitmap.empty());
  auto raster = CreateProtectedCanvasCopy(bitmap.pixmap(), kFixtureSeed, kPixelBytes);
  ASSERT_TRUE(raster.has_value());
  auto reference = blink::ImageDataBuffer::Create(raster->pixmap());
  ASSERT_TRUE(reference);
  auto result = CreateProtectedCanvasImage(FixtureImage(), kFixtureSeed, kPeakCopyBudget);
  ASSERT_TRUE(result.has_value());
  auto image_data = blink::ImageDataBuffer::Create(result.value());
  ASSERT_TRUE(image_data);
  EXPECT_EQ(image_data->ToDataURL(blink::kMimeTypePng, 1.0),
            reference->ToDataURL(blink::kMimeTypePng, 1.0));
}

TEST_F(GlintCanvasImageTest, RepeatedSnapshotsKeepPixelsAndPNGStable) {
  auto source = FixtureImage();
  ASSERT_TRUE(source);
  auto first = CreateProtectedCanvasImage(source, kFixtureSeed, kPeakCopyBudget);
  auto second = CreateProtectedCanvasImage(source, kFixtureSeed, kPeakCopyBudget);
  ASSERT_TRUE(first.has_value());
  ASSERT_TRUE(second.has_value());
  auto first_data = blink::ImageDataBuffer::Create(first.value());
  auto second_data = blink::ImageDataBuffer::Create(second.value());
  ASSERT_TRUE(first_data);
  ASSERT_TRUE(second_data);
  EXPECT_EQ(first_data->ToDataURL(blink::kMimeTypePng, 1.0),
            second_data->ToDataURL(blink::kMimeTypePng, 1.0));
}

TEST_F(GlintCanvasImageTest, DistinctFixtureSeedsProduceDifferentPixels) {
  auto source = FixtureImage();
  ASSERT_TRUE(source);
  auto other_seed = kFixtureSeed;
  other_seed[0] = 255;
  auto first = CreateProtectedCanvasImage(source, kFixtureSeed, kPeakCopyBudget);
  auto second = CreateProtectedCanvasImage(source, other_seed, kPeakCopyBudget);
  ASSERT_TRUE(first.has_value());
  ASSERT_TRUE(second.has_value());
  auto first_data = blink::ImageDataBuffer::Create(first.value());
  auto second_data = blink::ImageDataBuffer::Create(second.value());
  ASSERT_TRUE(first_data);
  ASSERT_TRUE(second_data);
  const auto a = first_data->PixelData();
  const auto b = second_data->PixelData();
  ASSERT_EQ(a.size(), b.size());
  EXPECT_FALSE(std::equal(a.begin(), a.end(), b.begin()));
}

TEST_F(GlintCanvasImageTest, CroppedReadUsesFullProtectedRaster) {
  auto result = CreateProtectedCanvasImage(FixtureImage(), kFixtureSeed, kPeakCopyBudget);
  ASSERT_TRUE(result.has_value());
  auto full = blink::ImageDataBuffer::Create(result.value());
  ASSERT_TRUE(full);
  const auto pixels = full->PixelData();
  ASSERT_EQ(pixels.size(), kPixelBytes);
  std::array<uint8_t, 2 * 2 * 4> cropped{};
  const auto info = SkImageInfo::Make(2, 2, kRGBA_8888_SkColorType,
                                     kUnpremul_SkAlphaType,
                                     SkColorSpace::MakeSRGB());
  ASSERT_TRUE(result.value()->PaintImageForCurrentFrame().readPixels(
      info, cropped.data(), 2 * 4, 1, 1));
  for (size_t y = 0; y < 2; ++y) {
    for (size_t x = 0; x < 2; ++x) {
      for (size_t channel = 0; channel < 4; ++channel) {
        EXPECT_EQ(cropped[(y * 2 + x) * 4 + channel],
                  pixels[((y + 1) * 4 + x + 1) * 4 + channel]);
      }
    }
  }
}

TEST_F(GlintCanvasImageTest, PartialReadPreservesTransparentPadding) {
  auto result = CreateProtectedCanvasImage(FixtureImage(), kFixtureSeed, kPeakCopyBudget);
  ASSERT_TRUE(result.has_value());
  auto full = blink::ImageDataBuffer::Create(result.value());
  ASSERT_TRUE(full);
  const auto pixels = full->PixelData();
  ASSERT_EQ(pixels.size(), kPixelBytes);
  std::array<uint8_t, 3 * 3 * 4> cropped{};
  const auto info = SkImageInfo::Make(3, 3, kRGBA_8888_SkColorType,
                                     kUnpremul_SkAlphaType,
                                     SkColorSpace::MakeSRGB());
  ASSERT_TRUE(result.value()->PaintImageForCurrentFrame().readPixels(
      info, cropped.data(), 3 * 4, -1, -1));
  for (size_t y = 0; y < 3; ++y) {
    for (size_t x = 0; x < 3; ++x) {
      for (size_t channel = 0; channel < 4; ++channel) {
        const uint8_t expected = x == 0 || y == 0
            ? 0 : pixels[((y - 1) * 4 + x - 1) * 4 + channel];
        EXPECT_EQ(cropped[(y * 3 + x) * 4 + channel], expected);
      }
    }
  }
}
}  // namespace
}  // namespace glint::candidate
