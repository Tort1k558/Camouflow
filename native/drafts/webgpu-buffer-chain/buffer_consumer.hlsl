// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
ByteAddressBuffer Input : register(t0);
RWByteAddressBuffer Output : register(u0);
RWByteAddressBuffer WritableInput : register(u0);
RWByteAddressBuffer WritableOutput : register(u1);
cbuffer Parameters : register(b0) { uint Words; };
[numthreads(64,1,1)]
void readonly_main(uint3 id : SV_DispatchThreadID) {
    if (id.x < Words) Output.Store(id.x * 4, Input.Load(id.x * 4));
}
[numthreads(64,1,1)]
void writable_main(uint3 id : SV_DispatchThreadID) {
    if (id.x >= Words) return;
    uint value = WritableInput.Load(id.x * 4);
    WritableOutput.Store(id.x * 4, value);
    if (id.x % 3 == 1) WritableInput.Store(id.x * 4, value ^ 0xa5a5a5a5u);
}
