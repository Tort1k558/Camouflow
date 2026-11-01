#include <cstdint>
#include <cstdio>
#include "gpu/command_buffer/common/glint/webgpu_readback_provenance.h"

using namespace glint::candidate;

bool Check(const WebGpuReadbackPlan& plan, uint32_t height, bool prefill,
           WebGpuPixelFormat format, uint64_t shift, uint64_t first_id = 2) {
    const uint64_t stride = uint64_t{height + 2} * 256;
    if (plan.status != WebGpuMapProvenance::kReadback || plan.count > (prefill ? 10u : 3u)) return false;
    for (uint64_t position = plan.mapping_offset; position < plan.mapping_offset + plan.mapping_size; ++position) {
        const uint64_t logical = position - shift;
        const bool after_prefix = logical >= 16;
        const uint64_t layer = after_prefix ? (logical - 16) / stride : 3;
        const uint64_t within = after_prefix ? (logical - 16) % stride : 0;
        const uint64_t y = within / 256, x = within % 256;
        const bool pixel = layer < 3 && y < height && x < 28;
        unsigned claims = 0;
        for (size_t index = 0; index < plan.count; ++index) {
            const auto& region = plan.regions[index];
            if (region.kind == WebGpuReadbackRegionKind::kCapturedBytes) {
                const auto byte = WebGpuCapturedByte(region, position);
                if (byte) {
                    if (pixel || !prefill || *byte != logical || region.snapshot.snapshot_id != 1) return false;
                    ++claims;
                }
            } else if (region.kind == WebGpuReadbackRegionKind::kPixels) {
                const auto byte = WebGpuCanonicalByte(region, position);
                if (byte) {
                    const uint64_t channel = x % 4;
                    const uint64_t mapped_channel = format == WebGpuPixelFormat::kBgra8Unorm && channel % 2 == 0 ? 2-channel : channel;
                    const uint64_t expected = y*28 + (x/4)*4 + mapped_channel;
                    const uint64_t expected_id = layer == 0 ? first_id : layer + 2;
                    if (!pixel || *byte != expected || region.snapshot.snapshot_id != expected_id) return false;
                    ++claims;
                }
            } else return false;
        }
        if (claims != (prefill || pixel ? 1u : 0u)) return false;
    }
    return true;
}

bool Run(uint32_t height, bool prefill, WebGpuPixelFormat format) {
    constexpr uint64_t epoch = 7;
    const uint64_t stride = uint64_t{height + 2} * 256;
    const uint64_t bytes = 16 + 3*stride + 32;
    WebGpuReadbackProvenance tracker(static_cast<size_t>(bytes), epoch);
    if (prefill && !tracker.RecordCapturedByteCopy(1, 0, bytes, {epoch, 1, 1, 1})) return false;
    for (uint32_t layer = 0; layer < 3; ++layer) {
        const uint64_t sequence = layer + 2;
        if (!tracker.RecordTextureCopy(sequence, {16+layer*stride, 256, 7, height, format},
                {epoch, sequence, sequence, 1}, {0, 0, 7, height})) return false;
    }
    const auto whole = tracker.PlanMap(0, bytes);
    if (!Check(whole, height, prefill, format, 0) ||
        !Check(tracker.PlanMap(24, bytes-48), height, prefill, format, 0)) return false;
    if (!tracker.RecordTextureCopy(5, {16, 256, 7, height, format}, {epoch, 100, 5, 1}, {0, 0, 7, height})) return false;
    if (!Check(tracker.PlanMap(0, bytes), height, prefill, format, 0, 100)) return false;
    WebGpuReadbackProvenance copied(static_cast<size_t>(bytes+64), epoch);
    if (!copied.RecordBufferCopy(6, 32, tracker, 0, bytes) ||
        !Check(copied.PlanMap(32, bytes), height, prefill, format, 32, 100)) return false;
    auto unsafe = copied;
    if (unsafe.RecordUncertainWrite(7, 32+16, 4) ||
        unsafe.PlanMap(0, bytes+64).status != WebGpuMapProvenance::kUnreliable) return false;
    if (!prefill && !copied.RecordUncertainWrite(7, 32+16+28, 4)) return false;
    std::printf("height=%u prefill=%u format=%u regions=%zu exact-byte-coverage/copy/producer-overwrite/denial=PASS\n",
        height, prefill ? 1u : 0u, static_cast<unsigned>(format), whole.count);
    return true;
}

int VerifyLedgerTests() {
    if (kWebGpuReadbackRegionLimit != 16) return 2;
    for (auto format : {WebGpuPixelFormat::kRgba8Unorm, WebGpuPixelFormat::kBgra8Unorm}) {
        for (uint32_t height : {2u, 5u, 17u, 1080u}) {
            if (!Run(height, true, format)) return 3;
        }
        if (!Run(5, false, format)) return 4;
    }
    for (auto mask : {WebGpuCapturedByteMask{0,1,0,0,0}, {256,256,0,0,1},
                     {256,4,256,0,1}, {256,4,0,1,1}}) {
        if (WebGpuCapturedByteMaskValid(mask)) return 5;
    }
    WebGpuReadbackProvenance bounded(512, 7);
    for (uint64_t index = 1; index <= 17; ++index) {
        const bool accepted = bounded.RecordCapturedByteCopy(index, index*8, 4, {7,index,index,1});
        if (accepted != (index <= 16)) return 6;
    }
    std::puts("PASS: compact byte masks preserve exact coverage; original 16-region capacity remains enforced.");
    return 0;
}

