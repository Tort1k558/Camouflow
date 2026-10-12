// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "document_surface_policy.h"

#include <array>
#include <vector>

#include "base/unguessable_token.h"
#include "net/base/schemeful_site.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace glint::candidate {
namespace {
class GlintDocumentSurfacePolicyTest : public testing::Test {
 protected:
  const url::Origin origin_ = url::Origin::Create(GURL("https://document.test/"));
  const blink::StorageKey partition_ = blink::StorageKey::CreateFirstParty(origin_);

  blink::mojom::GlintSurfacePolicyCommitPtr Wire(const blink::StorageKey& key) {
    SurfacePolicy policy;
    policy.partition_encoding = *key.SerializeForNativePrivacy();
    policy.canvas.fill(1);
    policy.webgl.fill(2);
    policy.webgpu.fill(3);
    policy.audio.fill(4);
    return EncodeSurfacePolicyCommit(policy, key);
  }

  std::optional<DocumentSurfacePolicy> Owned() {
    auto wire = Wire(partition_);
    return DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false);
  }
};

TEST_F(GlintDocumentSurfacePolicyTest, OwnsEverySeedAndPartitionAfterWireDestruction) {
  auto wire = Wire(partition_);
  auto owned = DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false);
  ASSERT_TRUE(owned);
  wire->audio_seed.assign(32, 255);
  wire->partition_encoding.clear();
  wire.reset();
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(owned, partition_, true, false));
  PartitionSeed expected_audio;
  expected_audio.fill(4);
  EXPECT_EQ(owned->policy.audio, expected_audio);
  EXPECT_EQ(owned->partition, partition_);
}

TEST_F(GlintDocumentSurfacePolicyTest, ResolvesInheritedProvisionalOriginBeforeOwningKey) {
  auto wire = Wire(partition_);
  const auto provisional = blink::StorageKey::CreateFirstParty(url::Origin());
  auto owned = DecodeOwnedDocumentSurfacePolicy(*wire, provisional, origin_, false);
  ASSERT_TRUE(owned);
  EXPECT_EQ(owned->partition, partition_);
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(owned, partition_, true, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, PreservesExactOpaqueOriginIdentity) {
  const auto key = blink::StorageKey::CreateFirstParty(url::Origin());
  auto wire = Wire(key);
  auto owned = DecodeOwnedDocumentSurfacePolicy(*wire, key, key.origin(), false);
  ASSERT_TRUE(owned);
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(owned, key, true, false));
  const auto other = blink::StorageKey::CreateFirstParty(url::Origin());
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(owned, other, true, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, PreservesNoncePartitionAndRejectsReplacement) {
  const auto key = blink::StorageKey::CreateWithNonce(
      origin_, base::UnguessableToken::Create());
  auto wire = Wire(key);
  auto owned = DecodeOwnedDocumentSurfacePolicy(*wire, key, origin_, false);
  ASSERT_TRUE(owned);
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(owned, key, true, false));
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(owned, partition_, true, false));
  const auto other = blink::StorageKey::CreateWithNonce(
      origin_, base::UnguessableToken::Create());
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, other, origin_, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, RejectsWrongBrowserOriginBeforeOwnership) {
  auto wire = Wire(partition_);
  const auto other = url::Origin::Create(GURL("https://other.test/"));
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, other, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, RejectsWireKeyAndCommitmentDisagreement) {
  auto wire = Wire(partition_);
  wire->partition = blink::StorageKey::CreateFirstParty(
      url::Origin::Create(GURL("https://other.test/")));
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, RejectsEveryMalformedSurfaceLength) {
  for (unsigned index = 0; index < 4; ++index) {
    for (unsigned size : {0u, 31u, 33u}) {
      auto wire = Wire(partition_);
      std::array<std::vector<uint8_t>*, 4> seeds{
          &wire->canvas_seed, &wire->webgl_seed, &wire->webgpu_seed, &wire->audio_seed};
      seeds[index]->resize(size);
      EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
    }
  }
}

TEST_F(GlintDocumentSurfacePolicyTest, RejectsWrongVersionAndEncodingBounds) {
  auto wire = Wire(partition_);
  wire->version = 1;
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
  wire = Wire(partition_);
  wire->partition_encoding.clear();
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
  wire->partition_encoding.assign(8193, 'x');
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, RejectsEveryReusedSurfacePair) {
  for (unsigned first = 0; first < 4; ++first) {
    for (unsigned second = first + 1; second < 4; ++second) {
      auto wire = Wire(partition_);
      std::array<std::vector<uint8_t>*, 4> seeds{
          &wire->canvas_seed, &wire->webgl_seed, &wire->webgpu_seed, &wire->audio_seed};
      *seeds[second] = *seeds[first];
      EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
    }
  }
}

TEST_F(GlintDocumentSurfacePolicyTest, RejectsLegacyAndSurfacePayloadMix) {
  auto wire = Wire(partition_);
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, true));
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(Owned(), partition_, true, true));
}

