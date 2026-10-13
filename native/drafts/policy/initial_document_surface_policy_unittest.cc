// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "initial_document_surface_policy.h"

#include "testing/gtest/include/gtest/gtest.h"
#include "url/gurl.h"

namespace glint::candidate {
namespace {
std::optional<DocumentSurfacePolicy> Owned(const url::Origin& origin) {
  const auto key = blink::StorageKey::CreateFirstParty(origin);
  SurfacePolicy policy;
  policy.partition_encoding = *key.SerializeForNativePrivacy();
  policy.canvas.fill(1);
  policy.webgl.fill(2);
  policy.webgpu.fill(3);
  policy.audio.fill(4);
  return DocumentSurfacePolicy{key, policy};
}
const url::Origin kOrigin = url::Origin::Create(GURL("https://initial.test/"));
}  // namespace

TEST(GlintInitialDocumentSurfacePolicyTest, RootWithoutCreatorAcceptsBrowserOrigin) {
  EXPECT_TRUE(CanAdoptInitialDocumentSurfacePolicy(Owned(kOrigin), std::nullopt, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, RootPreservesBrowserOpaqueIdentity) {
  const url::Origin opaque;
  EXPECT_TRUE(CanAdoptInitialDocumentSurfacePolicy(Owned(opaque), std::nullopt, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, PopupAcceptsExactCreatorOrigin) {
  EXPECT_TRUE(CanAdoptInitialDocumentSurfacePolicy(Owned(kOrigin), kOrigin, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, PopupRejectsDifferentCreatorOrigin) {
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(
      Owned(kOrigin), url::Origin::Create(GURL("https://other.test/")), false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, OpaqueCreatorAcceptsExactNonce) {
  const url::Origin opaque;
  EXPECT_TRUE(CanAdoptInitialDocumentSurfacePolicy(Owned(opaque), opaque, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, OpaqueCreatorRejectsDifferentNonce) {
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(Owned(url::Origin()), url::Origin(), false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, SandboxRequiresOpaqueBrowserOrigin) {
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(Owned(kOrigin), kOrigin, true));
}

TEST(GlintInitialDocumentSurfacePolicyTest, SandboxUsesBrowserOpaqueNotCreatorTuple) {
  EXPECT_TRUE(CanAdoptInitialDocumentSurfacePolicy(Owned(url::Origin()), kOrigin, true));
}

TEST(GlintInitialDocumentSurfacePolicyTest, SandboxMissingPayloadIsRejected) {
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(std::nullopt, kOrigin, true));
}

TEST(GlintInitialDocumentSurfacePolicyTest, RootMissingPayloadIsRejected) {
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(std::nullopt, std::nullopt, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, UnsupportedPolicyVersionIsRejected) {
  auto owned = Owned(kOrigin);
  owned->policy.version = 0;
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(owned, kOrigin, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, ReusedSurfaceSeedIsRejected) {
  auto owned = Owned(kOrigin);
  owned->policy.audio = owned->policy.canvas;
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(owned, kOrigin, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, ChangedPartitionCommitmentIsRejected) {
  auto owned = Owned(kOrigin);
  owned->policy.partition_encoding.back() ^= 1;
  EXPECT_FALSE(CanAdoptInitialDocumentSurfacePolicy(owned, kOrigin, false));
}

TEST(GlintInitialDocumentSurfacePolicyTest, FinalDifferentKeyStillRejectsAdoptedPolicy) {
  const auto owned = Owned(kOrigin);
  ASSERT_TRUE(CanAdoptInitialDocumentSurfacePolicy(owned, kOrigin, false));
  EXPECT_FALSE(ValidateDocumentSurfacePolicy(owned,
      blink::StorageKey::CreateFirstParty(url::Origin()), true, false));
}
}  // namespace glint::candidate
