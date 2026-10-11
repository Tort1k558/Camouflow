// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef CAMOUFLOW_NATIVE_CORE_HARDWARE_LIMITS_H_
#define CAMOUFLOW_NATIVE_CORE_HARDWARE_LIMITS_H_

#include <algorithm>
#include <charconv>
#include <optional>
#include <string_view>
#include <system_error>

namespace camouflow::native {

enum class HardwareLimitsError {
  kNone,
  kInvalidConcurrency,
  kInvalidMemory,
};

struct HardwareLimits {
  std::optional<unsigned> concurrency;
  std::optional<float> memory_gib;

  unsigned ReportedConcurrency(unsigned actual) const {
    return concurrency ? std::min(actual, *concurrency) : actual;
  }

  float ReportedMemory(float actual_gib) const {
    return memory_gib ? std::min(actual_gib, *memory_gib) : actual_gib;
  }
};

struct HardwareLimitsResult {
  HardwareLimits limits;
  HardwareLimitsError error = HardwareLimitsError::kNone;

  explicit operator bool() const { return error == HardwareLimitsError::kNone; }
};

inline HardwareLimitsResult ParseHardwareLimits(std::string_view concurrency,
                                               std::string_view memory_gib) {
  HardwareLimitsResult result;
  if (!concurrency.empty()) {
    unsigned value = 0;
    const auto parsed = std::from_chars(concurrency.data(),
                                        concurrency.data() + concurrency.size(),
                                        value);
    if (parsed.ec != std::errc{} ||
        parsed.ptr != concurrency.data() + concurrency.size() || value == 0 ||
        value > 64) {
      return {{}, HardwareLimitsError::kInvalidConcurrency};
    }
    result.limits.concurrency = value;
  }
  if (!memory_gib.empty()) {
    constexpr std::string_view names[] = {"0.25", "0.5", "1", "2", "4", "8", "16"};
    constexpr float values[] = {0.25f, 0.5f, 1.0f, 2.0f, 4.0f, 8.0f, 16.0f};
    bool found = false;
    for (unsigned index = 0; index < 7; ++index) {
      if (memory_gib == names[index]) {
        result.limits.memory_gib = values[index];
        found = true;
        break;
      }
    }
    if (!found) {
      return {{}, HardwareLimitsError::kInvalidMemory};
    }
  }
  return result;
}

}  // namespace camouflow::native
#endif  // CAMOUFLOW_NATIVE_CORE_HARDWARE_LIMITS_H_