#include <algorithm>
#include <array>
#include <cstdio>
#include <vector>
#include "gpu/command_buffer/common/glint/canvas_readback_candidate.h"
#include "gpu/command_buffer/common/glint/webgpu_readback_snapshot.h"

using namespace glint::candidate;
bool Fail(int line) { std::printf("Failed line=%d\n",line); return false; }

bool Run(uint32_t height, WebGpuPixelFormat format) {
    const size_t stride = size_t{height+2} * 256;
    const size_t bytes = 16 + 3*stride + 32;
    std::vector<uint8_t> literal(bytes, 165), mapped = literal, expected = literal;
    WebGpuReadbackProvenance ledger(bytes, 7);
    WebGpuReadbackSnapshots snapshots(7, 1, 4*1024*1024, 4*1024*1024);
    const WebGpuSnapshotToken fill{7,1,1,1};
    if (!snapshots.BeginByteCapture(fill, bytes) || !snapshots.CompleteByteCapture(fill, literal) ||
        !ledger.RecordCapturedByteCopy(1, 0, bytes, fill)) return Fail(__LINE__);
    std::array<uint8_t,32> seed{};
    for (size_t i=0; i<seed.size(); ++i) seed[i] = static_cast<uint8_t>(i);
    for (uint32_t layer=0; layer<3; ++layer) {
        const uint64_t sequence = layer+2;
        std::vector<uint8_t> rgba(size_t{7}*height*4);
        for (uint32_t y=0; y<height; ++y) for (uint32_t x=0; x<7; ++x) {
            const size_t offset = (size_t{y}*7+x)*4;
            rgba[offset] = static_cast<uint8_t>(x+1);
            rgba[offset+1] = static_cast<uint8_t>(y%251+1);
            rgba[offset+2] = static_cast<uint8_t>(85+layer*16);
            rgba[offset+3] = 255;
        }
        auto native = rgba;
        if (format == WebGpuPixelFormat::kBgra8Unorm)
            for (size_t i=0; i<native.size(); i+=4) std::swap(native[i], native[i+2]);
        const WebGpuSnapshotToken token{7,sequence,sequence,1};
        std::vector<uint8_t> native_padded(size_t{height}*256,165);
        for (uint32_t y=0; y<height; ++y)
            std::copy_n(native.data()+size_t{y}*28,28,native_padded.data()+size_t{y}*256);
        if (!snapshots.Capture(token, {0,256,7,height,format}, 0, native_padded, seed) ||
            !ledger.RecordTextureCopy(sequence, {16+layer*stride,256,7,height,format}, token, {0,0,7,height})) return Fail(__LINE__);
        if (!TransformEdgeCoherentCanvas(rgba, 7, height, seed)) return Fail(__LINE__);
        if (format == WebGpuPixelFormat::kBgra8Unorm)
            for (size_t i=0; i<rgba.size(); i+=4) std::swap(rgba[i], rgba[i+2]);
        for (uint32_t y=0; y<height; ++y) {
            const size_t offset = 16+layer*stride+size_t{y}*256;
            std::copy_n(native.data()+size_t{y}*28, 28, mapped.data()+offset);
            std::copy_n(rgba.data()+size_t{y}*28, 28, expected.data()+offset);
        }
    }
    const auto before = mapped;
    const auto plan = ledger.PlanMap(0, bytes);
    auto shadow = snapshots.BuildProtectedShadow(plan, 0, mapped);
    auto repeated = snapshots.BuildProtectedShadow(plan, 0, mapped);
    if (!shadow || !repeated || shadow->size != bytes || repeated->size != bytes ||
        !std::equal(expected.begin(),expected.end(),shadow->bytes.get()) ||
        !std::equal(expected.begin(),expected.end(),repeated->bytes.get()) || mapped != before) return Fail(__LINE__);
    auto partial = snapshots.BuildProtectedShadow(ledger.PlanMap(24,bytes-48),24,
        std::span<const uint8_t>(mapped).subspan(24,bytes-48));
    if (!partial || !std::equal(expected.begin()+24,expected.end()-24,partial->bytes.get())) return Fail(__LINE__);
    for (size_t offset : {size_t{0},size_t{16},size_t{44},bytes-1}) {
        auto corrupt = mapped;
        corrupt[offset] ^= 1;
        if (snapshots.BuildProtectedShadow(plan,0,corrupt)) return Fail(__LINE__);
    }
    auto invalid = plan;
    invalid.regions[0].byte_mask = {256,0,0,0,1};
    if (snapshots.BuildProtectedShadow(invalid,0,mapped)) return Fail(__LINE__);
    auto stale = plan;
    stale.regions[0].snapshot.policy_generation = 2;
    if (snapshots.BuildProtectedShadow(stale,0,mapped)) return Fail(__LINE__);
    WebGpuReadbackProvenance copied(bytes+64,7);
    if (!copied.RecordBufferCopy(5,32,ledger,0,bytes)) return Fail(__LINE__);
    auto copied_shadow = snapshots.BuildProtectedShadow(copied.PlanMap(32,bytes),32,mapped);
    if (!copied_shadow || !std::equal(expected.begin(),expected.end(),copied_shadow->bytes.get())) return Fail(__LINE__);
    snapshots.Destroy();
    if (snapshots.retained_bytes() != 0 || snapshots.reserved_bytes() != 0 ||
        snapshots.BuildProtectedShadow(plan,0,mapped)) return Fail(__LINE__);
    std::printf("height=%u format=%u regions=%zu publication/partial/copy/repeat/tamper/release=PASS\n",
        height,static_cast<unsigned>(format),plan.count);
    return true;
}

