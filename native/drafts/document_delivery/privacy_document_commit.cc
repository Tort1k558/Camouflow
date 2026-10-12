// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "content/browser/camouflow_native/privacy_document_commit.h"

#include <utility>

#include "content/public/browser/browser_context.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/native_privacy_context.h"
#include "third_party/blink/public/common/storage_key/storage_key.h"
#include "third_party/blink/public/mojom/navigation/navigation_params.mojom.h"

namespace content {

blink::mojom::GlintDocumentCanvasCommitPtr CreatePrivacyDocumentCanvasCommit(
    BrowserContext* context,
    const blink::StorageKey& trusted_partition) {
  DCHECK_CURRENTLY_ON(BrowserThread::UI);
  if (!context || context->ShutdownStarted()) {
    return nullptr;
  }
  auto seed = DeriveNativePrivacyKey(context, trusted_partition, "canvas");
  if (!seed) {
    return nullptr;
  }
  auto encoding = trusted_partition.SerializeForNativePrivacy();
  if (!encoding || encoding->empty() || encoding->size() > 8192u) {
    return nullptr;
  }
  auto policy = blink::mojom::GlintDocumentCanvasCommit::New();
  policy->version = 1;
  policy->partition_encoding = std::move(*encoding);
  policy->partition_seed.assign(seed->begin(), seed->end());
  return policy;
}

}  // namespace content
