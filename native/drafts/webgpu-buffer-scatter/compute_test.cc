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
#include <span>
#include <string>
#include <vector>

#include "buffer_scatter.h"
#include "gpu/command_buffer/common/glint/canvas_readback_candidate.h"

using Microsoft::WRL::ComPtr;
size_t assertions = 0, cases = 0, changed_channels = 0, rejected = 0;
void Check(bool valid, int line) {
  ++assertions;
  if (!valid) {
    std::fprintf(stderr, "compute assertion %d\n", line);
    std::exit(1);
  }
}
#define CHECK(x) Check((x), __LINE__)
void OkImpl(HRESULT value, int line) {
  if (FAILED(value)) {
    std::fprintf(stderr, "compute HRESULT %08lx at %d\n",
                 static_cast<unsigned long>(value), line);
  }
  CHECK(SUCCEEDED(value));
}
#define Ok(value) OkImpl((value), __LINE__)
struct Parameters {
  std::array<uint8_t, 32> key{};
  uint32_t width = 0, height = 0, pitch = 0, offset = 0;
  uint32_t bgra = 0, operation = 0, message_bytes = 0, reserved = 0;
};
static_assert(sizeof(Parameters) == 64);
ComPtr<ID3D12Resource> Buffer(ID3D12Device* device,
                              size_t bytes,
                              D3D12_HEAP_TYPE type,
                              bool unordered = false) {
  D3D12_RESOURCE_DESC desc{};
  desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
  desc.Width = bytes;
  desc.Height = desc.DepthOrArraySize = desc.MipLevels = 1;
  desc.SampleDesc.Count = 1;
  desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
  desc.Flags = unordered ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS
                         : D3D12_RESOURCE_FLAG_NONE;
  D3D12_HEAP_PROPERTIES heap{};
  heap.Type = type;
  heap.CreationNodeMask = heap.VisibleNodeMask = 1;
  ComPtr<ID3D12Resource> result;
  Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc,
                                     type == D3D12_HEAP_TYPE_UPLOAD
                                         ? D3D12_RESOURCE_STATE_GENERIC_READ
                                         : D3D12_RESOURCE_STATE_COPY_DEST,
                                     nullptr, IID_PPV_ARGS(&result)));
  return result;
}
void Transition(ID3D12GraphicsCommandList* cmd,
                ID3D12Resource* buffer,
                D3D12_RESOURCE_STATES before,
                D3D12_RESOURCE_STATES after) {
  D3D12_RESOURCE_BARRIER barrier{};
  barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
  barrier.Transition.pResource = buffer;
  barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
  barrier.Transition.StateBefore = before;
  barrier.Transition.StateAfter = after;
  cmd->ResourceBarrier(1, &barrier);
}

