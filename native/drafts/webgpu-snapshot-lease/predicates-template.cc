// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <span>
#include <type_traits>
#include <utility>

size_t assertions = 0;
void Check(bool value) { ++assertions; if (!value) std::abort(); }
#define CHECK(x) Check(x)
#define DAWN_ASSERT(x) CHECK(x)
#define DAWN_NATIVE_EXPORT
struct Error {};
template <typename T> class ResultOrError {
  public:
    ResultOrError(Error) : failed_(true) {}
    ResultOrError(T value) : value_(std::move(value)) {}
    bool IsError() const { return failed_; }
    Error AcquireError() { CHECK(failed_); return {}; }
    T AcquireSuccess() { CHECK(!failed_); return std::move(value_); }
  private:
    bool failed_ = false;
    T value_{};
};
#define DAWN_INTERNAL_ERROR_IF(condition, message) do { if (condition) return Error{}; } while (false)
#define DAWN_TRY_ASSIGN(target, expression) do { auto result = (expression); \
    if (result.IsError()) return result.AcquireError(); target = result.AcquireSuccess(); } while (false)
using HRESULT = int;
using DXGI_FORMAT = int;
constexpr HRESULT E_PENDING = 1;
constexpr DXGI_FORMAT DXGI_FORMAT_R8G8B8A8_UNORM = 1, DXGI_FORMAT_B8G8R8A8_UNORM = 2;
bool SUCCEEDED(HRESULT status) { return status == 0; }
namespace wgpu { enum class TextureFormat { RGBA8Unorm, BGRA8Unorm, Other }; }
struct IUnknown {};
struct ID3D12RootSignature {};
struct ID3D12PipelineState {};
template <typename T> using ComPtr = std::shared_ptr<T>;
struct Desc { uint64_t Width = 7; uint32_t Height = 3; DXGI_FORMAT Format = 1; };
struct ID3D12Resource { Desc desc; Desc GetDesc() { return desc; } };
int cpu_alive = 0, gpu_alive = 0, projection_fault = 0;
bool capture_failure = false;
namespace glint::candidate::d3d12 {
class ProjectedTexture {
  public:
    explicit ProjectedTexture(DXGI_FORMAT format) {
        ++gpu_alive;
        texture_.desc.Format = format;
        pixels_.desc.Width = 7 * 3 * 4;
        if (projection_fault == 2) texture_.desc.Width = 0;
        if (projection_fault == 3) texture_.desc.Format = 99;
        if (projection_fault == 4) pixels_.desc.Width -= 4;
    }
    ~ProjectedTexture() { --gpu_alive; }
    ID3D12Resource* texture() { return &texture_; }
    ID3D12Resource* canonical_pixel_buffer() { return projection_fault == 5 ? nullptr : &pixels_; }
    DXGI_FORMAT canonical_pixel_format() const { return texture_.desc.Format; }
    ComPtr<IUnknown> retirement_handle() const { return hold_; }
  private:
    ID3D12Resource texture_, pixels_;
    ComPtr<IUnknown> hold_ = std::make_shared<IUnknown>();
};
class TextureCapture {
  public:
    explicit TextureCapture(bool bgra) : bgra_(bgra) { ++cpu_alive; }
    ~TextureCapture() { --cpu_alive; }
    HRESULT ReadCompleted(std::span<const uint8_t>* pixels) const { *pixels = bytes_; return 0; }
    uint32_t width() const { return 7; }
    uint32_t height() const { return 3; }
    uint32_t row_pitch() const { return 256; }
    DXGI_FORMAT format() const { return bgra_ ? 2 : 1; }
  private:
    bool bgra_;
    uint8_t bytes_[4] = {0x19, 0x21, 0x27, 0xff};
};
}
namespace dawn::native {
enum class GlintReadbackStatus { Pending, Ready, Failed };
enum class GlintReadbackFormat { Unsupported, Rgba8Unorm, Bgra8Unorm };
/* GLINT_API */
class CpuOnlySnapshot final : public GlintReadbackSnapshot {
  public:
    GlintReadbackStatus Read(std::span<const uint8_t>*) const override { return GlintReadbackStatus::Failed; }
    uint32_t GetWidth() const override { return 0; }
    uint32_t GetHeight() const override { return 0; }
    uint32_t GetRowPitch() const override { return 0; }
    GlintReadbackFormat GetFormat() const override { return GlintReadbackFormat::Unsupported; }
};
namespace d3d12 {
class Device;
class TextureView;
struct CommandRecordingContext {};
class Texture {
  public:
    Device* owner = nullptr;
    bool accessible = true, resource = true;
    wgpu::TextureFormat format = wgpu::TextureFormat::RGBA8Unorm;
    Device* GetDevice() const { return owner; }
    bool HasAccess() const { return accessible; }
    bool GetD3D12Resource() const { return resource; }
    struct Format { wgpu::TextureFormat format; };
    Format GetFormat() const { return {format}; }
    DXGI_FORMAT GetD3D12Format() const { return format == wgpu::TextureFormat::BGRA8Unorm ? 2 : 1; }
};
/* GLINT_NATIVE */
class Device {
  public:
    Device() { projector = GlintTextureProjector::Create(this).AcquireSuccess(); }
    bool IsLockedByCurrentThreadIfNeeded() const { return true; }
    ResultOrError<GlintTextureProjector*> GetGlintTextureProjector() { return projector.get(); }
    std::unique_ptr<GlintTextureProjector> projector;
};
ResultOrError<std::unique_ptr<GlintTextureProjector>> GlintTextureProjector::Create(Device* device) {
    return std::unique_ptr<GlintTextureProjector>(new GlintTextureProjector(device));
}
ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>>
GlintTextureProjector::RecordTexture(CommandRecordingContext*, Texture*, DXGI_FORMAT format) {
    if (projection_fault == 1) return Error{};
    return std::make_unique<glint::candidate::d3d12::ProjectedTexture>(format);
}
/* GLINT_COPY */
/* GLINT_LEASE */
/* GLINT_SNAPSHOT */
ResultOrError<std::unique_ptr<glint::candidate::d3d12::TextureCapture>>
RecordGlintTextureReadbackSnapshot(Device*, CommandRecordingContext*, Texture* texture) {
    CHECK(gpu_alive == 1);
    if (capture_failure) return Error{};
    return std::make_unique<glint::candidate::d3d12::TextureCapture>(
        texture->format == wgpu::TextureFormat::BGRA8Unorm);
}
/* GLINT_FACTORY */
}  // namespace d3d12
}  // namespace dawn::native
int main() {
    using namespace dawn::native;
    using namespace dawn::native::d3d12;
    static_assert(std::is_default_constructible_v<CpuOnlySnapshot>);
    static_assert(!std::is_default_constructible_v<GlintGpuReadbackSnapshot>);
    CpuOnlySnapshot cpu_only;
    CHECK(!cpu_only.GetGpuSnapshot());
    for (int iteration = 0; iteration < 512; ++iteration) {
        alignas(Device) std::byte storage[sizeof(Device)];
        Device* device = std::construct_at(reinterpret_cast<Device*>(storage));
        Device other;
        Texture texture;
        texture.owner = device;
        texture.format = iteration % 2 ? wgpu::TextureFormat::BGRA8Unorm : wgpu::TextureFormat::RGBA8Unorm;
        CommandRecordingContext context;
        for (int fault = 1; fault <= 5; ++fault) {
            projection_fault = fault;
            CHECK(RecordGlintNativeTextureSnapshot(device, &context, &texture).IsError());
            CHECK(cpu_alive == 0 && gpu_alive == 0);
        }
        projection_fault = 0;
        capture_failure = true;
        CHECK(RecordGlintNativeTextureSnapshot(device, &context, &texture).IsError());
        CHECK(cpu_alive == 0 && gpu_alive == 0);
        capture_failure = false;
        auto result = RecordGlintNativeTextureSnapshot(device, &context, &texture);
        CHECK(!result.IsError());
        auto snapshot = result.AcquireSuccess();
        auto lease = snapshot->GetGpuSnapshot();
        CHECK(lease && lease->GetWidth() == 7 && lease->GetHeight() == 3);
        CHECK(lease->GetFormat() == snapshot->GetFormat());
        CHECK(!other.projector->ResolveSnapshot(lease));
        CHECK(!device->projector->ResolveSnapshot(nullptr));
        auto native = device->projector->ResolveSnapshot(lease);
        CHECK(native && native->PixelBuffer() && native->RetirementHandle());
        CHECK(native->PixelFormat() == texture.GetD3D12Format());
        std::span<const uint8_t> pixels;
        CHECK(snapshot->Read(&pixels) == GlintReadbackStatus::Ready && pixels.size() == 4 && pixels[0] == 0x19);
        snapshot.reset();
        CHECK(cpu_alive == 0 && gpu_alive == 1);
        std::destroy_at(device);
        device = std::construct_at(reinterpret_cast<Device*>(storage));
        CHECK(texture.owner == device);
        CHECK(!device->projector->ResolveSnapshot(lease));
        lease.reset(); CHECK(gpu_alive == 1);
        native.reset(); CHECK(gpu_alive == 0);
        std::destroy_at(device);
    }
    std::printf("{\"passed\":true,\"assertions\":%zu,\"iterations\":512,"
        "\"backend_mocked\":true,\"source_extracted_gpu_lease_only\":true,"
        "\"logical_owner_identity_verified\":true,\"reused_device_address_rejected\":true,"
        "\"actual_native_device_queue_executed\":false}\n", assertions);
}
