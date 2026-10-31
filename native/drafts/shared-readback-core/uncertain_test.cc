// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "webgpu_readback_provenance.h"

#include <cstdio>
#include <cstdlib>
#include <limits>

using namespace glint::candidate;
namespace {
size_t assertions = 0;
size_t range_cases = 0;
void Check(bool value, int line) {
  ++assertions;
  if (!value) {
    std::fprintf(stderr, "Uncertain-write assertion at line %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)
WebGpuSnapshotToken Token(uint64_t id = 1) { return {7, id, 1, 1}; }

bool PixelInRange(const WebGpuReadbackLayout& layout, uint64_t offset, uint64_t size) {
  for (uint64_t byte = offset; byte < offset + size; ++byte) {
    for (uint32_t row = 0; row < layout.height; ++row) {
      const uint64_t start = layout.offset + static_cast<uint64_t>(row) * layout.row_pitch;
      if (byte >= start && byte - start < static_cast<uint64_t>(layout.width) * 4) {
        return true;
      }
    }
  }
  return false;
}

void CheckRange(const WebGpuReadbackLayout& layout, size_t bytes,
                uint64_t offset, uint64_t size) {
  ++range_cases;
  WebGpuReadbackProvenance tracker(bytes, 7);
  CHECK(tracker.RecordFullTextureCopy(1, layout, Token()));
  const bool uncertain_pixels = PixelInRange(layout, offset, size);
  CHECK(tracker.RecordUncertainWrite(2, offset, size) == !uncertain_pixels);
  const auto plan = tracker.PlanMap(0, bytes);
  CHECK(plan.status == (uncertain_pixels ? WebGpuMapProvenance::kUnreliable
                                        : WebGpuMapProvenance::kReadback));
  CHECK(plan.count == (uncertain_pixels ? 0u : 1u));
  if (uncertain_pixels) {
    CHECK(!tracker.InvalidateWrite(3, 0, bytes));
    CHECK(tracker.PlanMap(0, bytes).status == WebGpuMapProvenance::kUnreliable);
  } else {
    CHECK(tracker.InvalidateWrite(3, 0, bytes));
    CHECK(tracker.PlanMap(0, bytes).status == WebGpuMapProvenance::kUnrelated);
  }
}

void RangeOracle() {
  for (auto format : {WebGpuPixelFormat::kRgba8Unorm, WebGpuPixelFormat::kBgra8Unorm}) {
    const WebGpuReadbackLayout single{8, 0, 16, 1, format};
    for (uint64_t offset = 0; offset <= 96; ++offset) {
      for (uint64_t size = 0; size <= 96 - offset; ++size) {
        CheckRange(single, 96, offset, size);
      }
    }
    const WebGpuReadbackLayout padded{8, 256, 5, 3, format};
    for (uint64_t offset = 0; offset <= 576; ++offset) {
      for (uint64_t size = 0; size <= 576 - offset; size += 17) {
        CheckRange(padded, 576, offset, size);
      }
      CheckRange(padded, 576, offset, 576 - offset);
      if (offset < 576) CheckRange(padded, 576, offset, 1);
    }
  }
}

void NoUnrelatedTaint() {
  WebGpuReadbackProvenance tracker(576, 7);
  CHECK(tracker.RecordUncertainWrite(1, 0, 576));
  CHECK(tracker.PlanMap(0, 576).status == WebGpuMapProvenance::kUnrelated);
  CHECK(tracker.RecordFullTextureCopy(2, {8, 256, 5, 3}, Token()));
  CHECK(tracker.RecordUncertainWrite(3, 0, 8));
  CHECK(tracker.RecordUncertainWrite(4, 28, 236));
  CHECK(tracker.RecordUncertainWrite(5, 540, 36));
  CHECK(tracker.RecordUncertainWrite(6, 8, 0));
  CHECK(tracker.PlanMap(0, 576).status == WebGpuMapProvenance::kReadback);
}

void UnknownCannotBecomeRawThroughCopy() {
  WebGpuReadbackProvenance source(576, 7), destination(576, 7);
  CHECK(source.RecordFullTextureCopy(1, {8, 256, 5, 3}, Token()));
  CHECK(!source.RecordUncertainWrite(2, 8, 4));
  CHECK(!destination.RecordBufferCopy(3, 0, source, 0, 576));
  CHECK(destination.PlanMap(0, 576).status == WebGpuMapProvenance::kUnreliable);
  CHECK(!source.RecordFullTextureCopy(4, {8, 256, 5, 3}, Token(2)));
  CHECK(source.PlanMap(0, 576).status == WebGpuMapProvenance::kUnreliable);
}

void FailedInputsAndDestruction() {
  for (auto sequence : {0ull, 1ull}) {
    WebGpuReadbackProvenance tracker(576, 7);
    CHECK(tracker.RecordFullTextureCopy(1, {8, 256, 5, 3}, Token()));
    CHECK(!tracker.RecordUncertainWrite(sequence, 0, 0));
    CHECK(tracker.PlanMap(0, 576).status == WebGpuMapProvenance::kUnreliable);
  }
  for (auto offset : {577ull, std::numeric_limits<uint64_t>::max()}) {
    WebGpuReadbackProvenance tracker(576, 7);
    CHECK(!tracker.RecordUncertainWrite(1, offset, 0));
    CHECK(tracker.PlanMap(0, 1).status == WebGpuMapProvenance::kUnreliable);
    tracker.Destroy();
    CHECK(!tracker.RecordUncertainWrite(2, 0, 0));
    CHECK(tracker.PlanMap(0, 1).status == WebGpuMapProvenance::kDestroyed);
  }
  WebGpuReadbackProvenance tracker(576, 7);
  CHECK(!tracker.RecordUncertainWrite(1, 1, std::numeric_limits<uint64_t>::max()));
  CHECK(tracker.PlanMap(0, 1).status == WebGpuMapProvenance::kUnreliable);
}
}  // namespace

int main() {
  RangeOracle();
  NoUnrelatedTaint();
  UnknownCannotBecomeRawThroughCopy();
  FailedInputsAndDestruction();
  std::printf("{\"passed\":true,\"range_cases\":%zu,\"assertions\":%zu,"
              "\"browser_integrated\":false}\n", range_cases, assertions);
}
