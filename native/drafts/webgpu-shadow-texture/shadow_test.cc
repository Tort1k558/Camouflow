// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include "projected_texture.h"
#include <d3dcompiler.h>
#include <dxgi1_6.h>
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "gpu/command_buffer/common/glint/canvas_readback_candidate.h"

using Microsoft::WRL::ComPtr;
using glint::candidate::d3d12::ProjectedTexture;
using glint::candidate::d3d12::CaptureMemoryBudget;
using glint::candidate::d3d12::TextureCapture;
size_t assertions = 0, cases = 0, quota_cases = 0;
void Check(bool valid, int line) {
    ++assertions;
    if (!valid) { std::fprintf(stderr, "shadow assertion %d\n", line); std::exit(1); }
}
#define CHECK(x) Check((x), __LINE__)
void OkImpl(HRESULT value, int line) {
    if (FAILED(value)) std::fprintf(stderr, "shadow HRESULT %08lx at %d\n", static_cast<unsigned long>(value), line);
    CHECK(SUCCEEDED(value));
}
#define Ok(x) OkImpl((x), __LINE__)
ComPtr<ID3D12Resource> Buffer(ID3D12Device* device, size_t bytes, D3D12_HEAP_TYPE type,
                             D3D12_RESOURCE_STATES state, bool uav = false) {
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    desc.Width = bytes;
    desc.Height = desc.DepthOrArraySize = desc.MipLevels = 1;
    desc.SampleDesc.Count = 1;
    desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    desc.Flags = uav ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE;
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = type; heap.CreationNodeMask = heap.VisibleNodeMask = 1;
    ComPtr<ID3D12Resource> result;
    Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc, state,
                                       nullptr, IID_PPV_ARGS(&result)));
    return result;
}
void Transition(ID3D12GraphicsCommandList* cmd, ID3D12Resource* resource,
                D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after) {
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = resource;
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = before; barrier.Transition.StateAfter = after;
    cmd->ResourceBarrier(1, &barrier);
}
ComPtr<ID3DBlob> Compile(const char* file, const char* entry) {
    std::ifstream stream(file, std::ios::binary);
    CHECK(stream.good());
    const std::string source{std::istreambuf_iterator<char>(stream), {}};
    ComPtr<ID3DBlob> code, errors;
    const HRESULT status = D3DCompile(source.data(), source.size(), "glint-shadow", nullptr, nullptr,
        entry, "cs_5_0", D3DCOMPILE_ENABLE_STRICTNESS | D3DCOMPILE_WARNINGS_ARE_ERRORS,
        0, &code, &errors);
    if (errors) std::fwrite(errors->GetBufferPointer(), 1, errors->GetBufferSize(), stderr);
    Ok(status);
    return code;
}
struct Fixture {
    ComPtr<ID3D12Device> device;
    ComPtr<ID3D12RootSignature> root;
    ComPtr<ID3D12PipelineState> projection, consumer;
    Fixture(const char* edge_file, const char* consumer_file) {
        const auto edge = Compile(edge_file, "edge_main");
        const auto sample = Compile(consumer_file, "main");
        ComPtr<IDXGIFactory6> factory;
        Ok(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)));
        ComPtr<IDXGIAdapter1> adapter;
        Ok(factory->EnumAdapterByGpuPreference(0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, IID_PPV_ARGS(&adapter)));
        DXGI_ADAPTER_DESC1 adapter_desc{};
        Ok(adapter->GetDesc1(&adapter_desc));
        CHECK((adapter_desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) == 0);
        Ok(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&device)));
        D3D12_DESCRIPTOR_RANGE ranges[2]{};
        ranges[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
        ranges[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_UAV;
        D3D12_ROOT_PARAMETER params[3]{};
        for (size_t i = 0; i < 2; ++i) {
            ranges[i].NumDescriptors = 1;
            params[i].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
            params[i].DescriptorTable.NumDescriptorRanges = 1;
            params[i].DescriptorTable.pDescriptorRanges = &ranges[i];
        }
        params[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
        params[2].Constants.Num32BitValues = 16;
        D3D12_ROOT_SIGNATURE_DESC desc{};
        desc.NumParameters = 3; desc.pParameters = params;
        ComPtr<ID3DBlob> serialized, errors;
        Ok(D3D12SerializeRootSignature(&desc, D3D_ROOT_SIGNATURE_VERSION_1, &serialized, &errors));
        Ok(device->CreateRootSignature(0, serialized->GetBufferPointer(), serialized->GetBufferSize(), IID_PPV_ARGS(&root)));
        D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline{};
        pipeline.pRootSignature = root.Get();
        pipeline.CS = {edge->GetBufferPointer(), edge->GetBufferSize()};
        Ok(device->CreateComputePipelineState(&pipeline, IID_PPV_ARGS(&projection)));
        pipeline.CS = {sample->GetBufferPointer(), sample->GetBufferSize()};
        Ok(device->CreateComputePipelineState(&pipeline, IID_PPV_ARGS(&consumer)));
    }
};

void Run(Fixture& fixture, DXGI_FORMAT storage_format, uint32_t width, uint32_t height,
          bool cancel_cpu_owner) {
    auto* device = fixture.device.Get();
    const bool bgra = storage_format == DXGI_FORMAT_B8G8R8A8_UNORM || storage_format == DXGI_FORMAT_B8G8R8A8_TYPELESS;
    const DXGI_FORMAT view_format = bgra ? DXGI_FORMAT_B8G8R8A8_UNORM : DXGI_FORMAT_R8G8B8A8_UNORM;
    D3D12_RESOURCE_DESC texture_desc{};
    texture_desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    texture_desc.Width = width; texture_desc.Height = height;
    texture_desc.DepthOrArraySize = texture_desc.MipLevels = 1;
    texture_desc.Format = storage_format;
    texture_desc.SampleDesc.Count = 1;
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = D3D12_HEAP_TYPE_DEFAULT; heap.CreationNodeMask = heap.VisibleNodeMask = 1;
    ComPtr<ID3D12Resource> original;
    Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &texture_desc,
        D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&original)));
    auto copy_desc = texture_desc;
    copy_desc.Format = view_format;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT rows = 0; UINT64 row_bytes = 0, total = 0;
    device->GetCopyableFootprints(&copy_desc, 0, 1, 0, &footprint, &rows, &row_bytes, &total);
    CHECK(rows == height && row_bytes == width * 4);
    const size_t bytes = static_cast<size_t>(footprint.Footprint.RowPitch) * height;
    std::vector<uint8_t> packed(static_cast<size_t>(width) * height * 4);
    std::vector<uint8_t> upload_bytes(bytes, 0xa7);
    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width; ++x) {
            for (uint32_t c = 0; c < 4; ++c) {
                const uint8_t value = c == 3 ? static_cast<uint8_t>((x + y) % 5 == 0 ? 128 : 255)
                    : static_cast<uint8_t>(x * 17 + y * 31 + c * 53);
                packed[(static_cast<size_t>(y) * width + x) * 4 + c] = value;
                const uint32_t native_c = bgra && c != 1 && c != 3 ? 2 - c : c;
                upload_bytes[y * footprint.Footprint.RowPitch + x * 4 + native_c] = value;
            }
        }
    }
    std::array<uint8_t, 32> key{}; key.fill(37);
    auto expected = packed;
    CHECK(glint::candidate::TransformEdgeCoherentCanvas(expected, width, height, key));
    auto upload = Buffer(device, bytes, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    auto original_probe = Buffer(device, bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST);
    auto original_readback = Buffer(device, bytes, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    const size_t pixel_bytes = packed.size();
    auto output = Buffer(device, pixel_bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_UNORDERED_ACCESS, true);
    auto readback = Buffer(device, pixel_bytes, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    void* mapped = nullptr; const D3D12_RANGE no_read{0, 0};
    Ok(upload->Map(0, &no_read, &mapped));
    std::memcpy(mapped, upload_bytes.data(), bytes); upload->Unmap(0, nullptr);
    ComPtr<ID3D12CommandQueue> queue;
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    Ok(device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue)));
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> cmd;
    ComPtr<ID3D12Fence> fence;
    Ok(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator)));
    Ok(device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), nullptr, IID_PPV_ARGS(&cmd)));
    Ok(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)));
    D3D12_TEXTURE_COPY_LOCATION from{}, to{};
    from.pResource = upload.Get(); from.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    from.PlacedFootprint = footprint;
    to.pResource = original.Get(); to.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    cmd->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
    Transition(cmd.Get(), original.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_COPY_SOURCE);
    auto budget = std::make_shared<CaptureMemoryBudget>(64 * 1024 * 1024);
    std::unique_ptr<ProjectedTexture> projected;
    auto record = [&](const std::shared_ptr<CaptureMemoryBudget>& target, bool initialized,
                      DXGI_FORMAT format, uint64_t serial) {
        return ProjectedTexture::Record(device, cmd.Get(), original.Get(), format, initialized,
            fixture.root.Get(), fixture.projection.Get(), key, fence.Get(), serial, target, &projected);
    };
    CHECK(record(budget, false, view_format, 1) == E_INVALIDARG && !projected && budget->used_bytes() == 0);
    CHECK(record(budget, true, DXGI_FORMAT_R8G8B8A8_UNORM_SRGB, 1) == E_INVALIDARG && !projected);
    CHECK(record(budget, true, view_format, 0) == E_INVALIDARG && !projected);
    CHECK(record(budget, true, view_format, UINT64_MAX) == E_INVALIDARG && !projected);
    auto denied = std::make_shared<CaptureMemoryBudget>(1);
    CHECK(record(denied, true, view_format, 1) == E_OUTOFMEMORY && !projected && denied->used_bytes() == 0);
    Ok(record(budget, true, view_format, 1));
    CHECK(projected && projected->texture() != original.Get());
    const uint64_t charged = projected->allocation_bytes();
    CHECK(charged > 0 && budget->used_bytes() == charged);
    auto* original_result = projected.get();
    CHECK(record(budget, true, view_format, 1) == E_INVALIDARG && projected.get() == original_result);
    CHECK(budget->used_bytes() == charged);
    CHECK(projected->CompletionStatus() == E_PENDING);
    auto queued_hold = projected->retirement_handle();
    auto marker = projected->submission_marker();
    auto* shadow = projected->texture();
    auto exactly_one = std::make_shared<CaptureMemoryBudget>(charged);
    std::unique_ptr<ProjectedTexture> extra;
    Ok(ProjectedTexture::Record(device, cmd.Get(), original.Get(), view_format, true,
        fixture.root.Get(), fixture.projection.Get(), key, fence.Get(), 1, exactly_one, &extra));
    std::unique_ptr<TextureCapture> capture;
    CHECK(TextureCapture::RecordBudgeted(device, cmd.Get(), original.Get(), fence.Get(), 1,
                                        exactly_one, &capture) == E_OUTOFMEMORY && !capture);
    auto extra_hold = extra->retirement_handle();
    extra.reset();
    CHECK(exactly_one->used_bytes() == charged);
    ++quota_cases;
    ComPtr<ID3D12DescriptorHeap> descriptors;
    D3D12_DESCRIPTOR_HEAP_DESC descriptors_desc{};
    descriptors_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    descriptors_desc.NumDescriptors = 2; descriptors_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    Ok(device->CreateDescriptorHeap(&descriptors_desc, IID_PPV_ARGS(&descriptors)));
    auto cpu = descriptors->GetCPUDescriptorHandleForHeapStart();
    const UINT increment = device->GetDescriptorHandleIncrementSize(descriptors_desc.Type);
    D3D12_SHADER_RESOURCE_VIEW_DESC srv{};
    srv.Format = view_format; srv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
    srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    srv.Texture2D.MipLevels = 1;
    device->CreateShaderResourceView(shadow, &srv, cpu);
    cpu.ptr += increment;
    D3D12_UNORDERED_ACCESS_VIEW_DESC uav{};
    uav.Format = DXGI_FORMAT_R32_TYPELESS; uav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
    uav.Buffer.NumElements = static_cast<UINT>(pixel_bytes / 4); uav.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
    device->CreateUnorderedAccessView(output.Get(), nullptr, &uav, cpu);
    cmd->SetPipelineState(fixture.consumer.Get()); cmd->SetComputeRootSignature(fixture.root.Get());
    ID3D12DescriptorHeap* heaps[] = {descriptors.Get()}; cmd->SetDescriptorHeaps(1, heaps);
    auto gpu = descriptors->GetGPUDescriptorHandleForHeapStart();
    cmd->SetComputeRootDescriptorTable(0, gpu); gpu.ptr += increment; cmd->SetComputeRootDescriptorTable(1, gpu);
    std::array<uint32_t, 16> params{}; params[8] = width; params[9] = height;
    cmd->SetComputeRoot32BitConstants(2, 16, params.data(), 0);
    cmd->Dispatch((width + 3) / 4, (height + 3) / 4, 1);
    Transition(cmd.Get(), output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    cmd->CopyBufferRegion(readback.Get(), 0, output.Get(), 0, pixel_bytes);
    cmd->CopyBufferRegion(original_probe.Get(), 0, upload.Get(), 0, bytes);
    from.pResource = original.Get(); from.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    to.pResource = original_probe.Get(); to.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; to.PlacedFootprint = footprint;
    cmd->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
    Transition(cmd.Get(), original_probe.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_COPY_SOURCE);
    cmd->CopyBufferRegion(original_readback.Get(), 0, original_probe.Get(), 0, bytes);
    if (cancel_cpu_owner) projected.reset();
    CHECK(budget->used_bytes() == charged);
    Ok(cmd->Close()); ID3D12CommandList* lists[] = {cmd.Get()}; queue->ExecuteCommandLists(1, lists);
    Ok(queue->Signal(fence.Get(), 1));
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr); CHECK(event != nullptr);
    const HRESULT armed = fence->SetEventOnCompletion(1, event);
    const DWORD waited = SUCCEEDED(armed) ? WaitForSingleObject(event, 30000) : WAIT_FAILED;
    CloseHandle(event); Ok(armed); CHECK(waited == WAIT_OBJECT_0); Ok(device->GetDeviceRemovedReason());
    if (projected) CHECK(projected->CompletionStatus() == E_PENDING);
    marker->store(true, std::memory_order_release);
    if (projected) CHECK(projected->CompletionStatus() == S_OK);
    CHECK(budget->used_bytes() == charged);
    queued_hold.Reset();
    CHECK(budget->used_bytes() == (cancel_cpu_owner ? 0 : charged));
    projected.reset(); CHECK(budget->used_bytes() == 0);
    extra_hold.Reset(); CHECK(exactly_one->used_bytes() == 0);
    CHECK(record(budget, true, view_format, 1) == E_INVALIDARG && !projected && budget->used_bytes() == 0);
    const D3D12_RANGE pixel_range{0, pixel_bytes};
    Ok(readback->Map(0, &pixel_range, &mapped));
    const auto* result = static_cast<const uint8_t*>(mapped);
    for (size_t i = 0; i < pixel_bytes; ++i) CHECK(result[i] == expected[i]);
    readback->Unmap(0, &no_read);
    const D3D12_RANGE source_range{0, bytes};
    Ok(original_readback->Map(0, &source_range, &mapped));
    result = static_cast<const uint8_t*>(mapped);
    for (size_t i = 0; i < bytes; ++i) CHECK(result[i] == upload_bytes[i]);
    original_readback->Unmap(0, &no_read);
    ++cases;
}
int main(int argc, char** argv) {
    CHECK(argc == 3); Fixture fixture(argv[1], argv[2]);
    for (DXGI_FORMAT format : {DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_FORMAT_B8G8R8A8_UNORM,
                              DXGI_FORMAT_R8G8B8A8_TYPELESS, DXGI_FORMAT_B8G8R8A8_TYPELESS}) {
        Run(fixture, format, 7, 3, false);
        Run(fixture, format, 65, 5, true);
    }
    std::printf("{\"passed\":true,\"hardware_adapter\":true,\"cases\":%zu,\"assertions\":%zu,"
                "\"shared_quota_cases\":%zu,\"typed_texture_consumer_verified\":true,"
                "\"original_unchanged\":true,\"browser_integrated\":false}\n", cases, assertions, quota_cases);
}
