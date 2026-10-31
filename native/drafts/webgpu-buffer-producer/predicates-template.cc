// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <unknwn.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cstdio>
#include <cstdlib>
#include <iterator>
#include <memory>
#include <new>
#include <span>
#include <vector>
#include "third_party/dawn/src/dawn/native/d3d12/glint/buffer_scatter_parameters.h"
size_t assertions = 0, cases = 0, record_calls = 0;
bool record_failure = false;
void Check(bool condition, int line) { ++assertions; if (!condition) { std::fprintf(stderr, "producer assertion %d\n", line); std::abort(); } }
#define CHECK(x) Check((x), __LINE__)
#define DAWN_ASSERT(x) CHECK(x)
struct Failure { bool failed = false; };
using MaybeError = Failure;
template <typename T> struct ResultOrError {
    ResultOrError(T v) : value(std::move(v)) {}
    ResultOrError(Failure failure) : error(failure.failed) {}
    bool error = false;
    T value{};
};
#define DAWN_INTERNAL_ERROR_IF(condition, message) do { if (condition) return Failure{true}; } while (false)
#define DAWN_TRY(expression) do { auto failure = (expression); if (failure.failed) return failure; } while (false)
#define DAWN_TRY_ASSIGN(lhs, expression) do { auto result = (expression); if (result.error) return Failure{true}; lhs = std::move(result.value); } while (false)
Failure CheckHRESULT(HRESULT status, const char*) { return {FAILED(status)}; }
template <typename T> class ComPtr {
  public:
    ComPtr() = default;
    ComPtr(T* pointer) : mPointer(pointer) { if (mPointer) mPointer->AddRef(); }
    ComPtr(const ComPtr& value) : ComPtr(value.mPointer) {}
    ComPtr(ComPtr&& value) noexcept : mPointer(value.mPointer) { value.mPointer = nullptr; }
    ~ComPtr() { Reset(); }
    ComPtr& operator=(const ComPtr& value) { if (this != &value) { Reset(); mPointer = value.mPointer; if (mPointer) mPointer->AddRef(); } return *this; }
    ComPtr& operator=(ComPtr&& value) noexcept { if (this != &value) { Reset(); mPointer = value.mPointer; value.mPointer = nullptr; } return *this; }
    void Attach(T* pointer) { Reset(); mPointer = pointer; }
    void Reset() { if (mPointer) mPointer->Release(); mPointer = nullptr; }
    T* Get() const { return mPointer; }
    T* operator->() const { return mPointer; }
    explicit operator bool() const { return mPointer != nullptr; }
  private:
    T* mPointer = nullptr;
};
struct Resource : IUnknown {
    ULONG refs = 1;
    uint64_t width = 1024;
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** result) override {
        if (!result) return E_POINTER;
        *result = nullptr;
        if (iid != __uuidof(IUnknown)) return E_NOINTERFACE;
        *result = this; AddRef(); return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++refs; }
    ULONG STDMETHODCALLTYPE Release() override { CHECK(refs > 1); return --refs; }
    struct Desc { uint64_t Width; };
    Desc GetDesc() const { return {width}; }
};
struct CommandRecordingContext {
    size_t markers = 0;
    Resource commands;
    Resource* GetCommandList() { return &commands; }
    void AddGlintReadbackSubmission(std::shared_ptr<std::atomic<bool>> marker) { CHECK(marker != nullptr); ++markers; }
};
struct Device;
namespace wgpu { enum class BufferUsage { CopySrc }; }
struct Buffer {
    Device* device;
    size_t refs = 1, init_calls = 0, transition_calls = 0;
    uint64_t size = 4096;
    Resource resource;
    bool access = true, private_backing = true, init_failure = false;
    explicit Buffer(Device* owner) : device(owner) {}
    Device* GetDevice() const { return device; }
    uint64_t GetSize() const { return size; }
    bool HasAccess() const { return access; }
    bool HasPrivateGlintReadbackBacking() const { return private_backing; }
    Resource* GetD3D12Resource() { return &resource; }
    MaybeError EnsureGlintAllocationInitialized(CommandRecordingContext*) { ++init_calls; return {init_failure}; }
    void TrackUsageAndTransitionNow(CommandRecordingContext*, wgpu::BufferUsage) { CHECK(init_calls); ++transition_calls; }
    void AddRef() { ++refs; }
    void Release() { CHECK(refs > 1); --refs; }
};
using BufferBase = Buffer;
template <typename T> class Ref {
  public:
    Ref() = default;
    explicit Ref(T* pointer) : mPointer(pointer) { if (mPointer) mPointer->AddRef(); }
    Ref(const Ref& value) : Ref(value.mPointer) {}
    Ref(Ref&& value) noexcept : mPointer(value.mPointer) { value.mPointer = nullptr; }
    ~Ref() { if (mPointer) mPointer->Release(); }
    Ref& operator=(const Ref& value) { if (this != &value) { if (mPointer) mPointer->Release(); mPointer = value.mPointer; if (mPointer) mPointer->AddRef(); } return *this; }
    T* Get() const { return mPointer; }
    T* operator->() const { return mPointer; }
    explicit operator bool() const { return mPointer != nullptr; }
  private:
    T* mPointer = nullptr;
};
using WGPUBuffer = void*;
WGPUBuffer ToAPI(Buffer* value) { return value; }
template <typename T> T* ToBackend(T* value) { return value; }
struct GlintBufferIdentity { WGPUBuffer handle = nullptr; uint64_t size = 0; };
struct GlintShaderBufferUse { GlintBufferIdentity buffer; bool readable = false, writable = false; uint64_t offset = 0, size = 0; bool rangeKnown = false; };
inline constexpr size_t kGlintShaderBufferUseLimit = 256;
struct GlintShaderScope { std::span<const GlintShaderBufferUse> buffers; bool hasTextureInputs = false, complete = false; };
enum class GlintReadbackFormat { Rgba8Unorm, Bgra8Unorm, Unsupported };
struct GlintProjectionIdentity {};
struct GlintGpuPixelSnapshot {
    std::shared_ptr<const GlintProjectionIdentity> mIdentity;
    Resource* pixels = nullptr;
    Resource* PixelBuffer() const { return pixels; }
    ComPtr<IUnknown> RetirementHandle() const { return ComPtr<IUnknown>(pixels); }
};
struct GlintGpuReadbackSnapshot {
    std::shared_ptr<const GlintGpuPixelSnapshot> mNative;
    uint32_t width = 16, height = 16;
    GlintReadbackFormat format = GlintReadbackFormat::Rgba8Unorm;
    uint32_t GetWidth() const { return width; }
    uint32_t GetHeight() const { return height; }
    GlintReadbackFormat GetFormat() const { return format; }
};
struct GlintGpuInputRegion {
    GlintBufferIdentity buffer;
    uint64_t bufferOffset = 0, size = 0, snapshotOffset = 0, layoutOffset = 0;
    uint32_t rowPitch = 0, width = 0, height = 0, sourceX = 0, sourceY = 0;
    GlintReadbackFormat format = GlintReadbackFormat::Rgba8Unorm;
    std::shared_ptr<const GlintGpuReadbackSnapshot> snapshot;
    std::array<uint32_t, 16> mapping{};
};
struct GlintGpuInputPlan { uint64_t deviceEpoch = 7, policyGeneration = 1, sequence = 1; std::vector<GlintGpuInputRegion> regions; };
struct GlintReadbackObserver {
    std::shared_ptr<GlintGpuInputPlan> plan = std::make_shared<GlintGpuInputPlan>();
    size_t errors = 0, prepares = 0, commits = 0;
    bool prepare_failure = false, commit_failure = false;
    void OnExecutionError() { ++errors; }
    std::shared_ptr<const GlintGpuInputPlan> PrepareGpuInputPlan(const GlintShaderScope&) { ++prepares; return prepare_failure ? nullptr : plan; }
    bool CommitGpuInputPlan(std::shared_ptr<const GlintGpuInputPlan> incoming) { ++commits; return !commit_failure && incoming == plan; }
};
struct Fence { Resource fence; Resource* GetD3DFence() { return &fence; } };
struct Queue { Fence fence; Fence* GetSharedFence() { return &fence; } uint64_t GetPendingCommandSerial() { return 3; } };
struct Device {
    std::shared_ptr<GlintReadbackObserver> observer = std::make_shared<GlintReadbackObserver>();
    Queue queue;
    Resource physical;
    std::vector<ComPtr<IUnknown>> retirement;
    bool IsLockedByCurrentThreadIfNeeded() const { return true; }
    std::shared_ptr<GlintReadbackObserver> GetGlintReadbackObserver() const { return observer; }
    Queue* GetQueue() { return &queue; }
    Resource* GetD3D12Device() { return &physical; }
    int GetGlintReadbackBudget() { return 1; }
    void ReferenceUntilUnused(ComPtr<IUnknown> hold) { retirement.push_back(std::move(hold)); }
};
namespace glint::candidate::d3d12 {
struct ProjectedBufferRegion { ComPtr<Resource> canonical_source; ComPtr<IUnknown> source_retirement; BufferScatterParameters parameters; };
class ProjectedBuffer {
  public:
    static HRESULT Record(Resource*, Resource*, Resource*, IUnknown* original_owner, uint64_t logical,
        bool initialized, std::span<const ProjectedBufferRegion> regions, Resource*, Resource*, Resource*,
        uint64_t serial, int budget, std::unique_ptr<ProjectedBuffer>* result) {
        ++record_calls;
        CHECK(initialized && logical == 4096 && serial == 3 && budget == 1 && original_owner);
        if (record_failure) return E_FAIL;
        auto value = std::make_unique<ProjectedBuffer>();
        value->hold = ComPtr<IUnknown>(original_owner);
        for (const auto& region : regions) { CHECK(region.source_retirement && region.canonical_source); value->sources.push_back(region.source_retirement); }
        *result = std::move(value); return S_OK;
    }
    ComPtr<IUnknown> retirement_handle() const { return hold; }
    std::shared_ptr<std::atomic<bool>> submission_marker() { return std::make_shared<std::atomic<bool>>(false); }
    ComPtr<IUnknown> hold;
    std::vector<ComPtr<IUnknown>> sources;
};
}
/* GLINT_TYPES */
struct GlintTextureProjector {
    Device* mDevice;
    const std::shared_ptr<const GlintProjectionIdentity> mIdentity = std::make_shared<const GlintProjectionIdentity>();
    ComPtr<Resource> mRoot, mBufferPipeline;
    bool pipeline_failure = false;
    size_t pipeline_calls = 0;
    explicit GlintTextureProjector(Device* device) : mDevice(device), mRoot(&device->physical), mBufferPipeline(&device->physical) {}
    MaybeError EnsureBufferPipeline() { ++pipeline_calls; return {pipeline_failure}; }
    std::shared_ptr<const GlintGpuPixelSnapshot> ResolveSnapshot(const std::shared_ptr<const GlintGpuReadbackSnapshot>& snapshot) const;
    ResultOrError<std::unique_ptr<GlintBufferProjectionBatch>> RecordBuffers(CommandRecordingContext*, const GlintShaderScope&, std::span<const Ref<BufferBase>>);
};
/* GLINT_HELPERS */
/* GLINT_RESOLVE */
/* GLINT_PRODUCER */
GlintGpuInputRegion Region(Buffer* buffer, Resource* pixels, const GlintTextureProjector& projector, uint32_t offset = 0) {
    auto native = std::make_shared<GlintGpuPixelSnapshot>(); native->mIdentity = projector.mIdentity; native->pixels = pixels;
    auto snapshot = std::make_shared<GlintGpuReadbackSnapshot>(); snapshot->mNative = std::move(native);
    glint::candidate::BufferScatterParameters params{};
    params.destination_offset = offset; params.region_bytes = 32; params.destination_bytes = 4096;
    params.protected_bytes = 1024; params.full_width = params.full_height = 16;
    GlintGpuInputRegion region;
    region.buffer = {ToAPI(buffer), 4096}; region.bufferOffset = offset; region.size = 32;
    region.snapshot = snapshot; region.mapping = std::bit_cast<std::array<uint32_t, 16>>(params);
    return region;
}
int main() {
    for (int iteration = 0; iteration < 32; ++iteration) for (int fault = 0; fault < 38; ++fault) {
        ++cases; record_calls = 0; record_failure = false;
        Device device, other;
        Buffer first(&device), second(&device);
        Resource pixels;
        GlintTextureProjector projector(&device), foreign(&device);
        std::vector<Ref<BufferBase>> owners; owners.emplace_back(&first); owners.emplace_back(&second);
        std::vector<GlintShaderBufferUse> uses{
            {{&first, 4096}, true, false, 0, 256, true},
            {{&first, 4096}, true, true, 16, 64, true},
            {{&first, 4096}, true, true, 64, 32, true},
            {{&first, 4096}, true, true, 160, 16, true},
            {{&second, 4096}, true, false, 0, 256, true}};
        auto observer = device.observer;
        observer->plan->regions = {Region(&first, &pixels, projector), Region(&first, &pixels, projector, 128), Region(&second, &pixels, projector)};
        auto& region = observer->plan->regions[0];
        CommandRecordingContext context;
        if (fault == 2) device.observer.reset();
        if (fault == 4) uses.resize(257, uses[0]);
        if (fault == 5) owners.resize(257, owners[0]);
        if (fault == 6) owners.clear();
        if (fault == 7) first.device = &other;
        if (fault == 8) first.access = false;
        if (fault == 9) first.private_backing = false;
        if (fault == 10) uses[0].buffer.size = 4095;
        if (fault == 11) uses[0].rangeKnown = false;
        if (fault == 12) uses[0].offset = 4097;
        if (fault == 13) uses[0].size = 4097;
        if (fault == 14) observer->prepare_failure = true;
        if (fault == 15) observer->plan->regions.resize(4097, region);
        if (fault == 16) region.buffer.handle = &other;
        if (fault == 17) region.buffer.size = 4095;
        if (fault == 18) region.size = 0;
        if (fault == 19) region.bufferOffset = 4097;
        if (fault == 20) region.bufferOffset = 300;
        if (fault == 21) region.snapshot = Region(&first, &pixels, foreign).snapshot;
        if (fault == 22) region.snapshot.reset();
        if (fault == 23) region.mapping[0] = 1;
        if (fault == 24) region.mapping[1] = 31;
        if (fault == 25) region.mapping[13] = 4095;
        if (fault == 26) region.mapping[14] = 1023;
        if (fault == 27) region.mapping[10] = 15;
        if (fault == 28) region.mapping[11] = 15;
        if (fault == 29) region.mapping[12] = 1;
        if (fault == 30) region.format = GlintReadbackFormat::Bgra8Unorm;
        if (fault == 31) observer->plan->regions.resize(18, region);
        if (fault == 32) observer->commit_failure = true;
        if (fault == 33) projector.pipeline_failure = true;
        if (fault == 34) first.init_failure = true;
        if (fault == 35) record_failure = true;
        if (fault == 36) observer->plan->regions.clear();
        if (fault == 37) { uses[0].size = 16; uses[1].offset = 17; }
        const GlintShaderScope scope{uses, false, fault != 3};
        auto result = projector.RecordBuffers(fault == 1 ? nullptr : &context, scope, owners);
        const bool success = fault == 0 || fault == 36;
        CHECK(result.error != success);
        CHECK(observer->errors == static_cast<size_t>(!success && fault > 5));
        if (success) {
            CHECK(result.value && observer->commits == 1);
            if (fault == 0) {
                CHECK(result.value->buffers.size() == 2 && record_calls == 2 && context.markers == 2);
                CHECK(first.init_calls == 1 && second.init_calls == 1);
                const auto& writes = result.value->buffers[0].writableRanges;
                CHECK(writes.size() == 2 && writes[0].offset == 16 && writes[0].size == 80 && writes[1].offset == 160 && writes[1].size == 16);
                CHECK(first.refs > 2 && second.refs > 2);
            } else { CHECK(result.value->buffers.empty() && !record_calls && !projector.pipeline_calls); }
        }
        if (fault > 5 && fault < 33) CHECK(!record_calls && !first.init_calls && !context.markers);
        result.value.reset(); device.retirement.clear(); owners.clear();
        CHECK(first.refs == 1 && second.refs == 1 && pixels.refs == 1);
    }
    std::printf("{\"passed\":true,\"cases\":%zu,\"assertions\":%zu,\"native_producer_control_flow_executed\":true,\"backend_mocked\":true,\"actual_native_device_queue_executed\":false}\n", cases, assertions);
}
