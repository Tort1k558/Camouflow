// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_COMMIT_PREFLIGHT_H_
#define THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_COMMIT_PREFLIGHT_H_

#include <algorithm>
#include <array>
#include <cstdint>
#include <optional>
#include <span>
#include <string_view>

#include "third_party/blink/public/common/native_privacy/document_canvas_policy_validation.h"
#include "third_party/blink/public/common/native_privacy/document_storage_key_resolution.h"

namespace blink {
// Checks the trusted browser payload before renderer commit mutations. Final
// Blink-selected partition validation is still required before seed installation.
inline std::optional<std::array<uint8_t, 32>> PreflightGlintDocumentCanvasCommit(
    uint32_t version,
    std::string_view partition_encoding,
    std::span<const uint8_t> partition_seed,
    const StorageKey& provisional_partition,
    const url::Origin& browser_origin_to_commit) {
  std::array<uint8_t, 32> owned_seed{};
  if (partition_encoding.size() > 8192u ||
      partition_seed.size() != owned_seed.size()) {
    return std::nullopt;
  }
  std::copy(partition_seed.begin(), partition_seed.end(), owned_seed.begin());
  return ValidateGlintDocumentCanvasPolicy(
      version, partition_encoding, owned_seed,
      ResolveGlintDocumentStorageKey(provisional_partition,
                                    browser_origin_to_commit));
}
}  // namespace blink

#endif
