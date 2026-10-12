// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_SURFACE_POLICY_WIRE_H_
#define GLINT_SURFACE_POLICY_WIRE_H_

#include <utility>

#include "surface_policy_preflight.h"
#include "worker_surface_policy.h"
#include "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom.h"

namespace glint::candidate {
inline SurfacePolicyView SurfacePolicyWireView(const blink::mojom::GlintSurfacePolicyCommit& wire) {
  return {wire.version, wire.partition_encoding, wire.canvas_seed, wire.webgl_seed,
          wire.webgpu_seed, wire.audio_seed};
}

inline bool HasMatchingWirePartition(const blink::mojom::GlintSurfacePolicyCommit& wire) {
  if (!HasValidSurfacePolicyPayload(SurfacePolicyWireView(wire))) {
    return false;
  }
  const auto encoding = wire.partition.SerializeForNativePrivacy();
  return encoding && *encoding == wire.partition_encoding;
}

inline blink::mojom::GlintSurfacePolicyCommitPtr EncodeSurfacePolicyCommit(
    const SurfacePolicy& policy,
    const blink::StorageKey& trusted_partition) {
  if (!ValidateSurfacePolicy(policy, trusted_partition)) {
    return nullptr;
  }
  auto wire = blink::mojom::GlintSurfacePolicyCommit::New();
  wire->version = policy.version;
  wire->partition = trusted_partition;
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
  if (!HasMatchingWirePartition(wire)) {
    return std::nullopt;
  }
  return PreflightSurfacePolicyCommit(
      SurfacePolicyWireView(wire),
      provisional_partition, browser_origin_to_commit);
}

inline std::optional<SurfacePolicy> DecodeWorkerSurfacePolicy(
    const blink::mojom::GlintSurfacePolicyCommit& wire,
    const blink::StorageKey& selected_worker_partition) {
  if (!HasMatchingWirePartition(wire)) {
    return std::nullopt;
  }
  // A worker has no provisional document-origin normalization. Preserve its
  // selected opaque/nonce/retained-site identity exactly.
  return PreflightSurfacePolicyForPartition(
      SurfacePolicyWireView(wire),
      selected_worker_partition);
}

inline std::optional<WorkerSurfacePolicy> DecodeOwnedWorkerSurfacePolicy(
    const blink::mojom::GlintSurfacePolicyCommit& wire,
    const url::Origin& browser_worker_origin,
    const std::optional<blink::StorageKey>& expected_partition = std::nullopt) {
  if (wire.partition.origin() != browser_worker_origin) {
    return std::nullopt;
  }
  auto policy = DecodeWorkerSurfacePolicy(
      wire, expected_partition ? *expected_partition : wire.partition);
  if (!policy) {
    return std::nullopt;
  }
  return WorkerSurfacePolicy{wire.partition, std::move(*policy)};
}
}  // namespace glint::candidate

#endif
