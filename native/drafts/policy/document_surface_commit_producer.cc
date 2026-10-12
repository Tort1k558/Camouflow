// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "document_surface_commit_producer.h"

#include "third_party/blink/public/common/native_privacy/glint/surface_policy_wire.h"

namespace glint::candidate {
blink::mojom::GlintSurfacePolicyCommitPtr CreateDocumentSurfacePolicyCommit(
    content::BrowserContext* context,
    const blink::StorageKey& provisional_partition,
    const url::Origin& browser_origin_to_commit) {
  const auto partition = blink::ResolveGlintDocumentStorageKey(
      provisional_partition, browser_origin_to_commit);
  auto policy = CreateSurfacePolicy(context, partition);
  return policy ? EncodeSurfacePolicyCommit(*policy, partition) : nullptr;
}
}  // namespace glint::candidate
