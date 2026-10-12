// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_SURFACE_POLICY_WIRE_H_
#define GLINT_SURFACE_POLICY_WIRE_H_

#include "surface_policy_preflight.h"
#include "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom.h"

namespace glint::candidate {
inline blink::mojom::GlintSurfacePolicyCommitPtr EncodeSurfacePolicyCommit(
    const SurfacePolicy& policy,
    const blink::StorageKey& trusted_partition) {
  if (!ValidateSurfacePolicy(policy, trusted_partition)) {
    return nullptr;
  }
  auto wire = blink::mojom::GlintSurfacePolicyCommit::New();
  wire->version = policy.version;
  wire->partition_encoding = policy.partition_encoding;
  wire->canvas_seed.assign(policy.canvas.begin(), policy.canvas.end());
  wire->webgl_seed.assign(policy.webgl.begin(), policy.webgl.end());
  wire->webgpu_seed.assign(policy.webgpu.begin(), policy.webgpu.end());
  wire->audio_seed.assign(policy.audio.begin(), policy.audio.end());
  return wire;
}

inline std::optional<SurfacePolicy> DecodeSurfacePolicyCommit(
    const blink::mojom::GlintSurfacePolicyCommit& wire,
    const blink::StorageKey& provisional_partition,
    const url::Origin& browser_origin_to_commit) {
  return PreflightSurfacePolicyCommit(
      {wire.version, wire.partition_encoding, wire.canvas_seed, wire.webgl_seed,
       wire.webgpu_seed, wire.audio_seed},
      provisional_partition, browser_origin_to_commit);
}
}  // namespace glint::candidate

#endif
