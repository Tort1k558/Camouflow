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
#include "gpu/command_buffer/common/glint/canvas_readback_candidate.h"
#include "third_party/boringssl/src/include/openssl/hmac.h"

using Microsoft::WRL::ComPtr;
size_t assertions = 0, image_cases = 0, hmac_cases = 0, changed_channels = 0;
void Check(bool valid, int line) {
  ++assertions;
  if (!valid) { std::fprintf(stderr, "compute assertion %d\n", line); std::exit(1); }
}
#define CHECK(x) Check((x), __LINE__)
void OkImpl(HRESULT value, int line) {
  if (FAILED(value)) std::fprintf(stderr, "compute HRESULT %08lx at %d\n", static_cast<unsigned long>(value), line);
  CHECK(SUCCEEDED(value));
}
#define Ok(value) OkImpl((value), __LINE__)
struct Parameters {
  std::array<uint8_t, 32> key{};
  uint32_t width = 0, height = 0, pitch = 0, offset = 0;
  uint32_t bgra = 0, operation = 0, message_bytes = 0, reserved = 0;
};
static_assert(sizeof(Parameters) == 64);
ComPtr<ID3D12Resource> Buffer(ID3D12Device* device, size_t bytes, D3D12_HEAP_TYPE type,
                             bool unordered = false) {
  D3D12_RESOURCE_DESC desc{};
  desc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
  desc.Width = bytes;
  desc.Height = desc.DepthOrArraySize = desc.MipLevels = 1;
  desc.SampleDesc.Count = 1;
  desc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
  desc.Flags = unordered ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE;
  D3D12_HEAP_PROPERTIES heap{};
  heap.Type = type;
  heap.CreationNodeMask = heap.VisibleNodeMask = 1;
  ComPtr<ID3D12Resource> result;
  Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &desc,
      type == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ : D3D12_RESOURCE_STATE_COPY_DEST,
      nullptr, IID_PPV_ARGS(&result)));
  return result;
}
void Transition(ID3D12GraphicsCommandList* cmd, ID3D12Resource* buffer,
                D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after) {
  D3D12_RESOURCE_BARRIER barrier{};
  barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
  barrier.Transition.pResource = buffer;
  barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
  barrier.Transition.StateBefore = before;
  barrier.Transition.StateAfter = after;
  cmd->ResourceBarrier(1, &barrier);
}
class Compute {
 public:
  explicit Compute(const char* shader_file, bool compile_only = false) {
    std::ifstream stream(shader_file, std::ios::binary);
    CHECK(stream.good());
    const std::string code{std::istreambuf_iterator<char>(stream), {}};
    std::array<ComPtr<ID3DBlob>, 2> shaders;
    const std::array<const char*, 2> entries{"edge_main", "hmac_main"};
    for (size_t i = 0; i < entries.size(); ++i) {
      ComPtr<ID3DBlob> errors;
      const HRESULT compiled = D3DCompile(code.data(), code.size(), "glint-edge-compute", nullptr,
          nullptr, entries[i], "cs_5_0", D3DCOMPILE_ENABLE_STRICTNESS | D3DCOMPILE_WARNINGS_ARE_ERRORS,
          0, &shaders[i], &errors);
      if (errors) std::fwrite(errors->GetBufferPointer(), 1, errors->GetBufferSize(), stderr);
      Ok(compiled);
      ComPtr<ID3DBlob> assembly;
      Ok(D3DDisassemble(shaders[i]->GetBufferPointer(), shaders[i]->GetBufferSize(), 0, nullptr, &assembly));
      std::ofstream dump(std::string(entries[i]) + ".asm", std::ios::binary);
      dump.write(static_cast<const char*>(assembly->GetBufferPointer()), assembly->GetBufferSize());
      CHECK(dump.good());
    }
    if (compile_only) return;
    ComPtr<IDXGIFactory6> factory;
    Ok(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)));
    ComPtr<IDXGIAdapter1> adapter;
    Ok(factory->EnumAdapterByGpuPreference(0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                                          IID_PPV_ARGS(&adapter)));
    DXGI_ADAPTER_DESC1 desc{};
    Ok(adapter->GetDesc1(&desc));
    CHECK((desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) == 0);
    Ok(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&device_)));
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
    Ok(D3D12SerializeRootSignature(&root_desc, D3D_ROOT_SIGNATURE_VERSION_1, &serialized, &errors));
    Ok(device_->CreateRootSignature(0, serialized->GetBufferPointer(), serialized->GetBufferSize(),
                                    IID_PPV_ARGS(&root_)));
    D3D12_COMPUTE_PIPELINE_STATE_DESC pipeline_desc{};
    pipeline_desc.pRootSignature = root_.Get();
    for (size_t i = 0; i < shaders.size(); ++i) {
      pipeline_desc.CS = {shaders[i]->GetBufferPointer(), shaders[i]->GetBufferSize()};
      Ok(device_->CreateComputePipelineState(&pipeline_desc, IID_PPV_ARGS(&pipelines_[i])));
    }
    D3D12_COMMAND_QUEUE_DESC queue_desc{};
    Ok(device_->CreateCommandQueue(&queue_desc, IID_PPV_ARGS(&queue_)));
    Ok(device_->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence_)));
  }
  std::vector<uint8_t> Run(std::span<const uint8_t> input, const Parameters& params) {
    CHECK(input.size() >= 64 && input.size() % 4 == 0 && input.size() <= 64 * 1024 * 1024);
    CHECK(params.operation <= 1 && params.bgra <= 1 && params.reserved == 0);
    if (params.operation == 1) {
      CHECK(params.message_bytes <= 55);
    } else {
      CHECK(params.width != 0 && params.height != 0 && params.width <= 8192 && params.height <= 8192);
      CHECK(params.pitch % 4 == 0 && params.offset % 4 == 0 && params.pitch >= params.width * 4);
      CHECK(static_cast<uint64_t>(params.offset) + static_cast<uint64_t>(params.pitch) *
            (params.height - 1) + static_cast<uint64_t>(params.width) * 4 <= input.size());
    }
    auto upload = Buffer(device_.Get(), input.size(), D3D12_HEAP_TYPE_UPLOAD);
    auto output = Buffer(device_.Get(), input.size(), D3D12_HEAP_TYPE_DEFAULT, true);
    auto readback = Buffer(device_.Get(), input.size(), D3D12_HEAP_TYPE_READBACK);
    ComPtr<ID3D12DescriptorHeap> descriptors;
    D3D12_DESCRIPTOR_HEAP_DESC heap_desc{};
    heap_desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
    heap_desc.NumDescriptors = 2;
    heap_desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    Ok(device_->CreateDescriptorHeap(&heap_desc, IID_PPV_ARGS(&descriptors)));
    const UINT increment = device_->GetDescriptorHandleIncrementSize(heap_desc.Type);
    auto cpu = descriptors->GetCPUDescriptorHandleForHeapStart();
    D3D12_SHADER_RESOURCE_VIEW_DESC srv{};
    srv.Format = DXGI_FORMAT_R32_TYPELESS;
    srv.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
    srv.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
    srv.Buffer.NumElements = static_cast<UINT>(input.size() / 4);
    srv.Buffer.Flags = D3D12_BUFFER_SRV_FLAG_RAW;
    device_->CreateShaderResourceView(upload.Get(), &srv, cpu);
    cpu.ptr += increment;
    D3D12_UNORDERED_ACCESS_VIEW_DESC uav{};
    uav.Format = DXGI_FORMAT_R32_TYPELESS;
    uav.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
    uav.Buffer.NumElements = static_cast<UINT>(input.size() / 4);
    uav.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
    device_->CreateUnorderedAccessView(output.Get(), nullptr, &uav, cpu);
    void* mapped = nullptr;
    const D3D12_RANGE no_read{0, 0};
    Ok(upload->Map(0, &no_read, &mapped));
    std::memcpy(mapped, input.data(), input.size());
    upload->Unmap(0, nullptr);
    ComPtr<ID3D12CommandAllocator> allocator;
    ComPtr<ID3D12GraphicsCommandList> cmd;
    Ok(device_->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator)));
    Ok(device_->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), pipelines_[params.operation].Get(),
                                 IID_PPV_ARGS(&cmd)));
    cmd->CopyBufferRegion(output.Get(), 0, upload.Get(), 0, input.size());
    Transition(cmd.Get(), output.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    cmd->SetComputeRootSignature(root_.Get());
    ID3D12DescriptorHeap* heaps[] = {descriptors.Get()};
    cmd->SetDescriptorHeaps(1, heaps);
    auto gpu = descriptors->GetGPUDescriptorHandleForHeapStart();
    cmd->SetComputeRootDescriptorTable(0, gpu);
    gpu.ptr += increment;
    cmd->SetComputeRootDescriptorTable(1, gpu);
    cmd->SetComputeRoot32BitConstants(2, sizeof(Parameters) / sizeof(uint32_t), &params, 0);
    cmd->Dispatch(params.operation == 1 ? 1 : (params.width + 3) / 4,
                  params.operation == 1 ? 1 : (params.height + 3) / 4, 1);
    Transition(cmd.Get(), output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    cmd->CopyBufferRegion(readback.Get(), 0, output.Get(), 0, input.size());
    Ok(cmd->Close());
    ID3D12CommandList* lists[] = {cmd.Get()};
    queue_->ExecuteCommandLists(1, lists);
    const uint64_t serial = ++serial_;
    Ok(queue_->Signal(fence_.Get(), serial));
    HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    CHECK(event != nullptr);
    const HRESULT armed = fence_->SetEventOnCompletion(serial, event);
    const DWORD waited = SUCCEEDED(armed) ? WaitForSingleObject(event, 30000) : WAIT_FAILED;
    CloseHandle(event);
    Ok(armed);
    CHECK(waited == WAIT_OBJECT_0);
    Ok(device_->GetDeviceRemovedReason());
    const D3D12_RANGE range{0, input.size()};
    Ok(readback->Map(0, &range, &mapped));
    std::vector<uint8_t> result(input.size());
    std::memcpy(result.data(), mapped, result.size());
    readback->Unmap(0, &no_read);
    return result;
  }
 private:
  ComPtr<ID3D12Device> device_;
  ComPtr<ID3D12RootSignature> root_;
  std::array<ComPtr<ID3D12PipelineState>, 2> pipelines_;
  ComPtr<ID3D12CommandQueue> queue_;
  ComPtr<ID3D12Fence> fence_;
  uint64_t serial_ = 0;
};

