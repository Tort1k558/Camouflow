// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_DRAFT_COMPRESSOR_MATH_POLICY_H_
#define GLINT_DRAFT_COMPRESSOR_MATH_POLICY_H_

#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>

#include "third_party/fdlibm/ieee754.h"

namespace glint::candidate {

enum class CompressorMathBackend : uint32_t { kNative = 0, kFloat32 = 1 };

// Unselected DSP prototype. This does not admit Audio fingerprint emulation or
// install a profile policy; reference/runtime compatibility is still required.
class CompressorMathPolicy {
 public:
  static constexpr std::optional<CompressorMathPolicy> Create(uint32_t value) {
    if (value > static_cast<uint32_t>(CompressorMathBackend::kFloat32)) {
      return std::nullopt;
    }
    return CompressorMathPolicy(static_cast<CompressorMathBackend>(value));
  }

  constexpr CompressorMathBackend backend() const { return backend_; }

  float Pow(float base, float exponent) const {
    if (backend_ == CompressorMathBackend::kNative) {
      return fdlibm::powf(base, exponent);
    }
    // Preserve Chromium fdlibm's unit-base rules, not the CRT's power rules.
    if ((base == 1.f && !std::isfinite(exponent)) ||
        (base == -1.f && std::isinf(exponent))) {
      return std::numeric_limits<float>::quiet_NaN();
    }
    return ::powf(base, exponent);
  }

  float Asin(float value) const {
    return backend_ == CompressorMathBackend::kNative ? fdlibm::asinf(value)
                                                      : ::asinf(value);
  }

  float Sin(double value) const {
    return backend_ == CompressorMathBackend::kNative
               ? static_cast<float>(::sin(value))
               : ::sinf(static_cast<float>(value));
  }

  float Exp(double value) const {
    return backend_ == CompressorMathBackend::kNative
               ? static_cast<float>(::exp(value))
               : ::expf(static_cast<float>(value));
  }

 private:
  explicit constexpr CompressorMathPolicy(CompressorMathBackend backend)
      : backend_(backend) {}

  const CompressorMathBackend backend_;
};

}  // namespace glint::candidate

#endif
