// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GPU_COMMAND_BUFFER_COMMON_GLINT_WEBGPU_DEVICE_POLICY_H_
#define GPU_COMMAND_BUFFER_COMMON_GLINT_WEBGPU_DEVICE_POLICY_H_

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>

namespace gpu::webgpu {
constexpr size_t kGlintWebGPUPolicyPacketBytes = 64;

class GlintWebGPUPolicyPacket {
 public:
  GlintWebGPUPolicyPacket(GlintWebGPUPolicyPacket&& other) noexcept;
  GlintWebGPUPolicyPacket& operator=(GlintWebGPUPolicyPacket&& other) noexcept;
  ~GlintWebGPUPolicyPacket();
  GlintWebGPUPolicyPacket(const GlintWebGPUPolicyPacket&) = delete;
  GlintWebGPUPolicyPacket& operator=(const GlintWebGPUPolicyPacket&) = delete;
  std::span<const uint8_t, kGlintWebGPUPolicyPacketBytes> bytes() const {
    return bytes_;
  }

 private:
  friend class GlintWebGPUDevicePolicy;
  GlintWebGPUPolicyPacket() = default;
  std::array<uint8_t, kGlintWebGPUPolicyPacketBytes> bytes_{};
};

// Private native transport only. Deliberately has no stream/trace formatter.
class GlintWebGPUDevicePolicy {
 public:
  static std::optional<GlintWebGPUDevicePolicy> Create(
      uint64_t generation,
      std::span<const uint8_t, 32> seed);
  static std::optional<GlintWebGPUDevicePolicy> Decode(
      std::span<const uint8_t> packet);
  GlintWebGPUDevicePolicy(GlintWebGPUDevicePolicy&& other) noexcept;
  GlintWebGPUDevicePolicy& operator=(GlintWebGPUDevicePolicy&& other) noexcept;
  ~GlintWebGPUDevicePolicy();
  GlintWebGPUDevicePolicy(const GlintWebGPUDevicePolicy&) = delete;
  GlintWebGPUDevicePolicy& operator=(const GlintWebGPUDevicePolicy&) = delete;
  std::optional<GlintWebGPUPolicyPacket> Encode() const;
  bool Matches(const GlintWebGPUDevicePolicy& other) const;
  uint64_t generation() const { return generation_; }
  std::span<const uint8_t, 32> seed() const { return seed_; }

 private:
  GlintWebGPUDevicePolicy(uint64_t generation,
                          std::span<const uint8_t, 32> seed);
  uint64_t generation_ = 0;
  std::array<uint8_t, 32> seed_{};
};
}  // namespace gpu::webgpu
#endif
