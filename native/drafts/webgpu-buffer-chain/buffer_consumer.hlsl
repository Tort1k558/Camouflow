// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
ByteAddressBuffer Input : register(t0);
RWByteAddressBuffer Output : register(u0);
cbuffer Parameters : register(b0) { uint Words; };
[numthreads(64,1,1)]
void main(uint3 id : SV_DispatchThreadID) {
    if (id.x < Words) Output.Store(id.x * 4, Input.Load(id.x * 4));
}