void HmacCase(Compute& gpu, const std::array<uint8_t, 32>& key, std::span<const uint8_t> data,
              const char* known = nullptr) {
  Parameters params;
  params.key = key;
  params.operation = 1;
  params.message_bytes = static_cast<uint32_t>(data.size());
  std::vector<uint8_t> input(64, 0);
  std::copy(data.begin(), data.end(), input.begin());
  const auto output = gpu.Run(input, params);
  std::array<uint8_t, 32> expected{};
  unsigned length = 0;
  CHECK(HMAC(EVP_sha256(), key.data(), key.size(), data.data(), data.size(), expected.data(), &length));
  CHECK(length == expected.size());
  for (size_t i = 0; i < expected.size(); ++i) CHECK(output[i] == expected[i]);
  if (known) {
    constexpr char digits[] = "0123456789abcdef";
    for (size_t i = 0; i < expected.size(); ++i) {
      CHECK(known[i * 2] == digits[expected[i] >> 4]);
      CHECK(known[i * 2 + 1] == digits[expected[i] & 15]);
    }
  }
  ++hmac_cases;
}
void ImageCase(Compute& gpu, uint32_t width, uint32_t height, uint32_t phase, bool bgra) {
  Parameters params;
  for (size_t i = 0; i < params.key.size(); ++i) params.key[i] = static_cast<uint8_t>(i * 11 + phase);
  params.width = width;
  params.height = height;
  params.offset = 64;
  params.pitch = ((width * 4 + 255) / 256) * 256;
  params.bgra = bgra;
  std::vector<uint8_t> packed(static_cast<size_t>(width) * height * 4);
  std::vector<uint8_t> source(params.offset + static_cast<size_t>(params.pitch) * height + 64, 0xa7);
  for (uint32_t y = 0; y < height; ++y) {
    for (uint32_t x = 0; x < width; ++x) {
      for (uint32_t c = 0; c < 4; ++c) {
        uint8_t value = c == 3 ? uint8_t{255} : static_cast<uint8_t>(x * 17 + y * 31 + c * 53 + phase);
        if (phase == 0) value = c == 3 ? uint8_t{255} : uint8_t{100};
        if (phase == 2 && c == 3) value = static_cast<uint8_t>((x + y) % 3 == 0 ? 0 : 127);
        if (phase == 3 && c == 3 && (x + y) % 3 == 0) value = 128;
        packed[(static_cast<size_t>(y) * width + x) * 4 + c] = value;
        const uint32_t native_c = bgra && c != 3 && c != 1 ? 2 - c : c;
        source[params.offset + y * params.pitch + x * 4 + native_c] = value;
      }
    }
  }
  auto protected_pixels = packed;
  CHECK(glint::candidate::TransformEdgeCoherentCanvas(protected_pixels, width, height, params.key));
  auto expected = source;
  for (uint32_t y = 0; y < height; ++y) {
    for (uint32_t x = 0; x < width; ++x) {
      for (uint32_t c = 0; c < 4; ++c) {
        const size_t i = (static_cast<size_t>(y) * width + x) * 4 + c;
        if (protected_pixels[i] != packed[i]) ++changed_channels;
        CHECK(std::abs(static_cast<int>(protected_pixels[i]) - packed[i]) <= 1);
        if (c == 3) CHECK(protected_pixels[i] == packed[i]);
        const uint32_t native_c = bgra && c != 3 && c != 1 ? 2 - c : c;
        expected[params.offset + y * params.pitch + x * 4 + native_c] = protected_pixels[i];
      }
    }
  }
  const auto first = gpu.Run(source, params);
  const auto repeated = gpu.Run(source, params);
  CHECK(first.size() == expected.size());
  for (size_t i = 0; i < expected.size(); ++i) { CHECK(first[i] == expected[i]); CHECK(repeated[i] == first[i]); }
  // Edge-colour projection is idempotent, including padding and non-opaque data.
  const auto projected = gpu.Run(first, params);
  CHECK(projected == first);
  if (phase == 1 && width == 65) {
    auto other_params = params;
    for (auto& byte : other_params.key) byte ^= 0x9d;
    auto other_pixels = packed;
    CHECK(glint::candidate::TransformEdgeCoherentCanvas(other_pixels, width, height, other_params.key));
    auto other_expected = source;
    for (uint32_t y = 0; y < height; ++y) {
      for (uint32_t x = 0; x < width; ++x) {
        for (uint32_t c = 0; c < 4; ++c) {
          const uint32_t native_c = bgra && c != 3 && c != 1 ? 2 - c : c;
          other_expected[params.offset + y * params.pitch + x * 4 + native_c] =
              other_pixels[(static_cast<size_t>(y) * width + x) * 4 + c];
        }
      }
    }
    const auto other = gpu.Run(source, other_params);
    CHECK(other == other_expected);
    CHECK(other != first);
    CHECK(gpu.Run(source, params) == first);
  }
  if (phase == 0 || phase == 2) CHECK(first == source);
  ++image_cases;
}
int main(int argc, char** argv) {
  if (argc == 3 && std::strcmp(argv[2], "--compile-only") == 0) {
    Compute compilation(argv[1], true);
    std::printf("{\"passed\":true,\"hardware_adapter\":false,\"compile_only\":true}\n");
    return 0;
  }
  CHECK(argc == 2);
  Compute gpu(argv[1]);
  std::array<uint8_t, 32> key{};
  std::fill_n(key.begin(), 20, uint8_t{0x0b});
  const std::string hello = "Hi There";
  HmacCase(gpu, key, {reinterpret_cast<const uint8_t*>(hello.data()), hello.size()},
           "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7");
  key.fill(0);
  std::memcpy(key.data(), "Jefe", 4);
  const std::string question = "what do ya want for nothing?";
  HmacCase(gpu, key, {reinterpret_cast<const uint8_t*>(question.data()), question.size()},
           "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843");
  for (uint32_t length : {0u, 1u, 33u, 55u}) {
    std::vector<uint8_t> message(length);
    for (size_t i = 0; i < key.size(); ++i) key[i] = static_cast<uint8_t>(i * 19 + length);
    for (size_t i = 0; i < message.size(); ++i) message[i] = static_cast<uint8_t>(i * 13 + 9);
    HmacCase(gpu, key, message);
  }
  for (bool bgra : {false, true}) {
    for (uint32_t phase = 0; phase < 4; ++phase) {
      for (const auto& size : {std::array<uint32_t, 2>{1, 1}, {7, 3}, {65, 5}, {32, 17}})
        ImageCase(gpu, size[0], size[1], phase, bgra);
    }
  }
  CHECK(changed_channels > 0);
  std::printf("{\"passed\":true,\"hardware_adapter\":true,\"hmac_cases\":%zu,\"image_cases\":%zu,"
              "\"assertions\":%zu,\"changed_channels\":%zu,\"browser_integrated\":false,"
              "\"shader_input_routing_implemented\":false}\n",
              hmac_cases, image_cases, assertions, changed_channels);
}
