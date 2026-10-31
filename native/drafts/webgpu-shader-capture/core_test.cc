#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "gpu/command_buffer/common/glint/webgpu_readback_snapshot.h"

using namespace glint::candidate;
size_t assertions = 0;
void Check(bool value, int line) {
  ++assertions;
  if (!value) { std::fprintf(stderr, "captured-byte assertion %d\n", line); std::exit(1); }
}
#define CHECK(x) Check((x), __LINE__)
int main() {
  WebGpuReadbackSnapshots snapshots(7, 3, 128, 512);
  const WebGpuSnapshotToken token{7, 1, 1, 3};
  std::vector<uint8_t> bytes(32);
  for (size_t i = 0; i < bytes.size(); ++i) bytes[i] = static_cast<uint8_t>(i + 41);
  const auto captured = bytes;
  CHECK(snapshots.BeginByteCapture(token, bytes.size()));
  CHECK(snapshots.pending_count() == 1 && snapshots.reserved_bytes() == 32 && snapshots.retained_bytes() == 0);
  WebGpuReadbackProvenance source(64, 7);
  CHECK(source.RecordCapturedByteCopy(1, 8, 32, token));
  std::vector<uint8_t> mapped(64, 7);
  std::copy(bytes.begin(), bytes.end(), mapped.begin() + 8);
  auto plan = source.PlanMap(0, 64);
  CHECK(plan.status == WebGpuMapProvenance::kReadback && plan.count == 1);
  CHECK(!snapshots.BuildProtectedShadow(plan, 0, mapped));
  auto bad_token = token; ++bad_token.policy_generation;
  CHECK(!snapshots.CompleteByteCapture(bad_token, bytes));
  CHECK(snapshots.pending_count() == 1 && snapshots.reserved_bytes() == 32);
  CHECK(snapshots.CompleteByteCapture(token, bytes));
  CHECK(!snapshots.CompleteByteCapture(token, bytes));
  CHECK(snapshots.pending_count() == 0 && snapshots.retained_bytes() == 32);
  bytes.assign(32, 231);
  auto shadow = snapshots.BuildProtectedShadow(plan, 0, mapped);
  CHECK(shadow && shadow->size == mapped.size());
  CHECK(std::equal(mapped.begin(), mapped.end(), shadow->bytes.get()));
  mapped[8] ^= 1;
  CHECK(shadow->bytes[8] == captured[0]);
  CHECK(!snapshots.BuildProtectedShadow(plan, 0, mapped));
  mapped[8] ^= 1;
  auto clipped = source.PlanMap(12, 16);
  CHECK(clipped.count == 1 && clipped.regions[0].snapshot_offset == 4);
  CHECK(snapshots.BuildProtectedShadow(clipped, 12, std::span(mapped).subspan(12, 16)).has_value());
  auto forged = plan; forged.count = 2; forged.regions[1] = forged.regions[0];
  CHECK(!snapshots.BuildProtectedShadow(forged, 0, mapped));
  forged = plan; forged.regions[0].kind = WebGpuReadbackRegionKind::kPixels;
  CHECK(!snapshots.BuildProtectedShadow(forged, 0, mapped));
  forged = plan; forged.regions[0].kind = WebGpuReadbackRegionKind::kShaderDerived;
  CHECK(!snapshots.BuildProtectedShadow(forged, 0, mapped));
  forged = plan; forged.regions[0].snapshot.snapshot_id = 999;
  CHECK(!snapshots.BuildProtectedShadow(forged, 0, mapped));
  forged = plan; forged.regions[0].snapshot_offset = UINT64_MAX;
  CHECK(!snapshots.BuildProtectedShadow(forged, 0, mapped));
  WebGpuReadbackProvenance copy(64, 7);
  CHECK(copy.RecordBufferCopy(2, 32, source, 16, 16));
  const auto copied_plan = copy.PlanMap(32, 16);
  CHECK(copied_plan.count == 1 && copied_plan.regions[0].snapshot_offset == 8);
  CHECK(snapshots.BuildProtectedShadow(copied_plan, 32, std::span(captured).subspan(8, 16)).has_value());
  WebGpuReadbackProvenance wrong_epoch(64, 8);
  CHECK(!wrong_epoch.RecordBufferCopy(2, 32, source, 16, 16));
  WebGpuReadbackSnapshots other_policy(7, 4, 128, 512);
  CHECK(!other_policy.BeginByteCapture(token, 32));
  CHECK(!other_policy.BuildProtectedShadow(plan, 0, mapped));
  auto uncertain = source;
  CHECK(!uncertain.RecordUncertainWrite(2, 16, 4));
  CHECK(uncertain.PlanMap(0, 64).status == WebGpuMapProvenance::kUnreliable);
  CHECK(source.InvalidateWrite(3, 16, 8));
  std::fill(mapped.begin() + 16, mapped.begin() + 24, uint8_t{99});
  CHECK(source.PlanMap(16, 8).status == WebGpuMapProvenance::kUnrelated);
  CHECK(snapshots.BuildProtectedShadow(source.PlanMap(0, 64), 0, mapped).has_value());
  const WebGpuReadbackLayout pixel_layout{0, 0, 1, 1, WebGpuPixelFormat::kRgba8Unorm};
  const WebGpuSnapshotToken pixel_token{7, 2, 4, 3};
  std::array<uint8_t, 4> pixel{11, 22, 33, 255};
  std::array<uint8_t, 32> seed{};
  CHECK(snapshots.Capture(pixel_token, pixel_layout, 0, pixel, seed));
  CHECK(snapshots.reserved_bytes() == 40 && snapshots.retained_bytes() == 40);
  WebGpuReadbackProvenance pixel_provenance(4, 7);
  CHECK(pixel_provenance.RecordFullTextureCopy(4, pixel_layout, pixel_token));
  auto pixel_plan = pixel_provenance.PlanMap(0, 4);
  CHECK(snapshots.BuildProtectedShadow(pixel_plan, 0, pixel).has_value());
  pixel_plan.regions[0].kind = WebGpuReadbackRegionKind::kCapturedBytes;
  CHECK(!snapshots.BuildProtectedShadow(pixel_plan, 0, pixel));
  CHECK(snapshots.Release(token));
  CHECK(snapshots.reserved_bytes() == 8 && snapshots.retained_bytes() == 8);
  CHECK(!snapshots.BuildProtectedShadow(plan, 0, mapped));
  CHECK(snapshots.Release(pixel_token));
  CHECK(snapshots.reserved_bytes() == 0 && snapshots.retained_bytes() == 0);
  CHECK(!snapshots.Release(token));
  WebGpuReadbackSnapshots bounded(7, 3, 64, 128);
  CHECK(!bounded.BeginByteCapture(token, 65));
  CHECK(!bounded.BeginByteCapture(token, 0));
  CHECK(bounded.BeginByteCapture(token, 32));
  CHECK(!bounded.CompleteByteCapture(token, pixel));
  CHECK(bounded.pending_count() == 0 && bounded.reserved_bytes() == 0);
  CHECK(!bounded.BeginByteCapture(token, 32));
  auto next_token = token; ++next_token.snapshot_id;
  CHECK(bounded.BeginByteCapture(next_token, 32));
  bounded.Destroy();
  CHECK(bounded.reserved_bytes() == 0 && !bounded.CompleteByteCapture(next_token, captured));
  WebGpuReadbackSnapshots slots(7, 3, 64, 128);
  for (uint64_t id = 1; id <= kWebGpuReadbackRegionLimit; ++id)
    CHECK(slots.BeginByteCapture({7, id, id, 3}, 1));
  CHECK(!slots.BeginByteCapture({7, 17, 17, 3}, 1));
  CHECK(slots.Release({7, 1, 1, 3}));
  CHECK(slots.BeginByteCapture({7, 17, 17, 3}, 1));

  for (size_t sample = 0; sample < 1000; ++sample) {
    WebGpuReadbackSnapshots store(7, 3, 256, 512);
    WebGpuReadbackProvenance provenance(128, 7);
    const size_t offset = sample % 64, length = 1 + sample % 64;
    std::vector<uint8_t> captured_bytes(length);
    for (size_t i = 0; i < length; ++i) captured_bytes[i] = static_cast<uint8_t>(sample + i);
    CHECK(store.BeginByteCapture(token, length));
    CHECK(store.CompleteByteCapture(token, captured_bytes));
    CHECK(provenance.RecordCapturedByteCopy(1, offset, length, token));
    std::vector<uint8_t> data(128, 7);
    std::copy(captured_bytes.begin(), captured_bytes.end(), data.begin() + offset);
    const size_t begin = (sample * 7) % 129, count = (sample * 11) % (129 - begin);
    auto range = provenance.PlanMap(begin, count);
    const bool intersects = count != 0 && begin < offset + length && offset < begin + count;
    CHECK(range.status == (intersects ? WebGpuMapProvenance::kReadback : WebGpuMapProvenance::kUnrelated));
    if (intersects) {
      auto result = store.BuildProtectedShadow(range, begin, std::span(data).subspan(begin, count));
      CHECK(result && std::equal(data.begin() + begin, data.begin() + begin + count, result->bytes.get()));
      const size_t changed = std::max(begin, offset);
      data[changed] ^= 1;
      CHECK(!store.BuildProtectedShadow(range, begin, std::span(data).subspan(begin, count)));
    }
  }
  std::printf("{\"passed\":true,\"assertions\":%zu,\"oracle_cases\":1000,"
              "\"native_controller_eligibility_executed\":false,\"runtime_verified\":false}\n", assertions);
}
