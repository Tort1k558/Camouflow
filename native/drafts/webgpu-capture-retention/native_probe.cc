#include <algorithm>
#include <array>
#include <cstring>
#include <vector>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <source_location>
#include <thread>

#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
#include "gpu/command_buffer/common/glint/canvas_readback_candidate.h"
#include "dawn/dawn_proc.h"
#include "dawn/native/DawnNative.h"
#include "webgpu/webgpu_cpp.h"

void Check(bool value, std::source_location location = std::source_location::current()) {
    if (!value) {
        std::fprintf(stderr, "Native Dawn probe failed at line %u\n", location.line());
        std::exit(1);
    }
}

std::vector<uint8_t> ReadBytes(dawn::native::Instance& instance,
                              const wgpu::Buffer& buffer, size_t bytes) {
    std::atomic_bool done = false;
    std::atomic_bool mapped = false;
    buffer.MapAsync(wgpu::MapMode::Read, 0, bytes, wgpu::CallbackMode::AllowSpontaneous,
        [&](wgpu::MapAsyncStatus status, wgpu::StringView message) {
            if (status != wgpu::MapAsyncStatus::Success) {
                std::fprintf(stderr, "Map status %u: %.*s\n", static_cast<unsigned>(status),
                             static_cast<int>(message.length), message.data);
            }
            mapped.store(status == wgpu::MapAsyncStatus::Success);
            done.store(true);
        });
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
    while (!done.load() && std::chrono::steady_clock::now() < deadline) {
        dawn::native::InstanceProcessEvents(instance.Get());
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    Check(done.load() && mapped.load());
    const auto* data = static_cast<const uint8_t*>(buffer.GetConstMappedRange());
    Check(data != nullptr);
    std::vector<uint8_t> result(data, data + bytes);
    buffer.Unmap();
    return result;
}

void ProtectedScenario(dawn::native::Instance& instance, dawn::native::Adapter& adapter) {
    wgpu::DeviceDescriptor descriptor{};
    descriptor.SetUncapturedErrorCallback([](const wgpu::Device&, wgpu::ErrorType type,
                                             wgpu::StringView message) {
        std::fprintf(stderr, "Device error %u: %.*s\n", static_cast<unsigned>(type),
                     static_cast<int>(message.length), message.data);
    });
    descriptor.SetDeviceLostCallback(wgpu::CallbackMode::AllowSpontaneous,
        [](const wgpu::Device&, wgpu::DeviceLostReason reason, wgpu::StringView message) {
            std::fprintf(stderr, "Device lost %u: %.*s\n", static_cast<unsigned>(reason),
                         static_cast<int>(message.length), message.data);
        });
    auto device = wgpu::Device::Acquire(adapter.CreateDevice(&descriptor));
    Check(static_cast<bool>(device));
    std::array<uint8_t, 32> seed{};
    seed.fill(37);
    auto policy = gpu::webgpu::GlintWebGPUDevicePolicy::Create(1, seed);
    Check(policy.has_value());
    auto owned = std::make_shared<gpu::webgpu::GlintWebGPUDevicePolicy>(std::move(*policy));
    auto observer = std::make_shared<gpu::webgpu::GlintWebGPUReadbackObserver>(
        std::move(owned), 1, gpu::webgpu::GlintReadbackLimits{});
    Check(observer->IsHealthy());
    Check(dawn::native::InstallGlintReadbackObserver(device.Get(), observer));
    auto queue = device.GetQueue();
    constexpr uint32_t width = 8, height = 8, pitch = 256;
    constexpr size_t packedBytes = width * height * 4, bufferBytes = pitch * height;
    std::vector<uint8_t> pixels(packedBytes);
    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width; ++x) {
            for (uint32_t c = 0; c < 4; ++c) {
                pixels[(y * width + x) * 4 + c] = c == 3 ? 255 : static_cast<uint8_t>(x * 17 + y * 31 + c * 53);
            }
        }
    }
    auto expected = pixels;
    Check(glint::candidate::TransformEdgeCoherentCanvas(expected, width, height, seed));
    size_t changed = 0;
    for (size_t i = 0; i < pixels.size(); ++i) changed += expected[i] != pixels[i];
    Check(changed != 0);
    wgpu::TextureDescriptor textureDescriptor{};
    textureDescriptor.size = {width, height, 1};
    textureDescriptor.format = wgpu::TextureFormat::RGBA8Unorm;
    textureDescriptor.usage = wgpu::TextureUsage::CopySrc | wgpu::TextureUsage::CopyDst | wgpu::TextureUsage::TextureBinding;
    auto texture = device.CreateTexture(&textureDescriptor);
    wgpu::TexelCopyTextureInfo textureCopy{};
    textureCopy.texture = texture;
    wgpu::TexelCopyBufferLayout uploadLayout{};
    uploadLayout.bytesPerRow = width * 4;
    uploadLayout.rowsPerImage = height;
    wgpu::Extent3D extent{width, height, 1};
    queue.WriteTexture(&textureCopy, pixels.data(), pixels.size(), &uploadLayout, &extent);
    auto buffer = [&](uint64_t bytes, wgpu::BufferUsage usage) {
        wgpu::BufferDescriptor descriptor{};
        descriptor.size = bytes;
        descriptor.usage = usage;
        return device.CreateBuffer(&descriptor);
    };
    auto input = buffer(bufferBytes, wgpu::BufferUsage::CopyDst | wgpu::BufferUsage::CopySrc | wgpu::BufferUsage::Storage);
    auto directMap = buffer(bufferBytes, wgpu::BufferUsage::MapRead | wgpu::BufferUsage::CopyDst);
    wgpu::TexelCopyBufferInfo bufferCopy{};
    bufferCopy.buffer = input;
    bufferCopy.layout.bytesPerRow = pitch;
    bufferCopy.layout.rowsPerImage = height;
    auto first = device.CreateCommandEncoder();
    first.CopyTextureToBuffer(&textureCopy, &bufferCopy, &extent);
    first.CopyBufferToBuffer(input, 0, directMap, 0, bufferBytes);
    auto firstCommands = first.Finish();
    queue.Submit(1, &firstCommands);
    auto direct = ReadBytes(instance, directMap, bufferBytes);
    size_t directRawMismatches = 0, directProjectedMismatches = 0;
    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width * 4; ++x) {
            directRawMismatches += direct[y * pitch + x] != pixels[y * width * 4 + x];
            directProjectedMismatches += direct[y * pitch + x] != expected[y * width * 4 + x];
        }
    }
    std::fprintf(stderr, "Direct readback raw mismatches=%zu projected mismatches=%zu healthy=%d\n",
                 directRawMismatches, directProjectedMismatches, observer->IsHealthy());
    // Native MapAsync is the raw transport endpoint. Chromium's Wire filter
    // applies this observer contract before exposing bytes to the renderer.
    Check(directRawMismatches == 0);
    auto filtered = observer->PrepareReadMap({directMap.Get(), bufferBytes}, 0, direct);
    Check(filtered.status == dawn::native::GlintReadbackMapStatus::Protected);
    Check(filtered.bytes != nullptr && filtered.size == bufferBytes);
    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width * 4; ++x) Check(filtered.bytes[y * pitch + x] == expected[y * width * 4 + x]);
    }
    Check(observer->IsHealthy());
    std::fprintf(stderr, "Protected direct texture readback matched (%zu changed channels)\n", changed);
    auto output = buffer(packedBytes, wgpu::BufferUsage::Storage | wgpu::BufferUsage::CopySrc);
    auto outputMap = buffer(packedBytes, wgpu::BufferUsage::MapRead | wgpu::BufferUsage::CopyDst);
    wgpu::ShaderSourceWGSL wgsl{};
    wgsl.code = R"(
        @group(0) @binding(0) var<storage, read> pixels: array<u32>;
        @group(0) @binding(1) var<storage, read_write> output: array<u32>;
        @compute @workgroup_size(1) fn main(@builtin(global_invocation_id) id: vec3<u32>) {
            output[id.x] = pixels[(id.x / 8u) * 64u + (id.x % 8u)] ^ 0xa1b2c3d4u;
        }
    )";
    wgpu::ShaderModuleDescriptor shaderDescriptor{};
    shaderDescriptor.nextInChain = &wgsl;
    auto shader = device.CreateShaderModule(&shaderDescriptor);
    wgpu::ComputePipelineDescriptor pipelineDescriptor{};
    pipelineDescriptor.compute.module = shader;
    pipelineDescriptor.compute.entryPoint = "main";
    auto pipeline = device.CreateComputePipeline(&pipelineDescriptor);
    std::array<wgpu::BindGroupEntry, 2> entries{};
    entries[0].binding = 0;
    entries[0].buffer = input;
    entries[0].size = bufferBytes;
    entries[1].binding = 1;
    entries[1].buffer = output;
    entries[1].size = packedBytes;
    wgpu::BindGroupDescriptor groupDescriptor{};
    groupDescriptor.layout = pipeline.GetBindGroupLayout(0);
    groupDescriptor.entryCount = entries.size();
    groupDescriptor.entries = entries.data();
    auto group = device.CreateBindGroup(&groupDescriptor);
    auto second = device.CreateCommandEncoder();
    auto pass = second.BeginComputePass();
    pass.SetPipeline(pipeline);
    pass.SetBindGroup(0, group);
    pass.DispatchWorkgroups(width * height);
    pass.End();
    second.CopyBufferToBuffer(output, 0, outputMap, 0, packedBytes);
    auto secondCommands = second.Finish();
    queue.Submit(1, &secondCommands);
    auto actual = ReadBytes(instance, outputMap, packedBytes);
    for (size_t i = 0; i < width * height; ++i) {
        uint32_t wanted = 0, got = 0;
        std::memcpy(&wanted, expected.data() + i * 4, 4);
        std::memcpy(&got, actual.data() + i * 4, 4);
        wanted ^= 0xa1b2c3d4u;
        if (got != wanted) std::fprintf(stderr, "Shader mismatch at %zu: %08x != %08x\n", i, got, wanted);
        Check(got == wanted);
    }
    Check(observer->IsHealthy());
    std::fprintf(stderr, "Protected native buffer shader matched CPU reference\n");
    auto filteredOutput = observer->PrepareReadMap({outputMap.Get(), packedBytes}, 0, actual);
    Check(filteredOutput.status == dawn::native::GlintReadbackMapStatus::Protected);
    Check(filteredOutput.bytes != nullptr && filteredOutput.size == packedBytes);
    Check(std::equal(actual.begin(), actual.end(), filteredOutput.bytes.get()));
    std::array<dawn::native::GlintShaderBufferUse, 1> uses{
        dawn::native::GlintShaderBufferUse{{output.Get(), packedBytes}, true, false, 0,
                                         packedBytes, true}};
    auto plan = observer->PrepareGpuInputPlan({uses, false, true});
    Check(plan != nullptr && plan->regions.empty());
    Check(observer->CommitGpuInputPlan(plan));
    input.Destroy();
    directMap.Destroy();
    output.Destroy();
    outputMap.Destroy();
    Check(observer->IsHealthy());
}

