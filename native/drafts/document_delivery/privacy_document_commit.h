// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_DOCUMENT_COMMIT_H_
#define CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_DOCUMENT_COMMIT_H_

#include "content/common/content_export.h"
#include "third_party/blink/public/mojom/navigation/navigation_params.mojom-forward.h"

namespace blink {
class StorageKey;
}

namespace content {
class BrowserContext;

// UI thread only. The caller must provide the selected browser-owned partition.
// Missing/loading/failed policy returns null; no key loading or fallback here.
CONTENT_EXPORT blink::mojom::GlintDocumentCanvasCommitPtr
CreatePrivacyDocumentCanvasCommit(BrowserContext* context,
                                 const blink::StorageKey& trusted_partition);

}  // namespace content

#endif  // CONTENT_BROWSER_CAMOUFLOW_NATIVE_PRIVACY_DOCUMENT_COMMIT_H_
