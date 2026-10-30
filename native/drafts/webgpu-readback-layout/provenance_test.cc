#include "webgpu_readback_provenance.h"

#include <array>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <optional>
#include <utility>
#include <vector>

using namespace glint::candidate;
using Pixel = std::pair<uint64_t, size_t>;
using Oracle = std::vector<std::optional<Pixel>>;
size_t assertions = 0;
size_t cases = 0;
void Check(bool condition, int line) {
  ++assertions;
  if (!condition) {
    std::fprintf(stderr, "Provenance assertion failed at line %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)
#define CASE() ++cases

WebGpuSnapshotToken Token(uint64_t id) { return {7, id, 1, 1}; }

void SetTexture(Oracle& oracle,
                const WebGpuReadbackLayout& layout,
                uint64_t snapshot) {
  for (uint32_t y = 0; y < layout.height; ++y) {
    for (uint32_t x = 0; x < layout.width; ++x) {
      for (size_t channel = 0; channel < 4; ++channel) {
        size_t canonical = channel;
        if (layout.format == WebGpuPixelFormat::kBgra8Unorm && channel % 2 == 0) {
          canonical = 2 - channel;
        }
        const size_t target = static_cast<size_t>(layout.offset) +
                              static_cast<size_t>(y) * layout.row_pitch + x * 4 + channel;
        oracle[target] = Pixel{snapshot, (static_cast<size_t>(y) * layout.width + x) * 4 + canonical};
      }
    }
  }
}

void CheckPlan(const WebGpuReadbackProvenance& tracker,
               const Oracle& oracle,
               size_t begin,
               size_t size) {
  const auto plan = tracker.PlanMap(begin, size);
  bool has_pixel = false;
  for (size_t byte = begin; byte < begin + size; ++byte) {
    std::optional<Pixel> actual;
    for (size_t index = 0; index < plan.count; ++index) {
      const auto coordinate = WebGpuCanonicalByte(plan.regions[index], byte);
      if (coordinate) {
        CHECK(!actual);
        actual = Pixel{plan.regions[index].snapshot.snapshot_id, *coordinate};
      }
    }
    CHECK(actual == oracle[byte]);
    has_pixel |= actual.has_value();
  }
  CHECK(plan.status == (has_pixel ? WebGpuMapProvenance::kReadback
                                 : WebGpuMapProvenance::kUnrelated));
}

int main() {
  constexpr auto rgba = WebGpuPixelFormat::kRgba8Unorm;
  constexpr auto bgra = WebGpuPixelFormat::kBgra8Unorm;
  const WebGpuReadbackLayout layout{8, 256, 3, 3, rgba};
  CASE();
  CHECK(WebGpuReadbackEnd(layout, 532) == 532);
  CHECK(!WebGpuReadbackEnd(layout, 531));
  CHECK(!WebGpuReadbackEnd({}, 1024));
  CHECK(!WebGpuReadbackEnd({std::numeric_limits<uint64_t>::max() - 3, 0, 2, 1, rgba}, 1024));
  CASE();
  WebGpuReadbackProvenance source(1024, 7);
  Oracle expected(1024);
  CheckPlan(source, expected, 0, expected.size());
  CHECK(source.RecordFullTextureCopy(1, layout, Token(1)));
  SetTexture(expected, layout, 1);
  CheckPlan(source, expected, 0, expected.size());
  CheckPlan(source, expected, 20, 240);
  CheckPlan(source, expected, 268, 4);
  CASE();
  CHECK(source.PlanMap(1020, 8).status == WebGpuMapProvenance::kUnreliable);
  CheckPlan(source, expected, 0, expected.size());
  CASE();
  WebGpuReadbackProvenance destination(1024, 7);
  Oracle copied(1024);
  CHECK(destination.RecordBufferCopy(2, 64, source, 8, 524));
  for (size_t i = 0; i < 524; ++i) copied[64 + i] = expected[8 + i];
  CheckPlan(destination, copied, 0, copied.size());
  CheckPlan(source, expected, 0, expected.size());
  CASE();
  CHECK(destination.InvalidateWrite(3, 64, 4));
  for (size_t i = 64; i < 68; ++i) copied[i] = std::nullopt;
  CheckPlan(destination, copied, 0, copied.size());
  CASE();
  WebGpuReadbackProvenance padded(1024, 7);
  Oracle padding_expected(1024);
  CHECK(padded.RecordFullTextureCopy(1, {64, 0, 1, 1, rgba}, Token(2)));
  SetTexture(padding_expected, {64, 0, 1, 1, rgba}, 2);
  CHECK(padded.RecordFullTextureCopy(2, {0, 256, 1, 2, bgra}, Token(3)));
  SetTexture(padding_expected, {0, 256, 1, 2, bgra}, 3);
  CheckPlan(padded, padding_expected, 0, 1024);
  CHECK(padded.PlanMap(64, 4).count == 1);
  CHECK(padded.PlanMap(64, 4).regions[0].snapshot.snapshot_id == 2);
  CASE();
  CHECK(!padded.RecordBufferCopy(3, 768, padded, 0, 260));
  // Destination is intentionally outside the resource, so the tracker is poisoned.
  CHECK(padded.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  CASE();
  WebGpuReadbackProvenance alias(1024, 7);
  CHECK(alias.RecordFullTextureCopy(1, {0, 0, 2, 1, rgba}, Token(4)));
  CHECK(alias.RecordBufferCopy(2, 512, alias, 0, 8));
  CHECK(alias.PlanMap(512, 8).regions[0].snapshot.snapshot_id == 4);
  CHECK(!alias.RecordBufferCopy(3, 4, alias, 0, 8));
  CHECK(alias.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  CASE();
  WebGpuReadbackProvenance unordered(1024, 7);
  CHECK(unordered.RecordFullTextureCopy(8, layout, Token(1)));
  CHECK(!unordered.InvalidateWrite(7, 0, 4));
  CHECK(!unordered.RecordFullTextureCopy(9, layout, Token(1)));
  CHECK(unordered.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  CASE();
  for (WebGpuSnapshotToken token : {WebGpuSnapshotToken{8, 1, 1, 1},
                                    WebGpuSnapshotToken{7, 0, 1, 1},
                                    WebGpuSnapshotToken{7, 1, 0, 1},
                                    WebGpuSnapshotToken{7, 1, 1, 0}}) {
    WebGpuReadbackProvenance tracker(1024, 7);
    CHECK(!tracker.RecordFullTextureCopy(1, layout, token));
    CHECK(tracker.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  }
  CASE();
  WebGpuReadbackProvenance foreign(1024, 8);
  CHECK(!foreign.RecordBufferCopy(10, 0, source, 0, 512));
  CHECK(foreign.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  CASE();
  WebGpuReadbackProvenance future(1024, 7);
  CHECK(!future.RecordBufferCopy(1, 0, source, 0, 512));
  CHECK(future.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  CASE();
  WebGpuReadbackProvenance limited(1024, 7);
  for (size_t i = 0; i < kWebGpuReadbackRegionLimit; ++i) {
    CHECK(limited.RecordFullTextureCopy(i + 1, {i * 4, 0, 1, 1, rgba}, Token(i + 1)));
  }
  CHECK(limited.PlanMap(0, 1024).count == kWebGpuReadbackRegionLimit);
  CHECK(!limited.RecordFullTextureCopy(17, {64, 0, 1, 1, rgba}, Token(17)));
  CHECK(limited.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  CHECK(!limited.InvalidateWrite(18, 0, 1024));
  CASE();
  auto independent_plan = source.PlanMap(0, 1024);
  independent_plan.regions[0].snapshot.snapshot_id = 999;
  CheckPlan(source, expected, 0, 1024);
  CASE();
  WebGpuReadbackProvenance empty(1024, 7);
  CHECK(empty.RecordFullTextureCopy(1, {0, 0, 0, 1, rgba}, {}));
  CHECK(empty.RecordBufferCopy(2, 1024, empty, 1024, 0));
  CHECK(empty.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnrelated);
  empty.Destroy();
  empty.Destroy();
  CHECK(!empty.InvalidateWrite(3, 0, 4));
  CHECK(empty.PlanMap(0, 1024).status == WebGpuMapProvenance::kDestroyed);
  CASE();
  WebGpuReadbackProvenance zero_epoch(1024, 0);
  CHECK(zero_epoch.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  CASE();
  WebGpuReadbackProvenance cropped(1024, 7);
  Oracle crop_expected(1024);
  CHECK(cropped.RecordTextureCopy(1, {8, 256, 3, 2, bgra}, Token(10), {2, 3, 10, 8}));
  for (size_t y = 0; y < 2; ++y) for (size_t x = 0; x < 3; ++x) {
    for (size_t channel = 0; channel < 4; ++channel) {
      const size_t canonical = channel % 2 == 0 ? 2 - channel : channel;
      crop_expected[8 + y * 256 + x * 4 + channel] = Pixel{10, ((y + 3) * 10 + x + 2) * 4 + canonical};
    }
  }
  CheckPlan(cropped, crop_expected, 0, 1024);
  CASE();
  WebGpuReadbackProvenance bad_rectangle(1024, 7);
  CHECK(!bad_rectangle.RecordTextureCopy(1, {0, 256, 3, 2, rgba}, Token(11), {8, 3, 10, 8}));
  CHECK(bad_rectangle.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);

  uint64_t serial = 100;
  for (uint32_t iteration = 0; iteration < 256; ++iteration) {
    std::array<WebGpuReadbackProvenance, 3> trackers = {
        WebGpuReadbackProvenance(1024, 7), WebGpuReadbackProvenance(1024, 7),
        WebGpuReadbackProvenance(1024, 7)};
    std::array<Oracle, 3> oracle = {Oracle(1024), Oracle(1024), Oracle(1024)};
    const WebGpuReadbackLayout selected{(iteration % 8) * 4, 256,
        iteration % 7 + 1, iteration % 3 + 1, iteration % 2 == 0 ? rgba : bgra};
    CHECK(trackers[0].RecordFullTextureCopy(++serial, selected, Token(iteration + 10)));
    SetTexture(oracle[0], selected, iteration + 10);
    CHECK(trackers[1].RecordBufferCopy(++serial, 16, trackers[0], 0, 768));
    for (size_t i = 0; i < 768; ++i) oracle[1][16 + i] = oracle[0][i];
    const size_t dirty = 16 + static_cast<size_t>(selected.offset) + (iteration % selected.width) * 4;
    CHECK(trackers[1].InvalidateWrite(++serial, dirty, 4));
    for (size_t i = dirty; i < dirty + 4; ++i) oracle[1][i] = std::nullopt;
    CHECK(trackers[2].RecordBufferCopy(++serial, 0, trackers[1], 16, 768));
    for (size_t i = 0; i < 768; ++i) oracle[2][i] = oracle[1][16 + i];
    for (size_t index = 0; index < 3; ++index) {
      CheckPlan(trackers[index], oracle[index], 0, 1024);
      CheckPlan(trackers[index], oracle[index], 12, 513);
    }
  }
  std::printf("{\"passed\":true,\"named_cases\":%zu,\"property_iterations\":256,\"assertions\":%zu,\"browser_integrated\":false}\n", cases, assertions);
}
