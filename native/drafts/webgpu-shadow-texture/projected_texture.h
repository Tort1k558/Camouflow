// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#ifndef GLINT_D3D12_PROJECTED_TEXTURE_H_
#define GLINT_D3D12_PROJECTED_TEXTURE_H_
#include "texture_capture.h"

namespace glint::candidate::d3d12 {
class ProjectedTexture {
 public:
  ProjectedTexture(const ProjectedTexture&) = delete;
  ProjectedTexture& operator=(const ProjectedTexture&) = delete;
  // Requires an initialized COPY_SOURCE texture, an open DIRECT command list and
  // the trusted edge_main pipeline/root ABI (two tables + sixteen DWORDs).
  // Changes compute pipeline/root/descriptor state; caller must restore it.
  static HRESULT Record(ID3D12Device* device,
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
                        std::unique_ptr<ProjectedTexture>* result);
  // Borrowed pointer: retain the retirement handle for every use of this resource.
  // Output state is NON_PIXEL_SHADER_RESOURCE | PIXEL_SHADER_RESOURCE.
  ID3D12Resource* texture() const { return texture_; }
  uint64_t allocation_bytes() const { return allocation_bytes_; }
  // Queue must retain this handle until GPU retirement, even after CPU deletion.
  Microsoft::WRL::ComPtr<IUnknown> retirement_handle() const { return retirement_; }
  std::shared_ptr<std::atomic<bool>> submission_marker() const { return submitted_; }
  HRESULT CompletionStatus() const;

 private:
  ProjectedTexture() = default;
  ID3D12Resource* texture_ = nullptr;
  Microsoft::WRL::ComPtr<IUnknown> retirement_;
  Microsoft::WRL::ComPtr<ID3D12Fence> fence_;
  std::shared_ptr<std::atomic<bool>> submitted_;
  uint64_t completion_value_ = 0;
  uint64_t allocation_bytes_ = 0;
};
}  // namespace glint::candidate::d3d12
#endif
