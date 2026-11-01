// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <memory>

#include "offline_audio_candidate.h"
#include "third_party/boringssl/src/include/openssl/evp.h"
#include "third_party/boringssl/src/include/openssl/hmac.h"
#include "third_party/boringssl/src/include/openssl/mem.h"

namespace {
uint8_t digest_tag;
uint8_t* last_digest = nullptr;
unsigned hmac_calls = 0, digest_cleanses = 0, malformed_cleanses = 0;
bool wrong_length = false;
}

extern "C" const EVP_MD* EVP_sha256() {
  return reinterpret_cast<const EVP_MD*>(&digest_tag);
}

extern "C" uint8_t* HMAC(const EVP_MD*, const void*, size_t,
                         const uint8_t*, size_t, uint8_t* output, unsigned* length) {
  ++hmac_calls;
  last_digest = output;
  std::fill_n(output, 32, 0xa7);
  *length = wrong_length ? 31 : 32;
  return wrong_length ? output : nullptr;
}

extern "C" void OPENSSL_cleanse(void* pointer, size_t length) {
  const bool digest = pointer == last_digest;
  auto* bytes = static_cast<volatile uint8_t*>(pointer);
  if (digest) {
    ++digest_cleanses;
    if (length != 32) ++malformed_cleanses;
    for (size_t index = 0; index < length; ++index) {
      if (bytes[index] != 0xa7) ++malformed_cleanses;
    }
  }
  for (size_t index = 0; index < length; ++index) bytes[index] = 0;
  if (digest) {
    for (size_t index = 0; index < length; ++index) {
      if (bytes[index] != 0) ++malformed_cleanses;
    }
  }
}

int main() {
  using glint::candidate::OfflineAudioMasker;
  unsigned cleared_objects = 0;
  for (bool mode : {false, true}) {
    wrong_length = mode;
    std::array<uint8_t, 32> seed;
    seed.fill(27);
    alignas(OfflineAudioMasker) std::byte storage[sizeof(OfflineAudioMasker)];
    auto* masker = std::construct_at(reinterpret_cast<OfflineAudioMasker*>(storage), seed);
    const bool first_failed = !masker->Transform(0.1234f).has_value();
    const bool second_failed = !masker->Transform(0.1234f).has_value();
    std::destroy_at(masker);
    if (!first_failed || !second_failed) return 2;
    if (std::ranges::all_of(storage, [](std::byte value) { return value == std::byte{0}; })) ++cleared_objects;
    if (!std::ranges::all_of(seed, [](uint8_t value) { return value == 27; })) return 3;
  }
  if (hmac_calls != 4 || malformed_cleanses != 0) return 4;
  std::cout << "{\"injected_hmac_failures\":" << hmac_calls << ",\"digest_cleanses\":" << digest_cleanses
            << ",\"destroyed_storage_cleansed\":" << cleared_objects
            << ",\"malformed_cleanses\":" << malformed_cleanses << ",\"failed_calls_not_cached\":true}\n";
}
