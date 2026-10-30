# Canvas extended-format compatibility

Status: **compiled in 001–072; fresh format gate passes 32/32 and combined gate 18/18**.
Comparison baseline: preserved Chromium 156 / patches 001–070, Windows.
[Retained result](canvas-formats70-observations.json),
[reproducer](first-script/canvas_formats.py).
[Current format result](canvas-formats72-observations.json),
[combined result](combined-math72-observations.json).

[The adaptive draft](canvas-formats-next/README.md) preserves source formats and
adds a binary16 transform with bounded changes. The single-LSB predecessor's
RGBA8 projection failure is retained. Its replacement passes 12 transform controls
including all 65,536 half encodings, plus 283 native Skia copy/projection controls.
Four source/read sRGB/P3 pairs retain distinct outputs for 32 seeds on the owned
fixture. The fresh independent PNG gate also passes eight cases / 12 carriers per
baseline and protected profile, including async snapshot and color metadata.
[Export evidence](canvas-export72-observations.json).
Six classic/module dedicated/shared/service workers pass all 96 Offscreen format
cases and match document output within each profile. [Worker evidence](worker-formats72-observations.json).
Worker PNG also passes 24/24 cases/carriers per baseline and protected profile,
including async capture, color metadata and document coherence, on preserved
001–072. [Worker PNG evidence](worker-export72-observations.json).
Nested/Blob restart and broad HDR quality remain open; this is not 001–073 admission.
The additional [finite F16 gate](canvas-hdr72-observations.json) passes four
HTML/Offscreen × sRGB/P3 contexts with alpha/nonopaque preservation, bounded
mantissa changes, sign/exponent preservation and crop/repeat/re-put controls.
It extends the existing conversion observer, not a claim of lossless HDR PNG.
The [initial unsuitable effect oracle](canvas-hdr72-initial-oracle-observations.json)
is retained: isolated opaque pixels supplied no eligible edges. The revised
fixture includes adjacent opaque HDR colors; the native policy was not changed.

## Cause of the retained 001–070 failure

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
proof of all these acceptance requirements. The native correction and orientation/
visibility work are now compiled together. Preserve the verified 001–070 runtime
for comparison; remaining worker/quality/lifecycle gates still block release.

## Reproduce the browser gates

Use a completed successful eight-profile desktop combined cohort from
`scripts/verify_native_combined_math.py`, its exact preserved `chrome.exe` and
driver stage. Run sequentially: these commands reopen existing owned QA profiles.
Use a fresh absolute D: output directory for each run.

```powershell
$python = '.\.venv\Scripts\python.exe'
$browser = 'D:\Glint156Candidate\preserved-runtime72-20261030-v1\runtime\chrome.exe'
$cohort = 'D:\GlintManagerQA\combined-math72-20261030-v1'
$stage = 'D:\GlintManagerQA\staged-python-js70-20261030-v1'
& $python native/drafts/environment/first-script/canvas_formats.py --executable $browser --cohort-directory $cohort --driver-stage $stage --candidate upstream-156 --work-dir D:\GlintManagerQA\canvas-formats72-recheck
& $python native/drafts/environment/first-script/canvas_export_runtime.py --executable $browser --cohort-directory $cohort --driver-stage $stage --candidate upstream-156 --work-dir D:\GlintManagerQA\canvas-export72-recheck
& $python native/drafts/environment/first-script/worker_formats_runtime.py --executable $browser --cohort-directory $cohort --driver-stage $stage --candidate upstream-156 --work-dir D:\GlintManagerQA\worker-formats72-recheck
& $python native/drafts/environment/first-script/worker_exports_runtime.py --executable $browser --cohort-directory $cohort --driver-stage $stage --candidate upstream-156 --work-dir D:\GlintManagerQA\worker-export72-recheck
& $python native/drafts/environment/first-script/canvas_hdr_runtime.py --executable $browser --cohort-directory $cohort --driver-stage $stage --candidate upstream-156 --work-dir D:\GlintManagerQA\canvas-hdr72-recheck
```

The export gate compares decoded PNG bytes with pre-mutation pixels and validates
color metadata. It does not decode through a second protected Canvas. Reports
retain source/receipt hashes, native API errors and postguards; a failed gate is
not automatically retried or treated as protection success.

The selected source manifest, browser receipt and cohort core must match. When
the checkout has already advanced to 001–073, the 001–072 examples require a
frozen 001–072 source layout with the exact public diagnostic files overlaid;
do not rewrite the receipt or relax its checks to reuse an older binary.
