// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
ByteAddressBuffer ProtectedPixels : register(t0);
RWByteAddressBuffer Shadow : register(u0);
cbuffer Mapping : register(b0) {
    uint DestinationOffset; uint RegionBytes; uint PrefixBytes; uint InitialRow;
    uint InitialColumn; uint SourcePitch; uint CopyWidth; uint CopyHeight;
    uint SourceX; uint SourceY; uint FullWidth; uint FullHeight;
    uint Bgra; uint DestinationBytes; uint ProtectedBytes; uint Reserved;
};

bool ProjectedByte(uint index, out uint source_address, out uint destination_address) {
    source_address = 0; destination_address = 0;
    if (index >= RegionBytes || index < PrefixBytes || !SourcePitch ||
        InitialColumn >= SourcePitch || Bgra > 1 || Reserved != 0 ||
        !CopyWidth || !CopyHeight || FullWidth > 8192 || FullHeight > 8192 ||
        !FullWidth || !FullHeight || SourceX > FullWidth || SourceY > FullHeight ||
        CopyWidth > FullWidth - SourceX || CopyHeight > FullHeight - SourceY ||
        DestinationOffset > DestinationBytes || index >= DestinationBytes - DestinationOffset) return false;
    const uint delta = index - PrefixBytes;
    uint row = InitialRow + delta / SourcePitch;
    const uint remainder = delta % SourcePitch;
    uint column;
    // Avoid uint overflow for legal very large native row pitches.
    if (remainder >= SourcePitch - InitialColumn) {
        row += 1; column = remainder - (SourcePitch - InitialColumn);
    } else {
        column = InitialColumn + remainder;
    }
    if (row >= CopyHeight || column >= CopyWidth * 4) return false;
    uint channel = column % 4;
    if (Bgra != 0 && channel % 2 == 0) channel = 2 - channel;
    source_address = ((row + SourceY) * FullWidth + column / 4 + SourceX) * 4 + channel;
    if (source_address >= ProtectedBytes) return false;
    destination_address = DestinationOffset + index;
    return true;
}

[numthreads(64,1,1)]
void scatter_main(uint3 tid : SV_DispatchThreadID) {
    const uint first = (tid.x + tid.y * 4096) * 4;
    [unroll] for (uint byte_index = 0; byte_index < 4; ++byte_index) {
        uint source_address, destination_address;
        if (!ProjectedByte(first + byte_index, source_address, destination_address)) continue;
        const uint value = (ProtectedPixels.Load(source_address & ~3u) >> ((source_address % 4) * 8)) & 255;
        const uint shift = (destination_address % 4) * 8;
        const uint mask = 255u << shift;
        uint previous;
        // Disjoint bytes can share a DWORD across threads/regions; preserve their bits atomically.
        Shadow.InterlockedAnd(destination_address & ~3u, ~mask, previous);
        Shadow.InterlockedOr(destination_address & ~3u, value << shift, previous);
    }
}

[numthreads(64,1,1)]
void consume_main(uint3 tid : SV_DispatchThreadID) {
    const uint address = (tid.x + tid.y * 4096) * 4;
    if (address < DestinationBytes) Shadow.Store(address, ProtectedPixels.Load(address) ^ 0xa5a5a5a5u);
}
