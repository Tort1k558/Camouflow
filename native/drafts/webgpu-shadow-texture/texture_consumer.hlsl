// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
Texture2D<float4> Source : register(t0);
RWByteAddressBuffer Output : register(u0);
cbuffer Parameters : register(b0) {
    uint4 UnusedKey0;
    uint4 UnusedKey1;
    uint Width;
    uint Height;
    uint Pitch;
    uint Offset;
    uint Bgra;
    uint Operation;
    uint MessageBytes;
    uint Reserved;
};
[numthreads(4,4,1)]
void main(uint3 tid : SV_DispatchThreadID) {
    if (tid.x >= Width || tid.y >= Height) return;
    uint4 rgba = (uint4)round(saturate(Source.Load(int3(tid.xy, 0))) * 255.0);
    Output.Store((tid.y * Width + tid.x) * 4,
                 rgba.r | (rgba.g << 8) | (rgba.b << 16) | (rgba.a << 24));
}
