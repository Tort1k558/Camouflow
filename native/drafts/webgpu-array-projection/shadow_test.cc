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

void RunArray(Fixture& fixture, DXGI_FORMAT storage_format, uint32_t width, uint32_t height,
              bool cancel_cpu_owner, bool narrow_views = false) {
    auto* device = fixture.device.Get();
    constexpr uint32_t mips = 3, layers = 2, count = mips * layers;
    const bool bgra = storage_format == DXGI_FORMAT_B8G8R8A8_UNORM ||
                      storage_format == DXGI_FORMAT_B8G8R8A8_TYPELESS;
    const auto format = bgra ? DXGI_FORMAT_B8G8R8A8_UNORM : DXGI_FORMAT_R8G8B8A8_UNORM;
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    desc.Width = width; desc.Height = height;
    desc.DepthOrArraySize = layers; desc.MipLevels = mips;
    desc.Format = storage_format; desc.SampleDesc.Count = 1;
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = D3D12_HEAP_TYPE_DEFAULT; heap.CreationNodeMask = heap.VisibleNodeMask = 1;
    ComPtr<ID3D12Resource> source;
    Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc,
        D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&source)));
    auto copy_desc = desc; copy_desc.Format = format;
    std::array<D3D12_PLACED_SUBRESOURCE_FOOTPRINT, count> footprints;
    UINT64 total = 0;
    device->GetCopyableFootprints(&copy_desc, 0, count, 0, footprints.data(), nullptr, nullptr, &total);
    std::vector<uint8_t> upload_bytes(static_cast<size_t>(total), 0xa5);
    std::array<uint8_t, 32> key{}; key.fill(37);
    std::vector<uint8_t> expected;
    std::array<uint32_t, count> offsets{};
    for (uint32_t layer = 0; layer < layers; ++layer) {
        for (uint32_t mip = 0; mip < mips; ++mip) {
            const uint32_t index = layer * mips + mip;
            const auto& fp = footprints[index];
            const uint32_t w = std::max(1u, width >> mip), h = std::max(1u, height >> mip);
            CHECK(fp.Footprint.Width == w && fp.Footprint.Height == h);
            std::vector<uint8_t> pixels(size_t{w} * h * 4);
            for (uint32_t y = 0; y < h; ++y) {
                for (uint32_t x = 0; x < w; ++x) {
                    for (uint32_t channel = 0; channel < 4; ++channel) {
                        const uint8_t value = channel == 3 ? 255 :
                            static_cast<uint8_t>(x * 17 + y * 31 + channel * 53 + layer * 41 + mip * 67);
                        pixels[(size_t{y} * w + x) * 4 + channel] = value;
                        const uint32_t native = bgra && channel != 1 && channel != 3 ? 2 - channel : channel;
                        upload_bytes[fp.Offset + size_t{y} * fp.Footprint.RowPitch + x * 4 + native] = value;
                    }
                }
            }
            CHECK(glint::candidate::TransformEdgeCoherentCanvas(pixels, w, h, key));
            offsets[index] = static_cast<uint32_t>(expected.size());
            expected.insert(expected.end(), pixels.begin(), pixels.end());
        }
    }
    auto upload = Buffer(device, total, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    auto shader_output = Buffer(device, expected.size(), D3D12_HEAP_TYPE_DEFAULT,
                                D3D12_RESOURCE_STATE_UNORDERED_ACCESS, true);
    auto shader_readback = Buffer(device, expected.size(), D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    auto canonical_readback = Buffer(device, expected.size(), D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    auto original_readback = Buffer(device, total, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    const D3D12_RANGE no_read{0, 0}; void* mapped = nullptr;
    Ok(upload->Map(0, &no_read, &mapped));
    std::memcpy(mapped, upload_bytes.data(), upload_bytes.size()); upload->Unmap(0, nullptr);
    ComPtr<ID3D12CommandQueue> queue;
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    Ok(device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue)));
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> commands;
    ComPtr<ID3D12Fence> fence;
    Ok(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator)));
    Ok(device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), nullptr, IID_PPV_ARGS(&commands)));
    Ok(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)));
    for (uint32_t index = 0; index < count; ++index) {
        D3D12_TEXTURE_COPY_LOCATION from{}, to{};
        from.pResource = upload.Get(); from.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
        from.PlacedFootprint = footprints[index];
        to.pResource = source.Get(); to.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX; to.SubresourceIndex = index;
        commands->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
    }
    Transition(commands.Get(), source.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_COPY_SOURCE);
    // Measure one valid slice's charge, then deny a later slice in the same command list.
    // If failed preparation records commands against freed temporaries, execution below is invalid.
    auto probe_budget = std::make_shared<CaptureMemoryBudget>(64 * 1024 * 1024);
    std::unique_ptr<ProjectedTexture> probe;
    Ok(ProjectedTexture::Record(device, commands.Get(), source.Get(), format, true,
        fixture.root.Get(), fixture.projection.Get(), key, fence.Get(), 1, probe_budget, &probe));
    auto late_denial = std::make_shared<CaptureMemoryBudget>(probe->allocation_bytes());
    auto budget = std::make_shared<CaptureMemoryBudget>(64 * 1024 * 1024);
    std::unique_ptr<ProjectedTexture> projected;
    auto record = [&](const std::shared_ptr<CaptureMemoryBudget>& quota, bool initialized) {
        return ProjectedTexture::RecordAll(device, commands.Get(), source.Get(), format, initialized,
            fixture.root.Get(), fixture.projection.Get(), key, fence.Get(), 1, quota, &projected);
    };
    CHECK(record(budget, false) == E_INVALIDARG && !projected && budget->used_bytes() == 0);
    CHECK(record(late_denial, true) == E_OUTOFMEMORY && !projected && late_denial->used_bytes() == 0);
    Ok(record(budget, true));
    const uint64_t charged = projected->allocation_bytes();
    CHECK(charged == budget->used_bytes() && charged > probe->allocation_bytes());
    CHECK(projected->texture()->GetDesc().Width == width && projected->texture()->GetDesc().Height == height);
    CHECK(projected->texture()->GetDesc().MipLevels == mips && projected->texture()->GetDesc().DepthOrArraySize == layers);
    CHECK(projected->canonical_pixel_buffer(0, 0) == projected->canonical_pixel_buffer());
    CHECK(!projected->canonical_pixel_buffer(mips, 0) && !projected->canonical_pixel_buffer(0, layers));
    auto queued_hold = projected->retirement_handle();
    auto marker = projected->submission_marker();
    std::shared_ptr<const ProjectedTexture> original_owner(std::move(projected));
    projected = ProjectedTexture::CloneLease(original_owner);
    CHECK(projected && projected->texture() == original_owner->texture());
    original_owner.reset();
    ComPtr<ID3D12DescriptorHeap> descriptors;
    D3D12_DESCRIPTOR_HEAP_DESC descriptor{};
    descriptor.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    descriptor.NumDescriptors = count * 2; descriptor.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    Ok(device->CreateDescriptorHeap(&descriptor, IID_PPV_ARGS(&descriptors)));
    const UINT increment = device->GetDescriptorHandleIncrementSize(descriptor.Type);
    for (uint32_t layer = 0; layer < layers; ++layer) {
        for (uint32_t mip = 0; mip < mips; ++mip) {
            const uint32_t index = layer * mips + mip;
            D3D12_SHADER_RESOURCE_VIEW_DESC srv{};
            srv.Format = format; srv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2DARRAY;
            srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
            srv.Texture2DArray.MostDetailedMip = narrow_views ? mip : 0;
            srv.Texture2DArray.FirstArraySlice = narrow_views ? layer : 0;
            srv.Texture2DArray.MipLevels = narrow_views ? 1 : mips;
            srv.Texture2DArray.ArraySize = narrow_views ? 1 : layers;
            auto cpu = descriptors->GetCPUDescriptorHandleForHeapStart();
            cpu.ptr += uint64_t{index} * increment * 2;
            device->CreateShaderResourceView(projected->texture(), &srv, cpu);
            cpu.ptr += increment;
            D3D12_UNORDERED_ACCESS_VIEW_DESC uav{};
            uav.Format = DXGI_FORMAT_R32_TYPELESS; uav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
            uav.Buffer.NumElements = static_cast<UINT>(expected.size() / 4); uav.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
            device->CreateUnorderedAccessView(shader_output.Get(), nullptr, &uav, cpu);
        }
    }
    commands->SetPipelineState(fixture.consumer.Get()); commands->SetComputeRootSignature(fixture.root.Get());
    ID3D12DescriptorHeap* heaps[] = {descriptors.Get()}; commands->SetDescriptorHeaps(1, heaps);
    for (uint32_t layer = 0; layer < layers; ++layer) {
        for (uint32_t mip = 0; mip < mips; ++mip) {
            const uint32_t index = layer * mips + mip;
            const uint32_t w = std::max(1u, width >> mip), h = std::max(1u, height >> mip);
            auto gpu = descriptors->GetGPUDescriptorHandleForHeapStart();
            gpu.ptr += uint64_t{index} * increment * 2;
            commands->SetComputeRootDescriptorTable(0, gpu);
            gpu.ptr += increment;
            commands->SetComputeRootDescriptorTable(1, gpu);
            auto* canonical = projected->canonical_pixel_buffer(mip, layer);
            CHECK(canonical && canonical->GetDesc().Width == uint64_t{w} * h * 4);
            Transition(commands.Get(), canonical, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_STATE_COPY_SOURCE);
            commands->CopyBufferRegion(canonical_readback.Get(), offsets[index], canonical, 0, uint64_t{w} * h * 4);
            Transition(commands.Get(), canonical, D3D12_RESOURCE_STATE_COPY_SOURCE, D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
            std::array<uint32_t, 16> parameters{};
            parameters[8] = w; parameters[9] = h; parameters[10] = narrow_views ? 0 : layer;
            parameters[11] = narrow_views ? 0 : mip; parameters[12] = offsets[index];
            commands->SetComputeRoot32BitConstants(2, 16, parameters.data(), 0);
            commands->Dispatch((w + 3) / 4, (h + 3) / 4, 1);
            D3D12_RESOURCE_BARRIER barrier{}; barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
            barrier.UAV.pResource = shader_output.Get(); commands->ResourceBarrier(1, &barrier);
        }
    }
    Transition(commands.Get(), shader_output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    commands->CopyBufferRegion(shader_readback.Get(), 0, shader_output.Get(), 0, expected.size());
    commands->CopyBufferRegion(original_readback.Get(), 0, upload.Get(), 0, total);
    for (uint32_t index = 0; index < count; ++index) {
        D3D12_TEXTURE_COPY_LOCATION from{}, to{};
        from.pResource = source.Get(); from.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX; from.SubresourceIndex = index;
        to.pResource = original_readback.Get(); to.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT; to.PlacedFootprint = footprints[index];
        commands->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
    }
    if (cancel_cpu_owner) projected.reset();
    CHECK(budget->used_bytes() == charged);
    Ok(commands->Close());
    ID3D12CommandList* lists[] = {commands.Get()}; queue->ExecuteCommandLists(1, lists);
    Ok(queue->Signal(fence.Get(), 1));
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr); CHECK(event != nullptr);
    const HRESULT armed = fence->SetEventOnCompletion(1, event);
    const DWORD waited = SUCCEEDED(armed) ? WaitForSingleObject(event, 30000) : WAIT_FAILED;
    CloseHandle(event); Ok(armed); CHECK(waited == WAIT_OBJECT_0); Ok(device->GetDeviceRemovedReason());
    if (projected) CHECK(projected->CompletionStatus() == E_PENDING);
    marker->store(true, std::memory_order_release);
    if (projected) CHECK(projected->CompletionStatus() == S_OK);
    queued_hold.Reset();
    CHECK(budget->used_bytes() == (cancel_cpu_owner ? 0 : charged));
    projected.reset(); CHECK(budget->used_bytes() == 0);
    probe.reset(); CHECK(probe_budget->used_bytes() == 0);
    for (uint32_t repeat = 0; repeat < 2; ++repeat) {
        const D3D12_RANGE range{0, expected.size()};
        Ok(shader_readback->Map(0, &range, &mapped));
        auto* values = static_cast<const uint8_t*>(mapped);
        for (size_t i = 0; i < expected.size(); ++i) CHECK(values[i] == expected[i]);
        shader_readback->Unmap(0, &no_read);
        Ok(canonical_readback->Map(0, &range, &mapped));
        values = static_cast<const uint8_t*>(mapped);
        for (size_t i = 0; i < expected.size(); ++i) {
            const size_t channel = i % 4;
            const size_t native = bgra && channel != 1 && channel != 3 ? i - channel + 2 - channel : i;
            CHECK(values[native] == expected[i]);
        }
        canonical_readback->Unmap(0, &no_read);
    }
    const D3D12_RANGE source_range{0, static_cast<size_t>(total)};
    Ok(original_readback->Map(0, &source_range, &mapped));
    auto* values = static_cast<const uint8_t*>(mapped);
    for (size_t i = 0; i < upload_bytes.size(); ++i) CHECK(values[i] == upload_bytes[i]);
    original_readback->Unmap(0, &no_read);
    ++cases;
}

int main(int argc, char** argv) {
    CHECK(argc == 3); Fixture fixture(argv[1], argv[2]);
    for (DXGI_FORMAT format : {DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_FORMAT_B8G8R8A8_UNORM,
                              DXGI_FORMAT_R8G8B8A8_TYPELESS, DXGI_FORMAT_B8G8R8A8_TYPELESS}) {
        RunArray(fixture, format, 65, 7, false);
        RunArray(fixture, format, 64, 8, true);
        RunArray(fixture, format, 65, 7, true, true);
    }
    std::printf("{\"passed\":true,\"hardware_adapter\":true,\"cases\":%zu,\"assertions\":%zu,"
                "\"subresources_per_case\":6,\"array_shader_verified\":true,\"narrow_views_verified\":true,"
                "\"canonical_bytes_verified\":true,\"original_unchanged\":true,"
                "\"late_quota_denial_drained\":true,\"browser_integrated\":false}\n", cases, assertions);
}
