// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "third_party/blink/public/common/native_privacy/document_commit_preflight.h"

#include <string>
#include <vector>

#include "base/unguessable_token.h"
#include "testing/gtest/include/gtest/gtest.h"
#include "url/gurl.h"

namespace blink {
namespace {
class GlintDocumentCommitPreflightTest : public testing::Test {
 protected:
  url::Origin origin_ = url::Origin::Create(GURL("https://canvas.test/"));
  StorageKey key_ = StorageKey::CreateFirstParty(origin_);
  std::vector<uint8_t> seed_ = std::vector<uint8_t>(32, 17);

  std::string Encoding(const StorageKey& key) {
    auto encoding = key.SerializeForNativePrivacy();
    EXPECT_TRUE(encoding);
    return encoding.value();
  }
};

TEST_F(GlintDocumentCommitPreflightTest, AcceptsMatchingBrowserPartition) {
  auto result = PreflightGlintDocumentCanvasCommit(
      1, Encoding(key_), seed_, key_, origin_);
  ASSERT_TRUE(result);
  EXPECT_EQ(std::vector<uint8_t>(result->begin(), result->end()), seed_);
}

TEST_F(GlintDocumentCommitPreflightTest, ReturnsOwnedSeedCopy) {
  auto result = PreflightGlintDocumentCanvasCommit(
      1, Encoding(key_), seed_, key_, origin_);
  ASSERT_TRUE(result);
  seed_.assign(32, 233);
  EXPECT_EQ((*result)[0], 17);
  EXPECT_EQ((*result)[31], 17);
}

TEST_F(GlintDocumentCommitPreflightTest, RejectsUnsupportedVersion) {
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      2, Encoding(key_), seed_, key_, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, RejectsEmptyCommitment) {
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, "", seed_, key_, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, RejectsOversizedCommitment) {
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, std::string(8193, 'a'), seed_, key_, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, RejectsShortSeed) {
  seed_.resize(31);
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, Encoding(key_), seed_, key_, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, RejectsLongSeed) {
  seed_.resize(33);
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, Encoding(key_), seed_, key_, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, RejectsTrailingBinaryCommitment) {
  auto encoding = Encoding(key_);
  encoding.push_back('\0');
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, encoding, seed_, key_, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, ResolvesOpaqueWithoutNonce) {
  const auto provisional = StorageKey::CreateFirstParty(url::Origin());
  EXPECT_TRUE(PreflightGlintDocumentCanvasCommit(
      1, Encoding(key_), seed_, provisional, origin_));
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, Encoding(provisional), seed_, provisional, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, PreservesStorageNonce) {
  const auto nonce = base::UnguessableToken::Create();
  const auto provisional = StorageKey::CreateWithNonce(url::Origin(), nonce);
  const auto final = StorageKey::CreateWithNonce(origin_, nonce);
  EXPECT_TRUE(PreflightGlintDocumentCanvasCommit(
      1, Encoding(final), seed_, provisional, origin_));
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, Encoding(key_), seed_, provisional, origin_));
}

TEST_F(GlintDocumentCommitPreflightTest, RejectsDifferentBrowserOrigin) {
  const auto other = url::Origin::Create(GURL("https://other.test/"));
  EXPECT_FALSE(PreflightGlintDocumentCanvasCommit(
      1, Encoding(key_), seed_, key_, other));
}
}  // namespace
}  // namespace blink
