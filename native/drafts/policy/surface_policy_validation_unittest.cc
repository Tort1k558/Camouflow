// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "surface_policy_validation.h"

#include "base/unguessable_token.h"
#include "net/base/schemeful_site.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace glint::candidate {
namespace {
blink::StorageKey Partition() {
  return blink::StorageKey::CreateFirstParty(url::Origin::Create(GURL("https://policy.test/")));
}
SurfacePolicy Policy() {
  SurfacePolicy policy;
  policy.partition_encoding = *Partition().SerializeForNativePrivacy();
  policy.canvas.fill(1);
  policy.webgl.fill(2);
  policy.webgpu.fill(3);
  policy.audio.fill(4);
  return policy;
}

TEST(GlintSurfacePolicyTest, ValidIndependentSnapshot) {
  EXPECT_TRUE(ValidateSurfacePolicy(Policy(), Partition()));
}
TEST(GlintSurfacePolicyTest, RejectsUnsupportedVersion) {
  auto policy = Policy();
  policy.version = 1;
  EXPECT_FALSE(ValidateSurfacePolicy(policy, Partition()));
  policy.version = 3;
  EXPECT_FALSE(ValidateSurfacePolicy(policy, Partition()));
}
TEST(GlintSurfacePolicyTest, RejectsEmptyAndOversizedEncoding) {
  auto policy = Policy();
  policy.partition_encoding.clear();
  EXPECT_FALSE(ValidateSurfacePolicy(policy, Partition()));
  policy.partition_encoding.assign(8193, 'x');
  EXPECT_FALSE(ValidateSurfacePolicy(policy, Partition()));
}
TEST(GlintSurfacePolicyTest, RejectsAnotherOrigin) {
  EXPECT_FALSE(ValidateSurfacePolicy(Policy(), blink::StorageKey::CreateFirstParty(
      url::Origin::Create(GURL("https://other.test/")))));
}
TEST(GlintSurfacePolicyTest, RejectsEveryPairOfReusedSeeds) {
  for (unsigned left = 0; left < 4; ++left) {
    for (unsigned right = left + 1; right < 4; ++right) {
      auto policy = Policy();
      std::array<PartitionSeed*, 4> seeds{
          &policy.canvas, &policy.webgl, &policy.webgpu, &policy.audio};
      *seeds[right] = *seeds[left];
      EXPECT_FALSE(ValidateSurfacePolicy(policy, Partition()));
    }
  }
}
TEST(GlintSurfacePolicyTest, SnapshotOwnsSeedsAndEncoding) {
  auto original = Policy();
  auto copy = original;
  original.audio.fill(1);
  original.partition_encoding.clear();
  EXPECT_TRUE(ValidateSurfacePolicy(copy, Partition()));
  EXPECT_FALSE(ValidateSurfacePolicy(original, Partition()));
}
TEST(GlintSurfacePolicyTest, RejectsDifferentOpaquePartition) {
  EXPECT_FALSE(ValidateSurfacePolicy(Policy(), blink::StorageKey::CreateFirstParty(url::Origin())));
}
TEST(GlintSurfacePolicyTest, NonceIdentityIsExact) {
  const auto origin = url::Origin::Create(GURL("https://policy.test/"));
  const auto first = blink::StorageKey::CreateWithNonce(origin, base::UnguessableToken::Create());
  const auto second = blink::StorageKey::CreateWithNonce(origin, base::UnguessableToken::Create());
  auto policy = Policy();
  policy.partition_encoding = *first.SerializeForNativePrivacy();
  EXPECT_TRUE(ValidateSurfacePolicy(policy, first));
  EXPECT_FALSE(ValidateSurfacePolicy(policy, second));
}
TEST(GlintSurfacePolicyTest, RetainedTopLevelSiteCannotBeDropped) {
  const auto origin = url::Origin::Create(GURL("https://policy.test/"));
  const auto first = blink::StorageKey::Create(origin, net::SchemefulSite(GURL("https://one.test/")),
      blink::mojom::AncestorChainBit::kCrossSite, false);
  const auto second = blink::StorageKey::Create(origin, net::SchemefulSite(GURL("https://two.test/")),
      blink::mojom::AncestorChainBit::kCrossSite, false);
  ASSERT_EQ(first, second);
  auto policy = Policy();
  policy.partition_encoding = *first.SerializeForNativePrivacy();
  EXPECT_TRUE(ValidateSurfacePolicy(policy, first));
  EXPECT_FALSE(ValidateSurfacePolicy(policy, second));
}
TEST(GlintSurfacePolicyTest, RejectsEmbeddedNullTruncationAndTrailingData) {
  auto policy = Policy();
  const auto null_position = policy.partition_encoding.find('\0');
  ASSERT_NE(null_position, std::string::npos);
  policy.partition_encoding.resize(null_position);
  EXPECT_FALSE(ValidateSurfacePolicy(policy, Partition()));
  policy = Policy();
  policy.partition_encoding.push_back('\0');
  EXPECT_FALSE(ValidateSurfacePolicy(policy, Partition()));
}
}  // namespace
}  // namespace glint::candidate
