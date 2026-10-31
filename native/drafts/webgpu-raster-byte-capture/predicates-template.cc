#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <vector>
#include "dawn/native/DawnNative.h"
#include "gpu/command_buffer/common/glint_webgpu_device_policy.h"
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
using namespace dawn::native;
using gpu::webgpu::GlintWebGPUReadbackObserver;
using gpu::webgpu::GlintWebGPUDevicePolicy;
size_t assertions = 0;
void Check(bool value, int line) {
    ++assertions;
    if (!value) { std::fprintf(stderr,"raster merge failure %d\n",line); std::exit(1); }
}
#define CHECK(x) Check((x),__LINE__)
struct FakeBuffer {
    uint64_t size;
    uint64_t GetSize() const { return size; }
};
using BufferBase = FakeBuffer;
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
GlintBoundScope Scope(const std::shared_ptr<FakeBuffer>& buffer, uint64_t offset,
                      uint64_t size, bool writable, bool texture = false) {
    return {{{{ToAPI(buffer.get()), buffer->GetSize()},true,writable,offset,size,true}},
            {{buffer}},texture};
}
class Bytes final : public GlintByteReadbackSnapshot {
 public:
    explicit Bytes(std::vector<uint8_t> value) : bytes_(std::move(value)) {}
    GlintReadbackStatus Read(std::span<const uint8_t>* result) const override {
        *result = bytes_; return GlintReadbackStatus::Ready;
    }
    uint64_t GetByteSize() const override { return bytes_.size(); }
 private:
    std::vector<uint8_t> bytes_;
};
uint32_t random_state = 17;
uint32_t Random() { random_state = random_state * 1664525u + 1013904223u; return random_state; }
int main() {
    const auto a = std::make_shared<FakeBuffer>(FakeBuffer{64});
    const auto b = std::make_shared<FakeBuffer>(FakeBuffer{64});
    {
        GlintBoundScope total;
        CHECK(MergeGlintBoundScope(&total,Scope(a,0,8,true)));
        CHECK(MergeGlintBoundScope(&total,Scope(a,16,8,true,true)));
        CHECK(total.uses.size()==2 && total.textureInputs && total.owners.size()==1);
        CHECK(MergeGlintBoundScope(&total,Scope(a,8,8,true)));
        CHECK(total.uses.size()==1 && total.uses[0].offset==0 && total.uses[0].size==24);
        CHECK(MergeGlintBoundScope(&total,Scope(a,0,64,false)));
        CHECK(total.uses.size()==2 && total.uses[0].writable && total.uses[0].size==24);
    }
    for (size_t pass=0; pass<1000; ++pass) {
        GlintBoundScope total;
        std::array<std::array<std::array<bool,64>,2>,2> oracle{};
        bool textured=false;
        for(size_t draw=0; draw<16; ++draw) {
            const size_t id=Random()%2;
            const auto buffer=id==0?a:b;
            const uint64_t offset=Random()%65;
            const uint64_t size=Random()%(65-offset);
            const bool writable=(Random()%2)!=0;
            const bool texture=Random()%13==0;
            textured|=texture;
            CHECK(MergeGlintBoundScope(&total,Scope(buffer,offset,size,writable,texture)));
            for(size_t byte=offset;byte<offset+size;++byte) oracle[id][writable][byte]=true;
            std::array<std::array<std::array<bool,64>,2>,2> measured{};
            for(const auto& use:total.uses) {
                CHECK(use.rangeKnown && use.offset<=64 && use.size<=64-use.offset);
                const size_t index=use.buffer.handle==ToAPI(a.get())?0:1;
                CHECK(use.buffer.handle==ToAPI(index==0?a.get():b.get()));
                CHECK(use.readable);
                for(size_t byte=use.offset;byte<use.offset+use.size;++byte)
                    measured[index][use.writable][byte]=true;
            }
            CHECK(measured==oracle && total.textureInputs==textured && total.owners.size()<=2);
        }
    }
    {
        GlintBoundScope total;
        for(size_t draw=0; draw<8192; ++draw) CHECK(MergeGlintBoundScope(&total,Scope(a,0,64,true)));
        CHECK(total.uses.size()==1 && total.owners.size()==1);
    }
    {
        const auto big=std::make_shared<FakeBuffer>(FakeBuffer{2*kGlintShaderBufferUseLimit+4});
        GlintBoundScope total;
        for(size_t index=0;index<kGlintShaderBufferUseLimit;++index)
            CHECK(MergeGlintBoundScope(&total,Scope(big,index*2,1,true)));
        CHECK(total.uses.size()==kGlintShaderBufferUseLimit);
        CHECK(MergeGlintBoundScope(&total,Scope(big,0,1,true)));
        CHECK(!MergeGlintBoundScope(&total,Scope(big,2*kGlintShaderBufferUseLimit,1,true)));
    }
    for(size_t invalid=0;invalid<7;++invalid) {
        auto scope=Scope(a,0,16,true);
        if(invalid==0) scope.uses[0].offset=UINT64_MAX;
        if(invalid==1) scope.uses[0].size=UINT64_MAX;
        if(invalid==2) scope.uses[0].rangeKnown=false;
        if(invalid==3) scope.uses[0].buffer.handle=nullptr;
        if(invalid==4) scope.owners.clear();
        if(invalid==5) scope.owners[0].value=b;
        if(invalid==6) scope.uses[0].buffer.size=63;
        GlintBoundScope total;
        CHECK(!MergeGlintBoundScope(&total,std::move(scope)));
    }
    {
        GlintBoundScope total;
        auto owner=std::make_shared<FakeBuffer>(FakeBuffer{64});
        std::weak_ptr<FakeBuffer> weak=owner;
        CHECK(MergeGlintBoundScope(&total,Scope(owner,0,8,true)));
        owner.reset(); CHECK(!weak.expired());
        total={}; CHECK(weak.expired());
    }
    std::array<uint8_t,32> key{};key.fill(17);
    auto policy=std::make_shared<const GlintWebGPUDevicePolicy>(
        std::move(*GlintWebGPUDevicePolicy::Create(3,key)));
    for(size_t pass=0;pass<256;++pass) {
        GlintWebGPUReadbackObserver observer(policy,7,{});
        GlintBoundScope total;
        CHECK(MergeGlintBoundScope(&total,Scope(a,0,16,true,true)));
        CHECK(MergeGlintBoundScope(&total,Scope(a,32,16,true)));
        CHECK(MergeGlintBoundScope(&total,Scope(b,0,64,false)));
        CHECK(MergeGlintBoundScope(&total,Scope(a,16,16,true)));
        CHECK(total.uses.size()==2 && total.owners.size()==2);
        const GlintShaderScope scope{total.uses,total.textureInputs,true};
        auto plan=observer.BeginShaderByteScope(scope,true);
        CHECK(plan.ticket && !plan.failed && plan.requests.size()==1);
        const auto& request=plan.requests[0];
        CHECK(request.buffer.handle==ToAPI(a.get()) && request.offset==0 && request.size==48);
        std::vector<uint8_t> raw(64,0);
        std::fill_n(raw.begin(),48,static_cast<uint8_t>(pass));
        std::vector<GlintShaderByteResult> results;
        results.push_back({request.requestId,std::make_unique<Bytes>(std::vector<uint8_t>(raw.begin(),raw.begin()+48))});
        CHECK(observer.CommitShaderByteScope(plan.ticket,std::move(results)));
        auto result=observer.PrepareReadMap({ToAPI(a.get()),64},0,raw);
        CHECK(result.status==GlintReadbackMapStatus::Protected && result.size==64);
        CHECK(std::equal(raw.begin(),raw.end(),result.bytes.get()));
        raw[0]^=1;
        CHECK(observer.PrepareReadMap({ToAPI(a.get()),64},0,raw).status==GlintReadbackMapStatus::Denied);
    }
    std::printf("{\"passed\":true,\"assertions\":%zu,\"oracle_passes\":1000,\"oracle_draws\":16000,\"duplicate_draws\":8192,\"controller_passes\":256,\"source_extracted_merge_only\":true,\"backend_mocked\":true,\"actual_native_render_pass_executed\":false}\n",assertions);
}