int VerifyPublicationTests() {
    for (auto format : {WebGpuPixelFormat::kRgba8Unorm,WebGpuPixelFormat::kBgra8Unorm})
        for (uint32_t height : {5u,1080u}) if (!Run(height,format)) return 2;
    WebGpuReadbackSnapshots slots(7,1,65536,65536);
    for (uint64_t id=1; id<=16; ++id)
        if (!slots.BeginCapture({7,id,id,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 3;
    if (slots.reserved_bytes() != 128 ||
        slots.BeginCapture({7,17,17,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 4;
    if (!slots.Release({7,1,1,1}) ||
        !slots.BeginCapture({7,17,17,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 5;
    std::puts("Confirmed independent global slot limit: 17th 8-byte reservation fails below byte budget; release permits retry.");
    WebGpuReadbackSnapshots expanded(7,1,65536,65536,48);
    if (expanded.snapshot_capacity() != 48) return 6;
    for (uint64_t id=1; id<=48; ++id)
        if (!expanded.BeginCapture({7,id,id,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 7;
    if (expanded.reserved_bytes()!=384 || expanded.pending_count()!=48 ||
        expanded.BeginCapture({7,49,49,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 8;
    if (!expanded.Release({7,1,1,1}) ||
        !expanded.BeginCapture({7,49,49,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 9;
    expanded.Destroy();
    if (expanded.reserved_bytes()!=0 || expanded.pending_count()!=0) return 10;
    WebGpuReadbackSnapshots byte_limited(7,1,128,65536,48);
    for (uint64_t id=1; id<=16; ++id)
        if (!byte_limited.BeginCapture({7,id,id,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 11;
    if (byte_limited.reserved_bytes()!=128 ||
        byte_limited.BeginCapture({7,17,17,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 12;
    if (!byte_limited.Release({7,1,1,1}) ||
        !byte_limited.BeginCapture({7,17,17,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 13;
    for (size_t invalid_count : {size_t{0}, kWebGpuSnapshotSlotLimit+1}) {
        WebGpuReadbackSnapshots invalid_slots(7,1,65536,65536,invalid_count);
        if (invalid_slots.snapshot_capacity()!=0 ||
            invalid_slots.BeginCapture({7,1,1,1},{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm})) return 14;
    }
    WebGpuReadbackSnapshots retained(7,1,65536,65536,48);
    std::array<uint8_t,4> pixel{20,40,60,255};
    std::array<uint8_t,32> seed{};
    std::vector<std::unique_ptr<WebGpuReadbackProvenance>> live;
    for (uint64_t id=1; id<=24; ++id) {
        const WebGpuSnapshotToken token{7,id,id,1};
        if (!retained.Capture(token,{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm},0,pixel,seed)) return 15;
        live.push_back(std::make_unique<WebGpuReadbackProvenance>(4,7));
        if (!live.back()->RecordTextureCopy(id,{0,0,1,1,WebGpuPixelFormat::kRgba8Unorm},token,{0,0,1,1})) return 16;
    }
    for (const auto& buffer : live) {
        auto shadow = retained.BuildProtectedShadow(buffer->PlanMap(0,4),0,pixel);
        if (!shadow || shadow->size!=4 || !std::equal(pixel.begin(),pixel.end(),shadow->bytes.get())) return 17;
    }
    if (retained.retained_bytes()!=192 || retained.reserved_bytes()!=192) return 18;
    auto moved = std::move(retained);
    if (retained.snapshot_capacity()!=0 || retained.pending_count()!=0 || moved.retained_bytes()!=192) return 19;
    moved.Destroy();
    if (moved.reserved_bytes()!=0 || moved.retained_bytes()!=0) return 20;
    if (kWebGpuReadbackRegionLimit!=16) return 21;
    std::puts("PASS: configured 48-slot pool, 24 retained captures, reuse, byte quota, invalid capacities and move/destruction; region limit unchanged.");
    return 0;
}

int main() { const int ledger = VerifyLedgerTests(); return ledger ? ledger : VerifyPublicationTests(); }
