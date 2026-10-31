// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <span>
#include <utility>

size_t assertions = 0;
void Check(bool value) {
    ++assertions;
    if (!value) std::abort();
}
#define CHECK(x) Check(x)
#define DAWN_ASSERT(x) CHECK(x)
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
constexpr HRESULT E_PENDING = 1;
constexpr int DXGI_FORMAT_B8G8R8A8_UNORM = 2;
bool SUCCEEDED(HRESULT status) { return status == 0; }
namespace wgpu { enum class TextureFormat { RGBA8Unorm, BGRA8Unorm, Other }; }
int cpu_alive = 0, gpu_alive = 0, projection_calls = 0, capture_calls = 0;
bool projection_failure = false, capture_failure = false;
namespace glint::candidate::d3d12 {
class ProjectedTexture {
  public:
    ProjectedTexture() { ++gpu_alive; }
    ~ProjectedTexture() { --gpu_alive; }
};
class TextureCapture {
  public:
    explicit TextureCapture(bool bgra) : bgra_(bgra) { ++cpu_alive; }
    ~TextureCapture() { --cpu_alive; }
    HRESULT ReadCompleted(std::span<const uint8_t>* pixels) const {
        *pixels = bytes_; return 0;
    }
    uint32_t width() const { return 7; }
    uint32_t height() const { return 3; }
    uint32_t row_pitch() const { return 256; }
    int format() const { return bgra_ ? DXGI_FORMAT_B8G8R8A8_UNORM : 1; }
  private:
    bool bgra_;
    uint8_t bytes_[4] = {0x19, 0x21, 0x27, 0xff};
};
}
enum class GlintReadbackStatus { Pending, Ready, Failed };
enum class GlintReadbackFormat { Rgba8Unorm, Bgra8Unorm };
class GlintReadbackSnapshot {
  public:
    virtual ~GlintReadbackSnapshot() = default;
    virtual GlintReadbackStatus Read(std::span<const uint8_t>*) const = 0;
    virtual uint32_t GetWidth() const = 0;
    virtual uint32_t GetHeight() const = 0;
    virtual uint32_t GetRowPitch() const = 0;
    virtual GlintReadbackFormat GetFormat() const = 0;
};
class Device;
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
    int GetD3D12Format() const { return format == wgpu::TextureFormat::BGRA8Unorm ? 2 : 1; }
};
class GlintTextureProjector {
  public:
    explicit GlintTextureProjector(Device* device) : mDevice(device) {}
    ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>> RecordCopy(
        CommandRecordingContext*, Texture*);
    ResultOrError<std::unique_ptr<glint::candidate::d3d12::ProjectedTexture>> RecordTexture(
        CommandRecordingContext* context, Texture* texture, int format) {
        ++projection_calls;
        CHECK(context && texture && format == texture->GetD3D12Format());
        if (projection_failure) return Error{};
        return std::make_unique<glint::candidate::d3d12::ProjectedTexture>();
    }
  private:
    Device* mDevice;
};
class Device {
  public:
    GlintTextureProjector projector{this};
    bool unavailable = false;
    bool IsLockedByCurrentThreadIfNeeded() const { return true; }
    ResultOrError<GlintTextureProjector*> GetGlintTextureProjector() {
        if (unavailable) return Error{};
        return &projector;
    }
};
/* GLINT_SNAPSHOT */
/* GLINT_COPY */
ResultOrError<std::unique_ptr<glint::candidate::d3d12::TextureCapture>>
RecordGlintTextureReadbackSnapshot(Device*, CommandRecordingContext*, Texture* texture) {
    ++capture_calls;
    CHECK(gpu_alive == 1);
    if (capture_failure) return Error{};
    return std::make_unique<glint::candidate::d3d12::TextureCapture>(
        texture->format == wgpu::TextureFormat::BGRA8Unorm);
}
/* GLINT_FACTORY */
int main() {
    Device device, other;
    Texture texture;
    texture.owner = &device;
    CommandRecordingContext context;
    CHECK(RecordGlintNativeTextureSnapshot(nullptr, &context, &texture).IsError());
    CHECK(RecordGlintNativeTextureSnapshot(&device, nullptr, &texture).IsError());
    CHECK(RecordGlintNativeTextureSnapshot(&device, &context, nullptr).IsError());
    CHECK(RecordGlintNativeTextureSnapshot(&other, &context, &texture).IsError());
    CHECK(projection_calls == 0 && capture_calls == 0);
    device.unavailable = true;
    CHECK(RecordGlintNativeTextureSnapshot(&device, &context, &texture).IsError());
    device.unavailable = false;
    for (int iteration = 0; iteration < 1024; ++iteration) {
        texture.format = iteration % 2 ? wgpu::TextureFormat::BGRA8Unorm : wgpu::TextureFormat::RGBA8Unorm;
        for (int fault = 0; fault < 6; ++fault) {
            const auto format = texture.format;
            texture.accessible = fault != 0;
            texture.resource = fault != 1;
            if (fault == 2) texture.format = wgpu::TextureFormat::Other;
            projection_failure = fault == 3;
            capture_failure = fault == 4;
            const int before_capture = capture_calls;
            auto result = RecordGlintNativeTextureSnapshot(&device, &context, &texture);
            CHECK(result.IsError() == (fault != 5));
            if (fault < 4) CHECK(capture_calls == before_capture);
            if (!result.IsError()) {
                auto snapshot = result.AcquireSuccess();
                CHECK(snapshot && cpu_alive == 1 && gpu_alive == 1);
                CHECK(snapshot->GetWidth() == 7 && snapshot->GetHeight() == 3 && snapshot->GetRowPitch() == 256);
                CHECK(snapshot->GetFormat() == (format == wgpu::TextureFormat::BGRA8Unorm
                    ? GlintReadbackFormat::Bgra8Unorm : GlintReadbackFormat::Rgba8Unorm));
                std::span<const uint8_t> pixels;
                CHECK(snapshot->Read(&pixels) == GlintReadbackStatus::Ready);
                CHECK(pixels.size() == 4 && pixels[0] == 0x19);
            }
            CHECK(cpu_alive == 0 && gpu_alive == 0);
            texture.format = format;
        }
    }
    std::printf("{\"passed\":true,\"assertions\":%zu,\"factory_cases\":6149,"
                "\"backend_mocked\":true,\"source_extracted_paired_factory_only\":true,"
                "\"actual_native_device_queue_executed\":false}\n", assertions);
}
