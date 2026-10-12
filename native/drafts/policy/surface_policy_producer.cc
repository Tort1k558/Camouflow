// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "surface_policy_producer.h"

#include <utility>

#include "content/public/browser/browser_context.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/native_privacy_context.h"
#include "third_party/blink/public/common/storage_key/storage_key.h"

namespace glint::candidate {
std::optional<SurfacePolicy> CreateSurfacePolicy(
    content::BrowserContext* context,
    const blink::StorageKey& trusted_partition) {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->ShutdownStarted()) {
    return std::nullopt;
  }
  auto encoding = trusted_partition.SerializeForNativePrivacy();
  if (!encoding || encoding->empty() || encoding->size() > 8192) {
    return std::nullopt;
  }
  auto canvas = content::DeriveNativePrivacyKey(context, trusted_partition, "canvas");
  auto webgl = content::DeriveNativePrivacyKey(context, trusted_partition, "webgl");
  auto webgpu = content::DeriveNativePrivacyKey(context, trusted_partition, "webgpu");
  auto audio = content::DeriveNativePrivacyKey(context, trusted_partition, "audio");
  if (!canvas || !webgl || !webgpu || !audio) {
    return std::nullopt;
  }
  SurfacePolicy policy{kSurfacePolicyVersion, std::move(*encoding),
                       *canvas, *webgl, *webgpu, *audio};
  if (!HasIndependentSurfaceSeeds(policy)) {
    return std::nullopt;
  }
  return policy;
}
}  // namespace glint::candidate
