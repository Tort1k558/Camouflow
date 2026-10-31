# Raster shader-byte capture — unselected source batch

Render draws and bundles accumulate owned buffer/control dependencies across a
pass. Storage-buffer snapshots are recorded **after `EndRenderPass`**, through the
same prepare/commit and private-copy path as compute. Nothing is enabled in the
selected browser.

| Layer | Evidence | Boundary |
| --- | --- | --- |
| Source | Fifteen-packet replay/reverse, 78 paths | One native command-recorder file changed |
| Accumulator | 191,422 assertions each normal/ASan; 1,000 oracle passes / 16,000 draws, 8,192 duplicate draws | Exact extracted merge method, synthetic owners |
| CPU controller | 256 aggregated pass transactions, owned-map verification and tamper rejection | Not a Dawn render recorder |
| GPU experiment | Eight D3D12 hardware cases / 58,791 assertions each normal/ASan; 16 scissored draws | Real fragment UAV writes, synthetic Dawn handles/allocator |
| Pass API | Four valid `BeginRenderPass` cases with UAV-write permission; four explicit OM cases | Not actual Dawn pass execution or bundles |
| Native syntax | Ten target-flag translation units passed | No GN regeneration, component link or browser admission |

## Reproduce the accumulator/controller check

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-raster-byte-capture\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-raster-byte-capture-check
```

Requires Windows and the pinned 001–076 checkout/SDK. The existing source replay,
hash guards and CPU compiler runner are reused from `webgpu-private-backing`.
All fifteen packets are composed outside the checkout; the real merge method is
inserted into the measured template before normal/ASan execution.

GPU experiment assets are also public: `hardware.patch` extends the preceding
shader-capture hardware fixture, `raster_consumer.hlsl` writes fragment bytes, and
`raster-scope-template.h` embeds the extracted merge method. The command above is
**CPU-only**, not an automated reproduction of that GPU experiment. A public
GPU runner remains pending.

## Invariants and unfinished gates

- Vertex, index, indirect and count inputs retain native `Ref` owners and pass
  the same private-backing/range validation as bound buffers.
- Equal-access overlapping/adjacent intervals merge; gaps and read/write access
  classes remain separate. Owners deduplicate; capacity failures reject recording.
- No per-draw observer mutation occurs before the pass-wide transaction. Compute
  and raster reuse the same output-owner and writable-union validation.
- The hardware fixture uses two disjoint scissors and checks both fragment UAV
  output and render-target pixels against the shared CPU projection. Snapshots
  stay unavailable until submission is marked; mismatching bytes are rejected.
- Copying is outside the active pass, following the
  [Microsoft render-pass contract](https://learn.microsoft.com/en-us/windows/win32/direct3d12/direct3d-12-render-passes).

This is storage-buffer output capture, **not complete protection of all raster
outputs**, arbitrary formats, attachment/depth/blend dependencies or GPU
buffer-input projection. Actual Dawn recording/allocator/queue, bundles, Wire
roundtrips and the real browser consistency gate remain unverified. The selected
browser's negative Canvas/GPU consistency result is unchanged. No privacy,
production or CAPTCHA admission follows from these experiments.
