# GPU image-source consistency — unselected draft

**Native implementation draft, not a verified repair or admitted package.**

The [R9 runtime](../upstream-156-canvas-r9/runtime-observations.json) found that
protected WebGL readPixels and PNG agree, while drawImage and transferred
ImageBitmap expose raw pixels. This packet moves protection to the detached
source-image boundary for explicitly selected Canvas rendering v2.

| Boundary | Draft implementation |
| --- | --- |
| DOM / Offscreen drawImage sources | Resolve the source owner's GPU seed before obtaining the snapshot |
| WebGL ImageBitmap transfer | Validate before detachment; protect the detached image after the required buffer-clear operation |
| WebGPU ImageBitmap transfer | Protect detached images, including spec-defined fallback images |
| Legacy / ordinary 2D | Keep existing drawing and unselected transfer-constructor paths |
| Origin / orientation | Preserve the source image's origin-clean flag and orientation |
| Errors / memory | Reuse the bounded detached-copy adapter; never export raw on a required-copy failure |

[Patch](canvas-gpu-image-sources.patch), [source/type-check evidence](source-observations.json).
The six-file extension is based on the exact R9 source state, including an
explicit pinned upstream blob for GPUCanvasContext, which earlier Glint patches
did not modify. Source application/reversal restores every input.

Seven native cases are prepared for pointer identity in unselected mode, missing
images, the copy-budget boundary, both origin states, source immutability,
determinism, seed separation and translucent alpha. C++ parsing/type checking is
not execution of these cases, linking a browser or proving a runtime repair.
**Five translation units passed type checking:** DOM Canvas, OffscreenCanvas,
WebGL, WebGPU and the seven-case native fixture. Earlier checker/fixture failures
remain recorded; the corrected fixture uses bounded storage without disabling
compiler safety warnings.

## Before any registration or activation

- The following [frame-provenance extension](../canvas-frame-provenance/README.md)
  implements transferred-placeholder metadata and has source/type evidence only;
  the composed browser and ownership/lifecycle cases still need verification.
- Establish large-image compatibility beyond the existing detached-copy budget.
- Check taint/error precedence, alpha, sRGB/P3/F16, crop/scale, workers and retained
  ImageBitmap objects in the actual browser; add negative/failure paths.
- Register and execute all seven native cases, then repeat the R9 copy fixture
  and combined Canvas/GPU/Audio/restart checks without weakening exact equality.
- Calibrate the protected WebGPU gate independently of the old raw-texture
  expectation. Do not disable GPU protection to obtain a passing result.

The current R9 browser and manager admission remain unchanged. This draft does
not repair known-colour substitution, establish realistic device cohorts, or
claim external detector/CAPTCHA acceptance.
