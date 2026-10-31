#include "dawn/native/DawnNative.h"
#include "dawn/wire/WireServer.h"
#include "base/compiler_specific.h"
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
namespace dawn::native::d3d12 {
namespace {
/* GLINT_BYTE_ADAPTER */
}
std::unique_ptr<GlintByteReadbackSnapshot> WrapActualCapture(
    std::unique_ptr<glint::candidate::d3d12::TextureCapture> capture,uint64_t size) {
    return std::make_unique<NativeGlintByteReadbackSnapshot>(std::move(capture),size);
}
}
namespace gpu::webgpu {
namespace {
/* GLINT_WIRE_FILTER */
}
std::shared_ptr<dawn::wire::BufferReadbackFilter> ExtractedFilter(
    std::shared_ptr<dawn::native::GlintReadbackObserver> observer) {
    return std::make_shared<NativeReadbackFilter>(std::move(observer));
}
}
