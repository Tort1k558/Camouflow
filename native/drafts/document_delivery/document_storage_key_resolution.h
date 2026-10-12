// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_STORAGE_KEY_RESOLUTION_H_
#define THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_STORAGE_KEY_RESOLUTION_H_

#include "third_party/blink/public/common/storage_key/storage_key.h"
#include "url/origin.h"

namespace blink {

// Mirrors the pinned DocumentLoader normalization after origin selection.
// The browser caller must use its trusted origin-to-commit, never a URL guess.
// This does not select the origin or make a navigation safe to cancel.
inline StorageKey ResolveGlintDocumentStorageKey(
    const StorageKey& provisional_partition,
    const url::Origin& final_origin) {
  if (provisional_partition.origin().opaque() &&
      !provisional_partition.nonce()) {
    return StorageKey::CreateFirstParty(final_origin);
  }
  return provisional_partition.WithOrigin(final_origin);
}

}  // namespace blink

#endif  // THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_STORAGE_KEY_RESOLUTION_H_
