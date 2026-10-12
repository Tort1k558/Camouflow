// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_SURFACE_POLICY_H_
#define GLINT_SURFACE_POLICY_H_

#include <array>
#include <cstdint>
#include <string>

namespace glint::candidate {
using PartitionSeed = std::array<uint8_t, 32>;
constexpr uint32_t kSurfacePolicyVersion = 2;

// Browser-owned snapshot for one exact trusted StorageKey. No profile root key.
struct SurfacePolicy {
  uint32_t version = kSurfacePolicyVersion;
  std::string partition_encoding;
  PartitionSeed canvas{};
  PartitionSeed webgl{};
  PartitionSeed webgpu{};
  PartitionSeed audio{};
};

inline bool HasIndependentSurfaceSeeds(const SurfacePolicy& policy) {
  return policy.canvas != policy.webgl && policy.canvas != policy.webgpu &&
         policy.canvas != policy.audio && policy.webgl != policy.webgpu &&
         policy.webgl != policy.audio && policy.webgpu != policy.audio;
}
}  // namespace glint::candidate

#endif
