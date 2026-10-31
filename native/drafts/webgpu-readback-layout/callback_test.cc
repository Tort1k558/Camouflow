#include "webgpu_readback_snapshot.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <vector>

using namespace glint::candidate;
size_t assertions = 0, named_cases = 0, completion_orders = 0;
void Check(bool condition, int line) {
  ++assertions;
  if (!condition) {
    std::fprintf(stderr, "Callback assertion failed at line %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)
#define CASE() ++named_cases

WebGpuSnapshotToken Token(uint64_t id) { return {7, id, 1, 1}; }

int main() {
  constexpr auto rgba = WebGpuPixelFormat::kRgba8Unorm;
  const WebGpuReadbackLayout full{0, 256, 8, 8, rgba};
  constexpr size_t pixels = 8 * 8 * 4;
  std::array<uint8_t, 32> seed{};
  seed[0] = 91;
  std::array<std::vector<uint8_t>, 3> raw;
  for (size_t index = 0; index < raw.size(); ++index) {
    raw[index].resize(2048, 0xa5);
    std::vector<uint8_t> packed(pixels);
    for (size_t byte = 0; byte < packed.size(); ++byte) {
      packed[byte] = byte % 4 == 3 ? 255 : static_cast<uint8_t>((byte * 17 + index * 31) % 256);
    }
    CHECK(StoreWebGpuRgba8(packed, full, 0, raw[index]));
  }
  std::array<size_t, 3> order = {0, 1, 2};
  do {
    ++completion_orders;
    WebGpuReadbackSnapshots cache(7, 1, pixels * 6, 65536);
    for (size_t index = 0; index < order.size(); ++index) {
      CHECK(cache.BeginCapture(Token(index + 1), full));
    }
    CHECK(cache.pending_count() == 3 && cache.retained_bytes() == 0);
    CHECK(cache.reserved_bytes() == pixels * 6);
    for (size_t position = 0; position < order.size(); ++position) {
      const size_t index = order[position];
      CHECK(cache.CompleteCapture(Token(index + 1), full, 0, raw[index], seed));
      CHECK(cache.pending_count() == order.size() - position - 1);
      CHECK(cache.retained_bytes() == (position + 1) * pixels * 2);
      CHECK(!cache.CompleteCapture(Token(index + 1), full, 0, raw[index], seed));
      WebGpuReadbackProvenance tracker(raw[index].size(), 7);
      CHECK(tracker.RecordFullTextureCopy(1, full, Token(index + 1)));
      CHECK(cache.BuildProtectedShadow(tracker.PlanMap(0, raw[index].size()), 0, raw[index]).has_value());
    }
  } while (std::next_permutation(order.begin(), order.end()));
  CASE();
  WebGpuReadbackSnapshots pending(7, 1, pixels * 4, 65536);
  CHECK(pending.BeginCapture(Token(1), full));
  WebGpuReadbackProvenance tracker(raw[0].size(), 7);
  CHECK(tracker.RecordFullTextureCopy(1, full, Token(1)));
  CHECK(!pending.BuildProtectedShadow(tracker.PlanMap(0, raw[0].size()), 0, raw[0]));
  CASE();
  CHECK(pending.Release(Token(1)));
  CHECK(pending.pending_count() == 0 && pending.reserved_bytes() == 0);
  CHECK(!pending.CompleteCapture(Token(1), full, 0, raw[0], seed));
  CHECK(!pending.BeginCapture(Token(1), full));
  CASE();
  CHECK(pending.BeginCapture(Token(2), full));
  CHECK(!pending.CompleteCapture(Token(1), full, 0, raw[0], seed));
  CHECK(pending.pending_count() == 1 && pending.reserved_bytes() == pixels * 2);
  CHECK(pending.CompleteCapture(Token(2), full, 0, raw[1], seed));
  CASE();
  CHECK(pending.BeginCapture(Token(3), full));
  auto wrong_layout = full;
  wrong_layout.offset = 4;
  CHECK(!pending.CompleteCapture(Token(3), wrong_layout, 0, raw[0], seed));
  CHECK(pending.pending_count() == 0 && pending.reserved_bytes() == pixels * 2);
  CHECK(!pending.CompleteCapture(Token(3), full, 0, raw[0], seed));
  CASE();
  CHECK(pending.BeginCapture(Token(4), full));
  CHECK(!pending.CompleteCapture(Token(4), full, 0, std::span<const uint8_t>(raw[0]).first(16), seed));
  CHECK(pending.pending_count() == 0 && pending.reserved_bytes() == pixels * 2);
  CASE();
  WebGpuReadbackSnapshots budget(7, 1, pixels * 2, 65536);
  CHECK(budget.BeginCapture(Token(1), full));
  CHECK(!budget.BeginCapture(Token(2), full));
  CHECK(budget.retained_bytes() == 0 && budget.reserved_bytes() == pixels * 2);
  CHECK(budget.Release(Token(1)));
  CHECK(budget.BeginCapture(Token(2), full));
  CASE();
  WebGpuReadbackSnapshots foreign(7, 1, pixels * 2, 65536);
  CHECK(foreign.BeginCapture(Token(1), full));
  CHECK(!foreign.CompleteCapture({8, 1, 1, 1}, full, 0, raw[0], seed));
  CHECK(!foreign.CompleteCapture({7, 1, 2, 1}, full, 0, raw[0], seed));
  CHECK(!foreign.CompleteCapture({7, 1, 1, 2}, full, 0, raw[0], seed));
  CHECK(foreign.pending_count() == 1);
  CHECK(foreign.CompleteCapture(Token(1), full, 0, raw[0], seed));
  CASE();
  WebGpuReadbackSnapshots dead(7, 1, pixels * 4, 65536);
  CHECK(dead.BeginCapture(Token(1), full));
  CHECK(dead.Capture(Token(2), full, 0, raw[1], seed));
  CHECK(dead.pending_count() == 1 && dead.retained_bytes() == pixels * 2);
  dead.Destroy();
  CHECK(dead.pending_count() == 0 && dead.retained_bytes() == 0 && dead.reserved_bytes() == 0);
  CHECK(!dead.CompleteCapture(Token(1), full, 0, raw[0], seed));
  CHECK(!dead.BeginCapture(Token(3), full));
  CASE();
  WebGpuReadbackSnapshots retry(7, 1, pixels * 2, 65536);
  CHECK(retry.BeginCapture(Token(1), full));
  CHECK(!retry.CompleteCapture(Token(1), full, 0, {}, seed));
  CHECK(!retry.BeginCapture(Token(1), full));
  CHECK(retry.BeginCapture(Token(2), full));
  CASE();
  WebGpuReadbackSnapshots capacity(7, 1, pixels * 2 * kWebGpuReadbackRegionLimit, 65536);
  for (size_t index = 0; index < kWebGpuReadbackRegionLimit; ++index) {
    CHECK(capacity.BeginCapture(Token(index + 1), full));
  }
  CHECK(!capacity.BeginCapture(Token(17), full));
  CHECK(capacity.Release(Token(8)));
  CHECK(capacity.BeginCapture(Token(17), full));
  CHECK(!capacity.CompleteCapture(Token(8), full, 0, raw[0], seed));
  CHECK(capacity.CompleteCapture(Token(17), full, 0, raw[2], seed));
  std::printf("{\"passed\":true,\"named_cases\":%zu,\"completion_orders\":%zu,\"assertions\":%zu,\"browser_integrated\":false}\n",
      named_cases, completion_orders, assertions);
}
