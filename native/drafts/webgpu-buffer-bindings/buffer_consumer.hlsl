// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
ByteAddressBuffer ReadonlyInput : register(t0);
RWByteAddressBuffer WritableInput : register(u0);
RWByteAddressBuffer Output : register(u1);
cbuffer UniformInput : register(b0) { uint4 UniformWords[32]; };
cbuffer Parameters : register(b1) { uint DynamicOffset; uint WriteInput; };
[numthreads(1, 1, 1)]
void uniform_main() { Output.Store(0, UniformWords[0].x); }
[numthreads(1, 1, 1)]
void readonly_main() { Output.Store(0, ReadonlyInput.Load(DynamicOffset)); }
[numthreads(1, 1, 1)]
void writable_main() {
    uint value = WritableInput.Load(DynamicOffset);
    if (WriteInput != 0) WritableInput.Store(DynamicOffset, value ^ 0xa5a5a5a5u);
    Output.Store(0, value);
}