using glint::candidate::BufferScatterParameters;
struct Output {
  std::vector<uint8_t> shadow, consumed, projected;
};
class Compute {
 public:
  Compute(const char* edge_file, const char* scatter_file) {
    std::array<ComPtr<ID3DBlob>, 3> shaders;
    const std::array<const char*, 3> files{edge_file, scatter_file,
                                           scatter_file};
    const std::array<const char*, 3> entries{"edge_main", "scatter_main",
                                             "consume_main"};
    for (size_t i = 0; i < shaders.size(); ++i) {
      std::ifstream stream(files[i], std::ios::binary);
      CHECK(stream.good());
      const std::string text{std::istreambuf_iterator<char>(stream), {}};
      ComPtr<ID3DBlob> errors;
      const HRESULT status = D3DCompile(
          text.data(), text.size(), "glint-buffer-scatter", nullptr, nullptr,
          entries[i], "cs_5_0",
          D3DCOMPILE_ENABLE_STRICTNESS | D3DCOMPILE_WARNINGS_ARE_ERRORS, 0,
          &shaders[i], &errors);
      if (errors) {
        std::fwrite(errors->GetBufferPointer(), 1, errors->GetBufferSize(),
                    stderr);
      }
      Ok(status);
    }
    ComPtr<IDXGIFactory6> factory;
    Ok(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)));
    ComPtr<IDXGIAdapter1> adapter;
    Ok(factory->EnumAdapterByGpuPreference(
        0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, IID_PPV_ARGS(&adapter)));
    DXGI_ADAPTER_DESC1 desc{};
    Ok(adapter->GetDesc1(&desc));
    CHECK((desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) == 0);
    Ok(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0,
                         IID_PPV_ARGS(&device_)));
    D3D12_ROOT_PARAMETER params[3]{};
    D3D12_DESCRIPTOR_RANGE ranges[2]{};
    ranges[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV;
    ranges[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_UAV;
    for (size_t i = 0; i < 2; ++i) {
      ranges[i].NumDescriptors = 1;
      params[i].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
      params[i].DescriptorTable.NumDescriptorRanges = 1;
      params[i].DescriptorTable.pDescriptorRanges = &ranges[i];
    }
    params[2].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
    params[2].Constants.Num32BitValues = sizeof(Parameters) / sizeof(uint32_t);
    D3D12_ROOT_SIGNATURE_DESC root_desc{};
    root_desc.NumParameters = 3;
    root_desc.pParameters = params;
    ComPtr<ID3DBlob> serialized, errors;
    Ok(D3D12SerializeRootSignature(&root_desc, D3D_ROOT_SIGNATURE_VERSION_1,
                                   &serialized, &errors));
    Ok(device_->CreateRootSignature(0, serialized->GetBufferPointer(),
                                    serialized->GetBufferSize(),
                                    IID_PPV_ARGS(&root_)));
    D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline_desc{};
    pipeline_desc.pRootSignature = root_.Get();
    for (size_t i = 0; i < shaders.size(); ++i) {
      pipeline_desc.CS = {shaders[i]->GetBufferPointer(),
                          shaders[i]->GetBufferSize()};
      Ok(device_->CreateComputePipelineState(&pipeline_desc,
                                             IID_PPV_ARGS(&pipelines_[i])));
    }
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    Ok(device_->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue_)));
    Ok(device_->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence_)));
  }

  Output Run(std::span<const uint8_t> input,
             std::span<const uint8_t> initial,
             const Parameters& edge,
             std::span<const BufferScatterParameters> mappings) {
    CHECK(input.size() >= 64 && input.size() % 4 == 0 && initial.size() >= 64 &&
          initial.size() % 4 == 0);
    CHECK(!mappings.empty());
    auto upload = Buffer(device_.Get(), input.size(), D3D12_HEAP_TYPE_UPLOAD);
    auto initial_upload =
        Buffer(device_.Get(), initial.size(), D3D12_HEAP_TYPE_UPLOAD);
    auto projected =
        Buffer(device_.Get(), input.size(), D3D12_HEAP_TYPE_DEFAULT, true);
    auto shadow =
        Buffer(device_.Get(), initial.size(), D3D12_HEAP_TYPE_DEFAULT, true);
    auto consumed =
        Buffer(device_.Get(), initial.size(), D3D12_HEAP_TYPE_DEFAULT, true);
    auto shadow_read =
        Buffer(device_.Get(), initial.size(), D3D12_HEAP_TYPE_READBACK);
    auto consumed_read =
        Buffer(device_.Get(), initial.size(), D3D12_HEAP_TYPE_READBACK);
    auto projected_read =
        Buffer(device_.Get(), input.size(), D3D12_HEAP_TYPE_READBACK);
    void* mapped = nullptr;
    const D3D12_RANGE no_read{0, 0};
    Ok(upload->Map(0, &no_read, &mapped));
    std::memcpy(mapped, input.data(), input.size());
    upload->Unmap(0, nullptr);
    Ok(initial_upload->Map(0, &no_read, &mapped));
    std::memcpy(mapped, initial.data(), initial.size());
    initial_upload->Unmap(0, nullptr);
    D3D12_DESCRIPTOR_HEAP_DESC desc{};
    desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    desc.NumDescriptors = 6;
    desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ComPtr<ID3D12DescriptorHeap> descriptors;
    Ok(device_->CreateDescriptorHeap(&desc, IID_PPV_ARGS(&descriptors)));
    const UINT increment = device_->GetDescriptorHandleIncrementSize(desc.Type);
    auto cpu = descriptors->GetCPUDescriptorHandleForHeapStart();
    auto srv = [&](ID3D12Resource* resource, size_t bytes) {
      D3D12_SHADER_RESOURCE_VIEW_DESC view{};
      view.Format = DXGI_FORMAT_R32_TYPELESS;
      view.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
      view.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
      view.Buffer.NumElements = static_cast<UINT>(bytes / 4);
      view.Buffer.Flags = D3D12_BUFFER_SRV_FLAG_RAW;
      device_->CreateShaderResourceView(resource, &view, cpu);
      cpu.ptr += increment;
    };
    auto uav = [&](ID3D12Resource* resource, size_t bytes) {
      D3D12_UNORDERED_ACCESS_VIEW_DESC view{};
      view.Format = DXGI_FORMAT_R32_TYPELESS;
      view.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
      view.Buffer.NumElements = static_cast<UINT>(bytes / 4);
      view.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
      device_->CreateUnorderedAccessView(resource, nullptr, &view, cpu);
      cpu.ptr += increment;
    };
    srv(upload.Get(), input.size());
    uav(projected.Get(), input.size());
    srv(projected.Get(), input.size());
    uav(shadow.Get(), initial.size());
    srv(shadow.Get(), initial.size());
    uav(consumed.Get(), initial.size());
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> cmd;
    Ok(device_->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,
                                       IID_PPV_ARGS(&allocator)));
    Ok(device_->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT,
                                  allocator.Get(), nullptr,
                                  IID_PPV_ARGS(&cmd)));
    cmd->CopyBufferRegion(projected.Get(), 0, upload.Get(), 0, input.size());
    cmd->CopyBufferRegion(shadow.Get(), 0, initial_upload.Get(), 0,
                          initial.size());
    cmd->CopyBufferRegion(consumed.Get(), 0, initial_upload.Get(), 0,
                          initial.size());
    Transition(cmd.Get(), projected.Get(), D3D12_RESOURCE_STATE_COPY_DEST,
               D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    Transition(cmd.Get(), shadow.Get(), D3D12_RESOURCE_STATE_COPY_DEST,
               D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    Transition(cmd.Get(), consumed.Get(), D3D12_RESOURCE_STATE_COPY_DEST,
               D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    cmd->SetComputeRootSignature(root_.Get());
    ID3D12DescriptorHeap* heaps[] = {descriptors.Get()};
    cmd->SetDescriptorHeaps(1, heaps);
    auto bind = [&](size_t pipeline, UINT first) {
      cmd->SetPipelineState(pipelines_[pipeline].Get());
      auto gpu = descriptors->GetGPUDescriptorHandleForHeapStart();
      gpu.ptr += increment * first;
      cmd->SetComputeRootDescriptorTable(0, gpu);
      gpu.ptr += increment;
      cmd->SetComputeRootDescriptorTable(1, gpu);
    };
    bind(0, 0);
    cmd->SetComputeRoot32BitConstants(2, 16, &edge, 0);
    cmd->Dispatch((edge.width + 3) / 4, (edge.height + 3) / 4, 1);
    Transition(cmd.Get(), projected.Get(),
               D3D12_RESOURCE_STATE_UNORDERED_ACCESS,
               D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    bind(1, 2);
    for (const auto& params : mappings) {
      CHECK(params.destination_bytes <= initial.size() &&
            params.protected_bytes <= input.size());
      cmd->SetComputeRoot32BitConstants(2, 16, &params, 0);
      const uint32_t threads = (params.region_bytes + 3) / 4;
      cmd->Dispatch(std::min(64u, (threads + 63) / 64), (threads + 4095) / 4096,
                    1);
      D3D12_RESOURCE_BARRIER barrier{};
      barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
      barrier.UAV.pResource = shadow.Get();
      cmd->ResourceBarrier(1, &barrier);
    }
    Transition(cmd.Get(), shadow.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS,
               D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
    bind(2, 4);
    BufferScatterParameters consume{};
    consume.destination_bytes = static_cast<uint32_t>(initial.size());
    cmd->SetComputeRoot32BitConstants(2, 16, &consume, 0);
    const uint32_t words = static_cast<uint32_t>(initial.size() / 4);
    cmd->Dispatch(std::min(64u, (words + 63) / 64), (words + 4095) / 4096, 1);
    Transition(cmd.Get(), shadow.Get(),
               D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,
               D3D12_RESOURCE_STATE_COPY_SOURCE);
    Transition(cmd.Get(), consumed.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS,
               D3D12_RESOURCE_STATE_COPY_SOURCE);
    Transition(cmd.Get(), projected.Get(),
               D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,
               D3D12_RESOURCE_STATE_COPY_SOURCE);
    cmd->CopyBufferRegion(shadow_read.Get(), 0, shadow.Get(), 0,
                          initial.size());
    cmd->CopyBufferRegion(consumed_read.Get(), 0, consumed.Get(), 0,
                          initial.size());
    cmd->CopyBufferRegion(projected_read.Get(), 0, projected.Get(), 0,
                          input.size());
    Ok(cmd->Close());
    ID3D12CommandList* lists[] = {cmd.Get()};
    queue_->ExecuteCommandLists(1, lists);
    const uint64_t serial = ++serial_;
    Ok(queue_->Signal(fence_.Get(), serial));
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    CHECK(event != nullptr);
    const HRESULT armed = fence_->SetEventOnCompletion(serial, event);
    const DWORD waited =
        SUCCEEDED(armed) ? WaitForSingleObject(event, 30000) : WAIT_FAILED;
    CloseHandle(event);
    Ok(armed);
    CHECK(waited == WAIT_OBJECT_0);
    Ok(device_->GetDeviceRemovedReason());
    auto read = [&](ID3D12Resource* resource, size_t bytes) {
      const D3D12_RANGE range{0, bytes};
      Ok(resource->Map(0, &range, &mapped));
      std::vector<uint8_t> result(bytes);
      std::memcpy(result.data(), mapped, bytes);
      resource->Unmap(0, &no_read);
      return result;
    };
    return {read(shadow_read.Get(), initial.size()),
            read(consumed_read.Get(), initial.size()),
            read(projected_read.Get(), input.size())};
  }

 private:
  ComPtr<ID3D12Device> device_;
  ComPtr<ID3D12RootSignature> root_;
  std::array<ComPtr<ID3D12PipelineState>, 3> pipelines_;
  ComPtr<ID3D12CommandQueue> queue_;
  ComPtr<ID3D12Fence> fence_;
  uint64_t serial_ = 0;
};

void Case(Compute& gpu, uint32_t fw, uint32_t fh, bool bgra, uint32_t variant) {
  Parameters edge;
  edge.width = fw;
  edge.height = fh;
  edge.pitch = fw * 4;
  for (size_t i = 0; i < edge.key.size(); ++i) {
    edge.key[i] = static_cast<uint8_t>(i * 17 + variant);
  }
  const size_t packed_bytes = static_cast<size_t>(fw) * fh * 4;
  std::vector<uint8_t> input(std::max(size_t{64}, packed_bytes), 0x91);
  for (uint32_t y = 0; y < fh; ++y) {
    for (uint32_t x = 0; x < fw; ++x) {
      for (uint32_t c = 0; c < 4; ++c) {
        input[(static_cast<size_t>(y) * fw + x) * 4 + c] =
            c == 3
                ? static_cast<uint8_t>((x + y + variant) % 7 == 0 ? 128 : 255)
                : static_cast<uint8_t>(x * 17 + y * 31 + c * 53);
      }
    }
  }
  std::vector<uint8_t> protected_pixels(input.begin(),
                                        input.begin() + packed_bytes);
  CHECK(glint::candidate::TransformEdgeCoherentCanvas(protected_pixels, fw, fh,
                                                      edge.key));
  auto projected_expected = input;
  std::copy(protected_pixels.begin(), protected_pixels.end(),
            projected_expected.begin());
  using namespace glint::candidate;
  WebGpuReadbackRegion region;
  region.kind = WebGpuReadbackRegionKind::kPixels;
  region.snapshot = {7, 17, 23, 3};
  const uint32_t sx = fw > 7 ? 3 : 0, sy = fh > 3 ? 1 : 0;
  const uint32_t cw = variant == 7 ? fw - sx : std::min(7u, fw - sx),
                 ch = variant == 7 ? fh - sy : std::min(3u, fh - sy);
  region.source_rect = {sx, sy, fw, fh};
  region.snapshot_layout = {
      variant == 4 ? (uint64_t{1} << 40) + 64 : 64,
      (variant == 5 || variant == 6)
          ? 0xffffff00u
          : (ch == 1 && variant == 1 ? 0u : ((cw * 4 + 255) / 256) * 256),
      cw, ch,
      bgra ? WebGpuPixelFormat::kBgra8Unorm : WebGpuPixelFormat::kRgba8Unorm};
  const uint64_t pitch = region.snapshot_layout.row_pitch
                             ? region.snapshot_layout.row_pitch
                             : cw * 4;
  region.buffer_offset = 65 + variant % 3;
  region.snapshot_offset = region.snapshot_layout.offset;
  region.size = pitch * (ch - 1) + cw * 4;
  if (variant == 2 && region.size > 5) {
    region.snapshot_offset += 3;
    region.size -= 5;
  }
  if (variant == 3) {
    region.snapshot_offset -= 3;
    region.size += 3;
  }
  if (variant == 5) {
    region.snapshot_offset += pitch * (ch - 1) + 1;
    region.size = std::max(1u, cw * 4 - 2);
  }
  if (variant == 6) {
    region.snapshot_offset =
        region.snapshot_layout.offset + (ch > 1 ? pitch - 3 : 0);
    region.size = (ch > 1 ? 3 : 0) + cw * 4 + 3;
  }
  const uint64_t logical_bytes = region.buffer_offset + region.size + 17;
  const size_t allocated_bytes =
      static_cast<size_t>((logical_bytes + 3) & ~uint64_t{3});
  std::vector<uint8_t> initial(allocated_bytes, 0xa7), expected = initial;
  for (uint64_t i = 0; i < region.size; ++i) {
    const auto canonical =
        WebGpuCanonicalByte(region, region.buffer_offset + i);
    if (canonical) {
      initial[region.buffer_offset + i] = input[*canonical];
      expected[region.buffer_offset + i] = protected_pixels[*canonical];
    }
  }
  std::vector<BufferScatterParameters> mappings;
  const auto complete = BuildBufferScatterParameters(region, logical_bytes);
  CHECK(complete.has_value());

  for (uint64_t begin = 0; begin < region.size;) {
    const uint64_t size =
        std::min(region.size - begin, begin == 0   ? uint64_t{1}
                                      : begin == 1 ? uint64_t{3}
                                                   : region.size - begin);
    auto part = region;
    part.buffer_offset += begin;
    part.snapshot_offset += begin;
    part.size = size;
    if (const auto params = BuildBufferScatterParameters(part, logical_bytes)) {
      mappings.push_back(*params);
    } else {
      for (uint64_t i = 0; i < part.size; ++i) {
        CHECK(!WebGpuCanonicalByte(part, part.buffer_offset + i));
      }
    }
    begin += size;
  }
  CHECK(!mappings.empty());
  const auto repeated = mappings;
  mappings.insert(mappings.end(), repeated.begin(), repeated.end());
  const auto output = gpu.Run(input, initial, edge, mappings);
  CHECK(output.projected == projected_expected);
  for (size_t i = 0; i < expected.size(); ++i) {
    CHECK(output.shadow[i] == expected[i]);
    CHECK(output.consumed[i] == static_cast<uint8_t>(expected[i] ^ 0xa5));
    if (expected[i] != initial[i]) {
      ++changed_channels;
    }
  }
  for (size_t invalid = 0; invalid < 12; ++invalid) {
    auto bad = region;
    uint64_t size = logical_bytes;
    if (invalid == 0) {
      bad.kind = WebGpuReadbackRegionKind::kShaderDerived;
    }
    if (invalid == 1) {
      bad.snapshot.device_epoch = 0;
    }
    if (invalid == 2) {
      bad.snapshot.snapshot_id = 0;
    }
    if (invalid == 3) {
      bad.snapshot.source_version = 0;
    }
    if (invalid == 4) {
      bad.snapshot.policy_generation = 0;
    }
    if (invalid == 5) {
      bad.size = 0;
    }
    if (invalid == 6) {
      bad.buffer_offset = UINT64_MAX;
    }
    if (invalid == 7) {
      bad.snapshot_offset = UINT64_MAX;
    }
    if (invalid == 8) {
      size = kBufferScatterByteLimit + 1;
    }
    if (invalid == 9) {
      bad.source_rect.x = bad.source_rect.full_width + 1;
    }
    if (invalid == 10) {
      bad.snapshot_layout.format = static_cast<WebGpuPixelFormat>(9);
    }
    if (invalid == 11) {
      bad.snapshot_layout.row_pitch = 3;
    }
    CHECK(!BuildBufferScatterParameters(bad, size));
    ++rejected;
  }
  ++cases;
}
int main(int argc, char** argv) {
  CHECK(argc == 3);
  Compute gpu(argv[1], argv[2]);
  for (bool bgra : {false, true}) {
    for (uint32_t variant = 0; variant < 7; ++variant) {
      for (auto size :
           {std::array<uint32_t, 2>{1, 1}, {7, 3}, {65, 5}, {32, 17}}) {
        Case(gpu, size[0], size[1], bgra, variant);
      }
    }
  }
  for (bool bgra : {false, true}) {
    Case(gpu, 129, 65, bgra, 7);
  }
  CHECK(changed_channels > 0);
  std::printf(
      R"({"passed":true,"hardware_adapter":true,"cases":%zu,"assertions":%zu,"changed_channels":%zu,"rejected_parameters":%zu,"gpu_projection_scatter_consumer_verified":true,"split_only_scatter_verified":true,"duplicate_scatter_verified":true,"protected_source_unchanged":true,"native_binding_routing_installed":false,"browser_integrated":false})"
      "\n",
      cases, assertions, changed_channels, rejected);
}
