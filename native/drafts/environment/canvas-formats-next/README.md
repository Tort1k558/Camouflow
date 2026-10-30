# Canvas format extension — isolated draft

**Selected as 0072 and compiled in the development 001–072 browser; the fresh format gate passes 32/32.**
[Format evidence](../canvas-formats72-observations.json),
[combined 18/18](../combined-math72-observations.json),
[PNG export 8 cases / 12 carriers](../canvas-export72-observations.json).
Workers and broad HDR quality remain separate gates.
[Build and baseline](../../upstream-156/build72-observations.json) do not supersede
the required real browser format/export/worker and combined-policy checks.
[Linked selection](../linked72-selection-observations.json) also includes orientation/visibility
and its strict four-case native gate. Source selection does not prove application,
compilation, native case execution or browser compatibility. The isolated records
below describe their earlier pre-selection measurements, not mutable readiness flags.
The preserved 001–070 browser still has the [30/32 format failure](../canvas-formats70-observations.json).

## Implemented in the draft

| Area | Change |
| --- | --- |
| Source formats | Detached RGBA8/BGRA8 and RGBA_F16/F16Norm, explicitly tagged sRGB or Display-P3 |
| Canonical snapshot | Keep source color space and F16 precision; native Skia conversion only after protection, for requested ImageData/crop/export |
| F16 transform | Version-2 HMAC domain; one deterministic mantissa bit at edges, adaptive quantum bounded by max(1/256, one ULP); sign/exponent/alpha and all other bits unchanged |
| Existing RGBA8 | Original transform unchanged; no 8-bit conversion of F16 storage, raw-pixel fallback or live-target mutation |
| Memory | Actual 4/8 bytes per pixel; checked dimensions and simultaneous raster/copy budget |

The [previous single-LSB prototype fails](mantissa-lsb-failure.json): all 32 seed
controls have different F16 results, but collapse to **one unchanged RGBA8 result**
in each measured source color space. The adaptive variant fixes that owned fixture
without an 8-bit round trip or independent per-output noise. This is **not** a
guarantee for every possible image, API or physical-device identity.

## Measured, not inferred

[Source-bound observations](observations.json): all four changed translation units
pass the pinned Chromium compiler's syntax checks. A separately linked executable
uses the actual modified transform and existing BoringSSL, not a Python model or
mock hash. It passes **12 controls**, including a known HMAC answer and all
**65,536 binary16 encodings**: bounded changes, sign/exponent/special values/alpha
preservation and idempotence.

A second executable links the actual copy helper and existing Skia. Its **283
controls** pass: detached copies, known HDR/crop/alpha cases, normalized F16,
memory/overflow/errors, and four sRGB/P3 source/read color-space pairs. For each
pair, **32 native seed controls retain 32 distinct F16 and RGBA8 results** on the
finite rich fixture. These are seed controls, **not 32 browser profiles** or broad
editor/HDR/perceptual quality evidence.

The five helper files can also be reconstructed and hash-checked in ordinary
pytest from public patches 0033/0034/0063, without the external Chromium checkout.
[Actual public-runner repeat](reproduction.json) records preparation, four syntax
checks, both native builds and their executions, with final input guards.

Repeat against a retained pinned Windows **001–070 source/build**, with a fresh
output on D. This historical prototype runner deliberately rejects already-patched
001–072 input; it never reverses or double-applies active source changes:

```powershell
.\.venv\Scripts\python.exe native/drafts/environment/canvas-formats-next/verify_draft.py --source-root D:\Glint156Candidate\chromium\src --build-dir D:\Glint156Candidate\chromium\src\out\CamouFlowNative --work-dir D:\GlintManagerQA\fresh-canvas-format-draft
```

The runner patches **only copied files in its fresh output**, checks prepared hashes,
borrows existing generated modules/production link dependencies, creates private
lazy archives of source-set objects, and writes compile/link logs and its
report there. It does not invoke Ninja, regenerate GN, change SDKs, build Chrome,
or alter source/output objects in the active tree. This is not a hermetic rebuild:
transitive generated modules and thin-library objects remain existing build inputs.

Next: browser export/crop/worker tests, the runtime 32-case differential matrix,
both derivation modes and combined policies, and broader image/HDR quality. Batch
with queued orientation/visibility changes only after those source-level gates are
ready; keep the preserved runtime available for comparison and rollback.
