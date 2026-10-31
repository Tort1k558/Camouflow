#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>
#include <vector>
#include "dawn/native/DawnNative.h"
#include "gpu/command_buffer/common/glint_webgpu_device_policy.h"
#include "gpu/command_buffer/service/glint_webgpu_readback_observer.h"
using namespace dawn::native;
using gpu::webgpu::GlintWebGPUReadbackObserver;
using gpu::webgpu::GlintWebGPUDevicePolicy;
size_t assertions=0, attachment_cases=0, accepted_attachments=0, denied_controls=0;
void Check(bool value,int line) {++assertions;if(!value){std::fprintf(stderr,"execution inputs failure %d\n",line);std::exit(1);}}
#define CHECK(x) Check((x),__LINE__)
struct FakeBuffer {uint64_t size;uint64_t GetSize() const{return size;}};
using BufferBase=FakeBuffer;
template<class T> struct Ref {
    std::shared_ptr<T> value;
    Ref()=default;
    Ref(std::shared_ptr<T> v):value(std::move(v)){}
    T* Get() const{return value.get();}
    T* operator->() const{return Get();}
    explicit operator bool() const{return value!=nullptr;}
};
WGPUBuffer ToAPI(BufferBase* buffer){return reinterpret_cast<WGPUBuffer>(buffer);}
/* GLINT_INPUTS */
/* GLINT_NATIVE_USE */
/* GLINT_INDIRECT */
enum class Aspect:uint32_t {None=0,Depth=1,Stencil=2};
bool operator&(Aspect a,Aspect b){return (static_cast<uint32_t>(a)&static_cast<uint32_t>(b))!=0;}
struct View {Aspect aspects;Aspect GetAspects() const{return aspects;}};
struct BeginRenderPassCmd {
    struct Depth {
        Ref<View> view;
        wgpu::LoadOp depthLoadOp=wgpu::LoadOp::Undefined,stencilLoadOp=wgpu::LoadOp::Undefined;
        bool depthReadOnly=false,stencilReadOnly=false;
    } depthStencilAttachment;
    struct Storage {Ref<View> storage;};
    std::array<Storage,4> storageAttachments;
};
/* GLINT_ATTACHMENTS */
class Pixels final:public GlintReadbackSnapshot {
 public:
    GlintReadbackStatus Read(std::span<const uint8_t>* pixels) const override {*pixels=bytes_;return GlintReadbackStatus::Ready;}
    uint32_t GetWidth() const override{return 1;}
    uint32_t GetHeight() const override{return 1;}
    uint32_t GetRowPitch() const override{return 256;}
    GlintReadbackFormat GetFormat() const override{return GlintReadbackFormat::Rgba8Unorm;}
 private:std::array<uint8_t,256> bytes_{};
};
class Bytes final:public GlintByteReadbackSnapshot {
 public:
    explicit Bytes(size_t size):bytes_(size,37){}
    GlintReadbackStatus Read(std::span<const uint8_t>* bytes) const override {*bytes=bytes_;return GlintReadbackStatus::Ready;}
    uint64_t GetByteSize() const override{return bytes_.size();}
 private:std::vector<uint8_t> bytes_;
};
GlintBufferIdentity Identity(const std::shared_ptr<FakeBuffer>& buffer){return {ToAPI(buffer.get()),buffer->size};}
void RawPixels(GlintWebGPUReadbackObserver& observer,const std::shared_ptr<FakeBuffer>& buffer) {
    GlintTextureToBufferCopy copy;copy.destination=Identity(buffer);copy.destinationRowPitch=256;
    copy.width=copy.height=1;copy.format=GlintReadbackFormat::Rgba8Unorm;
    observer.OnTextureToBufferCopy(copy,std::make_unique<Pixels>());CHECK(observer.IsHealthy());
}
void Finish(GlintWebGPUReadbackObserver& observer,const GlintShaderBytePlan& plan,
            const std::shared_ptr<FakeBuffer>& output) {
    CHECK(plan.ticket && !plan.failed && plan.requests.size()==1);
    std::vector<GlintShaderByteResult> results;
    for(const auto& request:plan.requests) results.push_back({request.requestId,std::make_unique<Bytes>(request.size)});
    CHECK(observer.CommitShaderByteScope(plan.ticket,std::move(results)));
    std::vector<uint8_t> raw(output->size,37);
    const auto mapped=observer.PrepareReadMap(Identity(output),0,raw);
    CHECK(mapped.status==GlintReadbackMapStatus::Protected && mapped.size==raw.size());
    CHECK(std::equal(raw.begin(),raw.end(),mapped.bytes.get()));
    raw[0]^=1;CHECK(observer.PrepareReadMap(Identity(output),0,raw).status==GlintReadbackMapStatus::Denied);
}
std::vector<GlintShaderBufferUse> ShaderUses(const std::vector<GlintNativeBufferUse>& controls,
                                           const std::shared_ptr<FakeBuffer>& output) {
    std::vector<GlintShaderBufferUse> uses{{Identity(output),true,true,0,32,true}};
    for(const auto& use:controls) uses.push_back({{ToAPI(use.owner.Get()),use.owner->GetSize()},true,false,use.offset,use.size,true});
    return uses;
}
int main() {
    auto source=std::make_shared<FakeBuffer>(FakeBuffer{256});
    auto scratch=std::make_shared<FakeBuffer>(FakeBuffer{256});
    auto count=std::make_shared<FakeBuffer>(FakeBuffer{8});
    auto output=std::make_shared<FakeBuffer>(FakeBuffer{256});
    for(uint64_t words:{3,4,5}) {
        for(uint32_t maximum:{1u,4u}) {
            GlintIndirectInputs original{source,4,count,4,maximum};
            std::vector<GlintNativeBufferUse> uses{{scratch,0,words*4}};
            CHECK(AppendGlintOriginalIndirectUses(&uses,original,words*4));
            CHECK(uses.size()==3 && uses[0].owner.Get()==scratch.get());
            CHECK(uses[1].owner.Get()==source.get() && uses[1].offset==4 && uses[1].size==words*4*maximum);
            CHECK(uses[2].owner.Get()==count.get() && uses[2].offset==4 && uses[2].size==4);
        }
    }
    for(size_t invalid=0;invalid<9;++invalid) {
        GlintIndirectInputs original{source,0,count,0,1};
        uint64_t bytes=12;
        if(invalid==0) original.buffer={};
        if(invalid==1) original.offset=UINT64_MAX;
        if(invalid==2) bytes=UINT64_MAX,original.maxCount=2;
        if(invalid==3) original.maxCount=0;
        if(invalid==4) bytes=0;
        if(invalid==5) original.countOffset=UINT64_MAX;
        if(invalid==6) original.countOffset=5;
        if(invalid==7) original.offset=250;
        std::vector<GlintNativeBufferUse> uses;
        if(invalid==8) uses.resize(kGlintShaderBufferUseLimit-1);
        const auto before=uses.size();
        CHECK(!AppendGlintOriginalIndirectUses(&uses,original,bytes));CHECK(uses.size()==before);
    }
    {
        GlintIndirectInputs original{source,0,{},0,1};
        CHECK(!AppendGlintOriginalIndirectUses(nullptr,original,12));
        std::vector<GlintNativeBufferUse> uses(kGlintShaderBufferUseLimit-1);
        CHECK(AppendGlintOriginalIndirectUses(&uses,original,12) && uses.size()==kGlintShaderBufferUseLimit);
    }
    {
        auto owner=std::make_shared<FakeBuffer>(FakeBuffer{64});std::weak_ptr<FakeBuffer> weak=owner;
        GlintIndirectInputs original{owner,4,{},0,1};owner.reset();CHECK(!weak.expired());
        std::vector<GlintNativeBufferUse> uses;
        CHECK(AppendGlintOriginalIndirectUses(&uses,original,12));
        original={};CHECK(!weak.expired());uses.clear();CHECK(weak.expired());
    }
    std::array<uint8_t,32> key{};key.fill(17);
    auto policy=std::make_shared<const GlintWebGPUDevicePolicy>(std::move(*GlintWebGPUDevicePolicy::Create(3,key)));
    // A sanitized scratch buffer alone must not hide the logical input's raw pixel provenance.
    for(size_t variant=0;variant<4;++variant) {
        GlintWebGPUReadbackObserver observer(policy,7,{});
        RawPixels(observer,source);
        std::vector<GlintNativeBufferUse> controls{{scratch,0,16}};
        if(variant!=0) {
            GlintIndirectInputs original{source,variant==2?16u:0u,{},0,1};
            if(variant==3) original.buffer=scratch;
            CHECK(AppendGlintOriginalIndirectUses(&controls,original,16));
        }
        const auto uses=ShaderUses(controls,output);
        const GlintShaderScope scope{uses,true,true};
        const auto plan=observer.BeginShaderByteScope(scope,true);
        if(variant==1) {
            CHECK(!plan.ticket && !plan.failed && observer.IsHealthy());
            observer.OnShaderScope(scope);
            CHECK(observer.ClassifyReadMap(Identity(output),0,32)==GlintReadbackMapStatus::Denied);
            ++denied_controls;
        } else Finish(observer,plan,output);
    }
    for(bool tainted:{false,true}) {
        GlintWebGPUReadbackObserver observer(policy,7,{});RawPixels(observer,count);
        GlintIndirectInputs original{source,16,count,tainted?0u:4u,1};
        std::vector<GlintNativeBufferUse> controls{{scratch,0,16}};
        CHECK(AppendGlintOriginalIndirectUses(&controls,original,16));
        const auto uses=ShaderUses(controls,output);const GlintShaderScope scope{uses,true,true};
        const auto plan=observer.BeginShaderByteScope(scope,true);
        if(tainted) {
            CHECK(!plan.ticket && !plan.failed);observer.OnShaderScope(scope);
            CHECK(observer.ClassifyReadMap(Identity(output),0,32)==GlintReadbackMapStatus::Denied);++denied_controls;
        } else Finish(observer,plan,output);
    }
    for(uint32_t aspects=0;aspects<4;++aspects) for(bool depth_read:{false,true})
    for(bool stencil_read:{false,true}) for(auto depth_load:{wgpu::LoadOp::Clear,wgpu::LoadOp::Load,wgpu::LoadOp::Undefined})
    for(auto stencil_load:{wgpu::LoadOp::Clear,wgpu::LoadOp::Load,wgpu::LoadOp::Undefined})
    for(size_t storage=0;storage<5;++storage) {
        BeginRenderPassCmd pass;
        auto view=std::make_shared<View>(View{static_cast<Aspect>(aspects)});
        pass.depthStencilAttachment={view,depth_load,stencil_load,depth_read,stencil_read};
        if(storage) pass.storageAttachments[storage-1].storage=view;
        const bool expected=storage!=0 || ((aspects&1) && (depth_read || depth_load!=wgpu::LoadOp::Clear)) ||
                            ((aspects&2) && (stencil_read || stencil_load!=wgpu::LoadOp::Clear));
        const bool unknown=HasGlintUnprojectedAttachmentInputs(pass);CHECK(unknown==expected);
        GlintWebGPUReadbackObserver observer(policy,7,{});
        const std::array uses{GlintShaderBufferUse{Identity(output),true,true,0,32,true}};
        const GlintShaderScope scope{uses,true,true};
        const auto plan=observer.BeginShaderByteScope(scope,!unknown);
        if(unknown) {
            CHECK(!plan.ticket && !plan.failed && observer.IsHealthy());observer.OnShaderScope(scope);
            CHECK(observer.ClassifyReadMap(Identity(output),0,32)==GlintReadbackMapStatus::Denied);
        } else {Finish(observer,plan,output);++accepted_attachments;}
        ++attachment_cases;
    }
    BeginRenderPassCmd empty;CHECK(!HasGlintUnprojectedAttachmentInputs(empty));
    std::printf("{\"passed\":true,\"assertions\":%zu,\"attachment_cases\":%zu,\"accepted_attachment_cases\":%zu,\"denied_logical_control_cases\":%zu,\"source_extracted_input_contracts_only\":true,\"backend_mocked\":true,\"actual_frontend_encoding_executed\":false,\"actual_native_device_queue_executed\":false}\n",assertions,attachment_cases,accepted_attachments,denied_controls);
}
