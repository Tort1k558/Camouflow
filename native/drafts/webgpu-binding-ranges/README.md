# WebGPU compute binding ranges — unselected source extension

This three-file delta follows `webgpu-ranged-provenance-next.patch` and the
earlier source packets. It does not change the selected 001–076 browser.

## Source changes

- Explicit range metadata; unknown or out-of-bounds ranges fail closed.
- Compute uniform/storage ranges include binding offsets and dynamic offsets.
- Texel-buffer bindings use the native view's buffer, offset, size and access.
- Indirect dispatch includes the 12-byte dispatch-control input.
- Aliased bindings inspect every input before any output changes. Each output
  receives a distinct execution sequence, even when bindings share a buffer.
- Metadata has a 256-binding cap; the configured buffer limit counts unique
  buffer identities, not aliases. Zero-byte uses do not create dependencies.

Declared compute-visible bindings are conservatively included; this is not
shader-instruction-level reflection. Render-pass notifications still cover whole
buffers. Shader-derived reads are still refused, not transformed compatibly.

## Evidence

| Check | Result | Boundary |
| --- | --- | --- |
| CPU normal / ASan | 4,969,118 assertions each | Synthetic native handles, no shader execution |
| Deterministic oracles | 4,000 core operations plus 1,000 controller scopes per mode | Includes aliases, partial writes and empty ranges |
| Chromium-flag syntax | Native D3D12 and service observer, zero diagnostics | No linking or native callback execution |
| Source replay | Nine ordered packets, 69 composed paths; extension reverse verified | Existing Chromium checkout unchanged |
| Public checker | Same normal/ASan results from reconstructed public packets | CPU/controller test only |
| Full Python baseline | 5107 passed, 1 skipped at `439d8d6` | Before this extension, not native evidence |

The [preparation record](../environment/webgpu-binding-ranges-preparation.json)
binds the packets, test source and observations. Native dynamic offsets, indirect
dispatches and texel views have **not** been exercised by these CPU tests.

## Reproduce the CPU check

Requires the pinned 001–076 source baseline, existing Windows SDK/compiler and
cached BoringSSL/libc++ objects; it does not download dependencies or run a browser.
Use a fresh D: output directory outside the repository, SDK and Chromium checkout.

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-binding-ranges\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\binding-ranges-fresh
```

## Still required

Real Dawn/Wire execution with nonzero dynamic offsets, sliced and aliased bindings,
indirect control dependencies and texel views; render draw/bundle ranges; compatible
shader pixel protection; static/component linking; browser regressions across
documents/workers/restarts. Combined GN was not rerun for this source-only delta.
The selected runtime's copy/shader/PNG mismatch remains unresolved. No runtime,
privacy or production admission follows from these results.
