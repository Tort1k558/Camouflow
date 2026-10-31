# Raster shadow routing — unselected source packet

Prepare sampled-texture shadows **before** entering a render pass, then bind them
through dispatch/draw-local descriptor tables without changing the original
BindGroup descriptors. The existing shared draw/bundle encoder uses these tables.
This packet is **not selected, linked or admitted in a browser**.

| Check | Observed result | Does not prove |
| --- | --- | --- |
| Native source syntax | Seven units passed pinned Chromium target flags | Linking or actual Dawn execution |
| Descriptor helper | Exact method extracted from the composed native packet; real D3D12 calls | Real Dawn layout/allocator behavior |
| Table isolation | Protected table and original table produce different, expected pixels | All native BindGroup/pipeline transitions |
| Heap replacement | Two separate GPU heaps retain valid tables across allocator exhaustion/retry | Dawn's real ring allocator rollover |
| Raster | Eight cases; four `BeginRenderPass` and four explicit OM target bindings | Dawn raster/bundle runtime |
| Hardware normal/ASan | 36,269 assertions and eight quota cases each | Browser privacy or CAPTCHA results |
| Lifetime | Four cases drop both CPU projection and simulated queue owner before submission; overrides retain resource/quota | Native device-loss recovery |
| Unsupported inputs | Owner, source, view, duplicate binding and descriptor preflight errors occur before allocation | Complete GPU format support |

The fixture uses adapted Dawn types and allocator bookkeeping, **not** the actual
Dawn backend. GPU resources, heaps, descriptor copies, shader dispatches, raster
draws and readbacks are real D3D12 operations. Every image verifies that protection
changed pixels; it then compares protected and unmodified descriptor paths against
their separate CPU references. The original texture is also verified unchanged.

## Run the hardware check

Requires Windows, the pinned Chromium checkout and SDK, and a hardware D3D12 adapter:

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-raster-routing\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-raster-check
```

Use a fresh external output directory. The checker reconstructs all twelve public
packets, verifies source hashes, extracts the descriptor method, applies a measured
delta to the shared shadow fixture, and runs normal/ASan. Helpers and compute shader
are reused rather than copied into a second implementation. No downloads, browser
profiles, production services or driver/security settings are changed.

Before using `BeginRenderPass`, the fixture requires `RenderPassesValid`, as specified
by [Microsoft](https://microsoft.github.io/DirectX-Specs/d3d/RenderPasses.html#checking-for-support).
It fails on unsupported hardware/runtime; it does not silently substitute WARP or
skip the requested path. This requirement is distinct from driver acceleration tier.

## Prepared native behavior and remaining work

- Aggregate validated pass usage is checked before projection; sampled sources
  with any in-pass write dependency are rejected, including bundle usage.
- Per-bind-group shadow descriptors are reused within the pass; the cache is reset
  between passes. Dynamic offsets continue through the existing native path.
- Readable storage textures, external textures, resource tables, framebuffer fetch
  and unsupported sampled views remain rejected without a raw-input fallback.
- Shader-derived output maps remain denied. Trusted protected-output provenance,
  real Dawn state/allocator/bundle execution, GN/component checks and the complete
  Canvas/GPU browser consistency gate remain unfinished.

The selected 001–076 browser and its negative Canvas/GPU consistency result are
unchanged. This packet and its standalone checks do not supersede that result.
