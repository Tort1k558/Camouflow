// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "glint_readback_metadata.h"

#include <GLES3/gl3.h>

#include <vector>

#include "testing/gtest/include/gtest/gtest.h"

namespace gpu::gles2 {
namespace {
TEST(GlintReadbackMetadataTest, ByteColourRoundTripPreservesNativeDimensions) {
  const auto wire = EncodeGlintReadbackMetadata(8192, 4096, GL_RGBA8, 0, true);
  const auto metadata = DecodeGlintReadbackMetadata(wire);
  ASSERT_TRUE(metadata.has_value());
  EXPECT_EQ(metadata->width, 8192);
  EXPECT_EQ(metadata->height, 4096);
  EXPECT_EQ(metadata->internal_format, GL_RGBA8);
  EXPECT_EQ(metadata->samples, 0);
  EXPECT_TRUE(metadata->rgba8_compatible);
}

TEST(GlintReadbackMetadataTest,
     NonByteAndMultisampleInformationIsNotFabricated) {
  const auto metadata = DecodeGlintReadbackMetadata(
      EncodeGlintReadbackMetadata(16, 8, GL_RGBA16F, 4, false));
  ASSERT_TRUE(metadata.has_value());
  EXPECT_EQ(metadata->internal_format, GL_RGBA16F);
  EXPECT_EQ(metadata->samples, 4);
  EXPECT_FALSE(metadata->rgba8_compatible);
}

TEST(GlintReadbackMetadataTest, UnavailableCannotBecomeReady) {
  EXPECT_FALSE(DecodeGlintReadbackMetadata(kGlintReadbackMetadataUnavailable));
}

TEST(GlintReadbackMetadataTest, TruncatedWireNeverReadsMissingFields) {
  const auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
  for (size_t length = 0; length < wire.size(); ++length) {
    EXPECT_FALSE(DecodeGlintReadbackMetadata(std::span(wire).first(length)));
  }
}

TEST(GlintReadbackMetadataTest, ExtraFieldsAreNotSilentlyAccepted) {
  const auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
  std::vector<GLint> extended(wire.begin(), wire.end());
  extended.push_back(0);
  EXPECT_FALSE(DecodeGlintReadbackMetadata(extended));
}

TEST(GlintReadbackMetadataTest, SchemaIsExact) {
  for (GLint version : {-1, 0, 2}) {
    auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
    wire[0] = version;
    EXPECT_FALSE(DecodeGlintReadbackMetadata(wire));
  }
}

TEST(GlintReadbackMetadataTest, ReadyStatusIsExact) {
  for (GLint status : {-1, 0, 2}) {
    auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
    wire[1] = status;
    EXPECT_FALSE(DecodeGlintReadbackMetadata(wire));
  }
}

TEST(GlintReadbackMetadataTest, DimensionsMustBePositive) {
  for (size_t field : {2u, 3u}) {
    for (GLint dimension : {-1, 0}) {
      auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
      wire[field] = dimension;
      EXPECT_FALSE(DecodeGlintReadbackMetadata(wire));
    }
  }
}

TEST(GlintReadbackMetadataTest, InvalidFormatIsNotGuessed) {
  for (GLint format : {-1, 0}) {
    auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
    wire[4] = format;
    EXPECT_FALSE(DecodeGlintReadbackMetadata(wire));
  }
}

TEST(GlintReadbackMetadataTest, NegativeSamplesAreRejected) {
  auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
  wire[5] = -1;
  EXPECT_FALSE(DecodeGlintReadbackMetadata(wire));
}

TEST(GlintReadbackMetadataTest, ByteColourClassificationIsAnExactBoolean) {
  for (GLint classification : {-1, 2}) {
    auto wire = EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, 0, true);
    wire[6] = classification;
    EXPECT_FALSE(DecodeGlintReadbackMetadata(wire));
  }
}

TEST(GlintReadbackMetadataTest,
     ByteColourClaimCannotPromoteFloatIntegerOrUnknownFormat) {
  for (GLenum format : {GL_RGBA16F, GL_RGBA8UI, GL_RED, GL_RGBA4, 0x7fffffff}) {
    auto wire = EncodeGlintReadbackMetadata(8, 8, format, 0, false);
    ASSERT_TRUE(DecodeGlintReadbackMetadata(wire));
    wire[6] = 1;
    EXPECT_FALSE(DecodeGlintReadbackMetadata(wire));
    EXPECT_EQ(EncodeGlintReadbackMetadata(8, 8, format, 0, true),
              kGlintReadbackMetadataUnavailable);
  }
}

TEST(GlintReadbackMetadataTest,
     ByteColourEligibilityPreservesAllSupportedFormats) {
  for (GLenum format : {GL_RGB, GL_RGBA, GL_RGB8, GL_RGBA8}) {
    for (bool compatible : {false, true}) {
      const auto metadata = DecodeGlintReadbackMetadata(
          EncodeGlintReadbackMetadata(8, 8, format, 4, compatible));
      ASSERT_TRUE(metadata);
      EXPECT_EQ(metadata->internal_format, format);
      EXPECT_EQ(metadata->samples, 4);
      EXPECT_EQ(metadata->rgba8_compatible, compatible);
    }
  }
}

TEST(GlintReadbackMetadataTest, ProducerRejectsInvalidRepresentations) {
  EXPECT_EQ(EncodeGlintReadbackMetadata(0, 8, GL_RGBA8, 0, true),
            kGlintReadbackMetadataUnavailable);
  EXPECT_EQ(EncodeGlintReadbackMetadata(8, -1, GL_RGBA8, 0, true),
            kGlintReadbackMetadataUnavailable);
  EXPECT_EQ(EncodeGlintReadbackMetadata(8, 8, 0, 0, true),
            kGlintReadbackMetadataUnavailable);
  EXPECT_EQ(EncodeGlintReadbackMetadata(
                8, 8, std::numeric_limits<GLenum>::max(), 0, true),
            kGlintReadbackMetadataUnavailable);
  EXPECT_EQ(EncodeGlintReadbackMetadata(8, 8, GL_RGBA8, -1, true),
            kGlintReadbackMetadataUnavailable);
}
}  // namespace
}  // namespace gpu::gles2
