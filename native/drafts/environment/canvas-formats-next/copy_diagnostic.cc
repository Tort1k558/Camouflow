// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <set>

#include "third_party/blink/renderer/core/html/canvas/glint/canvas_readback_copy.h"
#include "third_party/fp16/src/include/fp16.h"
#include "third_party/skia/include/core/SkColorSpace.h"

int main() {
  unsigned controls = 0;
  unsigned failed = 0;
  auto check = [&](bool result, const char* name) {
    ++controls;
    if (!result) {
      ++failed;
      std::fprintf(stderr, "FAIL: %s\n", name);
    }
  };
  const std::array<uint8_t, 32> seed{};
  const auto p3 =
      SkColorSpace::MakeRGB(SkNamedTransferFn::kSRGB, SkNamedGamut::kDisplayP3);
  const auto srgb = SkColorSpace::MakeSRGB();
  const auto half_info = SkImageInfo::Make(2, 1, kRGBA_F16_SkColorType,
                                           kUnpremul_SkAlphaType, srgb);
  const std::array<uint16_t, 8> alpha_source{0x3000, 0x3400, 0x3600, 0x3800,
                                             0x3000, 0x3400, 0x3600, 0x3800};
  const SkPixmap premultiplied(half_info.makeAlphaType(kPremul_SkAlphaType),
                               alpha_source.data(), 16);
  std::array<uint16_t, 8> unpremultiplied{};
  check(
      premultiplied.readPixels(SkPixmap(half_info, unpremultiplied.data(), 16)),
      "native alpha reference");
  auto alpha_copy =
      glint::candidate::CreateProtectedCanvasCopy(premultiplied, seed, 16);
  check(alpha_copy.has_value() && std::memcmp(alpha_copy->getPixels(),
                                              unpremultiplied.data(), 16) == 0,
        "premultiplied conversion follows Skia without perturbing translucent "
        "colors");
  const auto normalized = half_info.makeColorType(kRGBA_F16Norm_SkColorType);
  auto normalized_copy = glint::candidate::CreateProtectedCanvasCopy(
      SkPixmap(normalized, alpha_source.data(), 16), seed, 16);
  check(normalized_copy.has_value() &&
            normalized_copy->colorType() == kRGBA_F16_SkColorType,
        "normalized F16 source keeps half precision");
  const auto untagged = glint::candidate::CreateProtectedCanvasCopy(
      SkPixmap(half_info.makeColorSpace(nullptr), alpha_source.data(), 16),
      seed, 16);
  check(!untagged.has_value() &&
            untagged.error() ==
                glint::candidate::CanvasCopyError::kUnsupportedFormat,
        "untagged colors have no implicit fallback");
  const std::array<float, 8> unsupported_source{};
  const auto unsupported = glint::candidate::CreateProtectedCanvasCopy(
      SkPixmap(half_info.makeColorType(kRGBA_F32_SkColorType),
               unsupported_source.data(), 32),
      seed, 32);
  check(!unsupported.has_value() &&
            unsupported.error() ==
                glint::candidate::CanvasCopyError::kUnsupportedFormat,
        "unsupported source storage cannot escape protection");
  const auto missing = glint::candidate::CreateProtectedCanvasCopy(
      SkPixmap(half_info, nullptr, 16), seed, 16);
  check(
      !missing.has_value() &&
          missing.error() == glint::candidate::CanvasCopyError::kInvalidLayout,
      "missing pixels rejected before read");
  const int huge = std::numeric_limits<int>::max();
  const auto overflow = glint::candidate::CreateProtectedCanvasCopy(
      SkPixmap(half_info.makeDimensions(SkISize::Make(huge, huge)),
               alpha_source.data(), static_cast<size_t>(huge) * 8),
      seed, 16);
  check(
      !overflow.has_value() &&
          overflow.error() == glint::candidate::CanvasCopyError::kInvalidLayout,
      "dimension arithmetic overflow rejected before allocation");
  for (const auto& space : {srgb, p3}) {
    const auto info = SkImageInfo::Make(2, 1, kRGBA_F16_SkColorType,
                                        kUnpremul_SkAlphaType, space);
    std::array<uint16_t, 8> source{0x3555, 0xb955, 0x4055, 0x3c00,
                                   0x3aab, 0x2abc, 0xc800, 0x3c00};
    const auto original = source;
    auto copy = glint::candidate::CreateProtectedCanvasCopy(
        SkPixmap(info, source.data(), 16), seed, 16);
    check(copy.has_value(), "sRGB/P3 F16 copy available");
    if (!copy.has_value()) {
      continue;
    }
    check(copy->isImmutable() && copy->getPixels() != source.data() &&
              source == original,
          "copy detached immutable and source unchanged");
    check(copy->colorType() == kRGBA_F16_SkColorType &&
              copy->alphaType() == kUnpremul_SkAlphaType &&
              SkColorSpace::Equals(copy->colorSpace(), space.get()),
          "precision alpha and color space retained");
    const std::array<uint16_t, 8> expected{0x3545, 0xb95d, 0x4055, 0x3c00,
                                           0x3aab, 0x2abc, 0xc800, 0x3c00};
    check(std::memcmp(copy->getPixels(), expected.data(), 16) == 0,
          "negative HDR above-one and sub-byte values retained except one "
          "deliberate bounded mantissa bit");
    std::array<uint16_t, 4> crop{};
    check(
        copy->pixmap().readPixels(
            SkPixmap(info.makeDimensions(SkISize::Make(1, 1)), crop.data(), 8),
            1, 0) &&
            std::memcmp(crop.data(), expected.data() + 4, 8) == 0,
        "crop reads protected precision");
    const auto small = glint::candidate::CreateProtectedCanvasCopy(
        SkPixmap(info, source.data(), 16), seed, 15);
    check(!small.has_value() &&
              small.error() == glint::candidate::CanvasCopyError::kMemoryLimit,
          "F16 memory budget uses eight bytes per pixel");
  }
  const auto info =
      SkImageInfo::Make(2, 2, kRGBA_F16_SkColorType, kUnpremul_SkAlphaType, p3);
  std::array<uint16_t, 24> padded{
      0x3555, 0xb955, 0x4055, 0x3c00, 0x3aab, 0x2abc, 0xc800, 0x3c00,
      0x7e00, 0x7e00, 0x7e00, 0x7e00, 0x3555, 0xb955, 0x4055, 0x3c00,
      0x3aab, 0x2abc, 0xc800, 0x3c00, 0x7e00, 0x7e00, 0x7e00, 0x7e00};
  const auto original = padded;
  auto copy = glint::candidate::CreateProtectedCanvasCopy(
      SkPixmap(info, padded.data(), 24), seed, 32);
  check(copy.has_value() && padded == original,
        "padded rows and sentinels unchanged");
  if (copy.has_value()) {
    check(copy->rowBytes() == 16 && copy->computeByteSize() == 32,
          "output has checked tightly packed F16 layout");
  }
  const std::array<uint8_t, 8> flat{71, 91, 111, 255, 71, 91, 111, 255};
  for (const auto& space : {srgb, p3}) {
    const auto rgba = SkImageInfo::Make(2, 1, kRGBA_8888_SkColorType,
                                        kUnpremul_SkAlphaType, space);
    auto result = glint::candidate::CreateProtectedCanvasCopy(
        SkPixmap(rgba, flat.data(), 8), seed, 8);
    check(result.has_value() &&
              std::memcmp(result->getPixels(), flat.data(), 8) == 0,
          "sRGB/P3 8-bit flat fill remains exact");
  }
  std::array<uint16_t, 16 * 16 * 4> rich{};
  for (size_t y = 0; y < 16; ++y) {
    for (size_t x = 0; x < 16; ++x) {
      const size_t offset = (y * 16 + x) * 4;
      rich[offset] = fp16_ieee_from_fp32_value(
          static_cast<float>((x * 17 + y * 29 + 17) % 224 + 16) / 255.0f);
      rich[offset + 1] = fp16_ieee_from_fp32_value(
          static_cast<float>((x * 13 + y * 31 + 53) % 224 + 16) / 255.0f);
      rich[offset + 2] = fp16_ieee_from_fp32_value(
          static_cast<float>((x * 23 + y * 11 + 97) % 224 + 16) / 255.0f);
      rich[offset + 3] = 0x3c00;
    }
  }
  unsigned spaces_passed = 0;
  unsigned projection_index = 0;
  std::printf("{\"projection\":[");
  for (const auto& space : {srgb, p3}) {
    for (const auto& output_space : {srgb, p3}) {
      const auto high_info = SkImageInfo::Make(16, 16, kRGBA_F16_SkColorType,
                                               kUnpremul_SkAlphaType, space);
      const auto low_info = high_info.makeColorType(kRGBA_8888_SkColorType)
                                .makeColorSpace(output_space);
      const SkPixmap source(high_info, rich.data(), 16 * 8);
      std::array<uint8_t, 1024> baseline{};
      check(source.readPixels(SkPixmap(low_info, baseline.data(), 16 * 4)),
            "native baseline projection");
      std::set<std::array<uint8_t, 1024>> distinct_low;
      std::set<std::array<uint16_t, 1024>> distinct_high;
      unsigned affected = 0;
      for (unsigned index = 0; index < 32; ++index) {
        auto key = seed;
        key[0] = static_cast<uint8_t>(index);
        auto result = glint::candidate::CreateProtectedCanvasCopy(
            source, key, rich.size() * 2);
        check(result.has_value(), "rich copy for each key");
        if (!result.has_value()) {
          continue;
        }
        std::array<uint8_t, 1024> low{};
        std::array<uint16_t, 1024> high{};
        const bool read =
            result->pixmap().readPixels(SkPixmap(low_info, low.data(), 16 * 4));
        check(read, "protected native RGBA8 projection");
        std::memcpy(high.data(), result->getPixels(), high.size() * 2);
        distinct_low.insert(low);
        distinct_high.insert(high);
        affected += low != baseline;
      }
      if (projection_index++ != 0) {
        std::printf(",");
      }
      std::printf(
          "{\"color_space\":\"%s\",\"read_color_space\":\"%s\",\"seed_"
          "controls\":32,\"unique_f16\":%zu,"
          "\"unique_rgba8\":%zu,\"rgba8_affected\":%u}",
          space == p3 ? "display-p3" : "srgb",
          output_space == p3 ? "display-p3" : "srgb", distinct_high.size(),
          distinct_low.size(), affected);
      spaces_passed += affected == 32 && distinct_low.size() == 32 &&
                       distinct_high.size() == 32;
    }
  }
  std::printf(
      "],\"controls\":%u,\"failed\":%u,\"lower_precision_effect_passed\":%s,"
      "\"browser_runtime_verified\":false}\n",
      controls, failed, spaces_passed == 4 ? "true" : "false");
  return failed ? 1 : spaces_passed == 4 ? 0 : 2;
}
