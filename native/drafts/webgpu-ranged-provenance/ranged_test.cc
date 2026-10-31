#include <array>
#include <cstdio>
#include <cstdlib>

#include "gpu/command_buffer/common/glint/webgpu_readback_provenance.h"
#include "gpu/command_buffer/common/glint/webgpu_readback_snapshot.h"
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"

using namespace glint::candidate;
size_t assertions = 0;
void Check(bool valid, int line) {
  ++assertions;
  if (!valid) {
    std::fprintf(stderr, "ranged assertion %d\n", line);
    std::exit(1);
  }
}
#define CHECK(x) Check((x), __LINE__)
int main() {
  {
    using namespace dawn::native;
    using namespace gpu::webgpu;
    std::array<uint8_t, 32> key{};
    key.fill(37);
    const auto policy = std::make_shared<const GlintWebGPUDevicePolicy>(
        std::move(*GlintWebGPUDevicePolicy::Create(1, key)));
    GlintWebGPUReadbackObserver observer(policy, 7, {});
    const GlintBufferIdentity output{reinterpret_cast<WGPUBuffer>(1), 4096};
    const GlintBufferIdentity copy{reinterpret_cast<WGPUBuffer>(2), 4096};
    const std::array uses{GlintShaderBufferUse{output, false, true}};
    observer.OnShaderScope({uses, true, true});
    CHECK(observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(output, 0, 4096) == GlintReadbackMapStatus::Denied);
    observer.OnBufferWrite(output, 0, 256, GlintBufferWriteKind::KnownBytes);
    CHECK(observer.ClassifyReadMap(output, 0, 256) == GlintReadbackMapStatus::Unrelated);
    CHECK(observer.ClassifyReadMap(output, 256, 3840) == GlintReadbackMapStatus::Denied);
    observer.OnBufferToBufferCopy(output, 0, copy, 0, 512);
    CHECK(observer.ClassifyReadMap(copy, 0, 256) == GlintReadbackMapStatus::Unrelated);
    CHECK(observer.ClassifyReadMap(copy, 256, 256) == GlintReadbackMapStatus::Denied);
    observer.OnBufferDestroyed(output.handle);
    CHECK(observer.ClassifyReadMap(copy, 256, 256) == GlintReadbackMapStatus::Denied);
    observer.OnBufferWrite(copy, 256, 256, GlintBufferWriteKind::KnownBytes);
    CHECK(observer.ClassifyReadMap(copy, 0, 4096) == GlintReadbackMapStatus::Unrelated);
    std::array<uint8_t, 512> raw{};
    CHECK(observer.PrepareReadMap(copy, 0, raw).status == GlintReadbackMapStatus::Unrelated);
    CHECK(observer.IsHealthy());
  }
  {
    WebGpuReadbackProvenance state(1024, 7);
    for (uint64_t index = 0; index < kWebGpuReadbackRegionLimit; ++index) {
      CHECK(state.RecordDerivedWrite(index + 1, index * 32, 16));
    }
    CHECK(state.PlanMap(0, 1024).count == kWebGpuReadbackRegionLimit);
    CHECK(state.RecordDerivedWrite(17, 4, 4));
    CHECK(state.PlanMap(0, 1024).count == kWebGpuReadbackRegionLimit);
    CHECK(state.RecordDerivedWrite(18, 0, 512));
    CHECK(state.PlanMap(0, 1024).count == 1);
    CHECK(state.InvalidateWrite(19, 4, 4));
    CHECK(state.PlanMap(0, 1024).count == 2);
    CHECK(state.PlanMap(4, 4).status == WebGpuMapProvenance::kUnrelated);
    CHECK(state.RecordDerivedWrite(20, 4, 4));
    CHECK(state.PlanMap(0, 1024).count == 1);
    CHECK(state.InvalidateWrite(21, 0, 512));
    CHECK(state.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnrelated);
  }
  {
    WebGpuReadbackProvenance state(1024, 7);
    for (uint64_t index = 0; index < kWebGpuReadbackRegionLimit; ++index) {
      CHECK(state.RecordDerivedWrite(index + 1, index * 32, 16));
    }
    CHECK(!state.RecordDerivedWrite(17, 768, 16));
    CHECK(state.PlanMap(0, 1024).status == WebGpuMapProvenance::kUnreliable);
  }
  {
    WebGpuReadbackProvenance state(4096, 7);
    CHECK(state.RecordDerivedWrite(1, 256, 64));
    CHECK(state.PlanMap(0, 256).status == WebGpuMapProvenance::kUnrelated);
    CHECK(state.PlanMap(256, 64).status == WebGpuMapProvenance::kShaderDerived);
    CHECK(state.PlanMap(320, 3776).status == WebGpuMapProvenance::kUnrelated);
    CHECK(state.InvalidateWrite(2, 272, 16));
    CHECK(state.PlanMap(272, 16).status == WebGpuMapProvenance::kUnrelated);
    CHECK(state.PlanMap(256, 16).status == WebGpuMapProvenance::kShaderDerived);
    CHECK(state.PlanMap(288, 32).status == WebGpuMapProvenance::kShaderDerived);
    CHECK(state.RecordDerivedWrite(3, 272, 16));
    CHECK(state.PlanMap(256, 64).count == 1);
    WebGpuReadbackProvenance copied(4096, 7);
    CHECK(copied.RecordBufferCopy(4, 512, state, 240, 96));
    CHECK(copied.PlanMap(512, 16).status == WebGpuMapProvenance::kUnrelated);
    CHECK(copied.PlanMap(528, 64).status ==
          WebGpuMapProvenance::kShaderDerived);
    CHECK(copied.PlanMap(592, 16).status == WebGpuMapProvenance::kUnrelated);
    CHECK(copied.RecordBufferCopy(5, 512, state, 0, 96));
    CHECK(copied.PlanMap(512, 96).status == WebGpuMapProvenance::kUnrelated);
    CHECK(state.InvalidateWrite(6, 0, 4096));
    CHECK(state.PlanMap(0, 4096).status == WebGpuMapProvenance::kUnrelated);
  }
  {
    WebGpuReadbackProvenance state(4096, 7);
    const WebGpuReadbackLayout layout{0, 256, 16, 16,
                                      WebGpuPixelFormat::kRgba8Unorm};
    const WebGpuSnapshotToken token{7, 1, 1, 1};
    CHECK(state.RecordFullTextureCopy(1, layout, token));
    CHECK(state.RecordDerivedWrite(2, 256, 64));
    CHECK(state.PlanMap(0, 64).status == WebGpuMapProvenance::kReadback);
    CHECK(state.PlanMap(256, 64).status == WebGpuMapProvenance::kShaderDerived);
    const auto whole = state.PlanMap(0, 4096);
    CHECK(whole.status == WebGpuMapProvenance::kShaderDerived &&
          whole.count == 3);
    size_t snapshots = 0;
    for (size_t i = 0; i < whole.count; ++i) {
      if (whole.regions[i].snapshot == token) {
        ++snapshots;
      }
    }
    CHECK(snapshots == 2);
    CHECK(state.InvalidateWrite(3, 256, 64));
    CHECK(state.PlanMap(0, 4096).status == WebGpuMapProvenance::kReadback);
    CHECK(state.PlanMap(256, 64).status == WebGpuMapProvenance::kUnrelated);
  }
  {
    WebGpuReadbackProvenance state(16, 7);
    CHECK(!state.RecordDerivedWrite(1, 8, 16));
    CHECK(state.PlanMap(0, 16).status == WebGpuMapProvenance::kUnreliable);
  }
  {
    WebGpuReadbackProvenance state(64, 7);
    CHECK(state.RecordDerivedWrite(1, 0, 4));
    CHECK(!state.RecordDerivedWrite(1, 4, 4));
  }
  {
    WebGpuReadbackProvenance state(64, 7), other(64, 8);
    CHECK(other.RecordDerivedWrite(1, 0, 4));
    CHECK(!state.RecordBufferCopy(2, 0, other, 0, 4));
  }
  {
    WebGpuReadbackRegion opaque;
    opaque.kind = WebGpuReadbackRegionKind::kShaderDerived;
    opaque.size = 64;
    CHECK(!WebGpuCanonicalByte(opaque, 0));
    WebGpuReadbackSnapshots store(7, 1, 65536, 65536);
    std::array<uint8_t, 64> bytes{};
    WebGpuReadbackPlan forged;
    forged.status = WebGpuMapProvenance::kReadback;
    forged.mapping_size = 64;
    forged.count = 1;
    forged.regions[0] = opaque;
    CHECK(!store.BuildProtectedShadow(forged, 0, bytes));
  }
  {
    std::array<WebGpuReadbackProvenance, 4> states{
        WebGpuReadbackProvenance(64, 7), WebGpuReadbackProvenance(64, 7),
        WebGpuReadbackProvenance(64, 7), WebGpuReadbackProvenance(64, 7)};
    std::array<std::array<bool, 16>, 4> oracle{};
    uint64_t random = 0x6c696e74;
    auto next = [&] {
      random ^= random << 13;
      random ^= random >> 7;
      random ^= random << 17;
      return random;
    };
    for (uint64_t sequence = 1; sequence <= 4000; ++sequence) {
      size_t dest = next() % 4, start = next() % 17,
             length = next() % (17 - start);
      const size_t operation = next() % 3;
      if (operation == 0) {
        CHECK(states[dest].RecordDerivedWrite(sequence, start * 4, length * 4));
        for (size_t i = start; i < start + length; ++i) {
          oracle[dest][i] = true;
        }
      } else if (operation == 1) {
        CHECK(states[dest].InvalidateWrite(sequence, start * 4, length * 4));
        for (size_t i = start; i < start + length; ++i) {
          oracle[dest][i] = false;
        }
      } else {
        size_t source = (dest + 1 + next() % 3) % 4,
               from = next() % (17 - length);
        CHECK(states[dest].RecordBufferCopy(sequence, start * 4, states[source],
                                            from * 4, length * 4));
        for (size_t i = 0; i < length; ++i) {
          oracle[dest][start + i] = oracle[source][from + i];
        }
      }
      for (size_t buffer = 0; buffer < 4; ++buffer) {
        for (size_t begin = 0; begin <= 16; ++begin) {
          for (size_t end = begin; end <= 16; ++end) {
            bool derived = false;
            for (size_t i = begin; i < end; ++i) {
              derived |= oracle[buffer][i];
            }
            const auto plan =
                states[buffer].PlanMap(begin * 4, (end - begin) * 4);
            CHECK(plan.status == (derived ? WebGpuMapProvenance::kShaderDerived
                                          : WebGpuMapProvenance::kUnrelated));
            CHECK(plan.count <= kWebGpuReadbackRegionLimit);
          }
        }
      }
    }
  }
  std::printf(
      "{\"passed\":true,\"assertions\":%zu,\"oracle_operations\":4000,\"shader_"
      "transformation_implemented\":false}\n",
      assertions);
}
