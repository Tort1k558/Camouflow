// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include "projected_texture.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <new>

namespace glint::candidate::d3d12 {
using Microsoft::WRL::ComPtr;
namespace {
constexpr uint64_t kDescriptorCharge = 64 * 1024;
constexpr uint64_t kRawLimit = 64 * 1024 * 1024;
struct Parameters {
    std::array<uint8_t, 32> key;
    uint32_t width, height, pitch, offset;
    uint32_t bgra, operation, message_bytes, reserved;
};
static_assert(sizeof(Parameters) == 64);
bool SameDevice(ID3D12Device* device, ID3D12DeviceChild* child) {
    if (!child) {
        return false;
    }
    ComPtr<ID3D12Device> owner;
    ComPtr<IUnknown> expected, actual;
    return SUCCEEDED(child->GetDevice(IID_PPV_ARGS(&owner))) && SUCCEEDED(owner.As(&actual)) &&
           SUCCEEDED(device->QueryInterface(IID_PPV_ARGS(&expected))) &&
           expected.Get() == actual.Get();
}
void Transition(ID3D12GraphicsCommandList* commands,
                ID3D12Resource* resource,
                D3D12_RESOURCE_STATES before,
                D3D12_RESOURCE_STATES after) {
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = resource;
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = before;
    barrier.Transition.StateAfter = after;
    commands->ResourceBarrier(1, &barrier);
}
}  // namespace

class ProjectedTextureRetirement final : public IUnknown {
  public:
    ProjectedTextureRetirement(std::shared_ptr<CaptureMemoryBudget> budget, uint64_t bytes)
        : budget_(std::move(budget)), bytes_(bytes) {}
    explicit ProjectedTextureRetirement(std::shared_ptr<const ProjectedTexture> source)
        : bytes_(0), source_(std::move(source)) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** result) override {
        if (!result) {
            return E_POINTER;
        }
        *result = nullptr;
        if (iid != __uuidof(IUnknown)) {
            return E_NOINTERFACE;
        }
        *result = static_cast<IUnknown*>(this);
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override {
        return references_.fetch_add(1, std::memory_order_relaxed) + 1;
    }
    ULONG STDMETHODCALLTYPE Release() override {
        const ULONG remaining = references_.fetch_sub(1, std::memory_order_acq_rel) - 1;
        if (remaining == 0) {
            delete this;
        }
        return remaining;
    }
    ComPtr<ID3D12Resource> original, input, output, shadow, canonical_pixels;
    std::unique_ptr<std::unique_ptr<ProjectedTexture>[]> children;
    ComPtr<ID3D12DescriptorHeap> descriptors;
    ComPtr<ID3D12RootSignature> root;
    ComPtr<ID3D12PipelineState> pipeline;

  private:
    ~ProjectedTextureRetirement() {
        children.reset();
        original.Reset();
        input.Reset();
        output.Reset();
        shadow.Reset();
        canonical_pixels.Reset();
        descriptors.Reset();
        root.Reset();
        pipeline.Reset();
        if (budget_) budget_->Release(bytes_);
    }
    std::atomic<ULONG> references_{1};
    std::shared_ptr<CaptureMemoryBudget> budget_;
    uint64_t bytes_;
    std::shared_ptr<const ProjectedTexture> source_;
};

struct ProjectedTexture::Prepared {
    std::unique_ptr<ProjectedTexture> projected;
    ComPtr<ProjectedTextureRetirement> hold;
    ComPtr<ID3D12GraphicsCommandList> commands;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    Parameters params{};
    uint32_t subresource = 0, width = 0, height = 0, increment = 0;
    bool tight_rows = false;
    ~Prepared() { SecureZeroMemory(&params, sizeof(params)); }
};

HRESULT ProjectedTexture::Prepare(ID3D12Device* device,
                                 ID3D12GraphicsCommandList* commands,
                                 ID3D12Resource* source,
                                 DXGI_FORMAT view_format,
                                 bool source_initialized,
                                 ID3D12RootSignature* root,
                                 ID3D12PipelineState* pipeline,
                                 std::span<const uint8_t, 32> key,
                                 ID3D12Fence* fence,
                                 uint64_t completion_value,
                                 const std::shared_ptr<CaptureMemoryBudget>& budget,
                                 std::unique_ptr<Prepared>* result,
                                 uint32_t mip_level,
                                 uint32_t array_layer) {
    if (!result || *result || !device || !commands || !source || !root || !pipeline || !fence ||
        !budget || !source_initialized || budget->limit_bytes() == 0 || completion_value == 0 ||
        completion_value == std::numeric_limits<uint64_t>::max()) {
        return E_INVALIDARG;
    }
    if (commands->GetType() != D3D12_COMMAND_LIST_TYPE_DIRECT || !SameDevice(device, commands) ||
        !SameDevice(device, source) || !SameDevice(device, root) || !SameDevice(device, pipeline) ||
        !SameDevice(device, fence)) {
        return E_INVALIDARG;
    }
    const uint64_t completed = fence->GetCompletedValue();
    if (completed == std::numeric_limits<uint64_t>::max()) {
        return DXGI_ERROR_DEVICE_REMOVED;
    }
    if (completed >= completion_value) {
        return E_INVALIDARG;
    }
    const auto original_desc = source->GetDesc();
    const bool rgba = view_format == DXGI_FORMAT_R8G8B8A8_UNORM &&
                      (original_desc.Format == view_format ||
                       original_desc.Format == DXGI_FORMAT_R8G8B8A8_TYPELESS);
    const bool bgra = view_format == DXGI_FORMAT_B8G8R8A8_UNORM &&
                      (original_desc.Format == view_format ||
                       original_desc.Format == DXGI_FORMAT_B8G8R8A8_TYPELESS);
    if ((!rgba && !bgra) || original_desc.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D ||
        original_desc.DepthOrArraySize == 0 || original_desc.MipLevels == 0 ||
        mip_level >= original_desc.MipLevels || mip_level >= 32 ||
        array_layer >= original_desc.DepthOrArraySize ||
        original_desc.SampleDesc.Count != 1 || original_desc.SampleDesc.Quality != 0 ||
        original_desc.Width == 0 || original_desc.Height == 0 || original_desc.Width > 8192 ||
        original_desc.Height > 8192) {
        return E_INVALIDARG;
    }
    const uint32_t subresource = mip_level + array_layer * original_desc.MipLevels;
    auto shadow_desc = original_desc;
    shadow_desc.Width = std::max(uint64_t{1}, original_desc.Width >> mip_level);
    shadow_desc.Height = std::max(uint32_t{1}, original_desc.Height >> mip_level);
    shadow_desc.DepthOrArraySize = shadow_desc.MipLevels = 1;
    shadow_desc.Format = view_format;
    shadow_desc.Flags = D3D12_RESOURCE_FLAG_NONE;
    shadow_desc.Layout = D3D12_TEXTURE_LAYOUT_UNKNOWN;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT rows = 0;
    UINT64 row_size = 0, total = 0;
    device->GetCopyableFootprints(&shadow_desc, 0, 1, 0, &footprint, &rows, &row_size, &total);
    const uint64_t raw_bytes =
        static_cast<uint64_t>(footprint.Footprint.RowPitch) * shadow_desc.Height;
    if (rows != shadow_desc.Height || row_size != shadow_desc.Width * 4 || total == 0 ||
        total > raw_bytes || raw_bytes > kRawLimit || raw_bytes == 0) {
        return E_INVALIDARG;
    }
    D3D12_RESOURCE_DESC raw_desc{};
    raw_desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    raw_desc.Width = raw_bytes;
    raw_desc.Height = raw_desc.DepthOrArraySize = raw_desc.MipLevels = 1;
    raw_desc.SampleDesc.Count = 1;
    raw_desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    auto output_desc = raw_desc;
    output_desc.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    const bool tight_rows = footprint.Footprint.RowPitch == shadow_desc.Width * 4;
    auto canonical_desc = raw_desc;
    canonical_desc.Width = shadow_desc.Width * shadow_desc.Height * 4;
    uint64_t charged = kDescriptorCharge;
    for (const auto* resource_desc : {&output_desc, &shadow_desc, tight_rows ? nullptr : &canonical_desc}) {
        if (!resource_desc) continue;
        const auto& desc = *resource_desc;
        const auto info = device->GetResourceAllocationInfo(0, 1, &desc);
        if (info.SizeInBytes == 0 || info.SizeInBytes == std::numeric_limits<uint64_t>::max() ||
            info.SizeInBytes > std::numeric_limits<uint64_t>::max() - charged) {
            return E_INVALIDARG;
        }
        charged += info.SizeInBytes;
    }
    if (!budget->Reserve(charged)) {
        return E_OUTOFMEMORY;
    }
    ComPtr<ProjectedTextureRetirement> hold;
    hold.Attach(new (std::nothrow) ProjectedTextureRetirement(budget, charged));
    if (!hold) {
        budget->Release(charged);
        return E_OUTOFMEMORY;
    }
    std::unique_ptr<ProjectedTexture> projected(new (std::nothrow) ProjectedTexture());
    if (!projected) {
        return E_OUTOFMEMORY;
    }
    projected->submitted_ = std::make_shared<std::atomic<bool>>(false);
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = D3D12_HEAP_TYPE_DEFAULT;
    heap.CreationNodeMask = heap.VisibleNodeMask = 1;
    auto create = [&](const D3D12_RESOURCE_DESC& desc, D3D12_RESOURCE_STATES state,
                      ComPtr<ID3D12Resource>* target) {
        return device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc, state, nullptr,
                                               IID_PPV_ARGS(target->GetAddressOf()));
    };
    HRESULT status = create(output_desc, D3D12_RESOURCE_STATE_UNORDERED_ACCESS, &hold->output);
    if (FAILED(status)) {
        return status;
    }
    status = create(shadow_desc, D3D12_RESOURCE_STATE_COPY_DEST, &hold->shadow);
    if (FAILED(status)) {
        return status;
    }
    if (tight_rows) {
        hold->canonical_pixels = hold->output;
    } else {
        status = create(canonical_desc, D3D12_RESOURCE_STATE_COPY_DEST, &hold->canonical_pixels);
        if (FAILED(status)) return status;
    }
    D3D12_DESCRIPTOR_HEAP_DESC descriptor_desc{};
    descriptor_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    descriptor_desc.NumDescriptors = 2;
    descriptor_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    status = device->CreateDescriptorHeap(&descriptor_desc, IID_PPV_ARGS(&hold->descriptors));
    if (FAILED(status)) {
        return status;
    }
    hold->original = source;
    hold->root = root;
    hold->pipeline = pipeline;
    const UINT increment = device->GetDescriptorHandleIncrementSize(descriptor_desc.Type);
    auto cpu = hold->descriptors->GetCPUDescriptorHandleForHeapStart();
    D3D12_SHADER_RESOURCE_VIEW_DESC srv{};
    srv.Format = view_format;
    srv.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D;
    srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    srv.Texture2D.MipLevels = 1;
    device->CreateShaderResourceView(hold->shadow.Get(), &srv, cpu);
    cpu.ptr += increment;
    D3D12_UNORDERED_ACCESS_VIEW_DESC uav{};
    uav.Format = DXGI_FORMAT_R32_TYPELESS;
    uav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
    uav.Buffer.NumElements = static_cast<UINT>(raw_bytes / 4);
    uav.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
    device->CreateUnorderedAccessView(hold->output.Get(), nullptr, &uav, cpu);
    projected->texture_ = hold->shadow.Get();
    projected->canonical_pixel_buffer_ = hold->canonical_pixels.Get();
    projected->canonical_pixel_format_ = view_format;
    projected->retirement_ = hold;
    projected->fence_ = fence;
    projected->completion_value_ = completion_value;
    projected->allocation_bytes_ = charged;
    std::unique_ptr<Prepared> prepared(new (std::nothrow) Prepared());
    if (!prepared) return E_OUTOFMEMORY;
    prepared->projected = std::move(projected);
    prepared->hold = std::move(hold);
    prepared->commands = commands;
    prepared->footprint = footprint;
    prepared->increment = increment;
    prepared->subresource = subresource;
    prepared->width = static_cast<uint32_t>(shadow_desc.Width);
    prepared->height = shadow_desc.Height;
    prepared->tight_rows = tight_rows;
    std::memcpy(prepared->params.key.data(), key.data(), key.size());
    prepared->params.width = prepared->width;
    prepared->params.height = prepared->height;
    prepared->params.pitch = footprint.Footprint.RowPitch;
    prepared->params.bgra = bgra ? 1 : 0;
    *result = std::move(prepared);
    return S_OK;
}

