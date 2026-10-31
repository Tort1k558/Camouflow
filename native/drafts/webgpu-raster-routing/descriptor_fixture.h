
#include <variant>
namespace descriptor_fixture {
using BindingIndex = uint32_t;
namespace wgpu { enum class ShaderStage { None, Compute }; }
struct Failure { bool failed; };
template <typename T> struct ResultOrError {
    ResultOrError(T v) : value(v) {}
    ResultOrError(Failure e) : error(e.failed) {}
    bool error = false;
    T value{};
};
#define DAWN_INTERNAL_ERROR_IF(condition, message) if (condition) return Failure{true}
#define DAWN_TRY(expression) do { const auto error = (expression); if (error.failed) return error; } while (false)
Failure CheckHRESULT(HRESULT status, const char*) { return {FAILED(status)}; }
template <typename T> T* ToBackend(T* value) { return value; }
struct Queue { uint64_t GetPendingCommandSerial() const { return 1; } };
struct Device {
    ID3D12Device* physical;
    Queue queue;
    ID3D12Device* GetD3D12Device() const { return physical; }
    Queue* GetQueue() { return &queue; }
};
struct Texture { ID3D12Resource* resource; ID3D12Resource* GetD3D12Resource() { return resource; } };
struct TextureView {
    Device* owner;
    Texture texture;
    D3D12_SHADER_RESOURCE_VIEW_DESC srv;
    Device* GetDevice() const { return owner; }
    Texture* GetTexture() { return &texture; }
    const D3D12_SHADER_RESOURCE_VIEW_DESC& GetSRVDescriptor() const { return srv; }
};
struct TextureBindingInfo {};
struct BufferBindingInfo {};
struct BindingInfo {
    wgpu::ShaderStage visibility = wgpu::ShaderStage::Compute;
    std::variant<TextureBindingInfo, BufferBindingInfo> bindingLayout;
};
struct Layout {
    std::array<BindingInfo, 2> bindings;
    std::array<uint32_t, 2> offsets{0, 1};
    uint32_t increment;
    uint32_t count = 2;
    explicit Layout(uint32_t stride) : increment(stride) {
        bindings[1].bindingLayout = BufferBindingInfo{};
    }
    uint32_t GetCbvUavSrvDescriptorCount() const { return count; }
    uint32_t GetBindingCount() const { return 2; }
    const auto& GetDescriptorHeapOffsets() const { return offsets; }
    const BindingInfo& GetBindingInfo(BindingIndex index) const { return bindings[index]; }
    uint32_t GetViewSizeIncrement() const { return increment; }
};
struct GPUDescriptorHeapAllocation { D3D12_GPU_DESCRIPTOR_HANDLE base{0}; };
struct CPUDescriptorHeapAllocation {
    D3D12_CPU_DESCRIPTOR_HANDLE base;
    D3D12_CPU_DESCRIPTOR_HANDLE GetBaseDescriptor() const { return base; }
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
        desc.NumDescriptors = 2;
        desc.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
        ComPtr<ID3D12DescriptorHeap> heap;
        Ok(owner->physical->CreateDescriptorHeap(&desc, IID_PPV_ARGS(&heap)));
        heaps.push_back(std::move(heap));
        occupied = false;
    }
    bool AllocateGPUDescriptors(uint32_t count, uint64_t serial,
                                D3D12_CPU_DESCRIPTOR_HANDLE* cpu,
                                GPUDescriptorHeapAllocation* result) {
        ++allocations;
        CHECK(count == 2 && serial == 1);
        if (occupied) return false;
        occupied = true;
        *cpu = heaps.back()->GetCPUDescriptorHandleForHeapStart();
        result->base = heaps.back()->GetGPUDescriptorHandleForHeapStart();
        return true;
    }
};
struct GlintTextureViewOverride {
    BindingIndex binding;
    ComPtr<IUnknown> retirement;
    ComPtr<ID3D12Resource> resource;
};
struct BindGroup {
    Device* owner;
    Layout* layout;
    TextureView* view;
    CPUDescriptorHeapAllocation mCPUViewAllocation;
    Device* GetDevice() { return owner; }
    Layout* GetLayout() { return layout; }
    TextureView* GetBindingAsTextureView(BindingIndex) { return view; }
    ResultOrError<bool> PopulateGlintViews(ShaderVisibleDescriptorAllocator*,
        std::span<const GlintTextureViewOverride>, GPUDescriptorHeapAllocation*);
};
#include "native_method.inc"
#undef DAWN_INTERNAL_ERROR_IF
#undef DAWN_TRY
}  // namespace descriptor_fixture
