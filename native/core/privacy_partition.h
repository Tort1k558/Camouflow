// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CAMOUFLOW_NATIVE_CORE_PRIVACY_PARTITION_H_
#define CAMOUFLOW_NATIVE_CORE_PRIVACY_PARTITION_H_

#include <optional>
#include <string>
#include <string_view>

namespace camouflow::native {

// The browser must supply its canonical storage partition, not a caller URL.
// Sign this message with crypto::hmac::SignSha256 and the private profile key.
inline std::optional<std::string> PrivacyDerivationMessage(
    std::string_view partition, std::string_view surface) {
  if (partition.empty() || partition.size() > 8192 ||
      (surface != "canvas" && surface != "webgl" && surface != "webgpu" &&
       surface != "audio")) {
    return std::nullopt;
  }
  std::string message("CamouFlowNative/privacy/v1");
  message.push_back('\0');
  const auto append_length = [&message](std::size_t length) {
    for (int shift = 24; shift >= 0; shift -= 8)
      message.push_back(static_cast<char>((length >> shift) & 0xff));
  };
  append_length(surface.size());
  message.append(surface);
  append_length(partition.size());
  message.append(partition);
  return message;
}

}  // namespace camouflow::native

#endif  // CAMOUFLOW_NATIVE_CORE_PRIVACY_PARTITION_H_
