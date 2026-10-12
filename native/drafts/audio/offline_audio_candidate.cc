// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "offline_audio_candidate.h"

#include <bit>
#include <cstring>

#include "third_party/boringssl/src/include/openssl/hmac.h"

namespace glint::candidate {
namespace {
constexpr char kDomain[] = "glint.audio.offline.f32.candidate.v1";
static_assert(sizeof(float) == sizeof(uint32_t));
static_assert(std::numeric_limits<float>::is_iec559);
}  // namespace

OfflineAudioMasker::OfflineAudioMasker(const std::array<uint8_t, 32>& audio_seed)
    : seed_(audio_seed) {}

std::optional<float> OfflineAudioMasker::Transform(float sample) {
  const auto bits = std::bit_cast<uint32_t>(sample);
  const auto magnitude = bits & 0x7fffffffu;
  const auto exponent = magnitude & 0x7f800000u;
  // Preserve signed silence, subnormals, infinities/NaNs and out-of-range peaks.
  if (exponent == 0 || exponent == 0x7f800000u || magnitude >= 0x3f800000u) {
    return sample;
  }
  const auto normalized = bits & ~uint32_t{1};
  auto& entry = cache_[(normalized * 0x9e3779b9u) >> 24];
  if (entry.normalized != normalized) {
    std::array<uint8_t, sizeof(kDomain) - 1 + 4> message{};
    std::memcpy(message.data(), kDomain, sizeof(kDomain) - 1);
    for (size_t index = 0; index < 4; ++index) {
      message[sizeof(kDomain) - 1 + index] =
          static_cast<uint8_t>(normalized >> (24 - index * 8));
    }
    std::array<uint8_t, 32> digest{};
    unsigned length = 0;
    if (!HMAC(EVP_sha256(), seed_.data(), seed_.size(), message.data(),
              message.size(), digest.data(), &length) || length != digest.size()) {
      return std::nullopt;
    }
    entry.normalized = normalized;
    entry.bit = digest[0] & 1u;
  }
  return std::bit_cast<float>(normalized | entry.bit);
}
}  // namespace glint::candidate
