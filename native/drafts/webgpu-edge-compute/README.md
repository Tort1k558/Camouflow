# GPU edge projection — isolated hardware prototype

HLSL compute implementation of the existing CPU edge/HMAC-SHA-256 projection for
packed RGBA8/BGRA8 buffers. This is **not integrated into Dawn or the browser**.
It does not resolve the selected runtime's copy/shader/PNG mismatch.

## Measured hardware checks

| Check | Result | Boundary |
| --- | --- | --- |
| Hardware normal / ASan | 173,282 assertions each | One hardware adapter, no software fallback |
| HMAC | Six cases against BoringSSL, including two RFC 4231 known answers | Fixed 32-byte keys; messages up to 55 bytes |
| CPU/GPU pixel equivalence | 32 RGBA/BGRA fixtures | Raw byte-address buffers, not Dawn textures or views |
| Repeat / idempotence | Repeated output and re-projected output match | Same input/key in this standalone process |
| Key isolation | Same image with two keys differs and matches the corresponding CPU result | Two fixture cases, not browser profile isolation |
| Compatibility | Alpha, row padding, guard bytes, uniform and non-opaque fixtures preserved; channel delta at most one | Tested 1x1, 7x3, 65x5 and 32x17 sizes |
| Python baseline | 5124 passed, 1 skipped at `dfe2648` | Before this module; not GPU evidence |

HMAC references: [RFC 4231 cases 1–2](https://datatracker.ietf.org/doc/html/rfc4231#section-4.2)
and [SHA-256 specification](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf).
Short known-answer keys are zero-padded to the fixed 32-byte key interface, which
preserves their HMAC block padding. This is not a cryptographic certification.

## Reproduce

Requires Windows, a D3D12 hardware adapter, the existing pinned compiler/SDK and
cached BoringSSL/libc++ objects. The runner extracts the hash-pinned shared CPU math
from its public source packet; it does not depend on a private D: source stage.
It neither downloads dependencies nor rebuilds Chromium.

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-edge-compute\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\edge-compute-fresh
```

Use `--compile-only` for HLSL compilation/disassembly without creating a GPU
device. That mode explicitly reports hardware execution as unverified.
Compilation uses [D3DCompile](https://learn.microsoft.com/en-us/windows/win32/api/d3dcompiler/nf-d3dcompiler-d3dcompile)
with warnings treated as errors. The hardware path requires a hardware adapter;
there is no automatic WARP retry. Diagnostics and assembly stay in the chosen D:
output directory. No global GPU, security or watchdog settings are changed.

## Earlier failure and limitations

The first combined-entry/root-descriptor prototype returned
`DXGI_ERROR_DEVICE_HUNG (0x887A0006)`; its failed report was retained. The passing
version uses bounded SRV/UAV descriptor views, separate entry points and a rolling
SHA workspace. The original cause was **not isolated conclusively**; passing later
tests must not be presented as proof that one particular change fixed it.

This prototype projects raw buffers using a standalone harness. Production resource
ownership/budgets, typed texture conversion, Dawn descriptor routing, render-pass
state restoration, queue/device failures and performance remain required. FP16,
other formats and browser documents/workers/restarts are not covered. The browser
still needs compatible shader-input routing and a successful actual consistency
gate; refusing a mapped shader result is not a substitute.

[Hash-bound observations](../environment/webgpu-edge-compute-observations.json).
