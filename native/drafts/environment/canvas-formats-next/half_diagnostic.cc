// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "third_party/blink/renderer/core/html/canvas/glint/canvas_readback_candidate.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <span>

namespace {
using PixelPair = std::array<uint16_t, 8>;
constexpr std::array<uint8_t, 32> kSeed{};
constexpr PixelPair kFixture{0x3555, 0xb955, 0x4055, 0x3c00,
                             0x3aab, 0x2abc, 0xc800, 0x3c00};

bool Transform(std::span<uint16_t> pixels, uint32_t width, uint32_t height,
               const std::array<uint8_t, 32>& seed = kSeed) {
  return glint::candidate::TransformEdgeCoherentCanvasF16(pixels, width, height,
                                                         seed);
}
}  // namespace

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
  auto pixels = kFixture;
  check(Transform(pixels, 2, 1), "known-answer transform succeeds");
  const PixelPair expected{0x3554, 0xb954, 0x4054, 0x3c00,
                           0x3aaa, 0x2abc, 0xc801, 0x3c00};
  check(pixels == expected, "HMAC-SHA256 known answer");
  check(Transform(pixels, 2, 1) && pixels == expected, "idempotence");
  pixels = kFixture;
  check(Transform(pixels, 1, 2) && pixels == expected, "vertical edge coherence");
  pixels = kFixture;
  auto other_seed = kSeed;
  other_seed[0] = 1;
  check(Transform(pixels, 2, 1, other_seed) && pixels != expected,
        "different seed changes fixture");
  pixels = {0x3555, 0xb955, 0x4055, 0x3c00,
            0x3555, 0xb955, 0x4055, 0x3c00};
  const auto uniform = pixels;
  check(Transform(pixels, 2, 1) && pixels == uniform, "uniform fill exact");
  pixels = kFixture;
  pixels[3] = 0x3800;
  const auto translucent = pixels;
  check(Transform(pixels, 2, 1) && pixels == translucent,
        "translucent pixel is neither modified nor classified as opaque edge");
  pixels = kFixture;
  check(!Transform(pixels, 0, 1) && pixels == kFixture, "zero width rejected");
  check(!Transform(pixels, 2, 0) && pixels == kFixture, "zero height rejected");
  check(!Transform(std::span(pixels).first<7>(), 2, 1) && pixels == kFixture,
        "incomplete buffer rejected");
  check(!Transform(pixels, std::numeric_limits<uint32_t>::max(),
                   std::numeric_limits<uint32_t>::max()) && pixels == kFixture,
        "dimension overflow rejected");
  unsigned changed_normal = 0;
  bool exhaustive = true;
  for (uint32_t encoding = 0; encoding <= 0xffff; ++encoding) {
    const auto value = static_cast<uint16_t>(encoding);
    pixels = {value, value, value, 0x3c00, 0x4000, 0x4200, 0x4400, 0x3c00};
    const auto original = pixels;
    if (!Transform(pixels, 2, 1)) {
      exhaustive = false;
      break;
    }
    const auto exponent = value & 0x7c00;
    for (size_t channel = 0; channel < 3; ++channel) {
      if (exponent == 0 || exponent == 0x7c00) {
        exhaustive &= pixels[channel] == value;
      } else {
        exhaustive &= (pixels[channel] & 0xfffe) == (value & 0xfffe);
        changed_normal += pixels[channel] != value;
      }
    }
    // A pixel containing NaN/Inf is left entirely unchanged, as is its sole
    // neighbour: it cannot introduce an artificial finite-color edge.
    if (exponent == 0x7c00) {
      exhaustive &= pixels == original;
    }
    exhaustive &= pixels[3] == original[3] && pixels[7] == original[7];
    const auto once = pixels;
    exhaustive &= Transform(pixels, 2, 1) && pixels == once;
  }
  check(exhaustive && changed_normal > 0,
        "all 65536 half encodings preserve sign exponent special values alpha and idempotence");
  std::printf("{\"controls\":%u,\"failed\":%u,\"half_encodings\":65536,"
              "\"changed_normal_channels\":%u,\"runtime_verified\":false}\n",
              controls, failed, changed_normal);
  return failed ? 1 : 0;
}
