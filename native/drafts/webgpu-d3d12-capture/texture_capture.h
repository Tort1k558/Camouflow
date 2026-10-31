// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#ifndef GLINT_D3D12_TEXTURE_CAPTURE_H_
#define GLINT_D3D12_TEXTURE_CAPTURE_H_

#include <d3d12.h>
#include <wrl/client.h>

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <span>

namespace glint::candidate::d3d12 {
class CaptureRetirement;

class CaptureMemoryBudget {
  public:
    explicit CaptureMemoryBudget(uint64_t limit_bytes) : limit_bytes_(limit_bytes) {}
    uint64_t limit_bytes() const { return limit_bytes_; }
    uint64_t used_bytes() const { return used_bytes_.load(std::memory_order_acquire); }

  private:
    friend class TextureCapture;
    friend class CaptureRetirement;
    bool Reserve(uint64_t bytes);
    void Release(uint64_t bytes);
    const uint64_t limit_bytes_;
    std::atomic<uint64_t> used_bytes_{0};
};

class TextureCapture {
  public:
    // Caller owns validation, source initialization and COPY_SOURCE transition.
    // Mark submission only after ExecuteCommandLists. Retain the returned resource
    // until that submission retires, even if this CPU capture is cancelled early.
    static HRESULT Record(ID3D12Device* device,
                          ID3D12GraphicsCommandList* commands,
                          ID3D12Resource* texture,
                          ID3D12Fence* completion_fence,
                          uint64_t completion_value,
                          uint64_t allocation_budget,
                          std::unique_ptr<TextureCapture>* result);
    // The caller must enqueue retirement_handle(), not just retirement_resource().
    // Aggregate allocation bytes stay charged while either CPU or GPU owns the handle.
    static HRESULT RecordBudgeted(ID3D12Device* device,
                                  ID3D12GraphicsCommandList* commands,
                                  ID3D12Resource* texture,
                                  ID3D12Fence* completion_fence,
                                  uint64_t completion_value,
                                  const std::shared_ptr<CaptureMemoryBudget>& allocation_budget,
                                  std::unique_ptr<TextureCapture>* result);
    ~TextureCapture();
    TextureCapture(const TextureCapture&) = delete;
    TextureCapture& operator=(const TextureCapture&) = delete;
    HRESULT ReadCompleted(std::span<const uint8_t>* result) const;
    std::shared_ptr<std::atomic<bool>> submission_marker() const { return submitted_; }
    Microsoft::WRL::ComPtr<ID3D12Resource> retirement_resource() const { return resource_; }
    Microsoft::WRL::ComPtr<IUnknown> retirement_handle() const { return retirement_; }
    uint32_t width() const { return width_; }
    uint32_t height() const { return height_; }
    uint32_t row_pitch() const { return row_pitch_; }
    uint64_t allocation_bytes() const { return allocation_bytes_; }
    DXGI_FORMAT format() const { return format_; }

  private:
    static HRESULT RecordImpl(ID3D12Device* device,
                              ID3D12GraphicsCommandList* commands,
                              ID3D12Resource* texture,
                              ID3D12Fence* completion_fence,
                              uint64_t completion_value,
                              uint64_t allocation_limit,
                              const std::shared_ptr<CaptureMemoryBudget>& budget,
                              std::unique_ptr<TextureCapture>* result);
    TextureCapture() = default;
    Microsoft::WRL::ComPtr<ID3D12Device> device_;
    Microsoft::WRL::ComPtr<ID3D12Resource> resource_;
    Microsoft::WRL::ComPtr<ID3D12Fence> fence_;
    Microsoft::WRL::ComPtr<IUnknown> retirement_;
    std::shared_ptr<std::atomic<bool>> submitted_;
    std::span<const uint8_t> mapped_;
    uint64_t completion_value_ = 0;
    uint64_t allocation_bytes_ = 0;
    uint32_t width_ = 0;
    uint32_t height_ = 0;
    uint32_t row_pitch_ = 0;
    DXGI_FORMAT format_ = DXGI_FORMAT_UNKNOWN;
};
}  // namespace glint::candidate::d3d12
#endif
