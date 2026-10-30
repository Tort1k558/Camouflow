# Canvas format extension — isolated draft

**Not registered, applied to the active checkout, compiled into Chrome or admitted.**
The preserved 001–070 browser still has the [30/32 format failure](../canvas-formats70-observations.json).

## Implemented in the draft

| Area | Change |
| --- | --- |
| Source formats | Detached RGBA8/BGRA8 and RGBA_F16/F16Norm, explicitly tagged sRGB or Display-P3 |
| Canonical snapshot | Keep source color space and F16 precision; native Skia conversion only after protection, for requested ImageData/crop/export |
| F16 transform | Separate HMAC domain, edge-only deterministic mantissa LSB, unchanged sign/exponent/alpha; zero/subnormal channels and non-finite pixels left intact |
| Existing RGBA8 | Original transform unchanged; no 8-bit conversion of F16 storage, raw-pixel fallback or live-target mutation |
| Memory | Actual 4/8 bytes per pixel; checked dimensions and simultaneous raster/copy budget |

**Important limitation:** a half-float LSB change can disappear when converted to
RGBA8. This prototype therefore does **not** establish effective protection of
every lower-precision output. Do not enable it just because syntax/format checks
pass. The intended final policy still needs coherent, measured output effects and
color/HDR fidelity, not independent per-format noise or lossy quantization.

## Measured, not inferred

[Source-bound observations](observations.json): all four changed translation units
pass the pinned Chromium compiler's syntax checks. A separately linked executable
uses the actual modified transform and existing BoringSSL, not a Python model or
mock hash. It passes **12 controls**, including a known HMAC answer and all
**65,536 binary16 encodings**: sign/exponent/special values/alpha preservation and
idempotence. These are isolated native checks, **not browser compatibility**.

The five helper files can also be reconstructed and hash-checked in ordinary
pytest from public patches 0033/0034/0063, without the external Chromium checkout.
[Actual public-runner repeat](reproduction.json) passed all nine preparation,
syntax, compile, link and execution steps; guarded inputs did not change.

Repeat against the pinned Windows 001–070 source/build, with a fresh output on D:

```powershell
.\.venv\Scripts\python.exe native/drafts/environment/canvas-formats-next/verify_draft.py --source-root D:\Glint156Candidate\chromium\src --build-dir D:\Glint156Candidate\chromium\src\out\CamouFlowNative --work-dir D:\GlintManagerQA\fresh-canvas-format-draft
```

The runner patches **only copied files in its fresh output**, checks prepared hashes,
borrows existing generated modules/libraries, and writes compile/link logs and its
report there. It does not invoke Ninja, regenerate GN, change SDKs, build Chrome,
or alter source/output objects in the active tree. This is not a hermetic rebuild:
transitive generated modules and thin-library objects remain existing build inputs.

Next: native copy/HDR/crop/export fixtures, runtime 32-case differential checks,
workers and combined policies, and assessment of lower-precision effects. Batch
with queued orientation/visibility changes only after those source-level gates are
ready; keep the preserved runtime available for comparison and rollback.
