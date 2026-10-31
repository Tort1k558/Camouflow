#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "dawn/native/DawnNative.h"
using dawn::native::kGlintShaderBufferUseLimit;
size_t assertions=0;
void Check(bool v,int line) {++assertions;if(!v){std::fprintf(stderr,"private backing assertion %d\n",line);std::exit(1);}}
#define CHECK(x) Check((x),__LINE__)
enum class AllocationMethod { kDirect, kExternal };
struct Allocation {
    struct Info {AllocationMethod mMethod;};
    AllocationMethod method=AllocationMethod::kDirect;
    Info GetInfo() const {return {method};}
};
struct Buffer {
    bool alive=true,shared=false,mHostMappedHeap=false;
    Allocation mResourceAllocation;
    void* GetD3D12Resource() const {return alive?reinterpret_cast<void*>(1):nullptr;}
    void* GetSharedResourceMemoryContents() const {return shared?reinterpret_cast<void*>(1):nullptr;}
    uint64_t GetSize() const {return 64;}
/* GLINT_GETTER */
};
template <typename T> T* ToBackend(T* value) {return value;}
bool Binding(Buffer* buffer,uint64_t offset,uint64_t size,size_t used=0) {
    std::vector<int> uses(used);
/* GLINT_BINDING */    return true;
}
#define DAWN_INTERNAL_ERROR_IF(condition,message) if(condition) return false
bool Indirect(Buffer* indirectBuffer) {
/* GLINT_INDIRECT */
    return true;
}
bool Capture(Buffer* source,size_t* allocations) {
/* GLINT_CAPTURE */
    ++*allocations;
    return true;
}
#undef DAWN_INTERNAL_ERROR_IF
int main() {
    for(size_t flags=0;flags<16;++flags) {
        Buffer value;
        value.alive=(flags&1)==0;
        value.shared=(flags&2)!=0;
        value.mHostMappedHeap=(flags&4)!=0;
        value.mResourceAllocation.method=(flags&8)?AllocationMethod::kExternal:AllocationMethod::kDirect;
        const bool expected=flags==0;
        CHECK(value.HasPrivateGlintReadbackBacking()==expected);
        CHECK(Binding(&value,0,32)==expected);
        CHECK(Indirect(&value)==expected);
        size_t allocations=0;
        CHECK(Capture(&value,&allocations)==expected);
        CHECK(allocations==(expected?1u:0u));
    }
    Buffer ordinary,shared;shared.shared=true;
    CHECK(!Binding(nullptr,0,0));
    CHECK(!Binding(&ordinary,64,1));
    CHECK(!Binding(&ordinary,UINT64_MAX,4));
    CHECK(!Binding(&ordinary,0,UINT64_MAX));
    CHECK(!Binding(&ordinary,0,1,kGlintShaderBufferUseLimit));
    CHECK(Binding(&ordinary,0,1,kGlintShaderBufferUseLimit-1));
    for(size_t offset=0;offset<=64;++offset) {
        CHECK(Binding(&ordinary,offset,64-offset));
        CHECK(!Binding(&shared,offset,64-offset));
    }
    std::printf("{\"passed\":true,\"assertions\":%zu,\"source_extracted_predicates_only\":true,\"origin_combinations\":16,\"actual_shared_or_host_mapped_import_executed\":false}\n",assertions);
}
