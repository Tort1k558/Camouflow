# Canvas extended-format compatibility

Status: **measured browser failure; isolated native extension drafted, not compiled into the browser**.
Baseline: preserved Chromium 156 / patches 001–070, Windows.
[Retained result](canvas-formats70-observations.json),
[reproducer](first-script/canvas_formats.py).

[The adaptive draft](canvas-formats-next/README.md) preserves source formats and
adds a binary16 transform with bounded changes. The single-LSB predecessor's
RGBA8 projection failure is retained. Its replacement passes 12 transform controls
including all 65,536 half encodings, plus 283 native Skia copy/projection controls.
Four source/read sRGB/P3 pairs retain distinct outputs for 32 seeds on the owned
fixture. Browser export/worker/runtime and broad HDR quality acceptance remain open.

## Cause

`0033-native-surface-readback.patch` restricts `CreateProtectedCanvasCopy` and
`CreateProtectedCanvasImage` to 8-bit sRGB. The `getImageData` integration also
rejects non-sRGB/non-RGBA8 output before Skia can convert the protected snapshot.
Consequently the native baseline supports all 32 tested combinations, but the
protected path supports only default HTML/Offscreen sRGB/RGBA8 (2/32).
`NotReadableError` is fail-closed, not successful compatibility or a raw-pixel leak.

## Required implementation

1. Protect a detached full snapshot in its source color space and precision, then
   use native color-managed conversions for output, cropping and encoding. Do not
   independently randomize each requested output format.
2. Keep existing sRGB/RGBA8 outputs bit-identical for the same policy/key. Preserve
   profile/partition derivation, deterministic restart and immutable source pixels.
3. Support native Display-P3 and Float16 without an 8-bit round trip. Preserve
   alpha, sub-8-bit detail, negative/above-one HDR values and native metadata.
   Define handling of signed zero, subnormals and non-finite encodings explicitly;
   do not silently clamp or turn invalid values into valid colors.
4. Keep native origin-clean, argument, zero-size and access checks. Missing policy,
   allocation or unsupported-format errors must never return raw pixels. Disabling
   APIs, zero-filling and lossy fallback are not fixes.
5. Account for actual bytes per pixel, row stride, checked dimensions and both
   simultaneous detached buffers before allocation. Do not change the live target.

## Acceptance packet

| Gate | Required proof |
| --- | --- |
| Native copy/transform | Known answers, same-key repeat, different keys, immutable source, padded rows, alpha and precision preservation, non-finite policy, overflow/memory limits |
| Runtime formats | All 32 baseline-supported combinations remain supported with correct arrays, metadata and finite results on the finite fixture |
| Coherence | Repeated reads, crops, export, HTML/Offscreen, documents/iframe/workers and cross-format color-managed conversion agree |
| Identity | Both derivation modes, profile isolation, initial/restart and concurrent profiles |
| Compatibility | Taint/errors unchanged; normal editing/HDR fixtures preserve precision and color; no unprotected alternate readback |
| Regression | Existing sRGB/RGBA8 captures and combined Canvas/WebGL/Audio, Mobile Web and lifecycle checks repeated on the new binary |

The current 32-case collector is an initial format/shape/effect diagnostic, **not**
proof of all these acceptance requirements. Batch the native correction with the
queued orientation/visibility work; preserve the verified 001–070 runtime for
comparison. No release/admission until the linked packet is compiled and checked.
