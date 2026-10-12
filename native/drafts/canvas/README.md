# Canvas readback algorithm candidate

Inactive research prototype, not an approved privacy algorithm or Chromium
patch. No hooks, renderer policy consumer or advertised protection are enabled.

**Rejected for activation in its current coordinate-pattern form.** A native
diagnostic of a uniform white 1024x1024 canvas produced eight distinct RGB
colours and changed 917,930 of 1,048,576 opaque pixels. The channel delta is only
one, but the new spatial pattern is an easily observable inconsistency with a
uniform fill. Repeat/crop/idempotence success does not resolve this problem.
Evidence: `D:/CamouFlowNative/canvas-candidate-flat-colour-diagnostic/tests.log`
and `proof.json` (`privacy_admission: false`). The baseline candidate remains
public for comparison, not as a patch to apply to production.

The candidate transforms only detached unpremultiplied RGBA8/sRGB copies.
It canonically selects the RGB least-significant bits of fully opaque pixels
from an HMAC-SHA256 stream keyed by a trusted partition/surface seed. Absolute
coordinates determine blocks (85 pixels, three bits each); crop origins do not
reset the stream. This makes repeated transformation idempotent and limits each
changed channel to a one-level difference. Nonopaque pixels and out-of-canvas
padding remain untouched. No profile root key is accepted or transported here.

The domain explicitly says `candidate`; it is not a released version-1 contract.
HMAC is already provided by Chromium's BoringSSL, not a new dependency.
Invalid layouts/coordinate overflow fail. A crypto failure may leave the detached
copy partially transformed: callers must discard it, never fall back to export.

## Verification so far

The translation unit passed isolated clang syntax checks with Chromium's browser
flags. A separate Windows executable linked the candidate against the existing
pinned BoringSSL libraries and upstream libc++ abort object, entirely outside
the active Chromium output tree. It executed 12 checks successfully:

- independent Python HMAC vector;
- idempotence;
- full/cropped reads and their agreement across 85-pixel block boundaries;
- channel delta bound and unchanged alpha;
- transparent/partial-alpha pixels and out-of-bounds padding;
- rejected invalid layout/coordinate overflow without changing the buffer;
- two public fixture seeds produce distinct results;
- a one-megapixel transform (13 ms in one local run, not a benchmark guarantee).

Evidence: `D:/CamouFlowNative/canvas-candidate-native-tests-libcpp-abort/proof.json`
and `tests.log`. These are algorithm-only results, not BrowserContext key
isolation, Blink API compatibility, export equivalence or privacy admission.

Important unresolved tradeoffs:

- Flat opaque colors gain a detectable deterministic low-bit pattern. Do not
  call this undetectable, or approve it from repeat/crop tests alone. The native
  diagnostic above confirmed this issue, rather than just assuming it.
- Editing/color-picker values can differ by one; quantify compatibility and
  detectability against more selective and alternative algorithms before adoption.
- Partial alpha, float16/HDR and other color spaces are not protected. Silently
  accepting them as a protected profile would violate capability admission.
- Export encoding must use the same canonical pixels without modifying drawImage,
  ImageBitmap, presentation or the live canvas backing store.
- Trusted policy must exist before the first synchronous read, in document and
  worker contexts. Current IPC drafts do not establish this startup guarantee.

Next gates: native vectors/idempotence/crop/padding/alpha/performance, then API
compatibility and adversarial detection tests. No getImageData/toDataURL/toBlob/
OffscreenCanvas hook may activate this candidate before those gates are reviewed.

## Content-coherent alternative

`TransformContentCoherentReadback` is an explicitly selected second candidate,
not a fallback. It derives three canonical output bits from HMAC over RGB values
with the low bit removed. Equal input colours remain equal, and repeated
transformation remains idempotent. A fixed 256-entry direct-mapped cache bounds
memory; a colliding key is recomputed rather than incorrectly sharing a value.
Layout validation, alpha/padding handling and output bounds are shared with the
coordinate comparison; the original coordinate HMAC vector remains unchanged.

The current sources passed Chromium-flag clang syntax checks and **27 native
comparison checks**, including an independent Python oracle for a 4096-pixel
diverse-colour fixture that exercises cache collisions. A local uniform 1-Mp run
took 5 ms. Evidence:
`D:/CamouFlowNative/canvas-candidate-palette-comparison-oracle/proof.json` and
`tests.log`; syntax proof: `canvas-palette-candidate-cpp-check/proof.json`.

The second candidate preserves one colour in the white-fill diagnostic, but
changes that known white value in all 1,048,576 pixels. It therefore removes the
spatial pattern, **not known-value detectability**. Neither candidate is admitted
or hooked into Blink. A further comparison must preserve actual uniform fill
values, quantify gradients/antialiasing/editor round trips, and use whole-canvas
provenance rather than classify a crop independently and break crop/full equality.

## Edge-coherent full-canvas alternative

`TransformEdgeCoherentCanvas` explicitly accepts an entire detached canvas.
Only fully opaque pixels adjacent to a different quantized opaque colour are
eligible. Classification uses the upper seven RGB bits, so changing a low bit
does not change eligibility on a second pass. Uniform fill values and flat
interiors stay exact, nonopaque pixels remain unchanged, and transformed edge
colours use a separate HMAC domain. The same bounded palette cache is reused.

Current sources passed Chromium-flag syntax checks and a **37-check native
comparison** across all three candidates. The edge variant matched an independent
Python neighbour/HMAC oracle, retained 256 known uniform fills exactly, preserved
flat interior/nonopaque rows, was idempotent and separated fixture seeds. A white
1-Mp run retained every byte and took 11 ms in one local run. Evidence:
`D:/CamouFlowNative/canvas-candidate-edge-comparison-oracle/proof.json`, `tests.log`
and `canvas-edge-candidate-cpp-check/proof.json`.

Partial API reads must be cropped **after** transformation of the full canonical
canvas, not passed to this helper as if they were a complete canvas. Actual
getImageData/export integration, colour conversion, memory limits, gradients,
antialiasing, drawImage/putImageData and editor compatibility are unverified.
Known nonuniform geometry can still expose altered edge values. This candidate
is not admitted and does not make a browser or a Canvas readback undetectable.

## Full raster-copy adapter draft

`CreateProtectedCanvasCopy` takes a full SkPixmap after native access checks and
returns an owned immutable SkBitmap. RGBA/BGRA 8-bit sRGB sources are converted
explicitly to RGBA/unpremultiplied/sRGB before the edge candidate runs; opaque
metadata yields canonical alpha 255. It never writes the source backing store.
The caller supplies an explicit additional-copy memory limit. Invalid layout,
unsupported format/space, allocation/read/transform failures return typed errors,
not an original unprotected image or a replacement browser identity.

Crop reads and async encoders must retain this same full protected result. Float16,
HDR, untagged and non-sRGB sources remain unsupported. GPU snapshots still need
the pinned Blink snapshot-to-raster path; this adapter does not invent one.

The algorithm, adapter and ten Skia test definitions passed Chromium-flag clang
syntax checks: `D:/CamouFlowNative/canvas-copy-adapter-opaque-alpha-cpp-check/proof.json`.
The tests specify source ownership/immutability, exact fills, BGRA conversion,
premultiplied baseline conversion, opaque alpha, memory limit, unsupported space/
format, absent pixels and crop/full equality. They are **not linked or executed**,
and have not been added to the active Chromium target. These checks do not prove
DOM exception order, HTML/OffscreenCanvas encoding, GPU handling or runtime policy.
