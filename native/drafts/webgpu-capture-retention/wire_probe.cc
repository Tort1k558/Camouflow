#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <source_location>
#include <thread>
#include <vector>

#include "dawn/dawn_proc.h"
#include "dawn/native/DawnNative.h"
#include "dawn/wire/WireClient.h"
#include "dawn/wire/WireServer.h"
#include "gpu/command_buffer/common/glint/canvas_readback_candidate.h"
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
#include "gpu/command_buffer/service/glint_webgpu_wire_filter.h"
#include "src/dawn/utils/TerribleCommandBuffer.h"
#include "src/dawn/native/d3d12/DeviceD3D12.h"
#include "src/dawn/native/d3d12/glint/texture_capture.h"
#include "webgpu/webgpu_cpp.h"

void Check(bool value, std::source_location location = std::source_location::current()) {
    if (!value) {
        std::fprintf(stderr, "Wire hardware probe failed at line %u\n", location.line());
        std::exit(1);
    }
}

int main(int argc, char** argv) {
    const bool withoutFilter = argc == 2 && std::strcmp(argv[1], "--without-filter") == 0;
    const bool unsupportedFormat = argc == 2 && std::strcmp(argv[1], "--unsupported-format") == 0;
    const bool cancelMap = argc == 2 && std::strcmp(argv[1], "--cancel-map") == 0;
    const bool snapshotQuota = argc == 2 && std::strcmp(argv[1], "--snapshot-quota") == 0;
    Check(argc == 1 || withoutFilter || unsupportedFormat || cancelMap || snapshotQuota);
    const bool expectDenied = unsupportedFormat || cancelMap || snapshotQuota;
    dawnProcSetProcs(&dawn::native::GetProcs());
    dawn::native::Instance nativeInstance;
    auto toServer = std::make_unique<dawn::utils::TerribleCommandBuffer>();
    auto toClient = std::make_unique<dawn::utils::TerribleCommandBuffer>();
    dawn::wire::WireServerDescriptor serverDescriptor{};
    serverDescriptor.procs = &dawn::native::GetProcs();
    serverDescriptor.serializer = toClient.get();
    if (!withoutFilter) {
        serverDescriptor.bufferReadbackFilterFactory =
            gpu::webgpu::CreateGlintWebGPUReadbackFilterFactory();
    }
    auto server = std::make_unique<dawn::wire::WireServer>(serverDescriptor);
    dawn::wire::WireClientDescriptor clientDescriptor{};
    clientDescriptor.serializer = toServer.get();
    auto client = std::make_unique<dawn::wire::WireClient>(clientDescriptor);
    toServer->SetHandler(server.get());
    toClient->SetHandler(client.get());
    auto reservation = client->ReserveInstance();
    Check(server->InjectInstance(nativeInstance.Get(), reservation.handle));
    struct RestoreNativeProcs {
        ~RestoreNativeProcs() { dawnProcSetProcs(&dawn::native::GetProcs()); }
    } restore;
    dawnProcSetProcs(&dawn::wire::client::GetProcs());
    auto instance = wgpu::Instance::Acquire(reservation.instance);
    auto pump = [&] {
        Check(toServer->Flush());
        dawn::native::InstanceProcessEvents(nativeInstance.Get());
        Check(toClient->Flush());
        instance.ProcessEvents();
    };
    auto wait = [&](std::atomic_bool& done) {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
        while (!done.load() && std::chrono::steady_clock::now() < deadline) {
            pump();
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        Check(done.load());
    };
    std::atomic_bool adapterDone = false;
    wgpu::Adapter adapter;
    wgpu::RequestAdapterOptions options{};
    options.backendType = wgpu::BackendType::D3D12;
    instance.RequestAdapter(&options, wgpu::CallbackMode::AllowSpontaneous,
        [&](wgpu::RequestAdapterStatus status, wgpu::Adapter result, wgpu::StringView message) {
            if (status != wgpu::RequestAdapterStatus::Success)
                std::fprintf(stderr, "Wire adapter: %.*s\n", static_cast<int>(message.length), message.data);
            adapter = std::move(result);
            adapterDone = true;
        });
    wait(adapterDone);
    Check(static_cast<bool>(adapter));
    wgpu::AdapterInfo info{};
    Check(adapter.GetInfo(&info) == wgpu::Status::Success);
    Check(info.adapterType != wgpu::AdapterType::CPU);
    std::atomic_bool deviceDone = false;
    wgpu::Device device;
    wgpu::DeviceDescriptor deviceDescriptor{};
    deviceDescriptor.SetUncapturedErrorCallback(
        [](const wgpu::Device&, wgpu::ErrorType, wgpu::StringView message) {
            std::fprintf(stderr, "Wire device error: %.*s\n", static_cast<int>(message.length), message.data);
            Check(false);
        });
    adapter.RequestDevice(&deviceDescriptor, wgpu::CallbackMode::AllowSpontaneous,
        [&](wgpu::RequestDeviceStatus status, wgpu::Device result, wgpu::StringView message) {
            if (status != wgpu::RequestDeviceStatus::Success)
                std::fprintf(stderr, "Wire device: %.*s\n", static_cast<int>(message.length), message.data);
            device = std::move(result);
            deviceDone = true;
        });
    wait(deviceDone);
    Check(static_cast<bool>(device));
    auto handle = client->GetWireHandle(device.Get());
    auto nativeDevice = server->GetDevice(handle.id, handle.generation);
    Check(nativeDevice != nullptr);
    auto budget = dawn::native::d3d12::ToBackend(dawn::native::FromAPI(nativeDevice))->GetGlintReadbackBudget();
    Check(budget != nullptr && budget->used_bytes() == 0);
    auto requireBudgetDrained = [&] {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
        while (budget->used_bytes() != 0 && std::chrono::steady_clock::now() < deadline) {
            dawn::native::DeviceTick(nativeDevice);
            pump();
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        if (budget->used_bytes())
            std::fprintf(stderr, "Unretired native capture bytes: %llu\n",
                         static_cast<unsigned long long>(budget->used_bytes()));
        Check(budget->used_bytes() == 0);
    };
    std::array<uint8_t, 32> seed{};
    seed.fill(37);
    auto policy = gpu::webgpu::GlintWebGPUDevicePolicy::Create(1, seed);
    Check(policy.has_value());
    auto observer = std::make_shared<gpu::webgpu::GlintWebGPUReadbackObserver>(
        std::make_shared<gpu::webgpu::GlintWebGPUDevicePolicy>(std::move(*policy)), 1,
        gpu::webgpu::GlintReadbackLimits{});
    Check(dawn::native::InstallGlintReadbackObserver(nativeDevice, observer));
    constexpr uint32_t width = 8, height = 8, pitch = 256;
    constexpr size_t packed = width * height * 4, bytes = pitch * height;
    std::vector<uint8_t> pixels(packed);
    for (uint32_t y = 0; y < height; ++y)
        for (uint32_t x = 0; x < width; ++x)
            for (uint32_t c = 0; c < 4; ++c)
                pixels[(y * width + x) * 4 + c] = c == 3 ? 255 :
                    static_cast<uint8_t>(x * 17 + y * 31 + c * 53);
    auto expected = pixels;
    Check(glint::candidate::TransformEdgeCoherentCanvas(expected, width, height, seed));
    wgpu::TextureDescriptor textureDescriptor{};
    textureDescriptor.size = {width, height, 1};
    textureDescriptor.format = wgpu::TextureFormat::RGBA8Unorm;
    if (unsupportedFormat) textureDescriptor.format = wgpu::TextureFormat::RGBA8UnormSrgb;
    textureDescriptor.usage = wgpu::TextureUsage::CopySrc | wgpu::TextureUsage::CopyDst;
    auto texture = device.CreateTexture(&textureDescriptor);
    wgpu::TexelCopyTextureInfo textureCopy{};
    textureCopy.texture = texture;
    wgpu::TexelCopyBufferLayout upload{};
    upload.bytesPerRow = width * 4;
    upload.rowsPerImage = height;
    wgpu::Extent3D extent{width, height, 1};
    auto queue = device.GetQueue();
    queue.WriteTexture(&textureCopy, pixels.data(), pixels.size(), &upload, &extent);
    wgpu::BufferDescriptor mapDescriptor{};
    mapDescriptor.size = bytes;
    mapDescriptor.usage = wgpu::BufferUsage::CopyDst | wgpu::BufferUsage::MapRead;
    auto readback = device.CreateBuffer(&mapDescriptor);
    auto originalReadback = readback;
    wgpu::BufferDescriptor inputDescriptor{};
    inputDescriptor.size = bytes;
    inputDescriptor.usage = wgpu::BufferUsage::CopySrc | wgpu::BufferUsage::CopyDst |
                            wgpu::BufferUsage::Storage;
    auto input = device.CreateBuffer(&inputDescriptor);
    wgpu::TexelCopyBufferInfo bufferCopy{};
    bufferCopy.buffer = input;
    bufferCopy.layout.bytesPerRow = pitch;
    bufferCopy.layout.rowsPerImage = height;
    auto encoder = device.CreateCommandEncoder();
    encoder.CopyTextureToBuffer(&textureCopy, &bufferCopy, &extent);
    encoder.CopyBufferToBuffer(input, 0, readback, 0, bytes);
    std::vector<wgpu::Buffer> quotaBuffers;
    if (snapshotQuota) {
        for (size_t i = 0; i < 16; ++i) {
            quotaBuffers.push_back(device.CreateBuffer(&mapDescriptor));
            bufferCopy.buffer = quotaBuffers.back();
            encoder.CopyTextureToBuffer(&textureCopy, &bufferCopy, &extent);
        }
        readback = quotaBuffers.back();
    }
    auto commands = encoder.Finish();
    queue.Submit(1, &commands);
    std::atomic_bool mapDone = false;
    bool mapped = false;
    wgpu::MapAsyncStatus mapStatus = wgpu::MapAsyncStatus::CallbackCancelled;
    readback.MapAsync(wgpu::MapMode::Read, 0, bytes, wgpu::CallbackMode::AllowSpontaneous,
        [&](wgpu::MapAsyncStatus status, wgpu::StringView message) {
            if (!expectDenied && status != wgpu::MapAsyncStatus::Success)
                std::fprintf(stderr, "Wire map: %.*s\n", static_cast<int>(message.length), message.data);
            mapStatus = status;
            mapped = status == wgpu::MapAsyncStatus::Success;
            mapDone = true;
        });
    if (cancelMap) {
        Check(toServer->Flush());
        readback.Destroy();
    }
    wait(mapDone);
    Check(budget->used_bytes() <= budget->limit_bytes());
    const auto bytesAfterFirstMap = budget->used_bytes();
    if (expectDenied) {
        Check(!mapped);
        Check(mapStatus == (cancelMap ? wgpu::MapAsyncStatus::Aborted : wgpu::MapAsyncStatus::Error));
        Check(readback.GetMapState() == wgpu::BufferMapState::Unmapped);
        Check(observer->IsHealthy());
        for (auto& buffer : quotaBuffers) buffer.Destroy();
        input.Destroy();
        originalReadback.Destroy();
        readback.Destroy();
        pump();
        bool slotsReused = false;
        if (snapshotQuota) {
            auto fresh = device.CreateBuffer(&mapDescriptor);
            bufferCopy.buffer = fresh;
            auto freshEncoder = device.CreateCommandEncoder();
            freshEncoder.CopyTextureToBuffer(&textureCopy, &bufferCopy, &extent);
            auto freshCommands = freshEncoder.Finish();
            queue.Submit(1, &freshCommands);
            std::atomic_bool freshDone = false;
            bool freshMapped = false;
            fresh.MapAsync(wgpu::MapMode::Read, 0, bytes, wgpu::CallbackMode::AllowSpontaneous,
                [&](wgpu::MapAsyncStatus status, wgpu::StringView) {
                    freshMapped = status == wgpu::MapAsyncStatus::Success;
                    freshDone = true;
                });
            wait(freshDone);
            Check(freshMapped);
            auto* data = static_cast<const uint8_t*>(fresh.GetConstMappedRange());
            Check(data != nullptr);
            for (uint32_t y = 0; y < height; ++y)
                for (uint32_t x = 0; x < width * 4; ++x)
                    Check(data[y * pitch + x] == expected[y * width * 4 + x]);
            fresh.Unmap();
            fresh.Destroy();
            slotsReused = true;
        }
        Check(observer->IsHealthy());
        device.Destroy();
        pump();
        requireBudgetDrained();
        std::printf("{\"passed\":true,\"actual_wire_client_server_executed\":true,"
                    "\"denied_mapping\":true,\"raw_pixels_exposed\":false,"
                    "\"capture_budget_limit_bytes\":%llu,\"capture_bytes_after_first_map\":%llu,"
                    "\"capture_bytes_after_destroy\":%llu,"
                    "\"snapshot_slots_reused\":%s,\"browser_integrated\":false}\n",
                    static_cast<unsigned long long>(budget->limit_bytes()),
                    static_cast<unsigned long long>(bytesAfterFirstMap),
                    static_cast<unsigned long long>(budget->used_bytes()),
                    slotsReused ? "true" : "false");
        return 0;
    }
    Check(mapped);
    Check(budget->used_bytes() != 0);
    const auto* actual = static_cast<const uint8_t*>(readback.GetConstMappedRange());
    Check(actual != nullptr);
    size_t changed = 0;
    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width * 4; ++x) {
            if (actual[y * pitch + x] != expected[y * width * 4 + x]) {
                std::fprintf(stderr, "WIRE_FILTER_MISMATCH row=%u byte=%u actual=%u expected=%u raw=%u\n",
                             y, x, actual[y * pitch + x], expected[y * width * 4 + x],
                             pixels[y * width * 4 + x]);
            }
            Check(actual[y * pitch + x] == expected[y * width * 4 + x]);
            changed += actual[y * pitch + x] != pixels[y * width * 4 + x];
        }
    }
    Check(changed == 100 && observer->IsHealthy());
    readback.Unmap();
    auto wireRead = [&](const wgpu::Buffer& buffer, size_t count) {
        std::atomic_bool done = false;
        bool success = false;
        buffer.MapAsync(wgpu::MapMode::Read, 0, count, wgpu::CallbackMode::AllowSpontaneous,
            [&](wgpu::MapAsyncStatus status, wgpu::StringView message) {
                if (status != wgpu::MapAsyncStatus::Success)
                    std::fprintf(stderr, "Wire remap: %.*s\n", static_cast<int>(message.length), message.data);
                success = status == wgpu::MapAsyncStatus::Success;
                done = true;
            });
        wait(done);
        Check(success);
        auto* data = static_cast<const uint8_t*>(buffer.GetConstMappedRange());
        Check(data != nullptr);
        std::vector<uint8_t> result(data, data + count);
        buffer.Unmap();
        return result;
    };
    auto repeated = wireRead(readback, bytes);
    for (uint32_t y = 0; y < height; ++y)
        for (uint32_t x = 0; x < width * 4; ++x)
            Check(repeated[y * pitch + x] == expected[y * width * 4 + x]);
    wgpu::BufferDescriptor outputDescriptor{};
    outputDescriptor.size = packed;
    outputDescriptor.usage = wgpu::BufferUsage::Storage | wgpu::BufferUsage::CopySrc;
    auto output = device.CreateBuffer(&outputDescriptor);
    mapDescriptor.size = packed;
    auto outputMap = device.CreateBuffer(&mapDescriptor);
    wgpu::ShaderSourceWGSL source{};
    source.code = R"(
        @group(0) @binding(0) var<storage, read> pixels: array<u32>;
        @group(0) @binding(1) var<storage, read_write> output: array<u32>;
        @compute @workgroup_size(1) fn main(@builtin(global_invocation_id) id: vec3<u32>) {
            output[id.x] = pixels[(id.x / 8u) * 64u + (id.x % 8u)] ^ 0xa1b2c3d4u;
        }
    )";
    wgpu::ShaderModuleDescriptor shaderDescriptor{};
    shaderDescriptor.nextInChain = &source;
    auto shader = device.CreateShaderModule(&shaderDescriptor);
    wgpu::ComputePipelineDescriptor pipelineDescriptor{};
    pipelineDescriptor.compute.module = shader;
    pipelineDescriptor.compute.entryPoint = "main";
    auto pipeline = device.CreateComputePipeline(&pipelineDescriptor);
    std::array<wgpu::BindGroupEntry, 2> entries{};
    entries[0].binding = 0;
    entries[0].buffer = input;
    entries[0].size = bytes;
    entries[1].binding = 1;
    entries[1].buffer = output;
    entries[1].size = packed;
    wgpu::BindGroupDescriptor groupDescriptor{};
    groupDescriptor.layout = pipeline.GetBindGroupLayout(0);
    groupDescriptor.entryCount = entries.size();
    groupDescriptor.entries = entries.data();
    auto group = device.CreateBindGroup(&groupDescriptor);
    auto computeEncoder = device.CreateCommandEncoder();
    auto pass = computeEncoder.BeginComputePass();
    pass.SetPipeline(pipeline);
    pass.SetBindGroup(0, group);
    pass.DispatchWorkgroups(width * height);
    pass.End();
    computeEncoder.CopyBufferToBuffer(output, 0, outputMap, 0, packed);
    auto computeCommands = computeEncoder.Finish();
    queue.Submit(1, &computeCommands);
    auto transformed = wireRead(outputMap, packed);
    for (size_t i = 0; i < width * height; ++i) {
        uint32_t wanted = 0, got = 0;
        std::memcpy(&wanted, expected.data() + i * 4, 4);
        std::memcpy(&got, transformed.data() + i * 4, 4);
        Check(got == (wanted ^ 0xa1b2c3d4u));
    }
    std::array<uint32_t, 16> plain{};
    for (size_t i = 0; i < plain.size(); ++i) plain[i] = static_cast<uint32_t>(i * 1234567u);
    inputDescriptor.size = sizeof(plain);
    auto plainInput = device.CreateBuffer(&inputDescriptor);
    mapDescriptor.size = sizeof(plain);
    auto plainMap = device.CreateBuffer(&mapDescriptor);
    queue.WriteBuffer(plainInput, 0, plain.data(), sizeof(plain));
    auto plainEncoder = device.CreateCommandEncoder();
    plainEncoder.CopyBufferToBuffer(plainInput, 0, plainMap, 0, sizeof(plain));
    auto plainCommands = plainEncoder.Finish();
    queue.Submit(1, &plainCommands);
    auto plainBytes = wireRead(plainMap, sizeof(plain));
    Check(std::memcmp(plainBytes.data(), plain.data(), sizeof(plain)) == 0);
    Check(observer->IsHealthy());
    input.Destroy();
    output.Destroy();
    outputMap.Destroy();
    plainInput.Destroy();
    plainMap.Destroy();
    readback.Destroy();
    device.Destroy();
    pump();
    requireBudgetDrained();
    std::printf("{\"passed\":true,\"actual_wire_client_server_executed\":true,"
                "\"native_d3d12_queue_executed\":true,\"protected_channels\":%zu,"
                "\"projected_compute_values\":64,\"unrelated_values\":16,\"repeated_map\":true,"
                "\"capture_budget_limit_bytes\":%llu,\"capture_bytes_after_first_map\":%llu,"
                "\"capture_bytes_after_destroy\":%llu,"
                "\"observer_delivery_called_manually\":false,\"browser_integrated\":false}\n", changed,
                static_cast<unsigned long long>(budget->limit_bytes()),
                static_cast<unsigned long long>(bytesAfterFirstMap),
                static_cast<unsigned long long>(budget->used_bytes()));
}
