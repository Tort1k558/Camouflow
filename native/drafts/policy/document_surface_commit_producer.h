// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_DOCUMENT_SURFACE_COMMIT_PRODUCER_H_
#define GLINT_DOCUMENT_SURFACE_COMMIT_PRODUCER_H_

#include "surface_policy_producer.h"
#include "third_party/blink/public/mojom/native_privacy/native_privacy_surface_policy.mojom-forward.h"
#include "url/origin.h"

namespace glint::candidate {
// Browser UI sequence only. Both arguments come from the selected navigation,
// never a renderer URL or a caller-selected profile identity.
blink::mojom::GlintSurfacePolicyCommitPtr CreateDocumentSurfacePolicyCommit(
    content::BrowserContext* context,
    const blink::StorageKey& provisional_partition,
    const url::Origin& browser_origin_to_commit);
}  // namespace glint::candidate

#endif
