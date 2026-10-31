# Shader capture — unselected integrated source batch

The batch connects projected compute inputs, execution-bound output snapshots,
two-phase controller transactions and the existing owned map-shadow API. **It is
not linked, selected or released in the browser.**

| Layer | Verified evidence | Remaining boundary |
| --- | --- | --- |
| Native source | 13-packet replay, 77 composed paths; 12-path delta reverses exactly | No active checkout edits |
| Compute hooks | Direct/indirect dispatch capture, logical owners and writable-range coverage prepared; 10 native syntax units passed | Actual Dawn recording/queue execution |
| Controller | 10,154 assertions, 2,000 transaction cycles in normal/ASan | Synthetic Dawn handles, not native device lifecycle |
| Byte provenance | 4,886 assertions, 1,000 interval cases in normal/ASan | Controller eligibility is a separate gate |
| GPU → snapshot → controller → filter `Prepare` | 8 hardware cases, 47,613 assertions each in normal/ASan | Extracted adapter/filter, not actual Wire factory/server/serialization |
| Existing behavior | 4,969,123 CPU assertions and 22,720 hardware texture-capture assertions each | Not a browser-wide regression or privacy admission |

## Reproduce

Windows, pinned Chromium checkout/SDK and a fresh external D: output are required:

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-shader-capture\check.py `
  --suite hardware `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-shader-capture-check
```

| `--suite` | Execution |
| --- | --- |
| `hardware` (default) | Real GPU projection/copy/raster/readback, real CPU controller, source-extracted native snapshot adapter and Wire-filter `Prepare` |
| `controller` | Synthetic-handle prepare/commit, eligibility, aliases, failures, pending results and repeated transactions |
| `core` | Captured-byte identity, domain separation, clipping, tamper rejection, quotas and lifetime |
| `legacy` | Existing CPU provenance/controller oracle; its shader-transformation flag describes this legacy fixture, not the engine's feature inventory |
| `texture-compat` | Existing real hardware texture-capture/lifetime/contention fixture against the modified shared allocation helper |

Use a different fresh output for each command. Hardware suites require a hardware
D3D12 adapter; there is no WARP fallback or silent test skipping. Render-pass API
cases require `RenderPassesValid`, following the
[Microsoft contract](https://microsoft.github.io/DirectX-Specs/d3d/RenderPasses.html#checking-for-support).
All suites replay and hash-check the complete source chain outside the checkout.
The geometry/shadow fixtures and helpers are reused from existing public modules.

## Admission rules

- Captured byte regions are not labeled unrelated: maps compare every tracked byte
  with an owned immutable execution-bound snapshot. Pixel and byte domains differ.
- The controller requires complete known ranges and backend-owned input projection
  readiness. Raw pixel-derived, opaque, unsafe and unprojected inputs are ineligible.
- Existing output bytes must also be eligible because shaders may write only part
  of their bindings. Overlapping/adjacent outputs merge; disjoint intervals do not.
- Active transactions deny maps. Bad tickets, results, sizes, interleaved mutations
  and recording/submission failures invalidate state, never authorize raw reads.
- Query-resolve writes notify the controller as uncertain writes so old captured
  provenance cannot survive them. Full native buffer-write-path coverage still
  requires audit and runtime verification.
- Native requests are checked against logical owners and the actual writable
  binding union before private copies; GPU resources and quotas retire together.
- The hardware fixture deliberately injects an unreported later GPU overwrite:
  the extracted filter rejects its mismatching raw bytes and preserves owned output.

Raster-output capture, GPU buffer-input projection, full formats, actual native
device/queue/allocator execution, Wire server roundtrips, GN/component linking and
the real browser consistency gate remain unfinished. Prepared raster input routing
is not raster-output admission. The selected 001–076 browser and its negative
Canvas/GPU consistency result are unchanged. Do not enable this batch on an older
binary or treat these checks as CAPTCHA results or a production release.
