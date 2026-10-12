// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_CANVAS_COMMIT_H_
#define THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_CANVAS_COMMIT_H_

#include <array>
#include <cstdint>
#include <string>

namespace blink {

// Native-only owned payload. The browser must choose the profile and partition.
struct GlintDocumentCanvasCommit {
  uint32_t version = 0;
  std::string partition_encoding;
  std::array<uint8_t, 32> partition_seed{};
};

}  // namespace blink

#endif  // THIRD_PARTY_BLINK_PUBLIC_COMMON_NATIVE_PRIVACY_DOCUMENT_CANVAS_COMMIT_H_
