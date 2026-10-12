// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_readback_candidate.h"

#include <algorithm>
#include <limits>

#include "third_party/boringssl/src/include/openssl/hmac.h"

namespace glint::candidate {
namespace {
constexpr char kDomain[] = "glint.canvas.rgba8.candidate.v1";
constexpr uint32_t kPixelsPerBlock = 85;

void EncodeUint32(uint32_t value, uint8_t* output) {
  for (unsigned i = 0; i < 4; ++i) {
    output[i] = static_cast<uint8_t>(value >> (24 - i * 8));
  }
}
}  // namespace

bool TransformCanvasReadback(std::span<uint8_t> rgba,
                             uint32_t read_width,
                             uint32_t read_height,
                             int64_t origin_x,
                             int64_t origin_y,
                             uint32_t canvas_width,
                             uint32_t canvas_height,
                             const std::array<uint8_t, 32>& partition_seed) {
  if (read_width == 0 || read_height == 0 ||
      read_width > std::numeric_limits<size_t>::max() / 4 / read_height ||
      rgba.size() != static_cast<size_t>(read_width) * read_height * 4 ||
      origin_x > std::numeric_limits<int64_t>::max() - read_width ||
      origin_y > std::numeric_limits<int64_t>::max() - read_height) {
    return false;
  }
  std::array<uint8_t, sizeof(kDomain) - 1 + 8> message{};
  std::copy_n(reinterpret_cast<const uint8_t*>(kDomain), sizeof(kDomain) - 1,
              message.begin());
  std::array<uint8_t, 32> digest{};
  uint32_t cached_block = 0;
  uint32_t cached_y = 0;
  bool cached = false;
  for (uint32_t y = 0; y < read_height; ++y) {
    const int64_t absolute_y = origin_y + y;
    if (absolute_y < 0 || absolute_y >= canvas_height) {
      continue;
    }
    for (uint32_t x = 0; x < read_width; ++x) {
      const int64_t absolute_x = origin_x + x;
      const size_t offset = (static_cast<size_t>(y) * read_width + x) * 4;
      if (absolute_x < 0 || absolute_x >= canvas_width || rgba[offset + 3] != 255) {
        continue;
      }
      const uint32_t block = static_cast<uint32_t>(absolute_x) / kPixelsPerBlock;
      if (!cached || block != cached_block || absolute_y != cached_y) {
        EncodeUint32(block, message.data() + sizeof(kDomain) - 1);
        EncodeUint32(static_cast<uint32_t>(absolute_y),
                      message.data() + sizeof(kDomain) - 1 + 4);
        unsigned length = 0;
        if (!HMAC(EVP_sha256(), partition_seed.data(), partition_seed.size(),
                  message.data(), message.size(), digest.data(), &length) ||
            length != digest.size()) {
          return false;
        }
        cached_block = block;
        cached_y = static_cast<uint32_t>(absolute_y);
        cached = true;
      }
      const uint32_t pixel = static_cast<uint32_t>(absolute_x) % kPixelsPerBlock;
      for (uint32_t channel = 0; channel < 3; ++channel) {
        const uint32_t bit = pixel * 3 + channel;
        const uint8_t chosen = (digest[bit / 8] >> (bit % 8)) & 1;
        rgba[offset + channel] = (rgba[offset + channel] & 0xfe) | chosen;
      }
    }
  }
  return true;
}
}  // namespace glint::candidate
