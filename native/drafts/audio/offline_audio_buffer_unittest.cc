// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "offline_audio_buffer.h"

#include <bit>

#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/renderer/modules/webaudio/audio_buffer.h"
#include "third_party/blink/renderer/platform/testing/task_environment.h"

namespace glint::candidate {
namespace {
constexpr std::array<uint8_t, 32> kSeed{};
class GlintOfflineAudioBufferTest : public testing::Test {
 private:
  blink::test::TaskEnvironment task_environment_;
};

TEST_F(GlintOfflineAudioBufferTest, CopyPreservesFormatAndSourceBits) {
  auto* source = blink::AudioBuffer::Create(2, 8, 48000);
  ASSERT_TRUE(source);
  for (unsigned channel = 0; channel < 2; ++channel) {
    auto input = source->getChannelData(channel)->AsSpan();
    for (size_t index = 0; index < input.size(); ++index) {
      input[index] = 0.1234f;
    }
  }
  auto* output = CopyOfflineAudioBuffer(*source, kSeed);
  ASSERT_TRUE(output);
  EXPECT_NE(source, output);
  EXPECT_EQ(output->numberOfChannels(), 2u);
  EXPECT_EQ(output->length(), 8u);
  EXPECT_EQ(output->sampleRate(), 48000);
  for (unsigned channel = 0; channel < 2; ++channel) {
    const auto input = source->getChannelData(channel)->AsSpan();
    const auto result = output->getChannelData(channel)->AsSpan();
    EXPECT_NE(input.data(), result.data());
    for (size_t index = 0; index < input.size(); ++index) {
      EXPECT_EQ(std::bit_cast<uint32_t>(input[index]), std::bit_cast<uint32_t>(0.1234f));
      EXPECT_LE(std::bit_cast<uint32_t>(input[index]) ^ std::bit_cast<uint32_t>(result[index]), 1u);
    }
  }
}

TEST_F(GlintOfflineAudioBufferTest, EqualChannelsRemainEqual) {
  auto* source = blink::AudioBuffer::Create(2, 16, 44100);
  ASSERT_TRUE(source);
  for (unsigned channel = 0; channel < 2; ++channel) {
    auto input = source->getChannelData(channel)->AsSpan();
    for (size_t index = 0; index < input.size(); ++index) {
      input[index] = static_cast<float>(index) / 32;
    }
  }
  auto* output = CopyOfflineAudioBuffer(*source, kSeed);
  ASSERT_TRUE(output);
  const auto left = output->getChannelData(0)->AsSpan();
  const auto right = output->getChannelData(1)->AsSpan();
  for (size_t index = 0; index < left.size(); ++index) {
    EXPECT_EQ(left[index], right[index]);
  }
}

TEST_F(GlintOfflineAudioBufferTest, ResultRemainsNormallyMutable) {
  auto* source = blink::AudioBuffer::Create(1, 8, 44100);
  ASSERT_TRUE(source);
  auto* output = CopyOfflineAudioBuffer(*source, kSeed);
  ASSERT_TRUE(output);
  output->getChannelData(0)->AsSpan()[0] = 0.75f;
  EXPECT_EQ(output->getChannelData(0)->AsSpan()[0], 0.75f);
  EXPECT_EQ(source->getChannelData(0)->AsSpan()[0], 0);
}

TEST_F(GlintOfflineAudioBufferTest, RemaskedCopyIsIdempotent) {
  auto* source = blink::AudioBuffer::Create(1, 8, 44100);
  ASSERT_TRUE(source);
  source->getChannelData(0)->AsSpan()[0] = -0.1234f;
  auto* first = CopyOfflineAudioBuffer(*source, kSeed);
  ASSERT_TRUE(first);
  auto* second = CopyOfflineAudioBuffer(*first, kSeed);
  ASSERT_TRUE(second);
  EXPECT_EQ(std::bit_cast<uint32_t>(first->getChannelData(0)->AsSpan()[0]),
            std::bit_cast<uint32_t>(second->getChannelData(0)->AsSpan()[0]));
}
}  // namespace
}  // namespace glint::candidate
