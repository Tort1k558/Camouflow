// Copyright 2026 CamouFlow contributors.
// SPDX-License-Identifier: MIT
#include "texture_capture.h"

#include <dxgi1_6.h>
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <vector>

using Microsoft::WRL::ComPtr;
using glint::candidate::d3d12::TextureCapture;
namespace {
size_t assertions = 0;
void Check(bool condition) {
  ++assertions;
  if (!condition) {
    std::fprintf(stderr, "Assertion failed: %zu\n", assertions);
    std::exit(1);
  }
}
void Ok(HRESULT result) {
  if (FAILED(result)) {
    std::fprintf(stderr, "D3D12 HRESULT: %08lx\n", static_cast<unsigned long>(result));
  }
  Check(SUCCEEDED(result));
}
uint8_t Pixel(uint32_t x, uint32_t y, uint32_t channel, uint32_t phase) {
  return static_cast<uint8_t>((x * 17 + y * 31 + channel * 53 + phase * 101) % 256);
}
ComPtr<ID3D12Resource> Buffer(ID3D12Device* device, uint64_t bytes, D3D12_HEAP_TYPE type) {
  D3D12_RESOURCE_DESC descriptor{};
  descriptor.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
  descriptor.Width = bytes;
  descriptor.Height = 1;
  descriptor.DepthOrArraySize = descriptor.MipLevels = 1;
  descriptor.SampleDesc.Count = 1;
  descriptor.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
  D3D12_HEAP_PROPERTIES heap{};
  heap.Type = type;
  heap.CreationNodeMask = heap.VisibleNodeMask = 1;
  ComPtr<ID3D12Resource> resource;
  Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &descriptor,
      type == D3D12_HEAP_TYPE_UPLOAD ? D3D12_RESOURCE_STATE_GENERIC_READ : D3D12_RESOURCE_STATE_COPY_DEST,
      nullptr, IID_PPV_ARGS(&resource)));
  return resource;
}
void Transition(ID3D12GraphicsCommandList* commands, ID3D12Resource* resource,
                D3D12_RESOURCE_STATES before, D3D12_RESOURCE_STATES after) {
  D3D12_RESOURCE_BARRIER barrier{};
  barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
  barrier.Transition.pResource = resource;
  barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
  barrier.Transition.StateBefore = before;
  barrier.Transition.StateAfter = after;
  commands->ResourceBarrier(1, &barrier);
}

