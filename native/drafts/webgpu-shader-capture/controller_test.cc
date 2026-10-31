#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
using namespace dawn::native;
using namespace gpu::webgpu;
size_t assertions = 0;
void Check(bool value,int line) {
  ++assertions;
  if (!value) { std::fprintf(stderr,"shader-byte controller assertion %d\n",line); std::exit(1); }
}
#define CHECK(x) Check((x),__LINE__)
struct ByteState {
  GlintReadbackStatus status = GlintReadbackStatus::Pending;
  std::vector<uint8_t> bytes;
  uint64_t declared;
  explicit ByteState(size_t size) : bytes(size,37), declared(size) {}
};
class ByteSnapshot final : public GlintByteReadbackSnapshot {
 public:
  explicit ByteSnapshot(std::shared_ptr<ByteState> state) : state_(std::move(state)) {}
  GlintReadbackStatus Read(std::span<const uint8_t>* bytes) const override {
    *bytes = {};
    if (state_->status == GlintReadbackStatus::Ready) *bytes = state_->bytes;
    return state_->status;
  }
  uint64_t GetByteSize() const override { return state_->declared; }
 private:
  std::shared_ptr<ByteState> state_;
};
class PixelSnapshot final : public GlintReadbackSnapshot {
 public:
  GlintReadbackStatus Read(std::span<const uint8_t>* pixels) const override {
    *pixels = bytes_; return GlintReadbackStatus::Ready;
  }
  uint32_t GetWidth() const override { return 1; }
  uint32_t GetHeight() const override { return 1; }
  uint32_t GetRowPitch() const override { return 256; }
  GlintReadbackFormat GetFormat() const override { return GlintReadbackFormat::Rgba8Unorm; }
 private:
  std::array<uint8_t,256> bytes_{};
};
auto Policy() {
  std::array<uint8_t,32> key{}; key.fill(17);
  return std::make_shared<const GlintWebGPUDevicePolicy>(
      std::move(*GlintWebGPUDevicePolicy::Create(3,key)));
}
GlintBufferIdentity Buffer(size_t id) { return {reinterpret_cast<WGPUBuffer>(id),64}; }
GlintShaderBufferUse Write(size_t id,uint64_t offset=0,uint64_t size=32) {
  return {Buffer(id),true,true,offset,size,true};
}
std::vector<GlintShaderByteResult> Results(const GlintShaderBytePlan& plan,
    std::vector<std::shared_ptr<ByteState>>* states=nullptr) {
  std::vector<GlintShaderByteResult> results;
  for (const auto& request : plan.requests) {
    auto state = std::make_shared<ByteState>(static_cast<size_t>(request.size));
    results.push_back({request.requestId,std::make_unique<ByteSnapshot>(state)});
    if (states) states->push_back(state);
  }
  return results;
}
int main() {
  const auto policy = Policy();
  std::array uses{Write(1)};
  const GlintShaderScope scope{uses,true,true};
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    const auto ineligible=observer.BeginShaderByteScope(scope,false);
    CHECK(ineligible.ticket == 0 && !ineligible.failed && observer.IsHealthy());
    observer.OnShaderScope(scope);
    CHECK(observer.ClassifyReadMap(Buffer(1),0,32) == GlintReadbackMapStatus::Denied);
    CHECK(observer.BeginShaderByteScope(scope,true).ticket == 0 && observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    auto plan = observer.BeginShaderByteScope(scope,true);
    CHECK(plan.ticket && plan.requests.size() == 1 && plan.requests[0].size == 32);
    std::vector<uint8_t> bytes(32,37);
    CHECK(observer.ClassifyReadMap(Buffer(1),0,32) == GlintReadbackMapStatus::Denied);
    CHECK(observer.PrepareReadMap(Buffer(1),0,bytes).status == GlintReadbackMapStatus::Denied);
    std::vector<std::shared_ptr<ByteState>> states;
    CHECK(observer.CommitShaderByteScope(plan.ticket,Results(plan,&states)));
    CHECK(observer.ClassifyReadMap(Buffer(1),0,32) == GlintReadbackMapStatus::Protected);
    CHECK(observer.PrepareReadMap(Buffer(1),0,bytes).status == GlintReadbackMapStatus::Denied);
    states[0]->status = GlintReadbackStatus::Ready;
    auto mapped = observer.PrepareReadMap(Buffer(1),0,bytes);
    CHECK(mapped.status == GlintReadbackMapStatus::Protected && mapped.size == bytes.size());
    CHECK(std::equal(bytes.begin(),bytes.end(),mapped.bytes.get()));
    states[0]->bytes.assign(32,241);
    CHECK(observer.PrepareReadMap(Buffer(1),0,bytes).status == GlintReadbackMapStatus::Protected);
    bytes[0] ^= 1;
    CHECK(observer.PrepareReadMap(Buffer(1),0,bytes).status == GlintReadbackMapStatus::Denied);
    bytes[0] ^= 1;
    CHECK(observer.PrepareReadMap(Buffer(1),0,bytes).status == GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    std::array aliases{Write(1,0,16),Write(1,8,16),Write(1,24,8)};
    auto plan = observer.BeginShaderByteScope({aliases,true,true},true);
    CHECK(plan.ticket && plan.requests.size() == 1 && plan.requests[0].offset == 0 && plan.requests[0].size == 32);
    observer.OnExecutionError();
    CHECK(!observer.CommitShaderByteScope(plan.ticket,Results(plan)) && !observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    std::array aliases{Write(1,0,8),Write(1,16,8)};
    auto plan = observer.BeginShaderByteScope({aliases,true,true},true);
    CHECK(plan.ticket && plan.requests.size() == 2);
    std::vector<std::shared_ptr<ByteState>> states;
    CHECK(observer.CommitShaderByteScope(plan.ticket,Results(plan,&states)));
    for (auto& state : states) state->status = GlintReadbackStatus::Ready;
    std::array<uint8_t,32> bytes{};
    std::fill_n(bytes.begin(),8,uint8_t{37}); std::fill_n(bytes.begin()+16,8,uint8_t{37});
    CHECK(observer.PrepareReadMap(Buffer(1),0,bytes).status == GlintReadbackMapStatus::Protected);
    observer.OnBufferToBufferCopy(Buffer(1),0,Buffer(2),0,32);
    CHECK(observer.PrepareReadMap(Buffer(2),0,bytes).status == GlintReadbackMapStatus::Protected);
    auto input = Write(2); input.writable = false;
    std::array chain{input,Write(3)};
    auto chained = observer.BeginShaderByteScope({chain,false,true},false);
    CHECK(chained.ticket && chained.requests.size() == 1 && chained.requests[0].buffer.handle == Buffer(3).handle);
    CHECK(observer.CommitShaderByteScope(chained.ticket,Results(chained)));
    observer.OnBufferWrite(Buffer(3),0,32,GlintBufferWriteKind::KnownBytes);
    CHECK(observer.ClassifyReadMap(Buffer(3),0,32) == GlintReadbackMapStatus::Unrelated);
  }
  for (size_t invalid=0; invalid<9; ++invalid) {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    auto plan = observer.BeginShaderByteScope(scope,true);
    CHECK(plan.ticket != 0);
    if (invalid == 0) { CHECK(observer.BeginShaderByteScope(scope,true).ticket == 0); }
    else if (invalid == 1) observer.OnBufferWrite(Buffer(1),0,4,GlintBufferWriteKind::KnownBytes);
    else if (invalid == 2) observer.OnBufferDestroyed(Buffer(1).handle);
    else if (invalid == 3) observer.OnShaderScope(scope);
    else {
      std::vector<std::shared_ptr<ByteState>> states;
      auto results = Results(plan,&states);
      uint64_t ticket = plan.ticket;
      if (invalid == 4) ++ticket;
      if (invalid == 5) ++results[0].requestId;
      if (invalid == 6) results[0].snapshot.reset();
      if (invalid == 7) ++states[0]->declared;
      if (invalid == 8) results.clear();
      CHECK(!observer.CommitShaderByteScope(ticket,std::move(results)));
    }
    CHECK(!observer.IsHealthy());
    CHECK(observer.ClassifyReadMap(Buffer(1),0,32) == GlintReadbackMapStatus::Denied);
  }
  for (size_t invalid=0; invalid<4; ++invalid) {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    auto use = Write(1);
    if (invalid == 0) use.rangeKnown = false;
    if (invalid == 1) use.buffer.handle = nullptr;
    if (invalid == 2) use.offset = 65;
    std::array invalid_uses{use};
    CHECK(observer.BeginShaderByteScope({invalid_uses,true,invalid != 3},true).ticket == 0);
    CHECK(!observer.IsHealthy());
    CHECK(observer.BeginShaderByteScope(scope,true).failed);
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    GlintTextureToBufferCopy copy; copy.destination = Buffer(1); copy.destinationRowPitch=256;
    copy.width=copy.height=1; copy.format=GlintReadbackFormat::Rgba8Unorm;
    observer.OnTextureToBufferCopy(copy,std::make_unique<PixelSnapshot>());
    CHECK(observer.IsHealthy());
    CHECK(observer.BeginShaderByteScope(scope,true).ticket == 0 && observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{256,16,1024});
    CHECK(observer.BeginShaderByteScope(scope,true).ticket == 0 && observer.IsHealthy());
    observer.OnShaderScope(scope);
    CHECK(observer.ClassifyReadMap(Buffer(1),0,32) == GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    std::array<GlintShaderBufferUse,17> outputs;
    for(size_t i=0;i<outputs.size();++i) outputs[i]=Write(i+1);
    CHECK(observer.BeginShaderByteScope({outputs,true,true},true).ticket == 0 && observer.IsHealthy());
  }
  for (size_t invalid=0; invalid<2; ++invalid) {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    auto plan = observer.BeginShaderByteScope(scope,true);
    std::vector<std::shared_ptr<ByteState>> states;
    CHECK(observer.CommitShaderByteScope(plan.ticket,Results(plan,&states)));
    states[0]->status = invalid == 0 ? GlintReadbackStatus::Failed : GlintReadbackStatus::Ready;
    if (invalid == 1) states[0]->bytes.resize(31);
    std::vector<uint8_t> raw(32,37);
    CHECK(observer.PrepareReadMap(Buffer(1),0,raw).status == GlintReadbackMapStatus::Denied);
    CHECK(observer.ClassifyReadMap(Buffer(1),0,32) == GlintReadbackMapStatus::Denied);
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    GlintTextureToBufferCopy copy; copy.destination=Buffer(1); copy.destinationRowPitch=256;
    copy.width=copy.height=1; copy.format=GlintReadbackFormat::Rgba8Unorm;
    observer.OnTextureToBufferCopy(copy,std::make_unique<PixelSnapshot>());
    std::array partial{Write(1,8,32)};
    auto plan=observer.BeginShaderByteScope({partial,true,true},true);
    CHECK(plan.ticket != 0);
    std::vector<std::shared_ptr<ByteState>> states;
    CHECK(observer.CommitShaderByteScope(plan.ticket,Results(plan,&states)));
    states[0]->status=GlintReadbackStatus::Ready;
    std::array<uint8_t,64> bytes{}; std::fill_n(bytes.begin()+8,32,uint8_t{37});
    CHECK(observer.PrepareReadMap(Buffer(1),0,bytes).status == GlintReadbackMapStatus::Protected);
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    auto plan=observer.BeginShaderByteScope(scope,true);
    GlintTextureToBufferCopy copy; copy.destination=Buffer(2);
    observer.OnTextureToBufferCopy(copy,std::make_unique<PixelSnapshot>());
    CHECK(!observer.IsHealthy() && !observer.CommitShaderByteScope(plan.ticket,Results(plan)));
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    std::array outputs{Write(1),Write(2)};
    auto plan=observer.BeginShaderByteScope({outputs,true,true},true);
    auto results=Results(plan);
    std::swap(results[0],results[1]);
    CHECK(!observer.CommitShaderByteScope(plan.ticket,std::move(results)) && !observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    auto plan=observer.BeginShaderByteScope(scope,true);
    CHECK(observer.CommitShaderByteScope(plan.ticket,Results(plan)));
    // A later queue scope may replace an earlier capture before its CPU readback completes.
    auto next=observer.BeginShaderByteScope(scope,true);
    CHECK(next.ticket > plan.ticket);
    std::vector<std::shared_ptr<ByteState>> states;
    CHECK(observer.CommitShaderByteScope(next.ticket,Results(next,&states)));
    states[0]->status=GlintReadbackStatus::Ready;
    std::vector<uint8_t> raw(32,37);
    CHECK(observer.PrepareReadMap(Buffer(1),0,raw).status == GlintReadbackMapStatus::Protected);
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    auto zero=Write(1,0,0); std::array empty{zero};
    CHECK(observer.BeginShaderByteScope({empty,true,true},true).ticket == 0 && observer.IsHealthy());
  }
  {
    GlintWebGPUReadbackObserver observer(policy,7,{});
    uint64_t previous=0;
    for(size_t sample=0;sample<2000;++sample) {
      auto plan=observer.BeginShaderByteScope(scope,true);
      CHECK(plan.ticket > previous && plan.requests.size() == 1);
      previous=plan.ticket;
      std::vector<std::shared_ptr<ByteState>> states;
      auto results=Results(plan,&states);
      std::vector<uint8_t> raw(32,static_cast<uint8_t>(sample));
      states[0]->bytes=raw; states[0]->status=GlintReadbackStatus::Ready;
      CHECK(observer.CommitShaderByteScope(plan.ticket,std::move(results)));
      auto map=observer.PrepareReadMap(Buffer(1),0,raw);
      CHECK(map.status == GlintReadbackMapStatus::Protected && map.size == raw.size());
      CHECK(std::equal(raw.begin(),raw.end(),map.bytes.get()));
      if(sample%31==0) {
        observer.OnBufferWrite(Buffer(1),0,32,GlintBufferWriteKind::KnownBytes);
        CHECK(observer.ClassifyReadMap(Buffer(1),0,32) == GlintReadbackMapStatus::Unrelated);
      }
      CHECK(observer.IsHealthy());
    }
  }
  std::printf("{\"passed\":true,\"assertions\":%zu,\"scope_cycles\":2000,\"actual_native_gpu_hook_executed\":false,"
              "\"native_handles_synthetic\":true,\"runtime_verified\":false}\n",assertions);
}
