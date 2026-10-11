// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "core/hardware_limits.h"

#include <iostream>
#include <string_view>

int main() {
  using camouflow::native::HardwareLimitsError;
  using camouflow::native::ParseHardwareLimits;
  unsigned failures = 0;
  const auto check = [&failures](bool passed, std::string_view name) {
    if (!passed) {
      std::cerr << "Failed: " << name << '\n';
      ++failures;
    }
  };

  auto result = ParseHardwareLimits("", "");
  check(static_cast<bool>(result), "explicit native defaults");
  check(result.limits.ReportedConcurrency(12) == 12, "unconfigured concurrency");
  check(result.limits.ReportedMemory(16.0f) == 16.0f, "unconfigured memory");

  result = ParseHardwareLimits("4", "2");
  check(static_cast<bool>(result), "supported limits");
  check(result.limits.ReportedConcurrency(12) == 4, "concurrency limit");
  check(result.limits.ReportedConcurrency(2) == 2, "cannot invent processors");
  check(result.limits.ReportedMemory(16.0f) == 2.0f, "memory limit");
  check(result.limits.ReportedMemory(0.5f) == 0.5f, "cannot invent memory");

  for (auto value : {"0", "65", "-1", "+4", "4.0", " 4", "4 ", "4x", "true", "999999999999999999999999"}) {
    check(ParseHardwareLimits(value, "").error == HardwareLimitsError::kInvalidConcurrency,
          "invalid concurrency rejected");
  }
  for (auto value : {"0", "0.1", "3", "32", "nan", "inf", "4.0", " 4", "4x"}) {
    check(ParseHardwareLimits("", value).error == HardwareLimitsError::kInvalidMemory,
          "invalid memory rejected");
  }
  for (auto value : {"0.25", "0.5", "1", "2", "4", "8", "16"}) {
    check(static_cast<bool>(ParseHardwareLimits("64", value)), "supported memory bucket");
  }
  check(!static_cast<bool>(ParseHardwareLimits("4", "invalid")), "partial configuration is not success");
  check(!ParseHardwareLimits("4", "invalid").limits.concurrency.has_value(), "invalid configuration is atomic");
  return failures == 0 ? 0 : 1;
}
