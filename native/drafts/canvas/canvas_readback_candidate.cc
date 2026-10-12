// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "canvas_readback_candidate.h"

#include <algorithm>
#include <limits>

#include "third_party/boringssl/src/include/openssl/hmac.h"

namespace glint::candidate {
namespace {
constexpr char kDomain[] = "glint.canvas.rgba8.candidate.v1";
constexpr char kColourDomain[] = "glint.canvas.palette.candidate.v1";
constexpr uint32_t kPixelsPerBlock = 85;
enum class Strategy { kCoordinate, kColour };
struct PaletteEntry {
  uint32_t key = std::numeric_limits<uint32_t>::max();
  uint8_t bits = 0;
};

void EncodeUint32(uint32_t value, uint8_t* output) {
  for (unsigned i = 0; i < 4; ++i) {
    output[i] = static_cast<uint8_t>(value >> (24 - i * 8));
  }
}
bool TransformReadback(
    std::span<uint8_t> rgba,
    uint32_t read_width,
    uint32_t read_height,
    int64_t origin_x,
    int64_t origin_y,
    uint32_t canvas_width,
    uint32_t canvas_height,
    const std::array<uint8_t, 32>& partition_seed,
    Strategy strategy) {
  if (read_width == 0 || read_height == 0 ||
      read_width > std::numeric_limits<size_t>::max() / 4 / read_height ||
      rgba.size() != static_cast<size_t>(read_width) * read_height * 4 ||
      origin_x > std::numeric_limits<int64_t>::max() - read_width ||
      origin_y > std::numeric_limits<int64_t>::max() - read_height) {
    return false;
  }
  constexpr size_t kMessageCapacity =
      std::max(sizeof(kDomain), sizeof(kColourDomain)) - 1 + 8;
  std::array<uint8_t, kMessageCapacity> message{};
  const auto* domain =
      strategy == Strategy::kCoordinate ? kDomain : kColourDomain;
  const size_t domain_size = strategy == Strategy::kCoordinate
                                 ? sizeof(kDomain) - 1
                                 : sizeof(kColourDomain) - 1;
  const size_t message_size =
      domain_size + (strategy == Strategy::kCoordinate ? 8 : 3);
  std::copy_n(reinterpret_cast<const uint8_t*>(domain), domain_size,
              message.begin());
  std::array<uint8_t, 32> digest{};
  // Fixed-size direct-mapped cache: collisions recompute, never alias colours.
  std::array<PaletteEntry, 256> palette{};
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
      uint8_t selected_bits = 0;
      if (strategy == Strategy::kColour) {
        const uint32_t colour = (static_cast<uint32_t>(rgba[offset] >> 1) << 14) |
                                (static_cast<uint32_t>(rgba[offset + 1] >> 1) << 7) |
                                static_cast<uint32_t>(rgba[offset + 2] >> 1);
        auto& entry = palette[(colour * 0x9e3779b9u) >> 24];
        if (entry.key != colour) {
          for (size_t channel = 0; channel < 3; ++channel) {
            message[domain_size + channel] = rgba[offset + channel] >> 1;
          }
          unsigned length = 0;
          if (!HMAC(EVP_sha256(), partition_seed.data(), partition_seed.size(),
                    message.data(), message_size, digest.data(), &length) ||
              length != digest.size()) {
            return false;
          }
          entry.key = colour;
          entry.bits = digest[0] & 7;
        }
        selected_bits = entry.bits;
      } else {
        const uint32_t block = static_cast<uint32_t>(absolute_x) / kPixelsPerBlock;
        if (!cached || block != cached_block || absolute_y != cached_y) {
          EncodeUint32(block, message.data() + domain_size);
          EncodeUint32(static_cast<uint32_t>(absolute_y),
                        message.data() + domain_size + 4);
          unsigned length = 0;
          if (!HMAC(EVP_sha256(), partition_seed.data(), partition_seed.size(),
                    message.data(), message_size, digest.data(), &length) ||
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
          selected_bits |= ((digest[bit / 8] >> (bit % 8)) & 1) << channel;
        }
      }
      for (uint32_t channel = 0; channel < 3; ++channel) {
        const uint8_t chosen = (selected_bits >> channel) & 1;
        rgba[offset + channel] = (rgba[offset + channel] & 0xfe) | chosen;
      }
    }
  }
  return true;
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
  return TransformReadback(rgba, read_width, read_height, origin_x, origin_y,
                           canvas_width, canvas_height, partition_seed,
                           Strategy::kCoordinate);
}

bool TransformContentCoherentReadback(
    std::span<uint8_t> rgba,
    uint32_t read_width,
    uint32_t read_height,
    int64_t origin_x,
    int64_t origin_y,
    uint32_t canvas_width,
    uint32_t canvas_height,
    const std::array<uint8_t, 32>& partition_seed) {
  return TransformReadback(rgba, read_width, read_height, origin_x, origin_y,
                           canvas_width, canvas_height, partition_seed,
                           Strategy::kColour);
}
}  // namespace glint::candidate
