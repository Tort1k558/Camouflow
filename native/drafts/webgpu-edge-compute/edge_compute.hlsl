// Copyright 2026 CamouFlow contributors. SPDX-License-Identifier: MIT
// Experimental fixed-32-byte-key HMAC-SHA-256 projection; not browser-integrated.
ByteAddressBuffer Input : register(t0);
RWByteAddressBuffer Output : register(u0);
cbuffer Parameters : register(b0) {
    uint4 Key0;
    uint4 Key1;
    uint Width;
    uint Height;
    uint Pitch;
    uint Offset;
    uint Bgra;
    uint Operation;
    uint MessageBytes;
    uint Reserved;
};

static const uint K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
static const uint IV[8] = {
    0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
    0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
};
static const uint Domain[30] = {
    103,108,105,110,116,46,99,97,110,118,97,115,46,101,100,
    103,101,46,99,97,110,100,105,100,97,116,101,46,118,49
};
uint Rotate(uint value, uint bits) { return (value >> bits) | (value << (32 - bits)); }
uint Swap(uint value) {
    return (value << 24) | ((value & 0xff00) << 8) |
           ((value >> 8) & 0xff00) | (value >> 24);
}
void Initialize(out uint state[8]) {
    [unroll] for (uint i = 0; i < 8; ++i) state[i] = IV[i];
}
void Compress(inout uint state[8], uint block[16]) {
    uint w[16];
    [unroll] for (uint loadIndex = 0; loadIndex < 16; ++loadIndex) w[loadIndex] = block[loadIndex];
    uint a = state[0], b = state[1], c = state[2], d = state[3];
    uint e = state[4], f = state[5], g = state[6], h = state[7];
    [loop] for (uint round = 0; round < 64; ++round) {
        uint slot = round & 15;
        if (round >= 16) {
            uint x = w[(round - 15) & 15], y = w[(round - 2) & 15];
            uint small0 = Rotate(x, 7) ^ Rotate(x, 18) ^ (x >> 3);
            uint small1 = Rotate(y, 17) ^ Rotate(y, 19) ^ (y >> 10);
            w[slot] += small0 + w[(round - 7) & 15] + small1;
        }
        uint s1 = Rotate(e, 6) ^ Rotate(e, 11) ^ Rotate(e, 25);
        uint choose = (e & f) ^ (~e & g);
        uint t1 = h + s1 + choose + K[round] + w[slot];
        uint s0 = Rotate(a, 2) ^ Rotate(a, 13) ^ Rotate(a, 22);
        uint majority = (a & b) ^ (a & c) ^ (b & c);
        uint t2 = s0 + majority;
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}
void SetByte(inout uint words[16], uint index, uint value) {
    words[index / 4] |= (value & 255) << (24 - (index % 4) * 8);
}
void Hmac(uint message[16], uint length, out uint digest[8]) {
    uint key[8] = {Key0.x,Key0.y,Key0.z,Key0.w,Key1.x,Key1.y,Key1.z,Key1.w};
    uint block[16];
    [unroll] for (uint padIndex = 0; padIndex < 16; ++padIndex)
        block[padIndex] = (padIndex < 8 ? Swap(key[min(padIndex, 7)]) : 0) ^ 0x36363636;
    Initialize(digest);
    Compress(digest, block);
    SetByte(message, length, 128);
    message[15] = (64 + length) * 8;
    Compress(digest, message);
    uint inner[8];
    [unroll] for (uint innerIndex = 0; innerIndex < 8; ++innerIndex) inner[innerIndex] = digest[innerIndex];
    [unroll] for (uint outerPad = 0; outerPad < 16; ++outerPad)
        block[outerPad] = (outerPad < 8 ? Swap(key[min(outerPad, 7)]) : 0) ^ 0x5c5c5c5c;
    Initialize(digest);
    Compress(digest, block);
    [unroll] for (uint outerMessage = 0; outerMessage < 16; ++outerMessage)
        block[outerMessage] = outerMessage < 8 ? inner[min(outerMessage, 7)] : 0;
    block[8] = 0x80000000;
    block[15] = 768;
    Compress(digest, block);
}
uint Canonical(uint packed) {
    return Bgra != 0 ? (packed & 0xff00ff00) | ((packed & 255) << 16) |
                       ((packed >> 16) & 255) : packed;
}
bool Different(uint center, uint neighbour) {
    return (neighbour >> 24) == 255 && ((center ^ neighbour) & 0x00fefefe) != 0;
}
[numthreads(1,1,1)]
void hmac_main(uint3 tid : SV_DispatchThreadID) {
        if (MessageBytes > 55) return;
        uint message[16];
        [unroll] for (uint clearMessage = 0; clearMessage < 16; ++clearMessage) message[clearMessage] = 0;
        [loop] for (uint inputByte = 0; inputByte < MessageBytes; ++inputByte)
            SetByte(message, inputByte, (Input.Load((inputByte / 4) * 4) >> ((inputByte % 4) * 8)) & 255);
        uint digest[8];
        Hmac(message, MessageBytes, digest);
        [unroll] for (uint outputWord = 0; outputWord < 8; ++outputWord) Output.Store(outputWord * 4, Swap(digest[outputWord]));
}
[numthreads(4,4,1)]
void edge_main(uint3 tid : SV_DispatchThreadID) {
    if (tid.x >= Width || tid.y >= Height) return;
    uint address = Offset + tid.y * Pitch + tid.x * 4;
    uint center = Canonical(Input.Load(address));
    bool edge = false;
    if ((center >> 24) == 255) {
        uint left = Offset + tid.y * Pitch + (max(tid.x, 1) - 1) * 4;
        uint right = Offset + tid.y * Pitch + min(tid.x + 1, Width - 1) * 4;
        uint up = Offset + (max(tid.y, 1) - 1) * Pitch + tid.x * 4;
        uint down = Offset + min(tid.y + 1, Height - 1) * Pitch + tid.x * 4;
        if (tid.x > 0) edge = edge || Different(center, Canonical(Input.Load(left)));
        if (tid.x + 1 < Width) edge = edge || Different(center, Canonical(Input.Load(right)));
        if (tid.y > 0) edge = edge || Different(center, Canonical(Input.Load(up)));
        if (tid.y + 1 < Height) edge = edge || Different(center, Canonical(Input.Load(down)));
    }
    if (edge) {
        uint message[16];
        [unroll] for (uint clearPixel = 0; clearPixel < 16; ++clearPixel) message[clearPixel] = 0;
        [unroll] for (uint domainByte = 0; domainByte < 30; ++domainByte) SetByte(message, domainByte, Domain[domainByte]);
        SetByte(message, 30, (center & 255) >> 1);
        SetByte(message, 31, ((center >> 8) & 255) >> 1);
        SetByte(message, 32, ((center >> 16) & 255) >> 1);
        uint digest[8];
        Hmac(message, 33, digest);
        uint bits = digest[0] >> 24;
        center = (center & 0xfffefefe) | (bits & 1) | ((bits & 2) << 7) | ((bits & 4) << 14);
    }
    Output.Store(address, Canonical(center));
}