int main() {
    dawnProcSetProcs(&dawn::native::GetProcs());
    dawn::native::Instance instance;
    wgpu::RequestAdapterOptions options{};
    options.backendType = wgpu::BackendType::D3D12;
    auto adapters = instance.EnumerateAdapters(&options);
    Check(!adapters.empty());
    dawn::native::Adapter selected;
    for (auto& adapter : adapters) {
        wgpu::Adapter api(adapter.Get());
        wgpu::AdapterInfo info{};
        Check(api.GetInfo(&info) == wgpu::Status::Success);
        if (info.adapterType != wgpu::AdapterType::CPU) {
            selected = adapter;
            break;
        }
    }
    Check(static_cast<bool>(selected));
    auto device = wgpu::Device::Acquire(selected.CreateDevice());
    Check(static_cast<bool>(device));
    auto queue = device.GetQueue();
    constexpr size_t count = 64;
    constexpr size_t bytes = count * sizeof(uint32_t);
    wgpu::BufferDescriptor storageDescriptor{};
    storageDescriptor.size = bytes;
    storageDescriptor.usage = wgpu::BufferUsage::Storage | wgpu::BufferUsage::CopySrc;
    auto storage = device.CreateBuffer(&storageDescriptor);
    wgpu::BufferDescriptor mapDescriptor{};
    mapDescriptor.size = bytes;
    mapDescriptor.usage = wgpu::BufferUsage::MapRead | wgpu::BufferUsage::CopyDst;
    auto readback = device.CreateBuffer(&mapDescriptor);
    wgpu::ShaderSourceWGSL source{};
    source.code = R"(
        @group(0) @binding(0) var<storage, read_write> values: array<u32>;
        @compute @workgroup_size(1) fn main(@builtin(global_invocation_id) id: vec3<u32>) {
            values[id.x] = (id.x * 17u) ^ 0x35a55a3u;
        }
    )";
    wgpu::ShaderModuleDescriptor shaderDescriptor{};
    shaderDescriptor.nextInChain = &source;
    auto shader = device.CreateShaderModule(&shaderDescriptor);
    wgpu::ComputePipelineDescriptor pipelineDescriptor{};
    pipelineDescriptor.compute.module = shader;
    pipelineDescriptor.compute.entryPoint = "main";
    auto pipeline = device.CreateComputePipeline(&pipelineDescriptor);
    wgpu::BindGroupEntry entry{};
    entry.binding = 0;
    entry.buffer = storage;
    entry.size = bytes;
    wgpu::BindGroupDescriptor groupDescriptor{};
    groupDescriptor.layout = pipeline.GetBindGroupLayout(0);
    groupDescriptor.entryCount = 1;
    groupDescriptor.entries = &entry;
    auto group = device.CreateBindGroup(&groupDescriptor);
    auto encoder = device.CreateCommandEncoder();
    auto pass = encoder.BeginComputePass();
    pass.SetPipeline(pipeline);
    pass.SetBindGroup(0, group);
    pass.DispatchWorkgroups(count);
    pass.End();
    encoder.CopyBufferToBuffer(storage, 0, readback, 0, bytes);
    auto commands = encoder.Finish();
    queue.Submit(1, &commands);
    std::atomic_bool done = false;
    std::atomic_bool mapped = false;
    readback.MapAsync(wgpu::MapMode::Read, 0, bytes, wgpu::CallbackMode::AllowSpontaneous,
        [&](wgpu::MapAsyncStatus status, wgpu::StringView) {
            mapped.store(status == wgpu::MapAsyncStatus::Success);
            done.store(true);
        });
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
    while (!done.load() && std::chrono::steady_clock::now() < deadline) {
        dawn::native::InstanceProcessEvents(instance.Get());
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    Check(done.load() && mapped.load());
    const auto* data = static_cast<const uint32_t*>(readback.GetConstMappedRange());
    Check(data != nullptr);
    for (size_t i = 0; i < count; ++i) Check(data[i] == ((i * 17u) ^ 0x35a55a3u));
    readback.Unmap();
    auto protectedAdapters = instance.EnumerateAdapters(&options);
    bool protectedExecuted = false;
    for (auto& adapter : protectedAdapters) {
        wgpu::Adapter api(adapter.Get());
        wgpu::AdapterInfo info{};
        Check(api.GetInfo(&info) == wgpu::Status::Success);
        if (info.adapterType != wgpu::AdapterType::CPU) {
            ProtectedScenario(instance, adapter);
            protectedExecuted = true;
            break;
        }
    }
    Check(protectedExecuted);
    std::puts("{\"passed\":true,\"hardware_adapter\":true,\"native_dawn_queue_executed\":true,"
              "\"baseline_compute_values\":64,\"glint_protected_inputs_tested\":true,"
              "\"browser_integrated\":false}");
}
