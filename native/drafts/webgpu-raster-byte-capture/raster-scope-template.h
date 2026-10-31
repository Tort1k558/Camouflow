#include <algorithm>
#include <memory>
#include <vector>
using dawn::native::GlintShaderBufferUse;
using dawn::native::kGlintShaderBufferUseLimit;
struct RasterBuffer { uint64_t size; uint64_t GetSize() const { return size; } };
using BufferBase = RasterBuffer;
template<class T> struct Ref {
    std::shared_ptr<T> value;
    T* Get() const { return value.get(); }
    T* operator->() const { return Get(); }
    explicit operator bool() const { return value != nullptr; }
};
WGPUBuffer ToAPI(BufferBase* buffer) { return reinterpret_cast<WGPUBuffer>(buffer); }
struct GlintBoundScope {
    std::vector<GlintShaderBufferUse> uses;
    std::vector<Ref<BufferBase>> owners;
    bool textureInputs = false;
};
/* GLINT_MERGE */