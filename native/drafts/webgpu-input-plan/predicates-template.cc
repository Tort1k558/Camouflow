// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <vector>

#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"

size_t assertions = 0;
int capabilities_alive = 0, cpu_reads = 0;
void Check(bool value, int line) {
    ++assertions;
    if (!value) { std::fprintf(stderr, "input-plan assertion %d\n", line); std::abort(); }
}
#define CHECK(x) Check((x), __LINE__)
// Explicit mock boundary: this friend creates metadata-only capabilities, not native GPU resources.
namespace dawn::native::d3d12 {
class GlintGpuPixelSnapshot {
  public:
    GlintGpuPixelSnapshot() { ++capabilities_alive; }
    ~GlintGpuPixelSnapshot() { --capabilities_alive; }
};
class GlintTextureProjector {
  public:
    static std::shared_ptr<const GlintGpuReadbackSnapshot> Make(
        uint32_t width, uint32_t height, GlintReadbackFormat format) {
        return std::shared_ptr<const GlintGpuReadbackSnapshot>(new GlintGpuReadbackSnapshot(
            std::make_shared<const GlintGpuPixelSnapshot>(), width, height, format));
    }
};
}
using namespace dawn::native;
using namespace gpu::webgpu;
/* GLINT_LEGACY */
class Snapshot final : public GlintReadbackSnapshot {
  public:
    Snapshot(std::shared_ptr<const GlintGpuReadbackSnapshot> gpu, GlintReadbackFormat format)
        : GlintReadbackSnapshot(std::move(gpu)), format_(format) {}
    GlintReadbackStatus Read(std::span<const uint8_t>* pixels) const override {
        ++cpu_reads; *pixels = {}; return GlintReadbackStatus::Pending;
    }
    uint32_t GetWidth() const override { return 16; }
    uint32_t GetHeight() const override { return 16; }
    uint32_t GetRowPitch() const override { return 256; }
    GlintReadbackFormat GetFormat() const override { return format_; }
  private:
    GlintReadbackFormat format_;
};
class Bytes final : public GlintByteReadbackSnapshot {
  public:
    GlintReadbackStatus Read(std::span<const uint8_t>* bytes) const override {
        ++cpu_reads; *bytes = {}; return GlintReadbackStatus::Pending;
    }
    uint64_t GetByteSize() const override { return 32; }
};
GlintBufferIdentity Buffer(uintptr_t id = 1) { return {reinterpret_cast<WGPUBuffer>(id), 4096}; }
GlintShaderBufferUse Use(uint64_t offset = 0, uint64_t size = 4096) {
    return {Buffer(), true, false, offset, size, true};
}
void Copy(GlintWebGPUReadbackObserver& observer, int gpu_mode = 0,
          GlintReadbackFormat format = GlintReadbackFormat::Rgba8Unorm) {
    std::shared_ptr<const GlintGpuReadbackSnapshot> gpu;
    if (gpu_mode != 1) gpu = dawn::native::d3d12::GlintTextureProjector::Make(
        gpu_mode == 2 ? 8 : 16, 16,
        gpu_mode == 3 ? GlintReadbackFormat::Unsupported : format);
    GlintTextureToBufferCopy copy;
    copy.destination = Buffer(); copy.destinationRowPitch = 256;
    copy.width = copy.height = 16; copy.format = format;
    observer.OnTextureToBufferCopy(copy, std::make_unique<Snapshot>(std::move(gpu), format));
}
int main() {
    std::array<uint8_t, 32> key{}; key.fill(17);
    auto policy = std::make_shared<const GlintWebGPUDevicePolicy>(
        std::move(*GlintWebGPUDevicePolicy::Create(1, key)));
    std::array full{Use()};
    const GlintShaderScope scope{full, false, true};
    for (int iteration = 0; iteration < 256; ++iteration) {
        const auto format = iteration % 2 ? GlintReadbackFormat::Bgra8Unorm : GlintReadbackFormat::Rgba8Unorm;
        {
            GlintWebGPUReadbackObserver observer(policy, 7, {}), other(policy, 7, {});
            Copy(observer, 0, format); Copy(other, 0, format);
            auto plan = observer.PrepareGpuInputPlan(scope);
            auto foreign = other.PrepareGpuInputPlan(scope);
            CHECK(plan && plan->deviceEpoch == 7 && plan->policyGeneration == 1 && plan->sequence);
            CHECK(plan->regions.size() == 1 && plan->regions[0].snapshot);
            const auto& region = plan->regions[0];
            CHECK(region.buffer.handle == Buffer().handle && region.bufferOffset == 0);
            CHECK(region.size == 3904 && region.rowPitch == 256 && region.width == 16 && region.height == 16);
            CHECK(region.snapshot->GetFormat() == format && region.format == format);
            CHECK(!observer.CommitGpuInputPlan(foreign));
            CHECK(!observer.CommitGpuInputPlan(plan));
            std::array inputs_and_output{Use(), GlintShaderBufferUse{Buffer(2), false, true, 0, 32, true}};
            const GlintShaderScope output_scope{inputs_and_output, false, true};
            plan = observer.PrepareGpuInputPlan(output_scope);
            CHECK(observer.CommitGpuInputPlan(plan));
            CHECK(!observer.CommitGpuInputPlan(plan));
            CHECK(observer.BeginShaderByteScope(output_scope, false).ticket == 0);
            CHECK(observer.IsHealthy());
        }
        for (int mode = 1; mode <= 3; ++mode) {
            GlintWebGPUReadbackObserver observer(policy, 7, {});
            Copy(observer, mode, format);
            CHECK(!observer.PrepareGpuInputPlan(scope));
            CHECK(observer.IsHealthy());
        }
        {
            GlintWebGPUReadbackObserver observer(policy, 7, {});
            Copy(observer, 0, format);
            std::array overlap{Use(0, 128), Use(32, 256)};
            auto plan = observer.PrepareGpuInputPlan({overlap, false, true});
            CHECK(plan && plan->regions.size() == 1 && plan->regions[0].size == 288);
            CHECK(observer.CommitGpuInputPlan(plan));
            std::array clipped{Use(3, 37)};
            plan = observer.PrepareGpuInputPlan({clipped, false, true});
            CHECK(plan && plan->regions.size() == 1);
            CHECK(plan->regions[0].bufferOffset == 3 && plan->regions[0].snapshotOffset == 3 && plan->regions[0].size == 37);
            std::array disjoint{Use(0, 16), Use(32, 16)};
            auto next = observer.PrepareGpuInputPlan({disjoint, false, true});
            CHECK(next && next->regions.size() == 2);
            CHECK(!observer.CommitGpuInputPlan(plan));
            std::array<GlintShaderBufferUse, 17> fragmented{};
            for (size_t i = 0; i < fragmented.size(); ++i)
                fragmented[i] = Use((i / 16) * 256 + (i % 16) * 4, 1);
            CHECK(!observer.PrepareGpuInputPlan({fragmented, false, true}));
            CHECK(observer.IsHealthy());
        }
        for (int invalidation = 0; invalidation < 5; ++invalidation) {
            GlintWebGPUReadbackObserver observer(policy, 7, {});
            Copy(observer, 0, format);
            auto plan = observer.PrepareGpuInputPlan(scope);
            CHECK(plan && plan->regions.size() == 1);
            if (invalidation == 0) observer.OnBufferWrite(Buffer(), 0, 4096, GlintBufferWriteKind::KnownBytes);
            if (invalidation == 1) observer.OnBufferDestroyed(Buffer().handle);
            if (invalidation == 2) observer.OnExecutionError();
            if (invalidation == 3) observer.OnShaderScope(scope);
            if (invalidation == 4) observer.BeginShaderByteScope(scope, false);
            CHECK(!observer.CommitGpuInputPlan(plan));
            CHECK(plan->regions[0].snapshot->GetWidth() == 16);
        }
        {
            GlintWebGPUReadbackObserver observer(policy, 8, {});
            auto empty = observer.PrepareGpuInputPlan(scope);
            CHECK(empty && empty->deviceEpoch == 8 && empty->regions.empty());
            CHECK(observer.CommitGpuInputPlan(empty));
            Copy(observer, 0, format);
            std::array invalid{Use(4090, 16)};
            CHECK(!observer.PrepareGpuInputPlan({invalid, false, true}));
            CHECK(!observer.IsHealthy());
        }
        CHECK(capabilities_alive == 0);
        {
            GlintWebGPUReadbackObserver observer(policy, 7, {});
            std::array writable{GlintShaderBufferUse{Buffer(2), false, true, 0, 32, true}};
            const auto output = observer.BeginShaderByteScope({writable, true, true}, true);
            CHECK(output.ticket && output.requests.size() == 1);
            std::vector<GlintShaderByteResult> results;
            results.push_back({output.requests[0].requestId, std::make_unique<Bytes>()});
            CHECK(observer.CommitShaderByteScope(output.ticket, std::move(results)));
            auto input = writable;
            input[0].readable = true; input[0].writable = false;
            auto plan = observer.PrepareGpuInputPlan({input, false, true});
            CHECK(plan && plan->regions.empty());
            CHECK(observer.CommitGpuInputPlan(plan));
            observer.OnBufferWrite(Buffer(2), 0, 32, GlintBufferWriteKind::Uncertain);
            CHECK(!observer.PrepareGpuInputPlan({input, false, true}));
        }
    }
    CHECK(cpu_reads == 0);
    legacy::Run();
    CHECK(legacy::assertions == 10154);
    std::printf("{\"passed\":true,\"assertions\":%zu,\"iterations\":256,"
        "\"legacy_assertions\":10154,\"backend_mocked\":true,\"cpu_controller_executed\":true,"
        "\"stale_and_foreign_plan_rejected\":true,\"plan_commit_does_not_admit_raw_inputs\":true,"
        "\"actual_native_device_queue_executed\":false}\n", assertions);
}
