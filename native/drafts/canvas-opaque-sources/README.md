# Opaque GPU image-source normalization

**Selected R11 copy/frame repair verified; broad browser/resource admission open.**

[R11 measurements](../upstream-156-image-r11/README.md) now pass all five new native
cases, 32 direct copy variants, 40 worker-frame copies and the original combined
copy fixtures. Six full-size 4K copies also pass, but their resource measurement
remains incomplete. The source-preparation records below are historical: their
unselected/unexecuted fields have not been rewritten as later runtime evidence.

The [R10 diagnostic matrix](runtime-observations.json) narrows the original errors:

| Fixture | R10 result |
| --- | --- |
| WebGL1/2, alpha on/off, drawImage / PNG / createImageBitmap | 24 exact copies |
| WebGL1/2, alpha on, transferToImageBitmap | Four exact copies |
| WebGL1/2, alpha off, transferToImageBitmap | Four creation failures |
| Transferred worker frames, alpha on | 20 exact copies across five paths/backings |
| Transferred worker frames, alpha off | Both GPU variants remain unreadable |

Pinned Chromium uses RGBX/BGRX shared images for opaque WebGL surfaces. Its Skia
format adapter exposes both as `kRGB_888x_SkColorType`; Glint's detached-source
format filter rejected that type. The [two-file patch](canvas-opaque-sources.patch)
accepts it for existing RGBA normalization before protection. The owned mutable
raster still requires normalized RGBA8/F16: no X-byte masking, raw fallback,
changed pixel algorithm, increased budget or weakened ownership guard.

[Source evidence](source-observations.json): apply/reverse passed, both final
files matched, and three translation units type-checked with original Chromium
flags. Five native cases are prepared for exact RGBA-oracle agreement, opaque
alpha/origin/orientation/colour space, the same budget boundary, and rejection
of unnormalized owned rasters and unsupported formats.

[Complete R11 preparation](full-composition-observations.json) replays all 136
patches forward and backward, matches 406 final files and restores 273 upstream
inputs. That preparation predates the later R11 registration and measured build.

[Focused module continuity](module-continuity-observations.json) passed 24 paired
classic/module shared-worker reads across three launches with the gamma preset.
It did not reproduce the earlier combined-sequence mismatch; that failure is
still open and has not been fixed or waived.

Preparation left the canonical R10 checkout unchanged; its independent runtime
is still retained. The active source/runtime is now R11. The separate original
shared-worker mismatch, broader large-image/resource/cohort and manager/package
gates remain open despite the selected successful checks.
