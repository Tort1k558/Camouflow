// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_OFFLINE_AUDIO_CANDIDATE_H_
#define GLINT_OFFLINE_AUDIO_CANDIDATE_H_

#include <array>
#include <cstdint>
#include <limits>
#include <optional>

namespace glint::candidate {
// Experimental scalar transform for a detached offline result, before exposure.
// Callers must use the independently derived audio partition seed, not Canvas.
// This is not a WebAudio integration or a real-time audio processing hook.
class OfflineAudioMasker {
 public:
  explicit OfflineAudioMasker(const std::array<uint8_t, 32>& audio_seed);
  std::optional<float> Transform(float sample);

 private:
  struct Entry {
    uint32_t normalized = std::numeric_limits<uint32_t>::max();
    uint32_t bit = 0;
  };
  std::array<uint8_t, 32> seed_;
  std::array<Entry, 256> cache_{};
};
}  // namespace glint::candidate

#endif
