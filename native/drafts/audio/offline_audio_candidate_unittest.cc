// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "offline_audio_candidate.h"
#include "offline_audio_limits.h"

#include <bit>
#include <cmath>

#include "testing/gtest/include/gtest/gtest.h"

namespace glint::candidate {
namespace {
constexpr std::array<uint8_t, 32> kAudioSeed{};

TEST(GlintOfflineAudioCandidateTest, PreservesSignedSilence) {
  OfflineAudioMasker masker(kAudioSeed);
  for (uint32_t bits : {0u, 0x80000000u}) {
    ASSERT_TRUE(masker.Transform(std::bit_cast<float>(bits)));
    EXPECT_EQ(
        std::bit_cast<uint32_t>(*masker.Transform(std::bit_cast<float>(bits))),
        bits);
  }
}

TEST(GlintOfflineAudioCandidateTest, PreservesNonFinitePayloadBits) {
  OfflineAudioMasker masker(kAudioSeed);
  for (uint32_t bits : {0x7f800000u, 0xff800000u, 0x7fc00123u}) {
    auto value = masker.Transform(std::bit_cast<float>(bits));
    ASSERT_TRUE(value);
    EXPECT_EQ(std::bit_cast<uint32_t>(*value), bits);
  }
}

TEST(GlintOfflineAudioCandidateTest, PreservesSubnormalBits) {
  OfflineAudioMasker masker(kAudioSeed);
  for (uint32_t bits : {1u, 0x007fffffu, 0x80000001u}) {
    auto value = masker.Transform(std::bit_cast<float>(bits));
    ASSERT_TRUE(value);
    EXPECT_EQ(std::bit_cast<uint32_t>(*value), bits);
  }
}

TEST(GlintOfflineAudioCandidateTest, PreservesUnitAmplitudeAndPeaks) {
  OfflineAudioMasker masker(kAudioSeed);
  for (float sample : {1.0f, -1.0f, 4.0f, -4.0f}) {
    EXPECT_EQ(masker.Transform(sample), sample);
  }
}

TEST(GlintOfflineAudioCandidateTest, ChangesOnlyLeastMantissaBit) {
  OfflineAudioMasker masker(kAudioSeed);
  for (float sample : {0.25f, -0.25f, 0.1234f, -0.1234f}) {
    auto value = masker.Transform(sample);
    ASSERT_TRUE(value);
    EXPECT_LE(std::bit_cast<uint32_t>(*value) ^ std::bit_cast<uint32_t>(sample),
              1u);
    EXPECT_EQ(std::signbit(*value), std::signbit(sample));
  }
}

TEST(GlintOfflineAudioCandidateTest, RepeatedAndRemaskedValuesAreStable) {
  OfflineAudioMasker masker(kAudioSeed);
  auto value = masker.Transform(0.1234f);
  ASSERT_TRUE(value);
  EXPECT_EQ(masker.Transform(0.1234f), value);
  EXPECT_EQ(masker.Transform(*value), value);
}

TEST(GlintOfflineAudioCandidateTest, EqualStereoSamplesRemainEqual) {
  OfflineAudioMasker left(kAudioSeed), right(kAudioSeed);
  for (float sample : {0.1f, 0.2f, -0.3f}) {
    EXPECT_EQ(left.Transform(sample), right.Transform(sample));
  }
}

TEST(GlintOfflineAudioCandidateTest, DifferentSeedsDoNotShareAllOutputBits) {
  auto other_seed = kAudioSeed;
  other_seed.fill(233);
  OfflineAudioMasker first(kAudioSeed), second(other_seed);
  bool differs = false;
  for (uint32_t index = 0; index < 256; ++index) {
    const auto sample = std::bit_cast<float>(0x3e800000u + index * 2);
    auto left = first.Transform(sample), right = second.Transform(sample);
    ASSERT_TRUE(left);
    ASSERT_TRUE(right);
    differs |= *left != *right;
  }
  EXPECT_TRUE(differs);
}

TEST(GlintOfflineAudioCandidateTest,
     CacheCollisionsDoNotAliasDifferentSamples) {
  OfflineAudioMasker cached(kAudioSeed);
  for (uint32_t index = 0; index < 1024; ++index) {
    OfflineAudioMasker fresh(kAudioSeed);
    const auto sample = std::bit_cast<float>(0x3e800000u + index * 2);
    EXPECT_EQ(cached.Transform(sample), fresh.Transform(sample));
  }
}

TEST(GlintOfflineAudioCandidateTest, RejectsEmptyAndOverflowingCopySizes) {
  EXPECT_FALSE(CanCopyOfflineAudio(0, 1));
  EXPECT_FALSE(CanCopyOfflineAudio(1, 0));
  EXPECT_FALSE(CanCopyOfflineAudio(std::numeric_limits<unsigned>::max(),
                                   std::numeric_limits<uint32_t>::max()));
}

TEST(GlintOfflineAudioCandidateTest, CopyBudgetBoundaryIsExact) {
  constexpr uint32_t kFrames = kMaxOfflineAudioCopyBytes / sizeof(float) / 2;
  EXPECT_TRUE(CanCopyOfflineAudio(2, kFrames));
  EXPECT_FALSE(CanCopyOfflineAudio(2, kFrames + 1));
  EXPECT_TRUE(CanCopyOfflineAudio(2, 4096));
}

TEST(GlintOfflineAudioCandidateTest, MatchesIndependentHmacVectors) {
  OfflineAudioMasker masker(kAudioSeed);
  // Independently calculated HMAC-SHA256 over the domain and big-endian bits.
  constexpr std::array<std::array<uint32_t, 2>, 6> kVectors{{
      {0x3e800000u, 0x3e800000u},
      {0x3e800001u, 0x3e800000u},
      {0xbe800002u, 0xbe800003u},
      {0x3eaaaaaau, 0x3eaaaaabu},
      {0x00800000u, 0x00800000u},
      {0x3f7ffffeu, 0x3f7ffffeu},
  }};
  for (const auto& vector : kVectors) {
    auto result = masker.Transform(std::bit_cast<float>(vector[0]));
    ASSERT_TRUE(result);
    EXPECT_EQ(std::bit_cast<uint32_t>(*result), vector[1]);
  }
}

TEST(GlintOfflineAudioCandidateTest, MeasuredSignalMeetsNumericalErrorBudget) {
  OfflineAudioMasker masker(kAudioSeed);
  double signal_energy = 0;
  double error_energy = 0;
  unsigned changed_samples = 0;
  for (uint32_t index = 0; index < 4096; ++index) {
    const float sample = static_cast<float>(0.75 * std::sin(index * 0.03125));
    auto result = masker.Transform(sample);
    ASSERT_TRUE(result);
    EXPECT_LE(
        std::bit_cast<uint32_t>(*result) ^ std::bit_cast<uint32_t>(sample), 1u);
    const double error = static_cast<double>(*result) - sample;
    signal_energy += static_cast<double>(sample) * sample;
    error_energy += error * error;
    changed_samples += *result != sample;
  }
  EXPECT_GT(changed_samples, 0u);
  EXPECT_GT(error_energy, 0);
  EXPECT_GE(10 * std::log10(signal_energy / error_energy), 130);
}
}  // namespace
}  // namespace glint::candidate
