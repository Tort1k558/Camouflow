#include "webgpu_readback_snapshot.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "third_party/blink/renderer/core/html/canvas/glint/canvas_readback_candidate.h"

using namespace glint::candidate;
size_t assertions = 0;
size_t cases = 0;
void Check(bool condition, int line) {
  ++assertions;
  if (!condition) {
    std::fprintf(stderr, "Snapshot assertion failed at line %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)
#define CASE() ++cases

WebGpuSnapshotToken Token(uint64_t id) { return {7, id, 1, 1}; }

int main() {
  constexpr size_t width = 16, height = 16, pixels = width * height * 4;
  std::vector<uint8_t> original(pixels);
  for (size_t y = 0; y < height; ++y) for (size_t x = 0; x < width; ++x) {
    const size_t offset = (y * width + x) * 4;
    original[offset] = static_cast<uint8_t>((x * 17) % 256);
    original[offset + 1] = static_cast<uint8_t>((y * 29 + 31) % 256);
    original[offset + 2] = static_cast<uint8_t>((x * 43 + y * 11) % 256);
    original[offset + 3] = 255;
  }
  std::array<uint8_t, 32> seed{};
  for (size_t index = 0; index < seed.size(); ++index) seed[index] = static_cast<uint8_t>(index + 1);
  for (auto format : {WebGpuPixelFormat::kRgba8Unorm, WebGpuPixelFormat::kBgra8Unorm}) {
    const WebGpuReadbackLayout full{8, 256, width, height, format};
    std::vector<uint8_t> raw(4096, 0xa5);
    CHECK(StoreWebGpuRgba8(original, full, 0, raw));
    const auto raw_before = raw;
    auto protected_pixels = original;
    CHECK(TransformEdgeCoherentCanvas(protected_pixels, width, height, seed));
    CHECK(protected_pixels != original);
    auto expected = raw;
    CHECK(StoreWebGpuRgba8(protected_pixels, full, 0, expected));
    WebGpuReadbackSnapshots cache(7, 1, 65536, 65536);
    CASE();
    CHECK(cache.Capture(Token(1), full, 0, raw, seed));
    CHECK(cache.retained_bytes() == pixels * 2);
    CHECK(raw == raw_before);
    WebGpuReadbackProvenance tracker(raw.size(), 7);
    CHECK(tracker.RecordFullTextureCopy(1, full, Token(1)));
    auto plan = tracker.PlanMap(0, raw.size());
    auto shadow = cache.BuildProtectedShadow(plan, 0, raw);
    CHECK(shadow.has_value());
    CHECK(shadow->size == expected.size());
    CHECK(std::equal(expected.begin(), expected.end(), shadow->bytes.get()));
    CHECK(raw == raw_before);
    CASE();
    const size_t partial_offset = 8 + 2 * 256 + 8;
    auto partial_raw = std::span<const uint8_t>(raw).subspan(partial_offset, 12);
    auto partial = cache.BuildProtectedShadow(tracker.PlanMap(partial_offset, 12), partial_offset, partial_raw);
    CHECK(partial.has_value());
    CHECK(std::equal(expected.begin() + partial_offset, expected.begin() + partial_offset + 12, partial->bytes.get()));
    CASE();
    WebGpuReadbackProvenance destination(1024, 7);
    CHECK(destination.RecordBufferCopy(2, 64, tracker, 512, 512));
    std::vector<uint8_t> copied(1024, 0x5a), copied_expected = copied;
    std::copy_n(raw.begin() + 512, 512, copied.begin() + 64);
    std::copy_n(expected.begin() + 512, 512, copied_expected.begin() + 64);
    auto transfer = cache.BuildProtectedShadow(destination.PlanMap(0, copied.size()), 0, copied);
    CHECK(transfer.has_value());
    CHECK(std::equal(copied_expected.begin(), copied_expected.end(), transfer->bytes.get()));
    CASE();
    const WebGpuReadbackLayout roi{16, 256, 4, 3, format};
    std::vector<uint8_t> roi_original(4 * 3 * 4), roi_protected(roi_original.size());
    for (size_t y = 0; y < 3; ++y) {
      const size_t source_offset = ((y + 5) * width + 3) * 4;
      std::copy_n(original.begin() + source_offset, 16, roi_original.begin() + y * 16);
      std::copy_n(protected_pixels.begin() + source_offset, 16, roi_protected.begin() + y * 16);
    }
    std::vector<uint8_t> roi_raw(768, 0x75), roi_expected = roi_raw;
    CHECK(StoreWebGpuRgba8(roi_original, roi, 0, roi_raw));
    CHECK(StoreWebGpuRgba8(roi_protected, roi, 0, roi_expected));
    WebGpuReadbackProvenance roi_tracker(roi_raw.size(), 7);
    CHECK(roi_tracker.RecordTextureCopy(1, roi, Token(1), {3, 5, width, height}));
    auto roi_shadow = cache.BuildProtectedShadow(roi_tracker.PlanMap(0, roi_raw.size()), 0, roi_raw);
    CHECK(roi_shadow.has_value());
    CHECK(std::equal(roi_expected.begin(), roi_expected.end(), roi_shadow->bytes.get()));
    CASE();
    auto altered = raw;
    altered[8] ^= 1;
    CHECK(!cache.BuildProtectedShadow(plan, 0, altered));
    CHECK(cache.retained_bytes() == pixels * 2);
    CASE();
    auto written_raw = raw;
    for (size_t byte = 8; byte < 12; ++byte) written_raw[byte] = static_cast<uint8_t>(byte + 17);
    auto written_expected = expected;
    std::copy_n(written_raw.begin() + 8, 4, written_expected.begin() + 8);
    auto written_tracker = tracker;
    CHECK(written_tracker.InvalidateWrite(2, 8, 4));
    auto written_shadow = cache.BuildProtectedShadow(written_tracker.PlanMap(0, raw.size()), 0, written_raw);
    CHECK(written_shadow.has_value());
    CHECK(std::equal(written_expected.begin(), written_expected.end(), written_shadow->bytes.get()));
    CASE();
    auto duplicate = plan;
    duplicate.regions[1] = duplicate.regions[0];
    duplicate.count = 2;
    CHECK(!cache.BuildProtectedShadow(duplicate, 0, raw));
    CHECK(raw == raw_before);
    CASE();
    auto missing = plan;
    missing.regions[0].snapshot.snapshot_id = 999;
    CHECK(!cache.BuildProtectedShadow(missing, 0, raw));
    missing = plan;
    missing.regions[0].source_rect.full_width += 1;
    CHECK(!cache.BuildProtectedShadow(missing, 0, raw));
    missing = plan;
    missing.count = missing.regions.size() + 1;
    CHECK(!cache.BuildProtectedShadow(missing, 0, raw));
    CHECK(!cache.BuildProtectedShadow(plan, 4, raw));
    CASE();
    WebGpuReadbackSnapshots budget(7, 1, pixels * 2 - 1, 4096);
    CHECK(!budget.Capture(Token(1), full, 0, raw, seed));
    CHECK(budget.retained_bytes() == 0);
    WebGpuReadbackSnapshots small_shadow(7, 1, pixels * 2, raw.size());
    CHECK(small_shadow.Capture(Token(1), full, 0, raw, seed));
    CHECK(!small_shadow.BuildProtectedShadow(plan, 0, raw));
    CASE();
    CHECK(!cache.Capture(Token(1), full, 0, raw, seed));
    CHECK(!cache.Capture({8, 2, 1, 1}, full, 0, raw, seed));
    CHECK(!cache.Capture({7, 2, 1, 2}, full, 0, raw, seed));
    CHECK(!cache.Capture({7, 2, 0, 1}, full, 0, raw, seed));
    CASE();
    WebGpuReadbackProvenance compute(raw.size(), 7);
    CHECK(!cache.BuildProtectedShadow(compute.PlanMap(0, raw.size()), 0, raw));
    CHECK(raw == raw_before);
    CASE();
    CHECK(cache.Release(Token(1)));
    CHECK(cache.retained_bytes() == 0);
    CHECK(!cache.BuildProtectedShadow(plan, 0, raw));
    CHECK(!cache.Capture(Token(1), full, 0, raw, seed));
    CHECK(cache.Capture(Token(2), full, 0, raw, seed));
    CHECK(!cache.BuildProtectedShadow(plan, 0, raw));
    CASE();
    cache.Destroy();
    CHECK(cache.retained_bytes() == 0);
    CHECK(!cache.Capture(Token(3), full, 0, raw, seed));
    CHECK(!cache.Release(Token(2)));
    CHECK(!cache.BuildProtectedShadow(plan, 0, raw));
    CHECK(shadow->bytes[0] == expected[0]);
  }
  for (uint32_t iteration = 0; iteration < 64; ++iteration) {
    const auto format = iteration % 2 == 0 ? WebGpuPixelFormat::kRgba8Unorm : WebGpuPixelFormat::kBgra8Unorm;
    const uint32_t crop_width = iteration % 7 + 1, crop_height = iteration % 5 + 1;
    const uint32_t origin_x = iteration % 5, origin_y = iteration % 7;
    seed[0] = static_cast<uint8_t>(iteration + 1);
    auto transformed = original;
    CHECK(TransformEdgeCoherentCanvas(transformed, width, height, seed));
    const WebGpuReadbackLayout full{8, 256, width, height, format};
    std::vector<uint8_t> full_raw(4096, 0xa5);
    CHECK(StoreWebGpuRgba8(original, full, 0, full_raw));
    WebGpuReadbackSnapshots cache(7, 1, 65536, 65536);
    CHECK(cache.Capture(Token(1), full, 0, full_raw, seed));
    const WebGpuReadbackLayout cropped{16 + (iteration % 8) * 4, 256, crop_width, crop_height, format};
    std::vector<uint8_t> crop_original(static_cast<size_t>(crop_width) * crop_height * 4);
    auto crop_protected = crop_original;
    for (size_t row = 0; row < crop_height; ++row) {
      const size_t offset = ((row + origin_y) * width + origin_x) * 4;
      std::copy_n(original.begin() + offset, crop_width * 4, crop_original.begin() + row * crop_width * 4);
      std::copy_n(transformed.begin() + offset, crop_width * 4, crop_protected.begin() + row * crop_width * 4);
    }
    std::vector<uint8_t> raw(1536, 0x77), expected = raw;
    CHECK(StoreWebGpuRgba8(crop_original, cropped, 0, raw));
    CHECK(StoreWebGpuRgba8(crop_protected, cropped, 0, expected));
    WebGpuReadbackProvenance tracker(raw.size(), 7);
    CHECK(tracker.RecordTextureCopy(1, cropped, Token(1), {origin_x, origin_y, width, height}));
    auto shadow = cache.BuildProtectedShadow(tracker.PlanMap(0, raw.size()), 0, raw);
    CHECK(shadow.has_value());
    CHECK(std::equal(expected.begin(), expected.end(), shadow->bytes.get()));
    const size_t aligned = static_cast<size_t>(cropped.offset) & ~size_t{7};
    auto partial = cache.BuildProtectedShadow(tracker.PlanMap(aligned, 8), aligned,
        std::span<const uint8_t>(raw).subspan(aligned, 8));
    CHECK(partial.has_value());
    CHECK(std::equal(expected.begin() + aligned, expected.begin() + aligned + 8, partial->bytes.get()));
  }
  std::printf("{\"passed\":true,\"named_cases\":%zu,\"formats\":2,\"property_iterations\":64,\"assertions\":%zu,\"browser_integrated\":false}\n", cases, assertions);
}
