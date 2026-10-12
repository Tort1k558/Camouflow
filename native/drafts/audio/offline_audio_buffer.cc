// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "offline_audio_buffer.h"

#include "offline_audio_candidate.h"
#include "offline_audio_limits.h"
#include "third_party/blink/renderer/modules/webaudio/audio_buffer.h"

namespace glint::candidate {
blink::AudioBuffer* CopyOfflineAudioBuffer(
    blink::AudioBuffer& source,
    const std::array<uint8_t, 32>& audio_seed) {
  const auto channels = source.numberOfChannels();
  const auto frames = source.length();
  if (!CanCopyOfflineAudio(channels, frames)) {
    return nullptr;
  }
  // Check every source before allocation; detached/invalid channel views reject.
  for (unsigned channel = 0; channel < channels; ++channel) {
    auto input = source.getChannelData(channel);
    if (!input || input->AsSpan().size() != frames) {
      return nullptr;
    }
  }
  auto* output = blink::AudioBuffer::CreateUninitialized(
      channels, frames, source.sampleRate());
  if (!output) {
    return nullptr;
  }
  OfflineAudioMasker masker(audio_seed);
  for (unsigned channel = 0; channel < channels; ++channel) {
    const auto input = source.getChannelData(channel)->AsSpan();
    auto destination = output->getChannelData(channel)->AsSpan();
    for (size_t index = 0; index < input.size(); ++index) {
      auto value = masker.Transform(input[index]);
      if (!value) {
        return nullptr;
      }
      destination[index] = *value;
    }
  }
  return output;
}
}  // namespace glint::candidate
