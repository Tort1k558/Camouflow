# Opaque GPU image-source normalization

**Unselected source repair. No repaired browser or executed new native cases.**

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

The canonical R10 checkout/runtime is unchanged. Next: compose/register the
complete repair recipe, execute all existing and new native groups, then repeat
the original fixtures and these alpha variants. The separate shared-worker
rendering mismatch, large-image/resource/cohort and manager/package gates remain.
