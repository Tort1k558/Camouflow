// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_DOCUMENT_SURFACE_POLICY_H_
#define GLINT_DOCUMENT_SURFACE_POLICY_H_

#include <optional>
#include <utility>

#include "surface_policy_wire.h"

namespace glint::candidate {
enum class DocumentPrivacyBootstrapMode { kOff, kCanvas, kSurfaces, kConflict };

constexpr DocumentPrivacyBootstrapMode SelectDocumentPrivacyBootstrapMode(
    bool canvas_requested,
    bool surfaces_requested) {
  if (canvas_requested && surfaces_requested) {
    return DocumentPrivacyBootstrapMode::kConflict;
  }
  if (surfaces_requested) {
    return DocumentPrivacyBootstrapMode::kSurfaces;
  }
  return canvas_requested ? DocumentPrivacyBootstrapMode::kCanvas
                          : DocumentPrivacyBootstrapMode::kOff;
}

constexpr bool HasExpectedDocumentPrivacyPayload(
    DocumentPrivacyBootstrapMode mode,
    bool has_canvas,
    bool has_surfaces) {
  switch (mode) {
    case DocumentPrivacyBootstrapMode::kOff:
      return !has_canvas && !has_surfaces;
    case DocumentPrivacyBootstrapMode::kCanvas:
      return has_canvas && !has_surfaces;
    case DocumentPrivacyBootstrapMode::kSurfaces:
      return has_surfaces && !has_canvas;
    case DocumentPrivacyBootstrapMode::kConflict:
      return false;
  }
  return false;
}

// This snapshot never owns the profile root key. Both the selected partition and
// independently derived surface bytes must survive Mojo/commit parameter moves.
struct DocumentSurfacePolicy {
  blink::StorageKey partition;
  SurfacePolicy policy;
};

inline std::optional<DocumentSurfacePolicy> DecodeOwnedDocumentSurfacePolicy(
    const blink::mojom::GlintSurfacePolicyCommit& wire,
    const blink::StorageKey& provisional_partition,
    const url::Origin& browser_origin_to_commit,
    bool legacy_canvas_present) {
  if (legacy_canvas_present) {
    return std::nullopt;
  }
  auto policy = DecodeSurfacePolicyCommit(
      wire, provisional_partition, browser_origin_to_commit);
  if (!policy) {
    return std::nullopt;
  }
  return DocumentSurfacePolicy{wire.partition, std::move(*policy)};
}

// A second check is mandatory against Blink's final key. Passing renderer
// preflight is not permission to install into a different final document.
inline bool ValidateDocumentSurfacePolicy(
    const std::optional<DocumentSurfacePolicy>& owned,
    const blink::StorageKey& final_partition,
    bool required,
    bool legacy_canvas_present) {
  if (!owned) {
    return !required;
  }
  return !legacy_canvas_present &&
         ValidateSurfacePolicy(owned->policy, owned->partition) &&
         ValidateSurfacePolicy(owned->policy, final_partition);
}
}  // namespace glint::candidate

#endif