void Run(ID3D12Device* device, DXGI_FORMAT format, uint32_t width, uint32_t height) {
  const DXGI_FORMAT pixel_format = format == DXGI_FORMAT_R8G8B8A8_TYPELESS
      ? DXGI_FORMAT_R8G8B8A8_UNORM : format == DXGI_FORMAT_B8G8R8A8_TYPELESS
      ? DXGI_FORMAT_B8G8R8A8_UNORM : format;
  ComPtr<ID3D12CommandQueue> queue;
  D3D12_COMMAND_QUEUE_DESC queue_descriptor{};
  Ok(device->CreateCommandQueue(&queue_descriptor, IID_PPV_ARGS(&queue)));
  ComPtr<ID3D12CommandAllocator> allocator;
  Ok(device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator)));
  ComPtr<ID3D12GraphicsCommandList> commands;
  Ok(device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator.Get(), nullptr,
                              IID_PPV_ARGS(&commands)));
  ComPtr<ID3D12Fence> fence;
  Ok(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)));
  D3D12_RESOURCE_DESC descriptor{};
  descriptor.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
  descriptor.Width = width;
  descriptor.Height = height;
  descriptor.DepthOrArraySize = descriptor.MipLevels = 1;
  descriptor.Format = format;
  descriptor.SampleDesc.Count = 1;
  D3D12_HEAP_PROPERTIES heap{};
  heap.Type = D3D12_HEAP_TYPE_DEFAULT;
  heap.CreationNodeMask = heap.VisibleNodeMask = 1;
  ComPtr<ID3D12Resource> texture;
  Ok(device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &descriptor,
      D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&texture)));
  D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint{};
  UINT64 total = 0;
  device->GetCopyableFootprints(&descriptor, 0, 1, 0, &footprint, nullptr, nullptr, &total);
  footprint.Footprint.Format = pixel_format;
  std::array<ComPtr<ID3D12Resource>, 2> uploads;
  std::array<std::unique_ptr<TextureCapture>, 2> captures;
  std::span<const uint8_t> view;
  std::unique_ptr<TextureCapture> invalid;
  Check(TextureCapture::Record(device, commands.Get(), texture.Get(), fence.Get(), 0,
                                64 * 1024 * 1024, &invalid) == E_INVALIDARG);
  Check(!invalid);
  Check(TextureCapture::Record(device, commands.Get(), texture.Get(), fence.Get(), 1,
                                1, &invalid) == E_OUTOFMEMORY);
  Check(TextureCapture::Record(nullptr, commands.Get(), texture.Get(), fence.Get(), 1,
                                64 * 1024 * 1024, &invalid) == E_INVALIDARG);
  for (uint32_t phase = 0; phase < 2; ++phase) {
    uploads[phase] = Buffer(device, total, D3D12_HEAP_TYPE_UPLOAD);
    void* data = nullptr;
    D3D12_RANGE no_reads{0, 0};
    Ok(uploads[phase]->Map(0, &no_reads, &data));
    auto* pixels = static_cast<uint8_t*>(data);
    std::fill_n(pixels, static_cast<size_t>(total), 0xa5);
    for (uint32_t y = 0; y < height; ++y) {
      for (uint32_t x = 0; x < width; ++x) {
        for (uint32_t channel = 0; channel < 4; ++channel) {
          pixels[y * footprint.Footprint.RowPitch + x * 4 + channel] = Pixel(x, y, channel, phase);
        }
      }
    }
    uploads[phase]->Unmap(0, nullptr);
    if (phase != 0) {
      Transition(commands.Get(), texture.Get(), D3D12_RESOURCE_STATE_COPY_SOURCE,
                  D3D12_RESOURCE_STATE_COPY_DEST);
    }
    D3D12_TEXTURE_COPY_LOCATION source{};
    source.pResource = uploads[phase].Get();
    source.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    source.PlacedFootprint = footprint;
    D3D12_TEXTURE_COPY_LOCATION destination{};
    destination.pResource = texture.Get();
    destination.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    commands->CopyTextureRegion(&destination, 0, 0, 0, &source, nullptr);
    Transition(commands.Get(), texture.Get(), D3D12_RESOURCE_STATE_COPY_DEST,
                D3D12_RESOURCE_STATE_COPY_SOURCE);
    Ok(TextureCapture::Record(device, commands.Get(), texture.Get(), fence.Get(), 1,
                              64 * 1024 * 1024, &captures[phase]));
    Check(captures[phase]->ReadCompleted(&view) == E_PENDING && view.empty());
    captures[phase]->submission_marker()->store(true, std::memory_order_release);
    Check(captures[phase]->ReadCompleted(&view) == E_PENDING && view.empty());
    captures[phase]->submission_marker()->store(false, std::memory_order_release);
    auto* previous = captures[phase].get();
    Check(TextureCapture::Record(device, commands.Get(), texture.Get(), fence.Get(), 1,
                                  64 * 1024 * 1024, &captures[phase]) == E_INVALIDARG);
    Check(captures[phase].get() == previous);
    Check(captures[phase]->width() == width && captures[phase]->height() == height);
    Check(captures[phase]->row_pitch() >= width * 4 && captures[phase]->format() == pixel_format);
    Check(captures[phase]->allocation_bytes() <= 64 * 1024 * 1024);
  }
  // Keep the GPU allocation alive when the CPU capture is cancelled pre-submit.
  std::unique_ptr<TextureCapture> cancelled;
  Ok(TextureCapture::Record(device, commands.Get(), texture.Get(), fence.Get(), 1,
                            64 * 1024 * 1024, &cancelled));
  auto retirement = cancelled->retirement_resource();
  cancelled.reset();
  Check(retirement != nullptr);
  Ok(commands->Close());
  std::array<ID3D12CommandList*, 1> lists{commands.Get()};
  queue->ExecuteCommandLists(1, lists.data());
  captures[0]->submission_marker()->store(true, std::memory_order_release);
  // Fence completion alone must not admit an abandoned/uncommitted snapshot.
  Ok(queue->Signal(fence.Get(), 1));
  HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
  Check(event != nullptr);
  Ok(fence->SetEventOnCompletion(1, event));
  Check(WaitForSingleObject(event, 30000) == WAIT_OBJECT_0);
  CloseHandle(event);
  Check(TextureCapture::Record(device, commands.Get(), texture.Get(), fence.Get(), 1,
                                64 * 1024 * 1024, &invalid) == E_INVALIDARG);
  Check(captures[1]->ReadCompleted(&view) == E_PENDING && view.empty());
  captures[1]->submission_marker()->store(true, std::memory_order_release);
  for (uint32_t phase = 0; phase < 2; ++phase) {
    for (uint32_t repeat = 0; repeat < 2; ++repeat) {
      Ok(captures[phase]->ReadCompleted(&view));
      Check(view.size() == static_cast<size_t>(captures[phase]->row_pitch()) * height);
      for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width; ++x) {
          for (uint32_t channel = 0; channel < 4; ++channel) {
            Check(view[y * captures[phase]->row_pitch() + x * 4 + channel] == Pixel(x, y, channel, phase));
          }
        }
      }
    }
  }
  Check(device->GetDeviceRemovedReason() == S_OK);
}
}  // namespace

int main() {
  ComPtr<IDXGIFactory6> factory;
  Ok(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)));
  ComPtr<IDXGIAdapter1> adapter;
  Ok(factory->EnumAdapterByGpuPreference(0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                                        IID_PPV_ARGS(&adapter)));
  DXGI_ADAPTER_DESC1 descriptor{};
  Ok(adapter->GetDesc1(&descriptor));
  Check((descriptor.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) == 0);
  ComPtr<ID3D12Device> device;
  Ok(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&device)));
  for (auto format : {DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_FORMAT_B8G8R8A8_UNORM,
                     DXGI_FORMAT_R8G8B8A8_TYPELESS, DXGI_FORMAT_B8G8R8A8_TYPELESS}) {
    Run(device.Get(), format, 7, 3);
    Run(device.Get(), format, 65, 5);
  }
  std::printf("{\"passed\":true,\"hardware_adapter\":true,\"cases\":8,\"assertions\":%zu,"
              "\"browser_integrated\":false}\n", assertions);
}
