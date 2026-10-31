// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <vector>
size_t assertions = 0, cases = 0;
void Check(bool value, int line) {
    ++assertions;
    if (!value) { std::fprintf(stderr, "texel guard assertion %d\n", line); std::abort(); }
}
#define CHECK(x) Check((x), __LINE__)
struct Failure { bool failed = false; };
using MaybeError = Failure;
#define DAWN_INTERNAL_ERROR_IF(condition, message) do { if (condition) return Failure{true}; } while (false)
namespace wgpu {
enum class ShaderStage : unsigned { None = 0, Compute = 1, Vertex = 2, Fragment = 4, Render = 6, All = 7 };
unsigned operator&(ShaderStage a, ShaderStage b) { return static_cast<unsigned>(a) & static_cast<unsigned>(b); }
}
using BindingIndex = size_t;
struct Device {};
struct BufferBase {};
struct View {
    BufferBase* buffer;
    BufferBase* GetBuffer() { return buffer; }
};
struct BindingInfo { wgpu::ShaderStage visibility; };
struct Layout {
    std::array<BindingIndex, 2> indices{0, 1};
    std::array<BindingInfo, 2> infos{{{wgpu::ShaderStage::Compute}, {wgpu::ShaderStage::Render}}};
    const auto& GetTexelBufferIndices() const { return indices; }
    const auto& GetBindingInfo(BindingIndex index) const { return infos.at(index); }
};
struct BindGroupBase {
    Device* owner;
    Layout layout;
    std::array<View*, 2> views;
    Device* GetDevice() const { return owner; }
    const Layout* GetLayout() const { return &layout; }
    View* GetBindingAsTexelBufferView(BindingIndex index) { return views.at(index); }
};
struct Source { BufferBase* pointer; BufferBase* Get() const { return pointer; } };
struct GlintProjectedBuffer { Source source; };
struct Batch { std::vector<GlintProjectedBuffer> buffers; };
struct Tracker {
    Device* mDevice;
    std::unique_ptr<Batch> mGlintComputeBuffers;
/* GLINT_LOOKUP */
/* GLINT_GUARD */
};
int main() {
    for (int iteration = 0; iteration < 64; ++iteration) {
        for (auto stage : {wgpu::ShaderStage::None, wgpu::ShaderStage::Compute,
                          wgpu::ShaderStage::Vertex, wgpu::ShaderStage::Fragment,
                          wgpu::ShaderStage::Render, wgpu::ShaderStage::All}) {
            for (int fault = 0; fault < 10; ++fault) {
                ++cases;
                Device device, foreign;
                BufferBase regular, texel;
                View first{&regular}, second{&texel};
                BindGroupBase group{&device, {}, {{&first, &second}}};
                Tracker tracker{&device, std::make_unique<Batch>()};
                if (fault == 1 || fault == 9) tracker.mGlintComputeBuffers->buffers.push_back({{&texel}});
                if (fault == 2 || fault == 9) tracker.mGlintComputeBuffers->buffers.push_back({{&regular}});
                if (fault == 3) group.views[0] = nullptr;
                if (fault == 4) group.views[1] = nullptr;
                if (fault == 5) first.buffer = nullptr;
                if (fault == 6) second.buffer = nullptr;
                if (fault == 7) group.owner = &foreign;
                const bool compute_visible = (stage & wgpu::ShaderStage::Compute) != 0;
                const bool render_visible = (stage & wgpu::ShaderStage::Render) != 0;
                const bool denied = fault == 7 || fault == 8 ||
                    (compute_visible && (fault == 2 || fault == 3 || fault == 5 || fault == 9)) ||
                    (render_visible && (fault == 1 || fault == 4 || fault == 6 || fault == 9));
                const auto result = tracker.ValidateGlintProjectedTexelBindings(fault == 8 ? nullptr : &group, stage);
                CHECK(result.failed == denied);
                CHECK((tracker.FindGlintProjectedBuffer(&regular) != nullptr) == (fault == 2 || fault == 9));
                CHECK((tracker.FindGlintProjectedBuffer(&texel) != nullptr) == (fault == 1 || fault == 9));
            }
        }
        Device device;
        BufferBase buffer;
        View view{&buffer};
        BindGroupBase group{&device, {}, {{&view, &view}}};
        Tracker empty{&device, nullptr};
        CHECK(!empty.ValidateGlintProjectedTexelBindings(&group, wgpu::ShaderStage::All).failed);
    }
    std::printf("{\"passed\":true,\"cases\":%zu,\"assertions\":%zu,\"projected_texel_alias_denied\":true,\"unprojected_texel_binding_preserved\":true,\"backend_mocked\":true,\"actual_native_device_queue_executed\":false}\n", cases, assertions);
}