std::unique_ptr<ProjectedTexture> ProjectedTexture::Finish(std::unique_ptr<Prepared> prepared) {
    auto* commands = prepared->commands.Get();
    auto* hold = prepared->hold.Get();
    auto* source = hold->original.Get();
    auto* pipeline = hold->pipeline.Get();
    auto* root = hold->root.Get();
    const auto footprint = prepared->footprint;
    const auto subresource = prepared->subresource;
    const auto tight_rows = prepared->tight_rows;
    auto projected = std::move(prepared->projected);
    D3D12_TEXTURE_COPY_LOCATION from{}, raw{}, to{};
    from.pResource = source;
    from.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    from.SubresourceIndex = subresource;
    raw.pResource = hold->output.Get();
    raw.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    raw.PlacedFootprint = footprint;
    to.pResource = hold->shadow.Get();
    to.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    // All fallible allocations/validation precede the first recorded command.
    commands->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
    Transition(commands, hold->shadow.Get(), D3D12_RESOURCE_STATE_COPY_DEST,
               D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    commands->SetPipelineState(pipeline);
    commands->SetComputeRootSignature(root);
    ID3D12DescriptorHeap* heaps[] = {hold->descriptors.Get()};
    commands->SetDescriptorHeaps(1, heaps);
    auto gpu = hold->descriptors->GetGPUDescriptorHandleForHeapStart();
    commands->SetComputeRootDescriptorTable(0, gpu);
    gpu.ptr += prepared->increment;
    commands->SetComputeRootDescriptorTable(1, gpu);
    commands->SetComputeRoot32BitConstants(2, 16, &prepared->params, 0);
    SecureZeroMemory(&prepared->params, sizeof(prepared->params));
    commands->Dispatch((prepared->width + 3) / 4,
                       (prepared->height + 3) / 4, 1);
    Transition(commands, hold->output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS,
               D3D12_RESOURCE_STATE_COPY_SOURCE);
    if (!tight_rows) {
        // Footprint padding never enters the canonical byte stream.
        const uint64_t tight_pitch = prepared->width * 4;
        for (uint32_t row = 0; row < prepared->height; ++row) {
            commands->CopyBufferRegion(hold->canonical_pixels.Get(), row * tight_pitch,
                                       hold->output.Get(), uint64_t{row} * footprint.Footprint.RowPitch,
                                       tight_pitch);
        }
        Transition(commands, hold->canonical_pixels.Get(), D3D12_RESOURCE_STATE_COPY_DEST,
                   D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    }
    Transition(commands, hold->shadow.Get(), D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,
               D3D12_RESOURCE_STATE_COPY_DEST);
    raw.pResource = hold->output.Get();
    commands->CopyTextureRegion(&to, 0, 0, 0, &raw, nullptr);
    Transition(commands, hold->shadow.Get(), D3D12_RESOURCE_STATE_COPY_DEST,
               D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE |
                   D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE);
    if (tight_rows) {
        Transition(commands, hold->output.Get(), D3D12_RESOURCE_STATE_COPY_SOURCE,
                   D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    }
    return projected;
}

HRESULT ProjectedTexture::Record(ID3D12Device* device,
                                 ID3D12GraphicsCommandList* commands,
                                 ID3D12Resource* source,
                                 DXGI_FORMAT view_format,
                                 bool source_initialized,
                                 ID3D12RootSignature* root,
                                 ID3D12PipelineState* pipeline,
                                 std::span<const uint8_t, 32> key,
                                 ID3D12Fence* fence,
                                 uint64_t completion_value,
                                 const std::shared_ptr<CaptureMemoryBudget>& budget,
                                 std::unique_ptr<ProjectedTexture>* result,
                                 uint32_t mip_level,
                                 uint32_t array_layer) {
    if (!result || *result) return E_INVALIDARG;
    std::unique_ptr<Prepared> prepared;
    const HRESULT status = Prepare(device, commands, source, view_format, source_initialized,
        root, pipeline, key, fence, completion_value, budget, &prepared, mip_level, array_layer);
    if (FAILED(status)) return status;
    *result = Finish(std::move(prepared));
    return S_OK;

}


ID3D12Resource* ProjectedTexture::canonical_pixel_buffer(uint32_t mip_level,
                                                       uint32_t array_layer) const {
    if (mip_level >= mip_levels_ || array_layer >= array_layers_) return nullptr;
    if (!canonical_subresources_) return canonical_pixel_buffer_;
    return canonical_subresources_[size_t{array_layer} * mip_levels_ + mip_level];
}

HRESULT ProjectedTexture::RecordAll(ID3D12Device* device,
                                  ID3D12GraphicsCommandList* commands,
                                  ID3D12Resource* source,
                                  DXGI_FORMAT view_format,
                                  bool source_initialized,
                                  ID3D12RootSignature* root,
                                  ID3D12PipelineState* pipeline,
                                  std::span<const uint8_t, 32> key,
                                  ID3D12Fence* fence,
                                  uint64_t completion_value,
                                  const std::shared_ptr<CaptureMemoryBudget>& budget,
                                  std::unique_ptr<ProjectedTexture>* result) {
    if (!result || *result || !source || !device || !commands || !budget || !source_initialized) {
        return E_INVALIDARG;
    }
    const auto desc = source->GetDesc();
    if (desc.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D || desc.MipLevels == 0 ||
        desc.MipLevels > 32 || desc.DepthOrArraySize == 0) return E_INVALIDARG;
    if (desc.MipLevels == 1 && desc.DepthOrArraySize == 1) {
        return Record(device, commands, source, view_format, source_initialized, root, pipeline,
                      key, fence, completion_value, budget, result);
    }
    const size_t count = size_t{desc.MipLevels} * desc.DepthOrArraySize;
    std::unique_ptr<std::unique_ptr<Prepared>[]> prepared(
        new (std::nothrow) std::unique_ptr<Prepared>[count]);
    if (!prepared) return E_OUTOFMEMORY;
    uint64_t charged = 0;
    for (uint32_t layer = 0; layer < desc.DepthOrArraySize; ++layer) {
        for (uint32_t mip = 0; mip < desc.MipLevels; ++mip) {
            auto& slot = prepared[size_t{layer} * desc.MipLevels + mip];
            const HRESULT status = Prepare(device, commands, source, view_format, true,
                root, pipeline, key, fence, completion_value, budget, &slot, mip, layer);
            if (FAILED(status)) return status;
            const uint64_t bytes = slot->projected->allocation_bytes();
            if (bytes > std::numeric_limits<uint64_t>::max() - charged) return E_INVALIDARG;
            charged += bytes;
        }
    }
    auto aggregate_desc = desc;
    aggregate_desc.Format = view_format;
    aggregate_desc.Flags = D3D12_RESOURCE_FLAG_NONE;
    aggregate_desc.Layout = D3D12_TEXTURE_LAYOUT_UNKNOWN;
    const auto info = device->GetResourceAllocationInfo(0, 1, &aggregate_desc);
    if (info.SizeInBytes == 0 || info.SizeInBytes == std::numeric_limits<uint64_t>::max() ||
        info.SizeInBytes > std::numeric_limits<uint64_t>::max() - charged) return E_INVALIDARG;
    if (!budget->Reserve(info.SizeInBytes)) return E_OUTOFMEMORY;
    ComPtr<ProjectedTextureRetirement> hold;
    hold.Attach(new (std::nothrow) ProjectedTextureRetirement(budget, info.SizeInBytes));
    if (!hold) {
        budget->Release(info.SizeInBytes);
        return E_OUTOFMEMORY;
    }
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = D3D12_HEAP_TYPE_DEFAULT;
    heap.CreationNodeMask = heap.VisibleNodeMask = 1;
    HRESULT status = device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE,
        &aggregate_desc, D3D12_RESOURCE_STATE_COPY_DEST, nullptr,
        IID_PPV_ARGS(&hold->shadow));
    if (FAILED(status)) return status;
    std::unique_ptr<ProjectedTexture> aggregate(new (std::nothrow) ProjectedTexture());
    if (!aggregate) return E_OUTOFMEMORY;
    aggregate->submitted_ = std::make_shared<std::atomic<bool>>(false);
    aggregate->canonical_subresources_.reset(new (std::nothrow) ID3D12Resource*[count]{});
    if (!aggregate->canonical_subresources_) return E_OUTOFMEMORY;
    hold->children.reset(new (std::nothrow) std::unique_ptr<ProjectedTexture>[count]);
    if (!hold->children) return E_OUTOFMEMORY;
    aggregate->mip_levels_ = desc.MipLevels;
    aggregate->array_layers_ = desc.DepthOrArraySize;
    aggregate->canonical_pixel_format_ = view_format;
    aggregate->texture_ = hold->shadow.Get();
    aggregate->retirement_ = hold;
    aggregate->fence_ = fence;
    aggregate->completion_value_ = completion_value;
    aggregate->allocation_bytes_ = charged + info.SizeInBytes;
    for (size_t index = 0; index < count; ++index) {
        aggregate->canonical_subresources_[index] = prepared[index]->projected->canonical_pixel_buffer();
        prepared[index]->projected->submitted_ = aggregate->submitted_;
    }
    aggregate->canonical_pixel_buffer_ = aggregate->canonical_subresources_[0];
    // Every allocation, quota reservation and validation above precedes recording.
    // From here only noexcept moves and void D3D12 command-list calls are used.
    constexpr auto read = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE |
                          D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE;
    for (size_t index = 0; index < count; ++index) {
        hold->children[index] = Finish(std::move(prepared[index]));
        auto* child = hold->children[index]->texture();
        Transition(commands, child, read, D3D12_RESOURCE_STATE_COPY_SOURCE);
        D3D12_TEXTURE_COPY_LOCATION from{}, to{};
        from.pResource = child;
        from.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        to.pResource = hold->shadow.Get();
        to.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        to.SubresourceIndex = static_cast<uint32_t>(index);
        commands->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
        Transition(commands, child, D3D12_RESOURCE_STATE_COPY_SOURCE, read);
    }
    Transition(commands, hold->shadow.Get(), D3D12_RESOURCE_STATE_COPY_DEST, read);
    *result = std::move(aggregate);
    return S_OK;

}


std::unique_ptr<ProjectedTexture> ProjectedTexture::CloneLease(
    std::shared_ptr<const ProjectedTexture> source) {
    if (!source || !source->retirement_.Get()) return nullptr;
    std::unique_ptr<ProjectedTexture> result(new (std::nothrow) ProjectedTexture());
    if (!result) return nullptr;
    ComPtr<ProjectedTextureRetirement> hold;
    hold.Attach(new (std::nothrow) ProjectedTextureRetirement(source));
    if (!hold) return nullptr;
    result->texture_ = source->texture_;
    result->canonical_pixel_buffer_ = source->canonical_pixel_buffer_;
    if (source->canonical_subresources_) {
        const size_t count = size_t{source->mip_levels_} * source->array_layers_;
        result->canonical_subresources_.reset(new (std::nothrow) ID3D12Resource*[count]);
        if (!result->canonical_subresources_) return nullptr;
        std::copy_n(source->canonical_subresources_.get(), count, result->canonical_subresources_.get());
    }
    result->mip_levels_ = source->mip_levels_;
    result->array_layers_ = source->array_layers_;
    result->canonical_pixel_format_ = source->canonical_pixel_format_;
    result->retirement_ = hold;
    result->fence_ = source->fence_;
    result->submitted_ = source->submitted_;
    result->completion_value_ = source->completion_value_;
    result->allocation_bytes_ = source->allocation_bytes_;
    return result;
}

HRESULT ProjectedTexture::CompletionStatus() const {
    const uint64_t completed = fence_->GetCompletedValue();
    if (completed == std::numeric_limits<uint64_t>::max()) {
        return DXGI_ERROR_DEVICE_REMOVED;
    }
    if (!submitted_->load(std::memory_order_acquire)) {
        return E_PENDING;
    }
    return completed < completion_value_ ? E_PENDING : S_OK;
}
}  // namespace glint::candidate::d3d12
