// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include <xmmintrin.h>

#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <string_view>
#include <vector>

#include "DynamicsCompressor.h"
#include "LegacyDynamicsCompressor.h"

enum class Signal { kRandom, kSilence, kConstant, kImpulse, kTriangle, kBurst };
enum class Graph { kCompressor, kDirect };
struct ProbeCase {
  Signal signal = Signal::kRandom;
  Graph graph = Graph::kCompressor;
  unsigned channels = 1, frames = 8192, rate = 44100, seed = 123456789;
  float amplitude = 1, threshold = -24, knee = 30, ratio = 12, attack = .003f,
        release = .25f;
};
using Result = std::array<std::vector<float>, 2>;

template <class T>
bool Number(const char* value, T& result) {
  const std::string_view text(value);
  const auto parsed =
      std::from_chars(text.data(), text.data() + text.size(), result);
  return parsed.ec == std::errc() && parsed.ptr == text.data() + text.size();
}
bool Parse(int argc, char** argv, ProbeCase& spec) {
  if (argc == 1) {
    return true;
  }
  if (argc != 13) {
    return false;
  }
  const std::string_view signal(argv[1]), graph(argv[2]);
  if (signal == "random") {
    spec.signal = Signal::kRandom;
  } else if (signal == "silence") {
    spec.signal = Signal::kSilence;
  } else if (signal == "constant") {
    spec.signal = Signal::kConstant;
  } else if (signal == "impulse") {
    spec.signal = Signal::kImpulse;
  } else if (signal == "triangle") {
    spec.signal = Signal::kTriangle;
  } else if (signal == "burst") {
    spec.signal = Signal::kBurst;
  } else {
    return false;
  }
  if (graph == "compressor") {
    spec.graph = Graph::kCompressor;
  } else if (graph == "direct") {
    spec.graph = Graph::kDirect;
  } else {
    return false;
  }
  if (!Number(argv[3], spec.channels) || !Number(argv[4], spec.frames) ||
      !Number(argv[5], spec.rate) || !Number(argv[6], spec.seed) ||
      !Number(argv[7], spec.amplitude) || !Number(argv[8], spec.threshold) ||
      !Number(argv[9], spec.knee) || !Number(argv[10], spec.ratio) ||
      !Number(argv[11], spec.attack) || !Number(argv[12], spec.release)) {
    return false;
  }
  if (spec.channels < 1 || spec.channels > 2 || spec.frames < 256 ||
      spec.frames > 131072 || spec.rate < 8000 || spec.rate > 96000) {
    return false;
  }
  for (float value : {spec.amplitude, spec.threshold, spec.knee, spec.ratio,
                      spec.attack, spec.release}) {
    if (!std::isfinite(value)) {
      return false;
    }
  }
  return spec.amplitude >= -2 && spec.amplitude <= 2 &&
         spec.threshold >= -100 && spec.threshold <= 0 && spec.knee >= 0 &&
         spec.knee <= 40 && spec.ratio >= 1 && spec.ratio <= 20 &&
         spec.attack >= 0 && spec.attack <= 1 && spec.release >= 0 &&
         spec.release <= 1;
}
std::vector<float> Input(const ProbeCase& spec, unsigned channel) {
  std::vector<float> values(spec.frames);
  uint32_t state = spec.seed ^ (channel * 0x9e3779b9u);
  for (size_t i = 0; i < values.size(); ++i) {
    float value = 0;
    switch (spec.signal) {
      case Signal::kRandom:
        state = state * 1664525u + 1013904223u;
        value = static_cast<float>(state >> 12) / 524288.f - 1.f;
        break;
      case Signal::kSilence:
        break;
      case Signal::kConstant:
        value = 1;
        break;
      case Signal::kImpulse:
        value = i % 1024 == 0 ? 1.f : 0.f;
        break;
      case Signal::kTriangle: {
        const auto phase = static_cast<unsigned>(i % 256);
        value = phase < 128 ? static_cast<float>(phase) / 64.f - 1.f
                            : 3.f - static_cast<float>(phase) / 64.f;
        break;
      }
      case Signal::kBurst:
        value = i < spec.frames / 4
                    ? 1.f
                    : (i >= spec.frames / 2 && i < spec.frames * 5 / 8 ? -1.f
                                                                       : 0.f);
        break;
    }
    values[i] = spec.amplitude * value;
  }
  return values;
}
template <class Compressor>
void Configure(Compressor& compressor, const ProbeCase& spec) {
  compressor.SetParameterValue(Compressor::kParamThreshold, spec.threshold);
  compressor.SetParameterValue(Compressor::kParamKnee, spec.knee);
  compressor.SetParameterValue(Compressor::kParamRatio, spec.ratio);
  compressor.SetParameterValue(Compressor::kParamAttack, spec.attack);
  compressor.SetParameterValue(Compressor::kParamRelease, spec.release);
}
template <class Compressor>
void Process(Compressor& compressor,
             const blink::AudioBus& source,
             blink::AudioBus& output,
             unsigned quantum,
             const ProbeCase& spec) {
  if (spec.graph == Graph::kCompressor) {
    compressor.Process(&source, &output, quantum);
  } else {
    for (unsigned c = 0; c < 2; ++c) {
      const auto data = source.Channel(spec.channels == 1 ? 0 : c)->Span();
      std::copy(data.begin(), data.end(),
                output.Channel(c)->MutableSpan().begin());
    }
  }
}
template <class Compressor>
Result Render(uint32_t backend, unsigned quantum, const ProbeCase& spec) {
  const auto policy = glint::candidate::CompressorMathPolicy::Create(backend);
  if (!policy || !quantum || quantum % 32 != 0) {
    std::abort();
  }
  Compressor compressor(static_cast<float>(spec.rate), 2, *policy);
  Configure(compressor, spec);
  blink::AudioBus source(spec.channels, quantum), output(2, quantum);
  std::vector<std::vector<float>> inputs;
  for (unsigned c = 0; c < spec.channels; ++c) {
    inputs.push_back(Input(spec, c));
  }
  Result result{std::vector<float>(spec.frames),
                std::vector<float>(spec.frames)};
  for (unsigned offset = 0; offset < spec.frames; offset += quantum) {
    const auto count = std::min(quantum, spec.frames - offset);
    for (unsigned c = 0; c < spec.channels; ++c) {
      auto channel = source.Channel(c)->MutableSpan();
      std::fill(channel.begin(), channel.end(), 0.f);
      std::copy_n(inputs[c].begin() + offset, count, channel.begin());
    }
    Process(compressor, source, output, quantum, spec);
    for (unsigned c = 0; c < 2; ++c) {
      std::copy_n(output.Channel(c)->Span().begin(), count,
                  result[c].begin() + offset);
    }
  }
  return result;
}
size_t Different(const Result& a, const Result& b) {
  size_t count = 0;
  for (unsigned c = 0; c < 2; ++c) {
    if (a[c].size() != b[c].size()) {
      std::abort();
    }
    for (size_t i = 0; i < a[c].size(); ++i) {
      if (!std::isfinite(a[c][i]) || !std::isfinite(b[c][i])) {
        std::abort();
      }
      count +=
          std::bit_cast<uint32_t>(a[c][i]) != std::bit_cast<uint32_t>(b[c][i]);
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
int main(int argc, char** argv) {
  ProbeCase spec;
  if (!Parse(argc, argv, spec)) {
    std::cerr << "Invalid bounded DSP probe case\n";
    return 2;
  }
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
  const auto native = Render<blink::DynamicsCompressor>(0, 128, spec);
  const auto legacy = Render<blink::LegacyDynamicsCompressor>(0, 128, spec);
  const auto changed = Render<blink::DynamicsCompressor>(1, 128, spec);
  size_t segmentation = 0;
  const unsigned padded = (spec.frames + 31u) / 32u * 32u;
  for (unsigned quantum : {32u, 64u, 256u, padded}) {
    segmentation +=
        Different(native, Render<blink::DynamicsCompressor>(0, quantum, spec));
    segmentation +=
        Different(changed, Render<blink::DynamicsCompressor>(1, quantum, spec));
  }
  auto native_policy = *glint::candidate::CompressorMathPolicy::Create(0);
  auto changed_policy = *glint::candidate::CompressorMathPolicy::Create(1);
  blink::DynamicsCompressor a(static_cast<float>(spec.rate), 2, native_policy),
      b(static_cast<float>(spec.rate), 2, changed_policy);
  Configure(a, spec);
  Configure(b, spec);
  blink::AudioBus source(spec.channels, 128), out_a(2, 128), out_b(2, 128);
  Result inter_a{std::vector<float>(spec.frames),
                 std::vector<float>(spec.frames)};
  auto inter_b = inter_a;
  std::vector<std::vector<float>> inputs;
  for (unsigned c = 0; c < spec.channels; ++c) {
    inputs.push_back(Input(spec, c));
  }
  for (unsigned offset = 0; offset < spec.frames; offset += 128) {
    const auto count = std::min(128u, spec.frames - offset);
    for (unsigned c = 0; c < spec.channels; ++c) {
      auto channel = source.Channel(c)->MutableSpan();
      std::fill(channel.begin(), channel.end(), 0.f);
      std::copy_n(inputs[c].begin() + offset, count, channel.begin());
    }
    Process(a, source, out_a, 128, spec);
    Process(b, source, out_b, 128, spec);
    for (unsigned c = 0; c < 2; ++c) {
      std::copy_n(out_a.Channel(c)->Span().begin(), count,
                  inter_a[c].begin() + offset);
      std::copy_n(out_b.Channel(c)->Span().begin(), count,
                  inter_b[c].begin() + offset);
    }
  }
  double squared = 0, maximum = 0;
  for (unsigned c = 0; c < 2; ++c) {
    for (size_t i = 0; i < native[c].size(); ++i) {
      const double error = static_cast<double>(native[c][i]) - changed[c][i];
      squared += error * error;
      maximum = std::max(maximum, std::abs(error));
    }
  }
  Save("native156.f32", native);
  Save("native148.f32", legacy);
  Save("float32.f32", changed);
  const float infinity = std::numeric_limits<float>::infinity(),
              nan = std::numeric_limits<float>::quiet_NaN();
  const std::array<float, 9> bases = {0.f, -0.f,     1.f,       -1.f, 2.f,
                                      .5f, infinity, -infinity, nan};
  const std::array<float, 8> exponents = {0.f, -0.f,     1.f,       -1.f,
                                          .6f, infinity, -infinity, nan};
  const std::array<const char*, 9> base_names = {
      "zero",     "negative_zero",     "one", "negative_one", "two", "half",
      "infinity", "negative_infinity", "nan"};
  const std::array<const char*, 8> exponent_names = {
      "zero",     "negative_zero",     "one", "negative_one", "0.6",
      "infinity", "negative_infinity", "nan"};
  std::vector<std::array<size_t, 2>> edge_mismatches;
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
  for (size_t x = 0; x < bases.size(); ++x) {
    for (size_t y = 0; y < exponents.size(); ++y) {
      if (!same_category(native_policy.Pow(bases[x], exponents[y]),
                         changed_policy.Pow(bases[x], exponents[y]))) {
        edge_mismatches.push_back({x, y});
      }
    }
  }
  _mm_setcsr(saved_csr);
  std::cout.precision(17);
  std::cout << "{\"frames\":" << spec.frames
            << ",\"channels\":2,\"sample_rate\":" << spec.rate
            << ",\"legacy_native_different_samples\":"
            << Different(native, legacy)
            << ",\"native_float32_different_samples\":"
            << Different(native, changed)
            << ",\"segmentation_differences\":" << segmentation
            << ",\"interleaved_differences\":"
            << Different(native, inter_a) + Different(changed, inter_b)
            << ",\"max_abs_error\":" << maximum
            << ",\"rms_error\":" << std::sqrt(squared / (2. * spec.frames))
            << ",\"selector_values_checked\":1025,\"pow_edge_cases_checked\":"
               "72,\"pow_edge_category_mismatches\":"
            << edge_mismatches.size() << ",\"pow_edge_mismatches\":[";
  for (size_t i = 0; i < edge_mismatches.size(); ++i) {
    const auto& pair = edge_mismatches[i];
    std::cout << (i ? "," : "") << "{\"base\":\"" << base_names[pair[0]]
              << "\",\"exponent\":\"" << exponent_names[pair[1]] << "\"}";
  }
  std::cout << "]}" << std::endl;
}
