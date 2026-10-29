// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include <xmmintrin.h>

#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <span>
#include <vector>

#include "DynamicsCompressor.h"
#include "LegacyDynamicsCompressor.h"

using Result = std::array<std::vector<float>, 2>;
constexpr size_t kFrames = 8192;
std::vector<float> Input() {
  std::vector<float> values(kFrames);
  uint32_t state = 123456789;
  for (auto& value : values) {
    state = state * 1664525u + 1013904223u;
    value = static_cast<float>(state >> 12) / 524288.f - 1.f;
  }
  return values;
}
template <class Compressor>
Result Render(uint32_t backend, size_t quantum) {
  const auto policy = glint::candidate::CompressorMathPolicy::Create(backend);
  if (!policy || kFrames % quantum != 0 || quantum % 32 != 0) {
    std::abort();
  }
  Compressor compressor(44100, 2, *policy);
  blink::AudioBus source(1, quantum), output(2, quantum);
  Result result{std::vector<float>(kFrames), std::vector<float>(kFrames)};
  auto input = Input();
  for (size_t offset = 0; offset < kFrames; offset += quantum) {
    std::copy_n(input.begin() + offset, quantum,
                source.Channel(0)->MutableSpan().begin());
    compressor.Process(&source, &output, static_cast<unsigned>(quantum));
    for (unsigned channel = 0; channel < 2; ++channel) {
      std::copy(output.Channel(channel)->Span().begin(),
                output.Channel(channel)->Span().end(),
                result[channel].begin() + offset);
    }
  }
  return result;
}
size_t Different(const Result& a, const Result& b) {
  size_t count = 0;
  for (unsigned channel = 0; channel < 2; ++channel) {
    for (size_t frame = 0; frame < kFrames; ++frame) {
      if (!std::isfinite(a[channel][frame]) ||
          !std::isfinite(b[channel][frame])) {
        std::abort();
      }
      count += std::bit_cast<uint32_t>(a[channel][frame]) !=
               std::bit_cast<uint32_t>(b[channel][frame]);
    }
  }
  return count;
}
void Save(const char* filename, const Result& result) {
  std::ofstream file(filename, std::ios::binary);
  for (const auto& channel : result) {
    file.write(reinterpret_cast<const char*>(channel.data()),
               static_cast<std::streamsize>(channel.size() * sizeof(float)));
  }
  if (!file.good()) {
    std::abort();
  }
}
int main() {
  const auto saved_csr = _mm_getcsr();
  _mm_setcsr(saved_csr | 0x8040u);
  for (uint32_t value = 0; value < 1024; ++value) {
    if (glint::candidate::CompressorMathPolicy::Create(value).has_value() !=
        (value < 2)) {
      return 2;
    }
  }
  if (glint::candidate::CompressorMathPolicy::Create(UINT32_MAX)) {
    return 2;
  }
  const auto native = Render<blink::DynamicsCompressor>(0, 128);
  const auto legacy = Render<blink::LegacyDynamicsCompressor>(0, 128);
  const auto changed = Render<blink::DynamicsCompressor>(1, 128);
  size_t segmentation = 0;
  for (size_t quantum : {32u, 64u, 256u, 8192u}) {
    segmentation +=
        Different(native, Render<blink::DynamicsCompressor>(0, quantum));
    segmentation +=
        Different(changed, Render<blink::DynamicsCompressor>(1, quantum));
  }
  // Interleave independent instances; policy and DSP state are never global.
  auto native_policy = *glint::candidate::CompressorMathPolicy::Create(0);
  auto changed_policy = *glint::candidate::CompressorMathPolicy::Create(1);
  blink::DynamicsCompressor a(44100, 2, native_policy),
      b(44100, 2, changed_policy);
  blink::AudioBus source(1, 128), out_a(2, 128), out_b(2, 128);
  Result inter_a{std::vector<float>(kFrames), std::vector<float>(kFrames)};
  auto inter_b = inter_a;
  auto input = Input();
  for (size_t offset = 0; offset < kFrames; offset += 128) {
    std::copy_n(input.begin() + offset, 128,
                source.Channel(0)->MutableSpan().begin());
    a.Process(&source, &out_a, 128);
    b.Process(&source, &out_b, 128);
    for (unsigned channel = 0; channel < 2; ++channel) {
      std::copy(out_a.Channel(channel)->Span().begin(),
                out_a.Channel(channel)->Span().end(),
                inter_a[channel].begin() + offset);
      std::copy(out_b.Channel(channel)->Span().begin(),
                out_b.Channel(channel)->Span().end(),
                inter_b[channel].begin() + offset);
    }
  }
  double squared = 0, maximum = 0;
  for (size_t i = 0; i < kFrames; ++i) {
    const double error = static_cast<double>(native[0][i]) - changed[0][i];
    squared += error * error;
    maximum = std::max(maximum, std::abs(error));
  }
  Save("native156.f32", native);
  Save("native148.f32", legacy);
  Save("float32.f32", changed);
  // Category equality is separate from finite-domain numerical error.
  const float infinity = std::numeric_limits<float>::infinity();
  const float nan = std::numeric_limits<float>::quiet_NaN();
  const std::array<float, 9> bases = {0.f,  -0.f,     1.f,       -1.f, 2.f,
                                      0.5f, infinity, -infinity, nan};
  const std::array<float, 8> exponents = {0.f,  -0.f,     1.f,       -1.f,
                                          0.6f, infinity, -infinity, nan};
  const std::array<const char*, 9> base_names = {
      "zero",     "negative_zero",     "one", "negative_one", "two", "half",
      "infinity", "negative_infinity", "nan"};
  const std::array<const char*, 8> exponent_names = {
      "zero",     "negative_zero",     "one", "negative_one", "0.6",
      "infinity", "negative_infinity", "nan"};
  std::vector<std::array<size_t, 2>> edge_mismatches;
  size_t edge_cases = 0, edge_categories_different = 0;
  auto same_category = [](float x, float y) {
    if (std::isnan(x) || std::isnan(y)) {
      return std::isnan(x) && std::isnan(y);
    }
    if (std::isinf(x) || std::isinf(y)) {
      return std::isinf(x) && std::isinf(y) &&
             std::signbit(x) == std::signbit(y);
    }
    if (x == 0 || y == 0) {
      return x == y && std::signbit(x) == std::signbit(y);
    }
    return std::signbit(x) == std::signbit(y);
  };
  for (size_t base = 0; base < bases.size(); ++base) {
    for (size_t exponent = 0; exponent < exponents.size(); ++exponent) {
      ++edge_cases;
      if (!same_category(
              native_policy.Pow(bases[base], exponents[exponent]),
              changed_policy.Pow(bases[base], exponents[exponent]))) {
        ++edge_categories_different;
        edge_mismatches.push_back({base, exponent});
      }
    }
  }
  _mm_setcsr(saved_csr);
  std::cout.precision(17);
  std::cout << "{\"frames\":" << kFrames
            << ",\"channels\":2,\"sample_rate\":44100,"
            << "\"legacy_native_different_samples\":"
            << Different(native, legacy)
            << ",\"native_float32_different_samples\":"
            << Different(native, changed)
            << ",\"segmentation_differences\":" << segmentation
            << ",\"interleaved_differences\":"
            << Different(native, inter_a) + Different(changed, inter_b)
            << ",\"max_abs_error\":" << maximum
            << ",\"rms_error\":" << std::sqrt(squared / kFrames)
            << ",\"selector_values_checked\":1025,\"pow_edge_cases_checked\":"
            << edge_cases
            << ",\"pow_edge_category_mismatches\":" << edge_categories_different
            << ",\"pow_edge_mismatches\":[";
  for (size_t i = 0; i < edge_mismatches.size(); ++i) {
    const auto& pair = edge_mismatches[i];
    std::cout << (i ? "," : "") << "{\"base\":\"" << base_names[pair[0]]
              << "\",\"exponent\":\"" << exponent_names[pair[1]] << "\"}";
  }
  std::cout << "]}" << std::endl;
}
