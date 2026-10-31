#include <array>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <source_location>
#include <thread>
#include <utility>
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
    const bool sampledRGBA = argc == 2 && std::strcmp(argv[1], "--sampled-rgba") == 0;
    const bool sampledBGRA = argc == 2 && std::strcmp(argv[1], "--sampled-bgra") == 0;
    const bool sampledMode = sampledRGBA || sampledBGRA;
    const bool indirectReadonly = argc == 2 && std::strcmp(argv[1], "--indirect-readonly") == 0;
    const bool indirectZero = argc == 2 && std::strcmp(argv[1], "--indirect-zero") == 0;
    const bool indirectOffset = argc == 2 && std::strcmp(argv[1], "--indirect-offset") == 0;
    const bool indirectMode = indirectReadonly || indirectZero || indirectOffset;
    const bool withoutFilter = argc == 2 && std::strcmp(argv[1], "--without-filter") == 0;
    const bool unsupportedFormat = argc == 2 && std::strcmp(argv[1], "--unsupported-format") == 0;
    const bool cancelMap = argc == 2 && std::strcmp(argv[1], "--cancel-map") == 0;
    const bool snapshotQuota = argc == 2 && std::strcmp(argv[1], "--snapshot-quota") == 0;
    const bool vertexDirect = argc == 2 && std::strcmp(argv[1], "--vertex-direct") == 0;
    const bool vertexBundle = argc == 2 && std::strcmp(argv[1], "--vertex-bundle") == 0;
    const bool vertexMode = vertexDirect || vertexBundle;
    const bool indexDirect = argc == 2 && std::strcmp(argv[1], "--index-direct") == 0;
    const bool indexBundle = argc == 2 && std::strcmp(argv[1], "--index-bundle") == 0;
    const bool indexMode = indexDirect || indexBundle;
    const bool writableDirect = argc == 2 && std::strcmp(argv[1], "--render-writable-direct") == 0;
    const bool writableBundle = argc == 2 && std::strcmp(argv[1], "--render-writable-bundle") == 0;
    const bool writableMode = writableDirect || writableBundle;
    const bool renderDirect = vertexDirect || indexDirect || writableDirect || (argc == 2 && std::strcmp(argv[1], "--render-direct") == 0);
    const bool renderBundle = vertexBundle || indexBundle || writableBundle || (argc == 2 && std::strcmp(argv[1], "--render-bundle") == 0);
    Check(argc == 1 || withoutFilter || unsupportedFormat || cancelMap || snapshotQuota || renderDirect || renderBundle || indirectMode || sampledMode);
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
    std::atomic_bool diagnosticLossObserved = false;
    wgpu::DeviceDescriptor deviceDescriptor{};
    deviceDescriptor.SetDeviceLostCallback(wgpu::CallbackMode::AllowSpontaneous,
        [&](const wgpu::Device&, wgpu::DeviceLostReason reason, wgpu::StringView message) {
            diagnosticLossObserved = true;
            if (reason != wgpu::DeviceLostReason::Destroyed)
                std::fprintf(stderr, "WIRE_NATIVE_DEVICE_LOST: %.*s\n",
                             static_cast<int>(message.length > 8192 ? 8192 : message.length), message.data);
        });
    deviceDescriptor.SetUncapturedErrorCallback(
        [](const wgpu::Device&, wgpu::ErrorType, wgpu::StringView message) {
            std::fprintf(stderr, "Wire device error: %.*s\n", static_cast<int>(message.length), message.data);
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
    textureDescriptor.format = sampledBGRA ? wgpu::TextureFormat::BGRA8Unorm : wgpu::TextureFormat::RGBA8Unorm;
    if (unsupportedFormat) textureDescriptor.format = wgpu::TextureFormat::RGBA8UnormSrgb;
    textureDescriptor.usage = wgpu::TextureUsage::CopySrc | wgpu::TextureUsage::CopyDst;
    if (sampledMode) textureDescriptor.usage |= wgpu::TextureUsage::TextureBinding;
    if (sampledBGRA) {
        for (size_t index = 0; index < packed; index += 4) {
            std::swap(pixels[index], pixels[index + 2]);
            std::swap(expected[index], expected[index + 2]);
        }
    }
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
    if (vertexMode) inputDescriptor.usage |= wgpu::BufferUsage::Vertex;
    if (indexMode) inputDescriptor.usage |= wgpu::BufferUsage::Index;
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
        if (!success) wait(diagnosticLossObserved);
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
    if (renderDirect || renderBundle) {
        wgpu::ShaderSourceWGSL renderSource{};
        renderSource.code = R"(
            @group(0) @binding(0) var<storage, read> pixels: array<u32>;
            @vertex fn vs(@builtin(vertex_index) id: u32) -> @builtin(position) vec4f {
                let positions = array<vec2f, 3>(vec2f(-1.0, -1.0), vec2f(3.0, -1.0), vec2f(-1.0, 3.0));
                return vec4f(positions[id], 0.0, 1.0);
            }
            @fragment fn fs() -> @location(0) vec4f {
                let p = pixels[0];
                return vec4f(f32(p & 255u), f32((p >> 8u) & 255u),
                             f32((p >> 16u) & 255u), f32((p >> 24u) & 255u)) / 255.0;
            }
        )";
        if (writableMode) {
            renderSource.code = R"(
                @group(0) @binding(0) var<storage, read_write> pixels: array<u32>;
                @vertex fn vs(@builtin(vertex_index) id: u32) -> @builtin(position) vec4f {
                    let positions = array<vec2f, 3>(vec2f(-1.0, -1.0), vec2f(3.0, -1.0), vec2f(-1.0, 3.0));
                    return vec4f(positions[id], 0.0, 1.0);
                }
                @fragment fn fs(@builtin(position) position: vec4f) -> @location(0) vec4f {
                    if (position.x < 1.0 && position.y < 1.0) {
                        pixels[0] = pixels[0] ^ 0x00112233u;
                    }
                    return vec4f(0.0, 0.0, 1.0, 1.0);
                }
            )";
        }
        if (vertexMode) {
            renderSource.code = R"(
                struct VertexOutput {
                    @builtin(position) position: vec4f,
                    @location(0) @interpolate(flat) pixel: u32,
                }
                @vertex fn vs(@location(0) pixel: u32, @builtin(vertex_index) id: u32) -> VertexOutput {
                    let positions = array<vec2f, 3>(vec2f(-1.0, -1.0), vec2f(3.0, -1.0), vec2f(-1.0, 3.0));
                    return VertexOutput(vec4f(positions[id], 0.0, 1.0), pixel);
                }
                @fragment fn fs(in: VertexOutput) -> @location(0) vec4f {
                    let p = in.pixel;
                    return vec4f(f32(p & 255u), f32((p >> 8u) & 255u),
                                 f32((p >> 16u) & 255u), f32((p >> 24u) & 255u)) / 255.0;
                }
            )";
        }
        if (indexMode) {
            renderSource.code = R"(
                struct VertexOutput {
                    @builtin(position) position: vec4f,
                    @location(0) @interpolate(flat) pixel: u32,
                }
                @vertex fn vs(@builtin(vertex_index) id: u32) -> VertexOutput {
                    return VertexOutput(vec4f(0.0, 0.0, 0.0, 1.0), id | 0xff000000u);
                }
                @fragment fn fs(in: VertexOutput) -> @location(0) vec4f {
                    let p = in.pixel;
                    return vec4f(f32(p & 255u), f32((p >> 8u) & 255u),
                                 f32((p >> 16u) & 255u), f32((p >> 24u) & 255u)) / 255.0;
                }
            )";
        }
        wgpu::ShaderModuleDescriptor renderShaderDescriptor{};
        renderShaderDescriptor.nextInChain = &renderSource;
        auto renderShader = device.CreateShaderModule(&renderShaderDescriptor);
        wgpu::ColorTargetState target{};
        target.format = wgpu::TextureFormat::RGBA8Unorm;
        wgpu::FragmentState fragment{};
        fragment.module = renderShader;
        fragment.entryPoint = "fs";
        fragment.targetCount = 1;
        fragment.targets = &target;
        wgpu::RenderPipelineDescriptor renderPipelineDescriptor{};
        renderPipelineDescriptor.vertex.module = renderShader;
        renderPipelineDescriptor.vertex.entryPoint = "vs";
        renderPipelineDescriptor.fragment = &fragment;
        renderPipelineDescriptor.primitive.topology = wgpu::PrimitiveTopology::TriangleList;
        if (indexMode) renderPipelineDescriptor.primitive.topology = wgpu::PrimitiveTopology::PointList;
        wgpu::VertexAttribute attribute{};
        attribute.format = wgpu::VertexFormat::Uint32;
        attribute.shaderLocation = 0;
        wgpu::VertexBufferLayout vertexLayout{};
        vertexLayout.arrayStride = 4;
        vertexLayout.stepMode = wgpu::VertexStepMode::Instance;
        vertexLayout.attributeCount = 1;
        vertexLayout.attributes = &attribute;
        if (vertexMode) {
            renderPipelineDescriptor.vertex.bufferCount = 1;
            renderPipelineDescriptor.vertex.buffers = &vertexLayout;
        }
        auto renderPipeline = device.CreateRenderPipeline(&renderPipelineDescriptor);
        wgpu::BindGroupEntry renderEntry{};
        renderEntry.binding = 0;
        renderEntry.buffer = input;
        renderEntry.size = bytes;
        wgpu::BindGroupDescriptor renderGroupDescriptor{};
        wgpu::BindGroup renderGroup;
        if (!vertexMode && !indexMode) {
            renderGroupDescriptor.layout = renderPipeline.GetBindGroupLayout(0);
            renderGroupDescriptor.entryCount = 1;
            renderGroupDescriptor.entries = &renderEntry;
            renderGroup = device.CreateBindGroup(&renderGroupDescriptor);
        }
        wgpu::TextureDescriptor renderTextureDescriptor{};
        const uint32_t renderWidth = indexMode ? 1 : width;
        const uint32_t renderHeight = indexMode ? 1 : height;
        renderTextureDescriptor.size = {renderWidth, renderHeight, 1};
        renderTextureDescriptor.format = target.format;
        renderTextureDescriptor.usage = wgpu::TextureUsage::RenderAttachment | wgpu::TextureUsage::CopySrc;
        auto renderTexture = device.CreateTexture(&renderTextureDescriptor);
        auto renderMap = device.CreateBuffer(&mapDescriptor);
        wgpu::RenderPassColorAttachment color{};
        color.view = renderTexture.CreateView();
        color.loadOp = wgpu::LoadOp::Clear;
        color.storeOp = wgpu::StoreOp::Store;
        color.clearValue = {0, 0, 0, 0};
        wgpu::RenderPassDescriptor passDescriptor{};
        passDescriptor.colorAttachmentCount = 1;
        passDescriptor.colorAttachments = &color;
        auto renderEncoder = device.CreateCommandEncoder();
        auto renderPass = renderEncoder.BeginRenderPass(&passDescriptor);
        if (renderBundle) {
            wgpu::RenderBundleEncoderDescriptor bundleDescriptor{};
            bundleDescriptor.colorFormatCount = 1;
            bundleDescriptor.colorFormats = &target.format;
            auto bundleEncoder = device.CreateRenderBundleEncoder(&bundleDescriptor);
            bundleEncoder.SetPipeline(renderPipeline);
            if (vertexMode) bundleEncoder.SetVertexBuffer(0, input, 0, bytes);
            else if (!indexMode) bundleEncoder.SetBindGroup(0, renderGroup);
            if (indexMode) {
                bundleEncoder.SetIndexBuffer(input, wgpu::IndexFormat::Uint16, 0, bytes);
                bundleEncoder.DrawIndexed(1);
            } else bundleEncoder.Draw(3);
            auto bundle = bundleEncoder.Finish();
            renderPass.ExecuteBundles(1, &bundle);
        } else {
            renderPass.SetPipeline(renderPipeline);
            if (vertexMode) renderPass.SetVertexBuffer(0, input, 0, bytes);
            else if (!indexMode) renderPass.SetBindGroup(0, renderGroup);
            if (indexMode) {
                renderPass.SetIndexBuffer(input, wgpu::IndexFormat::Uint16, 0, bytes);
                renderPass.DrawIndexed(1);
            } else renderPass.Draw(3);
        }
        renderPass.End();
        if (writableMode) renderEncoder.CopyBufferToBuffer(input, 0, readback, 0, bytes);
        wgpu::TexelCopyTextureInfo renderedCopy{};
        renderedCopy.texture = renderTexture;
        bufferCopy.buffer = renderMap;
        wgpu::Extent3D renderExtent{renderWidth, renderHeight, 1};
        renderEncoder.CopyTextureToBuffer(&renderedCopy, &bufferCopy, &renderExtent);
        auto renderCommands = renderEncoder.Finish();
        queue.Submit(1, &renderCommands);
        auto rendered = wireRead(renderMap, bytes);
        std::vector<uint8_t> renderExpected(renderWidth * renderHeight * 4);
        for (size_t i = 0; i < renderExpected.size(); ++i) renderExpected[i] = expected[i % 4];
        if (writableMode) {
            for (size_t i = 0; i < renderExpected.size(); ++i)
                renderExpected[i] = (i % 4 >= 2) ? 255 : 0;
        }
        if (indexMode) {
            renderExpected[2] = 0;
            renderExpected[3] = 255;
        }
        Check(glint::candidate::TransformEdgeCoherentCanvas(renderExpected, renderWidth, renderHeight, seed));
        for (uint32_t y = 0; y < renderHeight; ++y)
            for (uint32_t x = 0; x < renderWidth * 4; ++x) {
                if (rendered[y * pitch + x] != renderExpected[y * renderWidth * 4 + x])
                    std::fprintf(stderr, "Render mismatch row=%u byte=%u actual=%u expected=%u\n",
                                 y, x, rendered[y * pitch + x], renderExpected[y * renderWidth * 4 + x]);
                Check(rendered[y * pitch + x] == renderExpected[y * renderWidth * 4 + x]);
            }
        renderMap.Destroy();
        renderTexture.Destroy();
        if (writableMode) {
            uint32_t first = 0;
            std::memcpy(&first, expected.data(), 4);
            first ^= 0x00112233u;
            std::memcpy(expected.data(), &first, 4);
            auto copiedBack = wireRead(readback, bytes);
            for (uint32_t y = 0; y < height; ++y)
                for (uint32_t x = 0; x < pitch; ++x) {
                    const uint8_t wanted = x < width * 4 ? expected[y * width * 4 + x] : 0;
                    if (copiedBack[y * pitch + x] != wanted)
                        std::fprintf(stderr, "Render copyback mismatch row=%u byte=%u actual=%u expected=%u\n",
                                     y, x, copiedBack[y * pitch + x], wanted);
                    Check(copiedBack[y * pitch + x] == wanted);
                }
        }
    }
    wgpu::BufferDescriptor outputDescriptor{};
    outputDescriptor.size = packed;
    outputDescriptor.usage = wgpu::BufferUsage::Storage | wgpu::BufferUsage::CopySrc | wgpu::BufferUsage::CopyDst;
    auto output = device.CreateBuffer(&outputDescriptor);
    // A zero-work indirect command must not modify or project unrelated output.
    std::array<uint32_t, width * height> initialOutput{};
    initialOutput.fill(0x31415926u);
    queue.WriteBuffer(output, 0, initialOutput.data(), sizeof(initialOutput));
    wgpu::Buffer indirect;
    const uint64_t indirectByteOffset = indirectOffset ? 16 : 0;
    if (indirectMode) {
        wgpu::BufferDescriptor descriptor{};
        descriptor.size = indirectByteOffset + 3 * sizeof(uint32_t);
        descriptor.usage = wgpu::BufferUsage::Indirect | wgpu::BufferUsage::CopyDst;
        indirect = device.CreateBuffer(&descriptor);
        const std::array<uint32_t, 3> arguments{indirectZero ? 0u : width * height, 1, 1};
        queue.WriteBuffer(indirect, indirectByteOffset, arguments.data(), sizeof(arguments));
    }
    mapDescriptor.size = packed;
    auto outputMap = device.CreateBuffer(&mapDescriptor);
    wgpu::ShaderSourceWGSL source{};
    source.code = sampledMode ? R"(
        @group(0) @binding(0) var pixels: texture_2d<f32>;
        @group(0) @binding(1) var<storage, read_write> output: array<u32>;
        @compute @workgroup_size(1) fn main(@builtin(global_invocation_id) id: vec3<u32>) {
            let p = vec4u(round(textureLoad(pixels, vec2i(i32(id.x % 8u), i32(id.x / 8u)), 0) * 255.0));
            output[id.x] = (p.r | (p.g << 8u) | (p.b << 16u) | (p.a << 24u)) ^ 0xa1b2c3d4u;
        }
    )" : R"(
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
    if (sampledMode) entries[0].textureView = texture.CreateView();
    else {
        entries[0].buffer = input;
        entries[0].size = bytes;
    }
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
    if (indirectMode) pass.DispatchWorkgroupsIndirect(indirect, indirectByteOffset);
    else pass.DispatchWorkgroups(width * height);
    pass.End();
    computeEncoder.CopyBufferToBuffer(output, 0, outputMap, 0, packed);
    auto computeCommands = computeEncoder.Finish();
    queue.Submit(1, &computeCommands);
    auto transformed = wireRead(outputMap, packed);
    for (size_t i = 0; i < width * height; ++i) {
        uint32_t wanted = 0, got = 0;
        std::array<uint8_t, 4> semantic{};
        std::memcpy(semantic.data(), expected.data() + i * 4, 4);
        if (sampledBGRA) std::swap(semantic[0], semantic[2]);
        std::memcpy(&wanted, semantic.data(), 4);
        std::memcpy(&got, transformed.data() + i * 4, 4);
        Check(got == (indirectZero ? initialOutput[i] : (wanted ^ 0xa1b2c3d4u)));
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
    if (indirect) indirect.Destroy();
    outputMap.Destroy();
    plainInput.Destroy();
    plainMap.Destroy();
    readback.Destroy();
    device.Destroy();
    pump();
    requireBudgetDrained();
    std::printf("{\"passed\":true,\"actual_wire_client_server_executed\":true,"
                "\"native_d3d12_queue_executed\":true,\"protected_channels\":%zu,"
                "\"projected_compute_values\":%zu,\"unrelated_values\":16,\"repeated_map\":true,"
                "\"capture_budget_limit_bytes\":%llu,\"capture_bytes_after_first_map\":%llu,"
                "\"capture_bytes_after_destroy\":%llu,"
                "\"render_pass_executed\":%s,\"render_bundle_executed\":%s,"
                "\"vertex_buffer_executed\":%s,"
                "\"index_buffer_executed\":%s,"
                "\"render_writable_copyback_executed\":%s,"
                "\"sampled_texture_executed\":%s,\"sampled_bgra_executed\":%s,\"indirect_dispatch_executed\":%s,\"zero_work_output_unchanged\":%s,\"indirect_offset_bytes\":%llu,\"observer_delivery_called_manually\":false,\"browser_integrated\":false}\n", changed,
                indirectZero ? size_t{0} : size_t{width * height},
                static_cast<unsigned long long>(budget->limit_bytes()),
                static_cast<unsigned long long>(bytesAfterFirstMap),
                static_cast<unsigned long long>(budget->used_bytes()),
                renderDirect || renderBundle ? "true" : "false", renderBundle ? "true" : "false",
                vertexMode ? "true" : "false", indexMode ? "true" : "false",
                writableMode ? "true" : "false", sampledMode ? "true" : "false",
                sampledBGRA ? "true" : "false", indirectMode ? "true" : "false",
                indirectZero ? "true" : "false", static_cast<unsigned long long>(indirectByteOffset));
}
