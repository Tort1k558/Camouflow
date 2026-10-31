// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <d3d12.h>
#include <d3dcompiler.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <span>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;
size_t assertions = 0, cases = 0, rejections = 0, root_cases = 0;
void Check(bool value, int line) {
    ++assertions;
    if (!value) { std::fprintf(stderr, "buffer-binding assertion %d\n", line); std::abort(); }
}
#define CHECK(x) Check((x), __LINE__)
void OkImpl(HRESULT value, int line) {
    if (FAILED(value)) std::fprintf(stderr, "buffer-binding HRESULT %08lx at %d\n", static_cast<unsigned long>(value), line);
    CHECK(SUCCEEDED(value));
}
#define Ok(x) OkImpl((x), __LINE__)
#include "descriptor_fixture.h"
ComPtr<ID3D12Resource> Buffer(ID3D12Device* device, uint64_t bytes, D3D12_HEAP_TYPE type,
                            D3D12_RESOURCE_STATES state, bool uav = false) {
    D3D12_RESOURCE_DESC desc{};
    desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    desc.Width = bytes; desc.Height = desc.DepthOrArraySize = desc.MipLevels = 1;
    desc.SampleDesc.Count = 1; desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    desc.Flags = uav ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE;
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = type; heap.CreationNodeMask = heap.VisibleNodeMask = 1;
    ComPtr<ID3D12Resource> result;
    Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc, state, nullptr, IID_PPV_ARGS(&result)));
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
    ComPtr<ID3DBlob> result, errors;
    const auto status = D3DCompile(source.data(), source.size(), "glint-buffer-binding", nullptr, nullptr,
        entry, "cs_5_0", D3DCOMPILE_ENABLE_STRICTNESS | D3DCOMPILE_WARNINGS_ARE_ERRORS, 0, &result, &errors);
    if (errors) std::fwrite(errors->GetBufferPointer(), 1, errors->GetBufferSize(), stderr);
    Ok(status); return result;
}
void Run(ID3D12Device* device, const char* shader, descriptor_fixture::wgpu::BufferBindingType type,
         bool dynamic, uint64_t binding_offset) {
    namespace f = descriptor_fixture;
    const bool uniform = type == f::wgpu::BufferBindingType::Uniform;
    const bool writable = type == f::wgpu::BufferBindingType::Storage || type == f::kInternalStorageBufferBinding;
    const bool root_uniform = uniform && dynamic;
    constexpr uint64_t bytes = 2048, logical_bytes = 1792, binding_size = 512;
    const uint32_t dynamic_offset = dynamic ? 256 : 0;
    auto original = Buffer(device, bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST, writable);
    auto shadow = Buffer(device, bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST, true);
    auto wrong_size = Buffer(device, 1024, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON, true);
    auto output = Buffer(device, 4, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_UNORDERED_ACCESS, true);
    auto upload = Buffer(device, bytes * 2, D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    auto readback = Buffer(device, bytes * 2 + 8, D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    std::array<uint32_t, bytes / 4> raw{}, projected{};
    for (size_t i = 0; i < raw.size(); ++i) { raw[i] = 0x11000000u + static_cast<uint32_t>(i); projected[i] = 0x22000000u + static_cast<uint32_t>(i); }
    void* mapped = nullptr; const D3D12_RANGE no_read{0, 0};
    Ok(upload->Map(0, &no_read, &mapped));
    std::memcpy(mapped, raw.data(), bytes); std::memcpy(static_cast<uint8_t*>(mapped) + bytes, projected.data(), bytes);
    upload->Unmap(0, nullptr);
    f::Device owner{device, {}}, foreign{device, {}};
    f::Buffer source{&owner, original.Get(), logical_bytes}, sink{&owner, output.Get(), 4};
    const UINT increment = device->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    f::Layout layout(increment);
    layout.bindings[0].bindingLayout = f::BufferBindingInfo{type};
    layout.bindings[1].bindingLayout = f::BufferBindingInfo{f::wgpu::BufferBindingType::Storage};
    layout.dynamic_count = dynamic ? 1 : 0;
    if (root_uniform) { layout.count = 1; layout.offsets = {UINT32_MAX, 0}; }
    D3D12_DESCRIPTOR_HEAP_DESC cpu_desc{};
    cpu_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV; cpu_desc.NumDescriptors = 2;
    ComPtr<ID3D12DescriptorHeap> cached;
    Ok(device->CreateDescriptorHeap(&cpu_desc, IID_PPV_ARGS(&cached)));
    f::BindGroup group{&owner, &layout, {{{&source, binding_offset, binding_size}, {&sink, 0, 4}}},
        {cached->GetCPUDescriptorHandleForHeapStart()}};
    if (!root_uniform) f::WriteBufferDescriptor(device, original.Get(), source.GetVA(), group.buffers[0], type, dynamic,
        {group.mCPUViewAllocation.base.ptr + uint64_t{layout.offsets[0]} * increment});
    f::WriteBufferDescriptor(device, output.Get(), sink.GetVA(), group.buffers[1], f::wgpu::BufferBindingType::Storage, false,
        {group.mCPUViewAllocation.base.ptr + uint64_t{layout.offsets[1]} * increment});
    f::ShaderVisibleDescriptorAllocator allocator(&owner);
    f::GlintBufferViewOverride replacement{0, shadow, shadow};
    f::GPUDescriptorHeapAllocation allocation;
    auto populate = [&](std::span<const f::GlintBufferViewOverride> replacements) {
        return group.PopulateGlintViews(&allocator, {}, replacements, &allocation);
    };
    auto denied = [&](std::span<const f::GlintBufferViewOverride> replacements) {
        const auto before = allocator.allocations;
        CHECK(populate(replacements).error); CHECK(allocator.allocations == before); ++rejections;
    };
    auto bad = replacement;
    bad.binding = 2; denied(std::span(&bad, 1));
    bad = replacement; bad.retirement.Reset(); denied(std::span(&bad, 1));
    bad = replacement; bad.resource = original; denied(std::span(&bad, 1));
    bad = replacement; bad.resource = wrong_size; denied(std::span(&bad, 1));
    std::array duplicate{replacement, replacement}; denied(duplicate);
    source.owner = &foreign; denied(std::span(&replacement, 1)); source.owner = &owner;
    source.private_backing = false; denied(std::span(&replacement, 1)); source.private_backing = true;
    source.accessible = false; denied(std::span(&replacement, 1)); source.accessible = true;
    source.va_bias = 4; denied(std::span(&replacement, 1)); source.va_bias = 0;
    source.size = bytes + 1; denied(std::span(&replacement, 1)); source.size = logical_bytes;
    layout.bindings[0].visibility = f::wgpu::ShaderStage::None; denied(std::span(&replacement, 1));
    layout.bindings[0].visibility = f::wgpu::ShaderStage::Compute;
    group.buffers[0].offset += 1; denied(std::span(&replacement, 1)); group.buffers[0].offset -= 1;
    if (uniform) {
        auto large_original = Buffer(device, 131072, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON);
        auto large_shadow = Buffer(device, 131072, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON, true);
        const auto saved = group.buffers[0];
        source.resource = large_original.Get(); source.size = 131072;
        group.buffers[0].offset = 0; group.buffers[0].size = 65537;
        auto oversized = replacement; oversized.resource = large_shadow;
        denied(std::span(&oversized, 1));
        group.buffers[0] = saved; source.resource = original.Get(); source.size = logical_bytes;
    }
    CHECK(group.ResolveGlintRootBufferAddress(0, dynamic_offset, {}).error);
    if (root_uniform) {
        CHECK(group.ResolveGlintRootBufferAddress(0, 1, std::span(&replacement, 1)).error);
        CHECK(group.ResolveGlintRootBufferAddress(0, 2048, std::span(&replacement, 1)).error);
        const auto root = group.ResolveGlintRootBufferAddress(0, dynamic_offset, std::span(&replacement, 1));
        CHECK(!root.error && root.value == shadow->GetGPUVirtualAddress() + binding_offset + dynamic_offset);
        const auto old_count = layout.count;
        layout.count = 0;
        CHECK(populate(std::span(&replacement, 1)).value && allocator.allocations == 0);
        layout.count = old_count; ++root_cases;
    } else {
        CHECK(group.ResolveGlintRootBufferAddress(0, dynamic_offset, std::span(&replacement, 1)).error);
    }
    const auto populated = populate(std::span(&replacement, 1)); CHECK(!populated.error && populated.value);
    const auto first = allocation;
    CHECK(!populate(std::span(&replacement, 1)).error && !populate(std::span(&replacement, 1)).value);
    allocator.Switch();
    CHECK(populate(std::span(&replacement, 1)).value);
    D3D12_DESCRIPTOR_HEAP_DESC control_desc = cpu_desc;
    control_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ComPtr<ID3D12DescriptorHeap> control;
    Ok(device->CreateDescriptorHeap(&control_desc, IID_PPV_ARGS(&control)));
    device->CopyDescriptorsSimple(layout.count, control->GetCPUDescriptorHandleForHeapStart(),
        group.mCPUViewAllocation.base, D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    D3D12_DESCRIPTOR_RANGE ranges[2]{};
    ranges[0].RangeType = uniform ? D3D12_DESCRIPTOR_RANGE_TYPE_CBV : writable ? D3D12_DESCRIPTOR_RANGE_TYPE_UAV : D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
    ranges[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_UAV; ranges[1].BaseShaderRegister = 1;
    D3D12_ROOT_PARAMETER params[3]{};
    for (size_t i = 0; i < 2; ++i) {
        ranges[i].NumDescriptors = 1;
        params[i].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
        params[i].DescriptorTable.NumDescriptorRanges = 1; params[i].DescriptorTable.pDescriptorRanges = &ranges[i];
    }
    if (root_uniform) { params[0] = {}; params[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_CBV; }
    params[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
    params[2].Constants.ShaderRegister = 1; params[2].Constants.Num32BitValues = 2;
    D3D12_ROOT_SIGNATURE_DESC root_desc{};
    root_desc.NumParameters = 3; root_desc.pParameters = params;
    ComPtr<ID3DBlob> signature, errors;
    Ok(D3D12SerializeRootSignature(&root_desc, D3D_ROOT_SIGNATURE_VERSION_1, &signature, &errors));
    ComPtr<ID3D12RootSignature> root;
    Ok(device->CreateRootSignature(0, signature->GetBufferPointer(), signature->GetBufferSize(), IID_PPV_ARGS(&root)));
    const auto code = Compile(shader, uniform ? "uniform_main" : writable ? "writable_main" : "readonly_main");
    D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline_desc{};
    pipeline_desc.pRootSignature = root.Get(); pipeline_desc.CS = {code->GetBufferPointer(), code->GetBufferSize()};
    ComPtr<ID3D12PipelineState> pipeline;
    Ok(device->CreateComputePipelineState(&pipeline_desc, IID_PPV_ARGS(&pipeline)));
    ComPtr<ID3D12CommandQueue> queue;
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    Ok(device->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue)));
    ComPtr<ID3D12CommandAllocator> commands;
    ComPtr<ID3D12GraphicsCommandList> cmd;
    ComPtr<ID3D12Fence> fence;
    Ok(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&commands)));
    Ok(device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, commands.Get(), pipeline.Get(), IID_PPV_ARGS(&cmd)));
    Ok(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)));
    cmd->CopyBufferRegion(original.Get(), 0, upload.Get(), 0, bytes);
    cmd->CopyBufferRegion(shadow.Get(), 0, upload.Get(), bytes, bytes);
    const auto state = writable ? D3D12_RESOURCE_STATE_UNORDERED_ACCESS : D3D12_RESOURCE_STATE_GENERIC_READ;
    Transition(cmd.Get(), original.Get(), D3D12_RESOURCE_STATE_COPY_DEST, state);
    Transition(cmd.Get(), shadow.Get(), D3D12_RESOURCE_STATE_COPY_DEST, state);
    cmd->SetComputeRootSignature(root.Get());
    auto dispatch = [&](ID3D12DescriptorHeap* heap, D3D12_GPU_DESCRIPTOR_HANDLE base, bool replacement_table) {
        ID3D12DescriptorHeap* heaps[] = {heap}; cmd->SetDescriptorHeaps(1, heaps);
        if (root_uniform) {
            const auto address = replacement_table ? group.ResolveGlintRootBufferAddress(0, dynamic_offset, std::span(&replacement, 1)).value
                : original->GetGPUVirtualAddress() + binding_offset + dynamic_offset;
            cmd->SetComputeRootConstantBufferView(0, address);
        } else cmd->SetComputeRootDescriptorTable(0, {base.ptr + uint64_t{layout.offsets[0]} * increment});
        cmd->SetComputeRootDescriptorTable(1, {base.ptr + uint64_t{layout.offsets[1]} * increment});
        std::array<uint32_t, 2> data{uniform ? 0u : dynamic_offset, replacement_table && writable ? 1u : 0u};
        cmd->SetComputeRoot32BitConstants(2, 2, data.data(), 0); cmd->Dispatch(1, 1, 1);
    };
    dispatch(allocator.heaps.front().Get(), first.base, true);
    Transition(cmd.Get(), output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    cmd->CopyBufferRegion(readback.Get(), bytes * 2, output.Get(), 0, 4);
    Transition(cmd.Get(), output.Get(), D3D12_RESOURCE_STATE_COPY_SOURCE, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    dispatch(control.Get(), control->GetGPUDescriptorHandleForHeapStart(), false);
    Transition(cmd.Get(), output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    cmd->CopyBufferRegion(readback.Get(), bytes * 2 + 4, output.Get(), 0, 4);
    Transition(cmd.Get(), original.Get(), state, D3D12_RESOURCE_STATE_COPY_SOURCE);
    Transition(cmd.Get(), shadow.Get(), state, D3D12_RESOURCE_STATE_COPY_SOURCE);
    cmd->CopyBufferRegion(readback.Get(), 0, original.Get(), 0, bytes);
    cmd->CopyBufferRegion(readback.Get(), bytes, shadow.Get(), 0, bytes);
    Ok(cmd->Close()); ID3D12CommandList* lists[] = {cmd.Get()}; queue->ExecuteCommandLists(1, lists); Ok(queue->Signal(fence.Get(), 1));
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr); CHECK(event != nullptr);
    Ok(fence->SetEventOnCompletion(1, event)); const auto waited = WaitForSingleObject(event, 30000); CloseHandle(event);
    CHECK(waited == WAIT_OBJECT_0); Ok(device->GetDeviceRemovedReason());
    const D3D12_RANGE read{0, bytes * 2 + 8}; Ok(readback->Map(0, &read, &mapped));
    const auto* values = static_cast<const uint32_t*>(mapped);
    const size_t index = (binding_offset + dynamic_offset) / 4;
    CHECK(values[bytes / 2] == projected[index] && values[bytes / 2 + 1] == raw[index]);
    for (size_t i = 0; i < raw.size(); ++i) {
        CHECK(values[i] == raw[i]);
        CHECK(values[raw.size() + i] == (writable && i == index ? projected[i] ^ 0xa5a5a5a5u : projected[i]));
    }
    readback->Unmap(0, &no_read); ++cases;
}
int main(int argc, char** argv) {
    CHECK(argc == 2);
    ComPtr<IDXGIFactory6> factory; Ok(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)));
    ComPtr<IDXGIAdapter1> adapter;
    Ok(factory->EnumAdapterByGpuPreference(0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, IID_PPV_ARGS(&adapter)));
    DXGI_ADAPTER_DESC1 desc{}; Ok(adapter->GetDesc1(&desc)); CHECK(!(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE));
    ComPtr<ID3D12Device> device; Ok(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&device)));
    namespace f = descriptor_fixture;
    for (auto type : {f::wgpu::BufferBindingType::Uniform, f::wgpu::BufferBindingType::Storage,
                     f::wgpu::BufferBindingType::ReadOnlyStorage, f::kInternalStorageBufferBinding, f::kInternalReadOnlyStorageBufferBinding})
        for (bool dynamic : {false, true}) for (uint64_t offset : {0u, 256u}) Run(device.Get(), argv[1], type, dynamic, offset);
    std::printf("{\"passed\":true,\"hardware_adapter\":true,\"cases\":%zu,\"assertions\":%zu,"
        "\"rejected_overrides\":%zu,\"root_uniform_cases\":%zu,\"native_descriptor_methods_executed\":true,"
        "\"cached_descriptors_unchanged\":true,\"original_buffer_unchanged\":true,"
        "\"browser_integrated\":false,\"native_binding_routing_installed\":false}\n", cases, assertions, rejections, root_cases);
}
