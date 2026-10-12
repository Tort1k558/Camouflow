// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "third_party/blink/public/common/native_privacy/document_canvas_policy_validation.h"

#include "base/unguessable_token.h"
#include "net/base/schemeful_site.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace blink {
namespace {

using Seed = std::array<uint8_t, 32>;

StorageKey FirstParty() {
  return StorageKey::CreateFirstParty(
      url::Origin::Create(GURL("https://canvas.test/")));
}

TEST(GlintDocumentCanvasPolicyTest, MatchingPartitionReturnsOwnedSeed) {
  const auto key = FirstParty();
  const auto encoding = key.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  Seed seed{};
  seed[0] = 17;
  auto validated = ValidateGlintDocumentCanvasPolicy(1, *encoding, seed, key);
  ASSERT_TRUE(validated);
  EXPECT_EQ(*validated, seed);
  seed[0] = 99;
  EXPECT_EQ((*validated)[0], 17);
}

TEST(GlintDocumentCanvasPolicyTest, UnknownVersionRejectsMatchingPartition) {
  const auto key = FirstParty();
  const auto encoding = key.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  for (uint32_t version : {0u, 2u, UINT32_MAX}) {
    EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(version, *encoding, Seed{}, key));
  }
}

TEST(GlintDocumentCanvasPolicyTest, MissingCommitmentRejectsPolicy) {
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, {}, Seed{}, FirstParty()));
}

TEST(GlintDocumentCanvasPolicyTest, OriginChangeRejectsPreviousCommitment) {
  const auto key = FirstParty();
  const auto encoding = key.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  const auto next = key.WithOrigin(
      url::Origin::Create(GURL("https://next.test/")));
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, *encoding, Seed{}, next));
}

TEST(GlintDocumentCanvasPolicyTest, RetainedTopLevelSiteMattersWithPartitioningOff) {
  const auto origin = url::Origin::Create(GURL("https://canvas.test/"));
  const auto first = StorageKey::Create(
      origin, net::SchemefulSite(GURL("https://first.test/")),
      mojom::AncestorChainBit::kCrossSite, false);
  const auto second = StorageKey::Create(
      origin, net::SchemefulSite(GURL("https://second.test/")),
      mojom::AncestorChainBit::kCrossSite, false);
  ASSERT_EQ(first, second);
  const auto encoding = first.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, *encoding, Seed{}, second));
}

TEST(GlintDocumentCanvasPolicyTest, RetainedAncestorChainMatters) {
  const auto origin = url::Origin::Create(GURL("https://canvas.test/"));
  const net::SchemefulSite site(GURL("https://canvas.test/"));
  const auto same = StorageKey::Create(
      origin, site, mojom::AncestorChainBit::kSameSite, false);
  const auto cross = StorageKey::Create(
      origin, site, mojom::AncestorChainBit::kCrossSite, false);
  const auto encoding = same.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, *encoding, Seed{}, cross));
}

TEST(GlintDocumentCanvasPolicyTest, StorageNonceChangeRejectsCommitment) {
  const auto origin = url::Origin::Create(GURL("https://canvas.test/"));
  const auto first = StorageKey::CreateWithNonce(
      origin, base::UnguessableToken::Create());
  const auto second = StorageKey::CreateWithNonce(
      origin, base::UnguessableToken::Create());
  const auto encoding = first.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, *encoding, Seed{}, second));
}

TEST(GlintDocumentCanvasPolicyTest, OpaqueOriginRequiresExactOwnedIdentity) {
  const auto first = StorageKey::CreateFirstParty(url::Origin());
  const auto second = StorageKey::CreateFirstParty(url::Origin());
  const auto encoding = first.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  EXPECT_TRUE(ValidateGlintDocumentCanvasPolicy(1, *encoding, Seed{}, first));
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, *encoding, Seed{}, second));
}

TEST(GlintDocumentCanvasPolicyTest, EmbeddedNullAndTrailingDataAreNotIgnored) {
  const auto key = FirstParty();
  auto encoding = key.SerializeForNativePrivacy();
  ASSERT_TRUE(encoding);
  ASSERT_NE(encoding->find('\0'), std::string::npos);
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(
      1, std::string_view(*encoding).substr(0, encoding->find('\0')), Seed{}, key));
  encoding->push_back('\0');
  EXPECT_FALSE(ValidateGlintDocumentCanvasPolicy(1, *encoding, Seed{}, key));
}

}  // namespace
}  // namespace blink
