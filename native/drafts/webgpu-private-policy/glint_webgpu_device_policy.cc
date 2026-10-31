// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "glint_webgpu_device_policy.h"

#include <algorithm>
#include <utility>

#include "third_party/boringssl/src/include/openssl/mem.h"

namespace gpu::webgpu {
namespace {
constexpr std::array<uint8_t, 8> kHeader = {'G', 'L', 'G', 'P', 1, 0, 0, 0};

bool HasSeed(std::span<const uint8_t, 32> seed) {
  return std::any_of(seed.begin(), seed.end(),
                     [](uint8_t byte) { return byte != 0; });
}
}  // namespace

GlintWebGPUPolicyPacket::GlintWebGPUPolicyPacket(
    GlintWebGPUPolicyPacket&& other) noexcept
    : bytes_(other.bytes_) {
  OPENSSL_cleanse(other.bytes_.data(), other.bytes_.size());
}

GlintWebGPUPolicyPacket& GlintWebGPUPolicyPacket::operator=(
    GlintWebGPUPolicyPacket&& other) noexcept {
  if (this != &other) {
    OPENSSL_cleanse(bytes_.data(), bytes_.size());
    bytes_ = other.bytes_;
    OPENSSL_cleanse(other.bytes_.data(), other.bytes_.size());
  }
  return *this;
}

GlintWebGPUPolicyPacket::~GlintWebGPUPolicyPacket() {
  OPENSSL_cleanse(bytes_.data(), bytes_.size());
}

GlintWebGPUDevicePolicy::GlintWebGPUDevicePolicy(
    uint64_t generation,
    std::span<const uint8_t, 32> seed)
    : generation_(generation) {
  std::copy(seed.begin(), seed.end(), seed_.begin());
}

GlintWebGPUDevicePolicy::GlintWebGPUDevicePolicy(
    GlintWebGPUDevicePolicy&& other) noexcept
    : generation_(std::exchange(other.generation_, 0)), seed_(other.seed_) {
  OPENSSL_cleanse(other.seed_.data(), other.seed_.size());
}

GlintWebGPUDevicePolicy& GlintWebGPUDevicePolicy::operator=(
    GlintWebGPUDevicePolicy&& other) noexcept {
  if (this != &other) {
    OPENSSL_cleanse(seed_.data(), seed_.size());
    generation_ = std::exchange(other.generation_, 0);
    seed_ = other.seed_;
    OPENSSL_cleanse(other.seed_.data(), other.seed_.size());
  }
  return *this;
}

GlintWebGPUDevicePolicy::~GlintWebGPUDevicePolicy() {
  OPENSSL_cleanse(seed_.data(), seed_.size());
}

std::optional<GlintWebGPUDevicePolicy> GlintWebGPUDevicePolicy::Create(
    uint64_t generation,
    std::span<const uint8_t, 32> seed) {
  if (generation == 0 || !HasSeed(seed)) {
    return std::nullopt;
  }
  return GlintWebGPUDevicePolicy(generation, seed);
}

std::optional<GlintWebGPUDevicePolicy> GlintWebGPUDevicePolicy::Decode(
    std::span<const uint8_t> packet) {
  if (packet.size() != kGlintWebGPUPolicyPacketBytes) {
    return std::nullopt;
  }
  // Snapshot untrusted shared memory before validation; cleanse on every exit.
  GlintWebGPUPolicyPacket owned;
  std::copy(packet.begin(), packet.end(), owned.bytes_.begin());
  packet = owned.bytes();
  if (!std::equal(kHeader.begin(), kHeader.end(), packet.begin()) ||
      std::any_of(packet.begin() + 48, packet.end(),
                  [](uint8_t byte) { return byte != 0; })) {
    return std::nullopt;
  }
  uint64_t generation = 0;
  for (size_t byte = 0; byte < 8; ++byte) {
    generation |= static_cast<uint64_t>(packet[8 + byte]) << (byte * 8);
  }
  return Create(generation, packet.subspan<16, 32>());
}

std::optional<GlintWebGPUPolicyPacket> GlintWebGPUDevicePolicy::Encode() const {
  if (generation_ == 0 || !HasSeed(seed_)) {
    return std::nullopt;
  }
  GlintWebGPUPolicyPacket packet;
  std::copy(kHeader.begin(), kHeader.end(), packet.bytes_.begin());
  for (size_t byte = 0; byte < 8; ++byte) {
    packet.bytes_[8 + byte] = static_cast<uint8_t>(generation_ >> (byte * 8));
  }
  std::copy(seed_.begin(), seed_.end(), packet.bytes_.begin() + 16);
  return packet;
}

bool GlintWebGPUDevicePolicy::Matches(
    const GlintWebGPUDevicePolicy& other) const {
  return generation_ != 0 && generation_ == other.generation_ &&
         CRYPTO_memcmp(seed_.data(), other.seed_.data(), seed_.size()) == 0;
}
}  // namespace gpu::webgpu
