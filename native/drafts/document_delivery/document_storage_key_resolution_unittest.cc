// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "third_party/blink/public/common/native_privacy/document_storage_key_resolution.h"

#include <array>

#include "base/unguessable_token.h"
#include "net/base/schemeful_site.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "third_party/blink/public/common/native_privacy/document_canvas_policy_validation.h"
#include "url/gurl.h"

namespace blink {
namespace {

url::Origin Origin() {
  return url::Origin::Create(GURL("https://canvas.test/"));
}

TEST(GlintDocumentStorageKeyTest, FirstPartyPartitionRemainsStable) {
  const auto origin = Origin();
  const auto key = StorageKey::CreateFirstParty(origin);
  EXPECT_EQ(ResolveGlintDocumentStorageKey(key, origin).SerializeForNativePrivacy(),
            key.SerializeForNativePrivacy());
}

TEST(GlintDocumentStorageKeyTest, NonOpaqueOriginChangeRetainsTopLevelSite) {
  const auto key = StorageKey::CreateFirstParty(Origin());
  const auto next = url::Origin::Create(GURL("https://next.test/"));
  const auto resolved = ResolveGlintDocumentStorageKey(key, next);
  EXPECT_EQ(resolved.origin(), next);
  EXPECT_EQ(resolved.top_level_site(), key.top_level_site());
  EXPECT_NE(resolved.SerializeForNativePrivacy(), key.SerializeForNativePrivacy());
}

TEST(GlintDocumentStorageKeyTest, DisabledPartitioningRetainsNativeSiteEncoding) {
  const auto origin = Origin();
  const auto first = StorageKey::Create(
      origin, net::SchemefulSite(GURL("https://first.test/")),
      mojom::AncestorChainBit::kCrossSite, false);
  const auto second = StorageKey::Create(
      origin, net::SchemefulSite(GURL("https://second.test/")),
      mojom::AncestorChainBit::kCrossSite, false);
  const auto resolved = ResolveGlintDocumentStorageKey(first, origin);
  EXPECT_EQ(resolved.SerializeForNativePrivacy(), first.SerializeForNativePrivacy());
  EXPECT_NE(resolved.SerializeForNativePrivacy(), second.SerializeForNativePrivacy());
}

TEST(GlintDocumentStorageKeyTest, EnabledPartitioningRetainsCrossSitePartition) {
  const auto origin = Origin();
  const auto key = StorageKey::Create(
      origin, net::SchemefulSite(GURL("https://top.test/")),
      mojom::AncestorChainBit::kCrossSite, true);
  const auto resolved = ResolveGlintDocumentStorageKey(key, origin);
  EXPECT_EQ(resolved.top_level_site(), key.top_level_site());
  EXPECT_EQ(resolved.ancestor_chain_bit(), mojom::AncestorChainBit::kCrossSite);
  EXPECT_EQ(resolved.SerializeForNativePrivacy(), key.SerializeForNativePrivacy());
}

TEST(GlintDocumentStorageKeyTest, OpaqueWithoutStorageNonceUsesFinalFirstPartyKey) {
  const auto provisional = StorageKey::CreateFirstParty(url::Origin());
  const auto final_origin = Origin();
  const auto resolved = ResolveGlintDocumentStorageKey(provisional, final_origin);
  const auto expected = StorageKey::CreateFirstParty(final_origin);
  EXPECT_EQ(resolved.SerializeForNativePrivacy(), expected.SerializeForNativePrivacy());
  EXPECT_FALSE(resolved.nonce());
}

TEST(GlintDocumentStorageKeyTest, OpaqueWithStorageNoncePreservesNonce) {
  const auto nonce = base::UnguessableToken::Create();
  const auto provisional = StorageKey::CreateWithNonce(url::Origin(), nonce);
  const auto final_origin = Origin();
  const auto resolved = ResolveGlintDocumentStorageKey(provisional, final_origin);
  ASSERT_TRUE(resolved.nonce());
  EXPECT_EQ(*resolved.nonce(), nonce);
  EXPECT_EQ(resolved.SerializeForNativePrivacy(),
            StorageKey::CreateWithNonce(final_origin, nonce).SerializeForNativePrivacy());
}

TEST(GlintDocumentStorageKeyTest, FinalOpaqueIdentityIsNotRegenerated) {
  const auto provisional = StorageKey::CreateFirstParty(url::Origin());
  const url::Origin final_origin;
  const auto resolved = ResolveGlintDocumentStorageKey(provisional, final_origin);
  EXPECT_EQ(resolved.origin(), final_origin);
  EXPECT_EQ(resolved.SerializeForNativePrivacy(),
            StorageKey::CreateFirstParty(final_origin).SerializeForNativePrivacy());
  EXPECT_NE(resolved.SerializeForNativePrivacy(), provisional.SerializeForNativePrivacy());
}

TEST(GlintDocumentStorageKeyTest, ResolutionDoesNotMutateProvisionalPartition) {
  const auto provisional = StorageKey::CreateFirstParty(url::Origin());
  const auto before = provisional.SerializeForNativePrivacy();
  const auto final_origin = Origin();
  const auto first = ResolveGlintDocumentStorageKey(provisional, final_origin);
  const auto second = ResolveGlintDocumentStorageKey(provisional, final_origin);
  EXPECT_EQ(first.SerializeForNativePrivacy(), second.SerializeForNativePrivacy());
  EXPECT_EQ(provisional.SerializeForNativePrivacy(), before);
}

TEST(GlintDocumentStorageKeyTest, ValidatorRejectsUnresolvedCommitment) {
  const auto provisional = StorageKey::CreateFirstParty(url::Origin());
  const auto resolved = ResolveGlintDocumentStorageKey(provisional, Origin());
  const auto before = provisional.SerializeForNativePrivacy();
  const auto after = resolved.SerializeForNativePrivacy();
  ASSERT_TRUE(before);
  ASSERT_TRUE(after);
  std::array<uint8_t, 32> seed{};
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, *before, seed, resolved));
  EXPECT_TRUE(ValidateGlintDocumentCanvasPolicy(1, *after, seed, resolved));
}

}  // namespace
}  // namespace blink
