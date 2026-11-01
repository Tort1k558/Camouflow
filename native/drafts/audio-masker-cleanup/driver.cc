// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <memory>
#include <utility>
#include <vector>

#include "offline_audio_candidate.h"

using glint::candidate::OfflineAudioMasker;
static_assert(std::endian::native == std::endian::little);

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  std::ofstream output(argv[1], std::ios::binary | std::ios::out);
  if (!output) return 3;
  std::vector<uint32_t> inputs = {0, 0x80000000, 1, 0x807fffff,
      0x7f800000, 0xff800000, 0x7fc00123, 0x3f800000, 0xbf800000,
      0x40800000, 0xc0800000, 0x3e800000, 0xbe800000};
  for (uint32_t index = 0; index < 4096; ++index) {
    inputs.push_back((0x3e800000 + index * 2) | ((index & 1) ? 0x80000000 : 0));
  }
  size_t cases = 0;
  for (uint8_t selected : {0, 27, 233}) {
    std::array<uint8_t, 32> seed;
    seed.fill(selected);
    OfflineAudioMasker masker(seed);
    for (uint32_t bits : inputs) {
      float sample = std::bit_cast<float>(bits);
      auto value = masker.Transform(sample);
      if (!value) return 4;
      const auto protected_bits = std::bit_cast<uint32_t>(*value);
      auto repeated = masker.Transform(sample);
      auto remasked = masker.Transform(*value);
      if (!repeated || !remasked || std::bit_cast<uint32_t>(*repeated) != protected_bits ||
          std::bit_cast<uint32_t>(*remasked) != protected_bits) return 5;
      output.write(reinterpret_cast<const char*>(&protected_bits), sizeof(protected_bits));
      ++cases;
    }
  }
  output.close();
  if (!output) return 6;

  std::array<uint8_t, 32> seed;
  seed.fill(27);
  alignas(OfflineAudioMasker) std::byte storage[sizeof(OfflineAudioMasker)];
  std::ranges::fill(storage, std::byte{0xa5});
  auto* masker = std::construct_at(reinterpret_cast<OfflineAudioMasker*>(storage), seed);
  auto transformed = masker->Transform(0.1234f);
  std::destroy_at(masker);
  if (!transformed || !std::ranges::all_of(seed, [](uint8_t value) { return value == 27; })) return 7;
  const bool cleansed = std::ranges::all_of(storage, [](std::byte value) { return value == std::byte{0}; });
  OfflineAudioMasker survivor(seed);
  {
    OfflineAudioMasker original(seed);
    auto value = original.Transform(0.1234f);
    if (!value || value != transformed) return 8;
    OfflineAudioMasker copied(original);
    survivor = copied;
    OfflineAudioMasker moved(std::move(original));
    copied = std::move(moved);
    if (copied.Transform(0.1234f) != transformed) return 9;
  }
  if (survivor.Transform(0.1234f) != transformed) return 10;
  std::cout << "{\"cases\":" << cases << ",\"storage_cleansed\":" << (cleansed ? "true" : "false")
            << ",\"caller_seed_unchanged\":true,\"copy_move_stable\":true}\n";
}
