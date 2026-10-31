# WebGPU SRV routing and readonly indirect dispatch

**Standalone native evidence, not a corrected Chromium release.**

The first complete 001–116 browser loses the protected WebGPU device in
`BindGroup::PopulateGlintViews`: Dawn represents a logical 2D view as a one-slice
`TEXTURE2DARRAY` SRV, while the projection guard accepted only `TEXTURE2D`.
The device reports the exact descriptor error; its hardware removal reason is
`S_OK`. Baseline rendering remains functional.

| Measured gate | Result | Boundary |
| --- | --- | --- |
| Same-source before/after sampled RGBA/BGRA | 12/12 expected results | Before: exact native device-loss error; after: protected shader reference matches |
| Corrected standalone matrix | 54/54 | Real Dawn client/server Wire and D3D12; includes no-filter and denied-map controls |
| Readonly indirect | Direct arguments, 16-byte offset, zero-work output preservation | Projected argument/count controls and writable inputs remain denied |
| Budget and cleanup | 64 MiB limit; capture bytes drain to zero | Not physical GPU memory accounting or quota recovery |
| Chromium with these corrections | Not yet built/tested | No privacy, production or CAPTCHA admission |

`srv-routing.patch` retains logical-2D, exact single-layer/mip/plane, native owner,
format and extent checks. It reuses Dawn's original descriptor rather than
changing its representation. `readonly-indirect.patch` retains native indirect
validation and only admits readonly projected shader buffers with untouched
indirect controls.

The two Wire sources are the measured case matrix and its diagnostic-only
lost-event observer. The latter drains the native loss event before exiting a
failed control; it does not suppress errors in the browser. Exact source hashes,
case results and earlier failed/incomplete measurements are recorded in
[`observations.json`](observations.json).

The explicit [118-patch candidate](../upstream-156-webgpu-r2/README.md) composes
these changes without rewriting the measured 116-patch candidate or its receipt.
Standalone executables need the measured `d3dcompiler_47.dll` beside the executable;
the first relocated-fixture attempts lacked it and supplied no hardware result.
