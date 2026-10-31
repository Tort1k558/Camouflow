// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "texture_capture.h"

#include <limits>
#include <new>
#include <utility>

namespace glint::candidate::d3d12 {
bool CaptureMemoryBudget::Reserve(uint64_t bytes) {
    if (bytes == 0 || bytes > limit_bytes_) {
        return false;
    }
    uint64_t used = used_bytes_.load(std::memory_order_relaxed);
    do {
        if (used > limit_bytes_ - bytes) {
            return false;
        }
    } while (!used_bytes_.compare_exchange_weak(used, used + bytes,
                                               std::memory_order_acq_rel,
                                               std::memory_order_relaxed));
    return true;
}

void CaptureMemoryBudget::Release(uint64_t bytes) {
    used_bytes_.fetch_sub(bytes, std::memory_order_acq_rel);
}

// Dawn's ReferenceUntilUnused accepts IUnknown. This object keeps the quota and
// actual GPU allocation together without adding a dependency on Blink or GPU common.
class CaptureRetirement final : public IUnknown {
  public:
    CaptureRetirement(std::shared_ptr<CaptureMemoryBudget> budget, uint64_t bytes)
        : budget_(std::move(budget)), bytes_(bytes) {}
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
    void SetResource(Microsoft::WRL::ComPtr<ID3D12Resource> resource) {
        resource_ = std::move(resource);
    }

