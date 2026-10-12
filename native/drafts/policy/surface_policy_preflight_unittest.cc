// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "surface_policy_preflight.h"
#include "surface_policy_wire.h"
#include "worker_surface_policy_validation.h"

#include "base/unguessable_token.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace glint::candidate {
namespace {
class GlintSurfacePolicyPreflightTest : public testing::Test {
 protected:
  const url::Origin origin_ = url::Origin::Create(GURL("https://preflight.test/"));
  const blink::StorageKey partition_ = blink::StorageKey::CreateFirstParty(origin_);
  std::string encoding_ = *partition_.SerializeForNativePrivacy();
  PartitionSeed canvas_{1}, webgl_{2}, webgpu_{3}, audio_{4};

  SurfacePolicyView Incoming() {
    return {kSurfacePolicyVersion, encoding_, canvas_, webgl_, webgpu_, audio_};
  }
};

TEST_F(GlintSurfacePolicyPreflightTest, ReturnsOwnedSnapshot) {
  auto result = PreflightSurfacePolicyCommit(Incoming(), partition_, origin_);
  ASSERT_TRUE(result);
  encoding_.clear();
  audio_.fill(1);
  EXPECT_TRUE(ValidateSurfacePolicy(*result, partition_));
  EXPECT_EQ(result->audio[0], 4u);
}
TEST_F(GlintSurfacePolicyPreflightTest, RejectsEveryShortAndLongSeedBeforeCopy) {
  std::array<uint8_t, 33> oversized{};
  for (unsigned index = 0; index < 4; ++index) {
    for (unsigned size : {0u, 31u, 33u}) {
      auto incoming = Incoming();
      std::array<std::span<const uint8_t>*, 4> seeds{
          &incoming.canvas, &incoming.webgl, &incoming.webgpu, &incoming.audio};
      *seeds[index] = std::span<const uint8_t>(oversized).first(size);
      EXPECT_FALSE(PreflightSurfacePolicyCommit(incoming, partition_, origin_));
    }
  }
}
TEST_F(GlintSurfacePolicyPreflightTest, RejectsWrongVersionAndHugeEncoding) {
  auto incoming = Incoming();
  incoming.version = 1;
  EXPECT_FALSE(PreflightSurfacePolicyCommit(incoming, partition_, origin_));
  encoding_.assign(8193, 'x');
  EXPECT_FALSE(PreflightSurfacePolicyCommit(Incoming(), partition_, origin_));
}
TEST_F(GlintSurfacePolicyPreflightTest, ResolvesInheritedProvisionalOrigin) {
  const auto provisional = blink::StorageKey::CreateFirstParty(url::Origin());
  EXPECT_TRUE(PreflightSurfacePolicyCommit(Incoming(), provisional, origin_));
}
TEST_F(GlintSurfacePolicyPreflightTest, RejectsWrongBrowserOriginAndReusedSurface) {
  const auto wrong = url::Origin::Create(GURL("https://wrong.test/"));
  EXPECT_FALSE(PreflightSurfacePolicyCommit(Incoming(), partition_, wrong));
  auto incoming = Incoming();
  incoming.audio = incoming.canvas;
  EXPECT_FALSE(PreflightSurfacePolicyCommit(incoming, partition_, origin_));
}
TEST_F(GlintSurfacePolicyPreflightTest, WireRoundtripRetainsBinaryEncodingAndOwnedSeeds) {
  auto policy = PreflightSurfacePolicyCommit(Incoming(), partition_, origin_);
  ASSERT_TRUE(policy);
  auto wire = EncodeSurfacePolicyCommit(*policy, partition_);
  ASSERT_TRUE(wire);
  auto decoded = DecodeSurfacePolicyCommit(*wire, partition_, origin_);
  ASSERT_TRUE(decoded);
  EXPECT_EQ(decoded->partition_encoding, encoding_);
  EXPECT_NE(decoded->partition_encoding.find('\0'), std::string::npos);
  EXPECT_EQ(decoded->audio, audio_);
  wire->audio_seed.assign(32, 0);
  EXPECT_EQ(decoded->audio, audio_);
}
TEST_F(GlintSurfacePolicyPreflightTest, WireRejectsMalformedSeedAndWrongPartition) {
  auto policy = PreflightSurfacePolicyCommit(Incoming(), partition_, origin_);
  ASSERT_TRUE(policy);
  auto wire = EncodeSurfacePolicyCommit(*policy, partition_);
  ASSERT_TRUE(wire);
  wire->audio_seed.pop_back();
  EXPECT_FALSE(DecodeSurfacePolicyCommit(*wire, partition_, origin_));
  const auto other = blink::StorageKey::CreateFirstParty(
      url::Origin::Create(GURL("https://other.test/")));
  EXPECT_FALSE(EncodeSurfacePolicyCommit(*policy, other));
}
TEST_F(GlintSurfacePolicyPreflightTest, WorkerDecoderPreservesExactOpaqueIdentity) {
  const auto first = blink::StorageKey::CreateFirstParty(url::Origin());
  const auto second = blink::StorageKey::CreateFirstParty(url::Origin());
  encoding_ = *first.SerializeForNativePrivacy();
  auto policy = PreflightSurfacePolicyForPartition(Incoming(), first);
  ASSERT_TRUE(policy);
  auto wire = EncodeSurfacePolicyCommit(*policy, first);
  ASSERT_TRUE(wire);
  EXPECT_TRUE(DecodeWorkerSurfacePolicy(*wire, first));
  EXPECT_FALSE(DecodeWorkerSurfacePolicy(*wire, second));
}
TEST_F(GlintSurfacePolicyPreflightTest, WorkerDecoderCannotReplaceNoncePartition) {
  const auto first = blink::StorageKey::CreateWithNonce(origin_, base::UnguessableToken::Create());
  const auto second = blink::StorageKey::CreateWithNonce(origin_, base::UnguessableToken::Create());
  encoding_ = *first.SerializeForNativePrivacy();
  auto policy = PreflightSurfacePolicyForPartition(Incoming(), first);
  ASSERT_TRUE(policy);
  auto wire = EncodeSurfacePolicyCommit(*policy, first);
  ASSERT_TRUE(wire);
  EXPECT_TRUE(DecodeWorkerSurfacePolicy(*wire, first));
  EXPECT_FALSE(DecodeWorkerSurfacePolicy(*wire, second));
  EXPECT_FALSE(DecodeWorkerSurfacePolicy(*wire, partition_));
}
TEST_F(GlintSurfacePolicyPreflightTest, BrowserOwnedWorkerPartitionMatchesFinalOrigin) {
  auto policy = PreflightSurfacePolicyCommit(Incoming(), partition_, origin_);
  ASSERT_TRUE(policy);
  auto wire = EncodeSurfacePolicyCommit(*policy, partition_);
  ASSERT_TRUE(wire);
  auto owned = DecodeOwnedWorkerSurfacePolicy(*wire, origin_);
  ASSERT_TRUE(owned);
  EXPECT_TRUE(ValidateWorkerSurfacePolicy(owned, origin_, false));
  EXPECT_FALSE(ValidateWorkerSurfacePolicy(owned, origin_, true));
  EXPECT_FALSE(ValidateWorkerSurfacePolicy(owned,
      url::Origin::Create(GURL("https://wrong.test/")), false));
}
TEST_F(GlintSurfacePolicyPreflightTest, WirePartitionCannotDisagreeWithBinaryCommitment) {
  auto policy = PreflightSurfacePolicyCommit(Incoming(), partition_, origin_);
  ASSERT_TRUE(policy);
  auto wire = EncodeSurfacePolicyCommit(*policy, partition_);
  ASSERT_TRUE(wire);
  wire->partition = blink::StorageKey::CreateFirstParty(url::Origin::Create(GURL("https://wrong.test/")));
  EXPECT_FALSE(DecodeOwnedWorkerSurfacePolicy(*wire, wire->partition.origin()));
  EXPECT_FALSE(DecodeSurfacePolicyCommit(*wire, partition_, origin_));
}
}  // namespace
}  // namespace glint::candidate
