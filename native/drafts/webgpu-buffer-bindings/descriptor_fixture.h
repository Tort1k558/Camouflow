// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <variant>
namespace descriptor_fixture {
using BindingIndex = uint32_t;
namespace wgpu {
enum class ShaderStage { None, Compute };
enum class BufferBindingType { Uniform, Storage, ReadOnlyStorage, InternalStorage, InternalReadonly, BindingNotUsed, Undefined };
}
constexpr auto kInternalStorageBufferBinding = wgpu::BufferBindingType::InternalStorage;
constexpr auto kInternalReadOnlyStorageBufferBinding = wgpu::BufferBindingType::InternalReadonly;
struct Failure { bool failed = false; };
using MaybeError = Failure;
template <typename T> struct ResultOrError {
    ResultOrError(T v) : value(v) {}
    ResultOrError(Failure e) : error(e.failed) {}
    bool error = false;
    T value{};
};
#define DAWN_INTERNAL_ERROR_IF(condition, message) do { if (condition) return Failure{true}; } while (false)
#define DAWN_TRY(expression) do { const auto failure = (expression); if (failure.failed) return failure; } while (false)
#define DAWN_UNREACHABLE() std::abort()
Failure CheckHRESULT(HRESULT status, const char*) { return {FAILED(status)}; }
template <typename T> T* ToBackend(T* value) { return value; }
template <typename T, typename U> T Align(T value, U alignment) {
    const T mask = static_cast<T>(alignment) - 1;
    return (value + mask) & ~mask;
}
struct Queue { uint64_t GetPendingCommandSerial() const { return 1; } };
struct Device {
    ID3D12Device* physical;
    Queue queue;
    ID3D12Device* GetD3D12Device() const { return physical; }
    Queue* GetQueue() { return &queue; }
};
struct Buffer {
    Device* owner;
    ID3D12Resource* resource;
    uint64_t size;
    bool accessible = true, private_backing = true;
    uint64_t va_bias = 0;
    Device* GetDevice() const { return owner; }
    uint64_t GetSize() const { return size; }
    bool HasAccess() const { return accessible; }
    bool HasPrivateGlintReadbackBacking() const { return resource && private_backing; }
    ID3D12Resource* GetD3D12Resource() const { return resource; }
    D3D12_GPU_VIRTUAL_ADDRESS GetVA() const { return resource->GetGPUVirtualAddress() + va_bias; }
};
struct BufferBinding { Buffer* buffer; uint64_t offset, size; };
struct Texture { ID3D12Resource* resource; ID3D12Resource* GetD3D12Resource() { return resource; } };
struct TextureView {
    Device* owner;
    Texture texture;
    D3D12_SHADER_RESOURCE_VIEW_DESC srv{};
    Device* GetDevice() const { return owner; }
    Texture* GetTexture() { return &texture; }
    const auto& GetSRVDescriptor() const { return srv; }
};
struct TextureBindingInfo {};
struct BufferBindingInfo { wgpu::BufferBindingType type = wgpu::BufferBindingType::Uniform; };
struct BindingInfo {
    wgpu::ShaderStage visibility = wgpu::ShaderStage::Compute;
    std::variant<TextureBindingInfo, BufferBindingInfo> bindingLayout = BufferBindingInfo{};
};
struct Layout {
    std::array<BindingInfo, 2> bindings;
    std::array<uint32_t, 2> offsets{0, 1};
    uint32_t increment, count = 2, dynamic_count = 0;
    explicit Layout(uint32_t stride) : increment(stride) {}
    uint32_t GetCbvUavSrvDescriptorCount() const { return count; }
    uint32_t GetBindingCount() const { return 2; }
    uint32_t GetDynamicBufferCount() const { return dynamic_count; }
    const auto& GetDescriptorHeapOffsets() const { return offsets; }
    const BindingInfo& GetBindingInfo(BindingIndex index) const { return bindings[index]; }
    uint32_t GetViewSizeIncrement() const { return increment; }
};
struct GPUDescriptorHeapAllocation { D3D12_GPU_DESCRIPTOR_HANDLE base{0}; };
struct CPUDescriptorHeapAllocation {
    D3D12_CPU_DESCRIPTOR_HANDLE base;
    auto GetBaseDescriptor() const { return base; }
};
struct ShaderVisibleDescriptorAllocator {
    Device* owner;
    std::vector<ComPtr<ID3D12DescriptorHeap>> heaps;
    bool occupied = false;
    size_t allocations = 0;
    explicit ShaderVisibleDescriptorAllocator(Device* device) : owner(device) { Switch(); }
    Device* GetDevice() const { return owner; }
    void Switch() {
        D3D12_DESCRIPTOR_HEAP_DESC desc{};
        desc.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV;
        desc.NumDescriptors = 2; desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
        ComPtr<ID3D12DescriptorHeap> heap;
        Ok(owner->physical->CreateDescriptorHeap(&desc, IID_PPV_ARGS(&heap)));
        heaps.push_back(std::move(heap)); occupied = false;
    }
    bool AllocateGPUDescriptors(uint32_t count, uint64_t serial,
                                D3D12_CPU_DESCRIPTOR_HANDLE* cpu, GPUDescriptorHeapAllocation* allocation) {
        ++allocations;
        CHECK(count > 0 && count <= 2 && serial == 1);
        if (occupied) return false;
        occupied = true;
        *cpu = heaps.back()->GetCPUDescriptorHandleForHeapStart();
        allocation->base = heaps.back()->GetGPUDescriptorHandleForHeapStart();
        return true;
    }
};
struct GlintTextureViewOverride { BindingIndex binding; ComPtr<IUnknown> retirement; ComPtr<ID3D12Resource> resource; };
struct GlintBufferViewOverride { BindingIndex binding; ComPtr<IUnknown> retirement; ComPtr<ID3D12Resource> resource; };
struct BindGroup {
    Device* owner;
    Layout* layout;
    std::array<BufferBinding, 2> buffers;
    CPUDescriptorHeapAllocation mCPUViewAllocation;
    Device* GetDevice() { return owner; }
    Layout* GetLayout() { return layout; }
    TextureView* GetBindingAsTextureView(BindingIndex) { return nullptr; }
    BufferBinding GetBindingAsBufferBinding(BindingIndex index) { return buffers[index]; }
    MaybeError ValidateGlintBufferOverrides(std::span<const GlintBufferViewOverride>);
    ResultOrError<D3D12_GPU_VIRTUAL_ADDRESS> ResolveGlintRootBufferAddress(
        BindingIndex, uint32_t, std::span<const GlintBufferViewOverride>);
    ResultOrError<bool> PopulateGlintViews(ShaderVisibleDescriptorAllocator*,
        std::span<const GlintTextureViewOverride>, GPUDescriptorHeapAllocation*);
    ResultOrError<bool> PopulateGlintViews(ShaderVisibleDescriptorAllocator*,
        std::span<const GlintTextureViewOverride>, std::span<const GlintBufferViewOverride>, GPUDescriptorHeapAllocation*);
};
#include "native_method.inc"
#undef DAWN_INTERNAL_ERROR_IF
#undef DAWN_TRY
#undef DAWN_UNREACHABLE
}  // namespace descriptor_fixture
