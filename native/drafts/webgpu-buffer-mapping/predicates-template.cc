// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>
#include <optional>
#include <span>
#include <vector>
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
#include "gpu/command_buffer/common/glint/buffer_scatter_mapping.h"
/* GLINT_REGRESSION */
namespace allocation_fixture {
struct Failure { bool failed = false; };
using MaybeError = Failure;
#define DAWN_INTERNAL_ERROR_IF(condition, message) do { if (condition) return Failure{true}; } while (false)
#define DAWN_TRY(expression) do { const auto result = (expression); if (result.failed) return result; } while (false)
#define DAWN_ASSERT(x) CHECK(x)
enum class Toggle { LazyClearResourceOnFirstUse };
struct CommandRecordingContext {};
struct Device {
    bool lazy = true;
    bool IsToggleEnabled(Toggle) const { return lazy; }
    bool IsLockedByCurrentThreadIfNeeded() const { return true; }
};
struct Resource {
    uint64_t width;
    struct Desc { uint64_t Width; };
    Desc GetDesc() const { return {width}; }
};
class Buffer {
  public:
    Device device;
    uint64_t logical = 37, allocated = 64;
    Resource resource{64};
    bool access = true, private_backing = true, initialized = true, init_fail = false, clear_fail = false;
    size_t init_calls = 0, clear_calls = 0;
    std::vector<uint8_t> data = std::vector<uint8_t>(64, 0x99);
    bool HasAccess() const { return access; }
    bool HasPrivateGlintReadbackBacking() const { return private_backing; }
    uint64_t GetSize() const { return logical; }
    uint64_t GetAllocatedSize() const { return allocated; }
    Device* GetDevice() { return &device; }
    Resource* GetD3D12Resource() { return &resource; }
    MaybeError EnsureDataInitialized(CommandRecordingContext*) {
        ++init_calls;
        if (init_fail) return {true};
        if (!initialized) { std::fill_n(data.begin(), static_cast<size_t>(logical), 0); initialized = true; }
        return {};
    }
    MaybeError ClearBuffer(CommandRecordingContext*, uint8_t value, uint64_t offset, uint64_t size) {
        ++clear_calls;
        CHECK(value == 0 && offset == logical && size == allocated - logical);
        if (clear_fail) return {true};
        std::fill(data.begin() + static_cast<size_t>(offset), data.end(), value);
        return {};
    }
    MaybeError EnsureGlintAllocationInitialized(CommandRecordingContext*);
};
/* GLINT_ALLOCATION */
#undef DAWN_INTERNAL_ERROR_IF
#undef DAWN_TRY
#undef DAWN_ASSERT
}  // namespace allocation_fixture
void CheckAllocation() {
    allocation_fixture::CommandRecordingContext context;
    for (int fault = 0; fault < 9; ++fault) {
        allocation_fixture::Buffer buffer;
        if (fault == 1) buffer.access = false;
        if (fault == 2) buffer.private_backing = false;
        if (fault == 3) buffer.allocated = 36;
        if (fault == 4) buffer.resource.width = 128;
        if (fault == 5) buffer.device.lazy = false;
        if (fault == 6) buffer.init_fail = true;
        if (fault == 7) buffer.clear_fail = true;
        const auto result = buffer.EnsureGlintAllocationInitialized(fault == 8 ? nullptr : &context);
        CHECK(result.failed == (fault != 0));
        for (size_t index = 0; index < 37; ++index) CHECK(buffer.data[index] == 0x99);
        if (fault == 0) {
            CHECK(buffer.init_calls == 1 && buffer.clear_calls == 1);
            for (size_t index = 37; index < 64; ++index) CHECK(buffer.data[index] == 0);
        } else {
            for (size_t index = 37; index < 64; ++index) CHECK(buffer.data[index] == 0x99);
        }
    }
    allocation_fixture::Buffer uninitialized;
    uninitialized.initialized = false;
    CHECK(!uninitialized.EnsureGlintAllocationInitialized(&context).failed);
    CHECK(std::all_of(uninitialized.data.begin(), uninitialized.data.end(), [](uint8_t value) { return value == 0; }));
    allocation_fixture::Buffer exact;
    exact.logical = exact.allocated;
    CHECK(!exact.EnsureGlintAllocationInitialized(&context).failed && exact.clear_calls == 0);
}
void CheckMapping() {
    using namespace glint::candidate;
    for (auto format : {WebGpuPixelFormat::kRgba8Unorm, WebGpuPixelFormat::kBgra8Unorm})
        for (bool native_bgra : {false, true}) for (uint64_t high : {uint64_t{0}, uint64_t{1} << 34})
            for (int delta : {-3, 0, 1, 50, 51, 52, 64, 255, 256, 500})
                for (uint64_t length : {1u, 3u, 37u, 64u, 512u}) {
                    WebGpuReadbackRegion region;
                    region.buffer_offset = 11; region.size = length;
                    region.snapshot_layout = {high + 64, 256, 13, 3, format};
                    region.snapshot_offset = static_cast<uint64_t>(static_cast<int64_t>(high + 64) + delta);
                    region.snapshot = {7, 1, 1, 1}; region.source_rect = {2, 1, 19, 7};
                    const auto words = BuildWebGpuBufferScatterWords(region, 4096, native_bgra);
                    bool has_pixel = false;
                    for (uint64_t index = 0; index < length; ++index) {
                        auto expected = WebGpuCanonicalByte(region, region.buffer_offset + index);
                        has_pixel |= expected.has_value();
                        if (expected && native_bgra && *expected % 4 % 2 == 0)
                            *expected = *expected - *expected % 4 + 2 - *expected % 4;
                        std::optional<size_t> actual;
                        if (words) {
                            const auto& p = *words;
                            CHECK(p[0] == 11 && p[1] == length && p[13] == 4096 && p[14] == 19 * 7 * 4);
                            if (index >= p[2]) {
                                const uint64_t relative = index - p[2];
                                const uint64_t column_sum = p[4] + relative % p[5];
                                const uint64_t row = p[3] + relative / p[5] + column_sum / p[5];
                                const uint64_t column = column_sum % p[5];
                                if (row < p[7] && column < uint64_t{p[6]} * 4) {
                                    uint64_t channel = column % 4;
                                    if (p[12] && channel % 2 == 0) channel = 2 - channel;
                                    actual = static_cast<size_t>(((row + p[9]) * p[10] + column / 4 + p[8]) * 4 + channel);
                                }
                            }
                        }
                        CHECK(actual == expected);
                    }
                    CHECK(words.has_value() == has_pixel);
                }
    std::array<uint8_t, 32> key{}; key.fill(17);
    auto policy = std::make_shared<const GlintWebGPUDevicePolicy>(std::move(*GlintWebGPUDevicePolicy::Create(1, key)));
    for (auto format : {GlintReadbackFormat::Rgba8Unorm, GlintReadbackFormat::Bgra8Unorm}) {
        GlintWebGPUReadbackObserver observer(policy, 7, {}); Copy(observer, 0, format);
        std::array use{Use(3, 37)};
        const auto plan = observer.PrepareGpuInputPlan({use, false, true});
        CHECK(plan && plan->regions.size() == 1);
        const auto& p = plan->regions[0].mapping;
        CHECK(p[0] == 3 && p[1] == 37 && p[2] == 0 && p[3] == 0 && p[4] == 3 && p[5] == 256);
        CHECK(p[12] == 0 && p[13] == 4096 && p[14] == 1024);
        CHECK(observer.CommitGpuInputPlan(plan));
    }
}
int main() {
    CheckMapping(); CheckAllocation();
    const size_t mapping_assertions = assertions;
    RunInputPlanRegression();
    CHECK(assertions - mapping_assertions == 12802);
    std::printf("{\"passed\":true,\"assertions\":%zu,\"prior_plan_assertions\":12802,\"legacy_assertions\":10154,"
        "\"backend_mocked\":true,\"cpu_controller_executed\":true,\"native_mapping_matches_byte_oracle\":true,"
        "\"physical_padding_contract_verified\":true,\"actual_native_device_queue_executed\":false}\n", assertions);
}
