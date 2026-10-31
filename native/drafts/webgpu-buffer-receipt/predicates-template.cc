// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <optional>
#include <span>
#include <type_traits>
#include <vector>
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
/* GLINT_REGRESSION */
namespace dawn::native::d3d12 {
// Explicit test-only issuer: this does not execute native command recording.
class CommandBuffer {
  public:
    static std::shared_ptr<const GlintGpuInputReceipt> Make(std::shared_ptr<const GlintGpuInputPlan> plan) {
        return std::shared_ptr<const GlintGpuInputReceipt>(new GlintGpuInputReceipt(std::move(plan)));
    }
};
}
static_assert(!std::is_constructible_v<GlintGpuInputReceipt, std::shared_ptr<const GlintGpuInputPlan>>);
static_assert(!std::is_copy_constructible_v<GlintGpuInputReceipt>);
class LegacyObserver final : public GlintReadbackObserver {
  public:
    size_t legacy_calls = 0;
    void OnTextureToBufferCopy(const GlintTextureToBufferCopy&, std::unique_ptr<GlintReadbackSnapshot>) override {}
    void OnBufferToBufferCopy(GlintBufferIdentity, uint64_t, GlintBufferIdentity, uint64_t, uint64_t) override {}
    void OnBufferWrite(GlintBufferIdentity, uint64_t, uint64_t, GlintBufferWriteKind) override {}
    void OnBufferDestroyed(WGPUBuffer) override {}
    void OnExecutionError() override {}
    bool CopyShaderProjectionSeed(std::span<uint8_t, 32>) override { return false; }
    void OnShaderScope(const GlintShaderScope&) override {}
    std::shared_ptr<const GlintGpuInputPlan> PrepareGpuInputPlan(const GlintShaderScope&) override { return {}; }
    bool CommitGpuInputPlan(std::shared_ptr<const GlintGpuInputPlan>) override { return false; }
    GlintShaderBytePlan BeginShaderByteScope(const GlintShaderScope&, bool) override { ++legacy_calls; return {17, {}, false}; }
    bool CommitShaderByteScope(uint64_t, std::vector<GlintShaderByteResult>) override { return false; }
    GlintReadbackMapStatus ClassifyReadMap(GlintBufferIdentity, uint64_t, uint64_t) override { return GlintReadbackMapStatus::Denied; }
    GlintReadbackMap PrepareReadMap(GlintBufferIdentity, uint64_t, std::span<const uint8_t>) override { return {}; }
};
static_assert(!std::is_abstract_v<LegacyObserver>);
namespace getter_fixture {
struct Failure { bool failed = false; };
template <typename T> struct ResultOrError {
    ResultOrError(T v) : value(std::move(v)) {}
    ResultOrError(Failure f) : error(f.failed) {}
    bool error = false;
    T value{};
};
#define DAWN_INTERNAL_ERROR_IF(condition, message) do { if (condition) return Failure{true}; } while (false)
struct ComputePipeline {};
using PipelineType = ComputePipeline;
struct Device { bool observer = true; bool GetGlintReadbackObserver() const { return observer; } };
struct Batch { std::vector<int> buffers{1}; std::shared_ptr<const GlintGpuInputPlan> plan = std::make_shared<GlintGpuInputPlan>(); };
struct Tracker {
    Device device;
    Device* mDevice = &device;
    std::optional<int> mGlintComputeScope{1};
    bool mGlintComputeProjectedReady = true, mGlintComputeBindingsApplied = true, mGlintComputeCopiedBack = true;
    std::unique_ptr<Batch> mGlintComputeBuffers = std::make_unique<Batch>();
/* GLINT_GETTER */
};
#undef DAWN_INTERNAL_ERROR_IF
}
int main() {
    RunOldInputPlanRegression();
    const size_t prior_plan_assertions = assertions;
    CHECK(prior_plan_assertions == 12802 && legacy::assertions == 10154);
    LegacyObserver legacy_observer;
    CHECK(legacy_observer.BeginShaderByteScope({{}, false, true}, true).ticket == 17);
    const auto unsupported = legacy_observer.BeginShaderByteScopeWithGpuInputs({{}, false, true}, true, nullptr);
    CHECK(unsupported.failed && !unsupported.ticket);
    CHECK(legacy_observer.legacy_calls == 1);

    for (int fault = 0; fault < 8; ++fault) {
        getter_fixture::Tracker tracker;
        if (fault == 1) tracker.device.observer = false;
        if (fault == 2) tracker.mGlintComputeScope.reset();
        if (fault == 3) tracker.mGlintComputeProjectedReady = false;
        if (fault == 4) tracker.mGlintComputeBindingsApplied = false;
        if (fault == 5) tracker.mGlintComputeCopiedBack = false;
        if (fault == 6) tracker.mGlintComputeBuffers.reset();
        if (fault == 7) tracker.mGlintComputeBuffers->buffers.clear();
        auto result = tracker.GetGlintGpuInputPlanForCapture();
        CHECK(result.error == (fault >= 2 && fault <= 6));
        CHECK(static_cast<bool>(result.value) == (fault == 0));
    }
    std::array<uint8_t, 32> key{}; key.fill(17);
    auto policy = std::make_shared<const GlintWebGPUDevicePolicy>(
        std::move(*GlintWebGPUDevicePolicy::Create(1, key)));
    auto second_policy = std::make_shared<const GlintWebGPUDevicePolicy>(
        std::move(*GlintWebGPUDevicePolicy::Create(2, key)));
    size_t cases = 0;
    for (int iteration = 0; iteration < 32; ++iteration) for (int fault = 0; fault < 28; ++fault) {
        ++cases;
        const auto format = iteration % 2 ? GlintReadbackFormat::Bgra8Unorm : GlintReadbackFormat::Rgba8Unorm;
        GlintWebGPUReadbackObserver observer(policy, 7, {});
        GlintWebGPUReadbackObserver other(fault == 22 ? second_policy : policy, 7, {});
        Copy(observer, 0, format); Copy(other, 0, format);
        std::vector<GlintShaderBufferUse> uses{Use(0, 256), {Buffer(2), false, true, 0, 32, true}};
        GlintShaderScope scope{uses, fault == 25, true};
        auto plan = observer.PrepareGpuInputPlan(scope);
        CHECK(plan && plan->regions.size() == 1);
        if (fault != 1) CHECK(observer.CommitGpuInputPlan(plan));
        auto receipt = dawn::native::d3d12::CommandBuffer::Make(plan);
        if (fault == 2 || fault == 22) {
            auto foreign = other.PrepareGpuInputPlan(scope);
            CHECK(foreign && other.CommitGpuInputPlan(foreign));
            receipt = dawn::native::d3d12::CommandBuffer::Make(std::move(foreign));
        }
        if (fault == 3) receipt = dawn::native::d3d12::CommandBuffer::Make(std::make_shared<const GlintGpuInputPlan>(*plan));
        if (fault == 4) ++uses[0].offset;
        if (fault == 5) --uses[0].size;
        if (fault == 6) uses[0].readable = false;
        if (fault == 7) uses[0].writable = true;
        if (fault == 8) ++uses[1].offset;
        if (fault == 9) uses[1].writable = false;
        if (fault == 10) --uses[0].buffer.size;
        if (fault == 11) uses[0].rangeKnown = false;
        if (fault == 12) scope.hasTextureInputs = true;
        if (fault == 13) scope.complete = false;
        if (fault == 14) std::swap(uses[0], uses[1]);
        if (fault == 15) observer.OnBufferWrite(Buffer(), 0, 4096, GlintBufferWriteKind::KnownBytes);
        if (fault == 16) observer.OnBufferDestroyed(Buffer().handle);
        if (fault == 17) observer.OnExecutionError();
        if (fault == 18) observer.OnBufferToBufferCopy(Buffer(), 0, Buffer(2), 0, 32);
        if (fault == 19) CHECK(observer.PrepareGpuInputPlan(scope) != nullptr);
        if (fault == 20) observer.OnShaderScope(scope);
        if (fault == 21) CHECK(!observer.BeginShaderByteScope(scope, true).ticket);
        if (fault == 23) {
            std::array unrelated{GlintShaderBufferUse{Buffer(3), false, true, 0, 32, true}};
            auto empty = observer.PrepareGpuInputPlan({unrelated, false, true});
            CHECK(empty && empty->regions.empty() && observer.CommitGpuInputPlan(empty));
            receipt = dawn::native::d3d12::CommandBuffer::Make(std::move(empty));
            uses.assign(unrelated.begin(), unrelated.end());
        }
        if (fault == 24) receipt.reset();
        if (fault == 26) uses.push_back({Buffer(3), true, false, 0, 32, true});
        if (fault == 27) Copy(observer, 0, format);
        scope.buffers = uses;
        const auto output = observer.BeginShaderByteScopeWithGpuInputs(scope, fault != 25, receipt);
        if (fault == 0) {
            CHECK(!output.failed && output.ticket && output.requests.size() == 1);
            CHECK(output.requests[0].buffer.handle == Buffer(2).handle && output.requests[0].size == 32);
            std::vector<GlintShaderByteResult> results;
            results.push_back({output.requests[0].requestId, std::make_unique<Bytes>()});
            CHECK(observer.CommitShaderByteScope(output.ticket, std::move(results)));
            const auto replay = observer.BeginShaderByteScopeWithGpuInputs(scope, true, receipt);
            CHECK(replay.failed && !replay.ticket && !observer.IsHealthy());
        } else if (fault == 24 || fault == 25) {
            CHECK(!output.failed && !output.ticket && observer.IsHealthy());
        } else {
            CHECK(output.failed && !output.ticket && !observer.IsHealthy());
        }
    }
    CHECK(capabilities_alive == 0 && cpu_reads == 0);
    std::printf("{\"passed\":true,\"assertions\":%zu,\"cases\":%zu,\"prior_plan_assertions\":%zu,\"legacy_assertions\":10154,\"backend_mocked\":true,\"cpu_controller_executed\":true,\"exact_scope_receipt_checked\":true,\"actual_native_device_queue_executed\":false}\n", assertions, cases, prior_plan_assertions);
}
