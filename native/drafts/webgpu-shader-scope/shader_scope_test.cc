#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"

using namespace dawn::native;
using namespace gpu::webgpu;
size_t assertions = 0;
void Check(bool valid, int line) {
  ++assertions;
  if (!valid) {
    std::fprintf(stderr, "shader scope assertion %d\n", line);
    std::exit(1);
  }
}
#define CHECK(value) Check((value), __LINE__)
GlintBufferIdentity Buffer(size_t id, uint64_t size = 4096) {
  return {reinterpret_cast<WGPUBuffer>(id), size};
}
auto Policy() {
  std::array<uint8_t, 32> key{};
  key.fill(37);
  return std::make_shared<const GlintWebGPUDevicePolicy>(
      std::move(*GlintWebGPUDevicePolicy::Create(1, key)));
}
class Snapshot final : public GlintReadbackSnapshot {
 public:
  GlintReadbackStatus Read(std::span<const uint8_t>* pixels) const override {
    *pixels = bytes_;
    return GlintReadbackStatus::Ready;
  }
  uint32_t GetWidth() const override { return 4; }
  uint32_t GetHeight() const override { return 4; }
  uint32_t GetRowPitch() const override { return 256; }
  GlintReadbackFormat GetFormat() const override {
    return GlintReadbackFormat::Rgba8Unorm;
  }

 private:
  std::array<uint8_t, 1024> bytes_{};
};
void Capture(GlintWebGPUReadbackObserver& observer,
             GlintBufferIdentity buffer) {
  GlintTextureToBufferCopy copy{};
  copy.destination = buffer;
  copy.destinationRowPitch = 256;
  copy.width = copy.height = 4;
  copy.format = GlintReadbackFormat::Rgba8Unorm;
  observer.OnTextureToBufferCopy(copy, std::make_unique<Snapshot>());
}
void Scope(GlintWebGPUReadbackObserver& observer,
           std::span<const GlintShaderBufferUse> uses,
           bool textures) {
  observer.OnShaderScope({uses, textures, true});
}

int main() {
  const auto a = Buffer(1), b = Buffer(2), c = Buffer(3), d = Buffer(4);
  const auto policy = Policy();
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    std::array uses{GlintShaderBufferUse{a, true, false},
                    GlintShaderBufferUse{b, false, true}};
    Scope(observer, uses, true);
    CHECK(observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Unrelated);
    CHECK(observer.ClassifyReadMap(b, 0, b.size) ==
          GlintReadbackMapStatus::Denied);
    observer.OnBufferToBufferCopy(b, 0, c, 0, b.size);
    CHECK(observer.ClassifyReadMap(c, 0, c.size) ==
          GlintReadbackMapStatus::Denied);
    uses = {GlintShaderBufferUse{c, true, false},
            GlintShaderBufferUse{d, false, true}};
    Scope(observer, uses, false);
    CHECK(observer.ClassifyReadMap(d, 0, d.size) ==
          GlintReadbackMapStatus::Denied);
    observer.OnBufferWrite(d, 0, d.size, GlintBufferWriteKind::KnownBytes);
    CHECK(observer.ClassifyReadMap(d, 0, d.size) ==
          GlintReadbackMapStatus::Denied);
    std::array<uint8_t, 16> raw{};
    CHECK(observer.PrepareReadMap(d, 0, raw).status ==
          GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    Capture(observer, a);
    std::array uses{GlintShaderBufferUse{a, true, false},
                    GlintShaderBufferUse{b, false, true}};
    Scope(observer, uses, false);
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Protected);
    CHECK(observer.ClassifyReadMap(b, 0, b.size) ==
          GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {1, 65536, 65536});
    const std::array output{GlintShaderBufferUse{b, false, true}};
    for (size_t i = 0; i < 100; ++i) {
      Scope(observer, output, false);
    }
    CHECK(observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Unrelated);
    CHECK(observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    Capture(observer, a);
    const std::array write{GlintShaderBufferUse{a, false, true}};
    Scope(observer, write, false);
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    Capture(observer, a);
    const std::array aliases{GlintShaderBufferUse{b, false, true},
                             GlintShaderBufferUse{a, true, true}};
    Scope(observer, aliases, false);
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Denied);
    CHECK(observer.ClassifyReadMap(b, 0, b.size) ==
          GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    const std::array readonly{GlintShaderBufferUse{a, true, false}};
    Scope(observer, readonly, true);
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Unrelated);
  }
  for (const auto& invalid :
       {std::vector<GlintShaderBufferUse>{{a, true, false}, {a, false, true}},
        std::vector<GlintShaderBufferUse>{{{}, true, true}}}) {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    Scope(observer, invalid, false);
    CHECK(!observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(b, 0, b.size) ==
          GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    Capture(observer, a);
    const std::array resized{
        GlintShaderBufferUse{Buffer(1, 8192), true, false}};
    Scope(observer, resized, false);
    CHECK(!observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    std::array<GlintShaderBufferUse, 257> excessive{};
    Scope(observer, excessive, true);
    CHECK(!observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    std::array<std::thread, 4> threads;
    std::atomic<size_t> completed{0};
    for (auto& thread : threads) {
      thread = std::thread([&] {
        const std::array uses{GlintShaderBufferUse{a, true, false},
                              GlintShaderBufferUse{b, false, true}};
        for (size_t i = 0; i < 100; ++i) {
          Scope(observer, uses, true);
          ++completed;
        }
      });
    }
    for (auto& thread : threads) {
      thread.join();
    }
    CHECK(completed == 400);
    CHECK(observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(b, 0, b.size) ==
          GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    observer.OnShaderScope({});
    CHECK(!observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy, 7, {1024, 65536, 65536});
    std::array<GlintShaderBufferUse, 257> uses{};
    for (size_t i = 0; i < uses.size(); ++i) {
      uses[i] = {Buffer(i + 100), true, false};
    }
    Scope(observer, uses, false);
    CHECK(!observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(a, 0, a.size) ==
          GlintReadbackMapStatus::Denied);
  }
  std::printf(
      "{\"passed\":true,\"assertions\":%zu,\"interim_denial_only\":true,"
      "\"compatible_shader_protection\":false,\"concurrent_scopes\":400}\n",
      assertions);
}
