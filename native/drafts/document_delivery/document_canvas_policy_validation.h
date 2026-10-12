// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_CANVAS_POLICY_VALIDATION_H_
#define THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_CANVAS_POLICY_VALIDATION_H_

#include <array>
#include <cstdint>
#include <optional>
#include <string_view>

#include "third_party/blink/public/common/storage_key/storage_key.h"

namespace blink {

// Inputs must come from the browser's navigation commit, not renderer requests.
// This checks partition consistency; it does not authenticate an IPC sender.
inline std::optional<std::array<uint8_t, 32>> ValidateGlintDocumentCanvasPolicy(
    uint32_t version,
    std::string_view browser_partition_encoding,
    const std::array<uint8_t, 32>& seed,
    const StorageKey& final_document_partition) {
  if (version != 1 || browser_partition_encoding.empty()) {
    return std::nullopt;
  }
  const auto final_encoding =
      final_document_partition.SerializeForNativePrivacy();
  if (!final_encoding || *final_encoding != browser_partition_encoding) {
    return std::nullopt;
  }
  return seed;
}

}  // namespace blink

#endif  // THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_CANVAS_POLICY_VALIDATION_H_