  private:
    ~CaptureRetirement() {
        resource_.Reset();
        budget_->Release(bytes_);
    }
    std::atomic<ULONG> references_{1};
    std::shared_ptr<CaptureMemoryBudget> budget_;
    const uint64_t bytes_;
    Microsoft::WRL::ComPtr<ID3D12Resource> resource_;
};

HRESULT TextureCapture::Record(ID3D12Device* device,
                               ID3D12GraphicsCommandList* commands,
                               ID3D12Resource* texture,
                               ID3D12Fence* completion_fence,
                               uint64_t completion_value,
                               uint64_t allocation_budget,
                               std::unique_ptr<TextureCapture>* result) {
    return RecordImpl(device, commands, texture, completion_fence, completion_value,
                      allocation_budget, nullptr, result);
}

HRESULT TextureCapture::RecordBudgeted(
    ID3D12Device* device,
    ID3D12GraphicsCommandList* commands,
    ID3D12Resource* texture,
    ID3D12Fence* completion_fence,
    uint64_t completion_value,
    const std::shared_ptr<CaptureMemoryBudget>& allocation_budget,
    std::unique_ptr<TextureCapture>* result) {
    if (!allocation_budget || allocation_budget->limit_bytes() == 0) {
        return E_INVALIDARG;
    }
    return RecordImpl(device, commands, texture, completion_fence, completion_value,
                      allocation_budget->limit_bytes(), allocation_budget, result);
}

HRESULT TextureCapture::RecordImpl(ID3D12Device* device,
                               ID3D12GraphicsCommandList* commands,
                               ID3D12Resource* texture,
                               ID3D12Fence* completion_fence,
                               uint64_t completion_value,
                               uint64_t allocation_budget,
                               const std::shared_ptr<CaptureMemoryBudget>& budget,
                               std::unique_ptr<TextureCapture>* result) {
    if (!result || *result) {
        return E_INVALIDARG;
    }
    if (!device || !commands || !texture || !completion_fence || completion_value == 0 ||
        completion_value == std::numeric_limits<uint64_t>::max() || allocation_budget == 0) {
        return E_INVALIDARG;
    }
    auto source = texture->GetDesc();
    const uint64_t prior_completion = completion_fence->GetCompletedValue();
    if (prior_completion == std::numeric_limits<uint64_t>::max()) {
        return DXGI_ERROR_DEVICE_REMOVED;
    }
    if (prior_completion >= completion_value) {
        return E_INVALIDARG;
    }
    if (source.Format == DXGI_FORMAT_R8G8B8A8_TYPELESS) {
        source.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    } else if (source.Format == DXGI_FORMAT_B8G8R8A8_TYPELESS) {
        source.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    }
    if (source.Dimension != D3D12_RESOURCE_DIMENSION_TEXTURE2D || source.Width == 0 ||
        source.Height == 0 || source.DepthOrArraySize != 1 || source.MipLevels != 1 ||
        source.SampleDesc.Count != 1 ||
        (source.Format != DXGI_FORMAT_R8G8B8A8_UNORM &&
         source.Format != DXGI_FORMAT_B8G8R8A8_UNORM) ||
        source.Width > std::numeric_limits<uint32_t>::max() / 4) {
        return E_INVALIDARG;
    }
    // A signal from another device must never authorize reading this resource.
    Microsoft::WRL::ComPtr<ID3D12Device> texture_device, commands_device, fence_device;
    HRESULT hr = texture->GetDevice(IID_PPV_ARGS(&texture_device));
    if (FAILED(hr)) {
        return hr;
    }
    hr = commands->GetDevice(IID_PPV_ARGS(&commands_device));
    if (FAILED(hr)) {
        return hr;
    }
    hr = completion_fence->GetDevice(IID_PPV_ARGS(&fence_device));
    if (FAILED(hr)) {
        return hr;
    }
    if (texture_device.Get() != device || commands_device.Get() != device ||
        fence_device.Get() != device) {
        return E_INVALIDARG;
    }
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
    UINT rows = 0;
    UINT64 row_bytes = 0, total_bytes = 0;
    device->GetCopyableFootprints(&source, 0, 1, 0, &footprint, &rows, &row_bytes, &total_bytes);
    if (rows != source.Height || row_bytes != source.Width * 4 || footprint.Offset != 0 ||
        footprint.Footprint.Depth != 1 || footprint.Footprint.RowPitch < row_bytes ||
        footprint.Footprint.RowPitch % D3D12_TEXTURE_DATA_PITCH_ALIGNMENT != 0) {
        return E_INVALIDARG;
    }
    const uint64_t mapped_bytes = static_cast<uint64_t>(footprint.Footprint.RowPitch) * rows;
    if (total_bytes > mapped_bytes || mapped_bytes == 0 ||
        mapped_bytes > std::numeric_limits<size_t>::max() || mapped_bytes > allocation_budget) {
        return E_OUTOFMEMORY;
    }
    D3D12_RESOURCE_DESC destination{};
    destination.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    destination.Width = mapped_bytes;
    destination.Height = 1;
    destination.DepthOrArraySize = 1;
    destination.MipLevels = 1;
    destination.SampleDesc.Count = 1;
    destination.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
    const auto allocation = device->GetResourceAllocationInfo(0, 1, &destination);
    if (allocation.SizeInBytes == std::numeric_limits<uint64_t>::max() ||
        allocation.SizeInBytes == 0 || allocation.SizeInBytes > allocation_budget) {
        return E_OUTOFMEMORY;
    }
    Microsoft::WRL::ComPtr<CaptureRetirement> retirement;
    if (budget) {
        if (!budget->Reserve(allocation.SizeInBytes)) {
            return E_OUTOFMEMORY;
        }
        auto* hold = new (std::nothrow) CaptureRetirement(budget, allocation.SizeInBytes);
        if (!hold) {
            budget->Release(allocation.SizeInBytes);
            return E_OUTOFMEMORY;
        }
        retirement.Attach(hold);
    }
    std::unique_ptr<TextureCapture> capture(new (std::nothrow) TextureCapture());
    if (!capture) {
        return E_OUTOFMEMORY;
    }
    D3D12_HEAP_PROPERTIES heap{};
    heap.Type = D3D12_HEAP_TYPE_READBACK;
    heap.CreationNodeMask = heap.VisibleNodeMask = 1;
    hr = device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &destination,
                                         D3D12_RESOURCE_STATE_COPY_DEST, nullptr,
                                         IID_PPV_ARGS(&capture->resource_));
    if (FAILED(hr)) {
        return hr;
    }
    if (retirement) {
        retirement->SetResource(capture->resource_);
        capture->retirement_ = retirement;
    }
    void* mapped = nullptr;
    D3D12_RANGE read_range{0, static_cast<SIZE_T>(mapped_bytes)};
    hr = capture->resource_->Map(0, &read_range, &mapped);
    if (FAILED(hr)) {
        return hr;
    }
    if (!mapped) {
        capture->resource_->Unmap(0, nullptr);
        return E_FAIL;
    }
    capture->mapped_ = std::span<const uint8_t>(static_cast<const uint8_t*>(mapped),
                                                static_cast<size_t>(mapped_bytes));
    capture->submitted_ = std::make_shared<std::atomic<bool>>(false);
    capture->device_ = device;
    capture->fence_ = completion_fence;
    capture->completion_value_ = completion_value;
    capture->allocation_bytes_ = allocation.SizeInBytes;
    capture->width_ = static_cast<uint32_t>(source.Width);
    capture->height_ = source.Height;
    capture->row_pitch_ = footprint.Footprint.RowPitch;
    capture->format_ = source.Format;
    D3D12_TEXTURE_COPY_LOCATION destination_location{};
    destination_location.pResource = capture->resource_.Get();
    destination_location.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    destination_location.PlacedFootprint = footprint;
    D3D12_TEXTURE_COPY_LOCATION source_location{};
    source_location.pResource = texture;
    source_location.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    source_location.SubresourceIndex = 0;
    commands->CopyTextureRegion(&destination_location, 0, 0, 0, &source_location, nullptr);
    *result = std::move(capture);
    return S_OK;
}

TextureCapture::~TextureCapture() {
    if (resource_ && !mapped_.empty()) {
        D3D12_RANGE written{0, 0};
        resource_->Unmap(0, &written);
    }
    // Drop the direct resource reference before the final quota-owning handle.
    resource_.Reset();
    retirement_.Reset();
}

HRESULT TextureCapture::ReadCompleted(std::span<const uint8_t>* result) const {
    if (!result) {
        return E_INVALIDARG;
    }
    *result = {};
    if (!submitted_->load(std::memory_order_acquire)) {
        return E_PENDING;
    }
    const HRESULT device_status = device_->GetDeviceRemovedReason();
    if (FAILED(device_status)) {
        return device_status;
    }
    const uint64_t completed = fence_->GetCompletedValue();
    if (completed == std::numeric_limits<uint64_t>::max()) {
        return DXGI_ERROR_DEVICE_REMOVED;
    }
    if (completed < completion_value_) {
        return E_PENDING;
    }
    *result = mapped_;
    return S_OK;
}
}  // namespace glint::candidate::d3d12
