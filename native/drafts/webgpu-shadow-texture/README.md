# GPU shadow textures — standalone native helper

`ProjectedTexture::Record` copies an initialized RGBA/BGRA texture into private GPU
buffers, applies the existing edge projection and creates a separate shader-readable
texture. No CPU pixel readback occurs between those GPU operations. The source
texture is not modified. **Dawn/browser routing is not installed.**

## Measured checks

| Check | Result | Boundary |
| --- | --- | --- |
| Hardware normal / ASan | Eight cases, 19,206 assertions each | RGBA/BGRA UNORM and compatible TYPELESS storage, 7x3 and 65x5 |
| Typed compute consumer | Texture.Load → storage bytes matches the CPU protected image | Standalone HLSL, not Dawn/WGSL or raster execution |
| Original texture | Original pixels remain unchanged | Tested fixture/source state only |
| Lifetime | Four CPU owners deleted before submit; queued owners retain resources/quota | Actual GPU completion in this harness, no device-loss injection |
| Completion | Withheld submission marker stays pending even after fence completion | Four retained CPU owners |
| Shared quota | Projection consumes the same budget as capture; exhausted capture is rejected | Eight cases; not a total-driver-VRAM measurement |
| Native target syntax | Helper and staged capture units passed actual Chromium/Dawn flags | No native/component linking |
| Python baseline | 5131 passed, 1 skipped at `04a22bd` | Before this helper |

## Ownership and recording contract

- Caller supplies an open DIRECT list, initialized COPY_SOURCE texture and trusted
  edge pipeline/root ABI: two descriptor tables and sixteen DWORD constants.
- Inputs are checked before recording; resource allocations precede the first GPU
  command. Unsupported dimensions/formats, stale fences and quota failures are
  rejected, not passed through as unprotected data.
- The returned texture pointer is **borrowed**. Retain `retirement_handle()` for
  every use, including descriptor/view caches. Retain it through GPU retirement
  even if the CPU object is deleted. A bare resource reference is not a quota owner.
- Mark submission only after ExecuteCommandLists. CPU readiness requires both the
  marker and fence completion. The output ends in pixel/non-pixel shader-read state.
- Compute root/pipeline/heaps are changed. Caller must restore bindings and inform
  its state tracker before other work. The harness explicitly rebinds its consumer;
  Dawn state restoration remains unverified.
- Device checks establish physical D3D12-device compatibility, **not logical Dawn
  device, origin or profile ownership**. Native integration must validate those.
- Quota charges GetResourceAllocationInfo for three new resources plus a fixed
  64 KiB descriptor allowance. It does not account for all driver/cache/CPU memory.

The budget uses the existing `CaptureMemoryBudget`, not a second counter. Its
two friendship declarations are applied only to staged copies of the unchanged
public capture source. The base capture module and active Chromium checkout are
not modified.

## Reproduce

Requires the existing Windows compiler/SDK, a D3D12 hardware adapter and cached
BoringSSL/libc++ objects. The runner reconstructs CPU math and the budget extension
from hash-bound public sources; no private source stage or downloads are needed.

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-shadow-texture\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\shadow-texture-fresh
```

## Not admitted

Actual Dawn descriptor substitution and logical ownership, resource-version
invalidation, render-pass/raster behavior, device loss, performance and the public
browser consistency gate remain required. SRGB, FP16, mip chains, arrays and MSAA
are unsupported by this helper. No browser/runtime/privacy/production admission is
granted by these hardware tests.

[Observed sources and results](../environment/webgpu-shadow-texture-observations.json).