TEST_F(GlintDocumentSurfacePolicyTest, MissingRequiredPolicyCannotInstall) {
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(std::nullopt, partition_, true, false));
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(std::nullopt, partition_, true, true));
}

TEST_F(GlintDocumentSurfacePolicyTest, OffModePreservesLegacyOrUpstreamAbsence) {
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(std::nullopt, partition_, false, false));
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(std::nullopt, partition_, false, true));
}

TEST_F(GlintDocumentSurfacePolicyTest, PayloadPresenceCannotSkipFinalValidation) {
  auto owned = Owned();
  ASSERT_TRUE(owned);
  owned->policy.version = 1;
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(owned, partition_, false, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, FinalDifferentOriginCannotInstall) {
  const auto other = blink::StorageKey::CreateFirstParty(
      url::Origin::Create(GURL("https://other.test/")));
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(Owned(), other, true, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, CorruptedOwnedKeyCannotInstall) {
  auto owned = Owned();
  ASSERT_TRUE(owned);
  owned->partition = blink::StorageKey::CreateFirstParty(url::Origin());
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(owned, partition_, true, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, RetainedTopLevelSiteSurvivesDisabledPartitioning) {
  const auto first = blink::StorageKey::Create(origin_,
      net::SchemefulSite(GURL("https://one.test/")),
      blink::mojom::AncestorChainBit::kCrossSite, false);
  const auto second = blink::StorageKey::Create(origin_,
      net::SchemefulSite(GURL("https://two.test/")),
      blink::mojom::AncestorChainBit::kCrossSite, false);
  ASSERT_EQ(first, second);
  auto wire = Wire(first);
  auto owned = DecodeOwnedDocumentSurfacePolicy(*wire, first, origin_, false);
  ASSERT_TRUE(owned);
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(owned, first, true, false));
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(owned, second, true, false));
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, second, origin_, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, BinaryCommitmentCannotBeTruncatedOrExtended) {
  auto wire = Wire(partition_);
  const auto separator = wire->partition_encoding.find('\0');
  ASSERT_NE(separator, std::string::npos);
  wire->partition_encoding.resize(separator);
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
  wire = Wire(partition_);
  wire->partition_encoding.push_back('\0');
  EXPECT_FALSE(DecodeOwnedDocumentSurfacePolicy(*wire, partition_, origin_, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, MutatingReturnedSnapshotDoesNotAlterOriginal) {
  const auto original = Owned();
  ASSERT_TRUE(original);
  auto copy = original;
  copy->policy.audio = copy->policy.canvas;
  copy->policy.partition_encoding.clear();
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(copy, partition_, true, false));
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(original, partition_, true, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, UnchangedPolicyRemainsValidAcrossOwnershipMoves) {
  auto original = Owned();
  ASSERT_TRUE(original);
  auto moved = std::move(original);
  original.reset();
  EXPECT_TRUE(ValidateDocumentSurfacePolicy(moved, partition_, true, false));
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(original, partition_, true, false));
}

TEST_F(GlintDocumentSurfacePolicyTest, SelectsFourExplicitModes) {
  EXPECT_EQ(SelectDocumentPrivacyBootstrapMode(false, false), DocumentPrivacyBootstrapMode::kOff);
  EXPECT_EQ(SelectDocumentPrivacyBootstrapMode(true, false), DocumentPrivacyBootstrapMode::kCanvas);
  EXPECT_EQ(SelectDocumentPrivacyBootstrapMode(false, true), DocumentPrivacyBootstrapMode::kSurfaces);
  EXPECT_EQ(SelectDocumentPrivacyBootstrapMode(true, true), DocumentPrivacyBootstrapMode::kConflict);
}

TEST_F(GlintDocumentSurfacePolicyTest, EveryModeRequiresOnlyItsOwnPayload) {
  for (auto mode : {DocumentPrivacyBootstrapMode::kOff, DocumentPrivacyBootstrapMode::kCanvas,
                    DocumentPrivacyBootstrapMode::kSurfaces, DocumentPrivacyBootstrapMode::kConflict}) {
    for (bool canvas : {false, true}) {
      for (bool surfaces : {false, true}) {
        const bool expected =
            (mode == DocumentPrivacyBootstrapMode::kOff && !canvas && !surfaces) ||
            (mode == DocumentPrivacyBootstrapMode::kCanvas && canvas && !surfaces) ||
            (mode == DocumentPrivacyBootstrapMode::kSurfaces && !canvas && surfaces);
        EXPECT_EQ(HasExpectedDocumentPrivacyPayload(mode, canvas, surfaces), expected);
      }
    }
  }
}

TEST_F(GlintDocumentSurfacePolicyTest, UnknownModeCannotAdmitAnyPayload) {
  const auto mode = static_cast<DocumentPrivacyBootstrapMode>(255);
  for (bool canvas : {false, true}) {
    for (bool surfaces : {false, true}) {
      EXPECT_FALSE(HasExpectedDocumentPrivacyPayload(mode, canvas, surfaces));
    }
  }
}
}  // namespace
}  // namespace glint::candidate
