// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_OFFLINE_AUDIO_LIMITS_H_
#define GLINT_OFFLINE_AUDIO_LIMITS_H_

#include <cstddef>
#include <cstdint>

namespace glint::candidate {
constexpr size_t kMaxOfflineAudioCopyBytes = 64 * 1024 * 1024;
constexpr bool CanCopyOfflineAudio(unsigned channels, uint32_t frames) {
  return channels && frames &&
         channels <= kMaxOfflineAudioCopyBytes / sizeof(float) / frames;
}
}  // namespace glint::candidate

#endif
