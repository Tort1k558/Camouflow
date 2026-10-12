// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_OFFLINE_AUDIO_BUFFER_H_
#define GLINT_OFFLINE_AUDIO_BUFFER_H_

#include <array>
#include <cstdint>

namespace blink {
class AudioBuffer;
}

namespace glint::candidate {
// A detached result only. Never exposes a partial transform or mutates source.
// No caller should fall back to unprotected output when this returns nullptr.
blink::AudioBuffer* CopyOfflineAudioBuffer(
    blink::AudioBuffer& source,
    const std::array<uint8_t, 32>& audio_seed);
}  // namespace glint::candidate

#endif
