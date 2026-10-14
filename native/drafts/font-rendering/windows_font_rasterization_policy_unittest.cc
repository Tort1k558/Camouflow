// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "ui/gfx/win/glint_font_rasterization_policy.h"

#include "testing/gtest/include/gtest/gtest.h"

namespace glint::candidate {
namespace {

TEST(GlintWindowsFontRasterizationTest, ParsesEveryNamedMode) {
  EXPECT_EQ(ParseWindowsFontRasterization("native"), WindowsFontRasterization::kNative);
  EXPECT_EQ(ParseWindowsFontRasterization("aliased"), WindowsFontRasterization::kAliased);
  EXPECT_EQ(ParseWindowsFontRasterization("grayscale"), WindowsFontRasterization::kGrayscale);
  EXPECT_EQ(ParseWindowsFontRasterization("cleartype-rgb"), WindowsFontRasterization::kClearTypeRgb);
  EXPECT_EQ(ParseWindowsFontRasterization("cleartype-bgr"), WindowsFontRasterization::kClearTypeBgr);
}

TEST(GlintWindowsFontRasterizationTest, RejectsInvalidNamesWithoutNormalization) {
  for (const auto value : {"", "Native", " grayscale", "grayscale ", "rgb", "macos", "1"}) {
    EXPECT_FALSE(ParseWindowsFontRasterization(value));
  }
}

TEST(GlintWindowsFontRasterizationTest, NativePreservesAllHostFields) {
  gfx::FontRenderParams params;
  params.antialiasing = false;
  params.subpixel_positioning = false;
  params.subpixel_rendering = gfx::FontRenderParams::SUBPIXEL_RENDERING_VRGB;
  params.text_gamma = 1.8f;
  params.text_contrast = 0.4f;
  const auto before = params;
  ASSERT_TRUE(ApplyWindowsFontRasterization(params, WindowsFontRasterization::kNative));
  EXPECT_TRUE(params == before);
}

TEST(GlintWindowsFontRasterizationTest, InvalidEnumPreservesAllHostFields) {
  gfx::FontRenderParams params;
  const auto before = params;
  EXPECT_FALSE(ApplyWindowsFontRasterization(params, static_cast<WindowsFontRasterization>(999)));
  EXPECT_TRUE(params == before);
}

TEST(GlintWindowsFontRasterizationTest, ModesOnlyChangeRasterizationFields) {
  for (const auto mode : {WindowsFontRasterization::kAliased,
                         WindowsFontRasterization::kGrayscale,
                         WindowsFontRasterization::kClearTypeRgb,
                         WindowsFontRasterization::kClearTypeBgr}) {
    gfx::FontRenderParams params;
    params.text_gamma = 1.8f;
    params.text_contrast = 0.4f;
    params.hinting = gfx::FontRenderParams::HINTING_FULL;
    params.autohinter = true;
    params.use_bitmaps = true;
    ASSERT_TRUE(ApplyWindowsFontRasterization(params, mode));
    EXPECT_EQ(params.antialiasing, mode != WindowsFontRasterization::kAliased);
    EXPECT_EQ(params.subpixel_positioning, params.antialiasing);
    EXPECT_EQ(params.text_gamma, 1.8f);
    EXPECT_EQ(params.text_contrast, 0.4f);
    EXPECT_EQ(params.hinting, gfx::FontRenderParams::HINTING_FULL);
    EXPECT_TRUE(params.autohinter);
    EXPECT_TRUE(params.use_bitmaps);
    const auto expected = mode == WindowsFontRasterization::kClearTypeRgb
                              ? gfx::FontRenderParams::SUBPIXEL_RENDERING_RGB
                         : mode == WindowsFontRasterization::kClearTypeBgr
                              ? gfx::FontRenderParams::SUBPIXEL_RENDERING_BGR
                              : gfx::FontRenderParams::SUBPIXEL_RENDERING_NONE;
    EXPECT_EQ(params.subpixel_rendering, expected);
    const auto once = params;
    ASSERT_TRUE(ApplyWindowsFontRasterization(params, mode));
    EXPECT_TRUE(params == once);
  }
}

}  // namespace
}  // namespace glint::candidate
