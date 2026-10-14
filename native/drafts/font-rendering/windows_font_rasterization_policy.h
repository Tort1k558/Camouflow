// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_WINDOWS_FONT_RASTERIZATION_POLICY_H_
#define GLINT_WINDOWS_FONT_RASTERIZATION_POLICY_H_

#include <optional>
#include <string_view>

#include "ui/gfx/font_render_params.h"

namespace glint::candidate {

inline constexpr char kWindowsFontRasterizationSwitch[] =
    "glint-windows-font-rasterization";

enum class WindowsFontRasterization {
  kNative,
  kAliased,
  kGrayscale,
  kClearTypeRgb,
  kClearTypeBgr,
};

constexpr std::optional<WindowsFontRasterization>
ParseWindowsFontRasterization(std::string_view value) {
  if (value == "native") {
    return WindowsFontRasterization::kNative;
  }
  if (value == "aliased") {
    return WindowsFontRasterization::kAliased;
  }
  if (value == "grayscale") {
    return WindowsFontRasterization::kGrayscale;
  }
  if (value == "cleartype-rgb") {
    return WindowsFontRasterization::kClearTypeRgb;
  }
  if (value == "cleartype-bgr") {
    return WindowsFontRasterization::kClearTypeBgr;
  }
  return std::nullopt;
}

inline bool ApplyWindowsFontRasterization(
    gfx::FontRenderParams& params,
    WindowsFontRasterization mode) {
  switch (mode) {
    case WindowsFontRasterization::kNative:
      return true;
    case WindowsFontRasterization::kAliased:
      params.antialiasing = false;
      params.subpixel_positioning = false;
      params.subpixel_rendering = gfx::FontRenderParams::SUBPIXEL_RENDERING_NONE;
      return true;
    case WindowsFontRasterization::kGrayscale:
      params.antialiasing = true;
      params.subpixel_positioning = true;
      params.subpixel_rendering = gfx::FontRenderParams::SUBPIXEL_RENDERING_NONE;
      return true;
    case WindowsFontRasterization::kClearTypeRgb:
    case WindowsFontRasterization::kClearTypeBgr:
      params.antialiasing = true;
      params.subpixel_positioning = true;
      params.subpixel_rendering =
          mode == WindowsFontRasterization::kClearTypeRgb
              ? gfx::FontRenderParams::SUBPIXEL_RENDERING_RGB
              : gfx::FontRenderParams::SUBPIXEL_RENDERING_BGR;
      return true;
  }
  return false;
}

}  // namespace glint::candidate
#endif
