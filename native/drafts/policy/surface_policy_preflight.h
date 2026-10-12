// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_SURFACE_POLICY_PREFLIGHT_H_
#define GLINT_SURFACE_POLICY_PREFLIGHT_H_

#include <algorithm>
#include <optional>
#include <span>
#include <string_view>

#include "surface_policy_validation.h"
#include "third_party/blink/public/common/native_privacy/document_storage_key_resolution.h"

namespace glint::candidate {
struct SurfacePolicyView {
  uint32_t version;
  std::string_view partition_encoding;
  std::span<const uint8_t> canvas;
  std::span<const uint8_t> webgl;
  std::span<const uint8_t> webgpu;
  std::span<const uint8_t> audio;
};

inline bool HasValidSurfacePolicyPayload(const SurfacePolicyView& incoming) {
  return incoming.version == kSurfacePolicyVersion &&
         !incoming.partition_encoding.empty() && incoming.partition_encoding.size() <= 8192 &&
         incoming.canvas.size() == 32 && incoming.webgl.size() == 32 &&
         incoming.webgpu.size() == 32 && incoming.audio.size() == 32;
}

// Validate all lengths before allocation/copy. The returned snapshot owns bytes.
// Final Blink partition validation must still occur before installation.
inline std::optional<SurfacePolicy> PreflightSurfacePolicyForPartition(
    const SurfacePolicyView& incoming,
    const blink::StorageKey& selected_partition) {
  if (!HasValidSurfacePolicyPayload(incoming)) {
    return std::nullopt;
  }
  SurfacePolicy owned;
  owned.partition_encoding = incoming.partition_encoding;
  std::ranges::copy(incoming.canvas, owned.canvas.begin());
  std::ranges::copy(incoming.webgl, owned.webgl.begin());
  std::ranges::copy(incoming.webgpu, owned.webgpu.begin());
  std::ranges::copy(incoming.audio, owned.audio.begin());
  if (!ValidateSurfacePolicy(owned, selected_partition)) {
    return std::nullopt;
  }
  return owned;
}

inline std::optional<SurfacePolicy> PreflightSurfacePolicyCommit(
    const SurfacePolicyView& incoming,
    const blink::StorageKey& provisional_partition,
    const url::Origin& browser_origin_to_commit) {
  return PreflightSurfacePolicyForPartition(
      incoming, blink::ResolveGlintDocumentStorageKey(
                    provisional_partition, browser_origin_to_commit));
}
}  // namespace glint::candidate

#endif
