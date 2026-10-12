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

## Complete test-only integration candidate

`test_integration.patch` contains the five algorithm/adapter/test source files
and adds `glint_canvas_readback_candidate` (test-only source set) plus
`glint_canvas_copy_unittests` to the existing content/browser GN file, following
the private-key native test target's layout. It does not add these helpers to
production Blink or the browser runtime. This avoids requiring another full
content_unittests compilation just to execute the ten raster-copy cases.

The complete patch passed applicability checks against the current 001-017 tree,
and its new target definitions passed pinned GN syntax/format validation.
Evidence: `D:/CamouFlowNative/canvas-copy-test-target-draft/proof-full.json`.
GN dependency graph generation, compilation, linkage and test execution remain
pending. The patch is **not registered or applied**. Do not change an active
checkout or run concurrent builds in the same output directory. Before using
the regular source-verifying build pipeline, promote the complete patch and its
checksum into the build lock; never bypass exact source verification to publish
a binary or declare a runtime capability.

After promotion in an idle checkout, the intended commands are:

```text
autoninja -C out/CamouFlowNative -j 1 glint_canvas_copy_unittests
out/CamouFlowNative/glint_canvas_copy_unittests.exe --gtest_filter=GlintCanvasCopyTest.* --single-process-tests --gtest_output=json:D:/CamouFlowNative/canvas-copy-native-tests.json
```

Use a fresh evidence path and inspect all ten named cases, not just an exit code.
Passing this target would establish adapter behavior, not Canvas API protection,
first-script policy delivery, cross-context compatibility or privacy admission.

## Blink snapshot-image adapter draft

`CreateProtectedCanvasImage` accepts the full StaticBitmapImage after the native
caller performs taint/layer/context checks. It uses pinned ImageDataBuffer's
PaintImage/readPixels route, creates the protected owned raster copy and wraps
it as an UnacceleratedStaticBitmapImage with the source orientation retained.
It is not a replacement for generic Snapshot/GetImage, drawImage or presentation.
The explicit additional-pixel budget accounts for both temporary full raster
copies; allocation, unsupported format/space and failed GPU/raster reads produce
typed failures, never fabricated pixels or an unprotected fallback image.

The algorithm, raster-copy adapter and image wrapper passed clang syntax checks
using actual Blink platform target flags:
`D:/CamouFlowNative/canvas-blink-implementation-flags-cpp-check/proof.json`.
The ten raster-copy test definitions were checked separately with test-appropriate
flags; production Blink global-constructor restrictions are not appropriate for
GoogleTest registrations. No warnings were disabled to compile implementations.

The image wrapper is **not linked, executed or called by Canvas APIs in the active browser**, and is
not part of the lightweight Skia-only test integration patch. Its runtime tests
require Blink platform dependencies and must cover GPU/lazy snapshots, failure
paths, orientation, snapshot lifetime and encoding. First-script trusted policy
bootstrap and the four DOM readback/export call sites remain unimplemented.

## Blink image tests and test-only registration

Eight `GlintCanvasImageTest` definitions cover missing snapshots, detached raster
ownership, source immutability, retained pixels after source release, the two-copy
memory budget, orientation metadata, PNG/canonical-raster equality, repeated
exports and separation of two public fixture seeds. Their translation unit passed
isolated syntax checks with the actual Blink platform unit-test flags. The
unbuilt unit-test PCH was omitted, not replaced with a browser PCH; no compiler
warnings were disabled. Evidence:
`D:/CamouFlowNative/canvas-blink-image-tests-no-pch-cpp-check/proof.json`.
These are test definitions, **not eight executed/passing runtime cases**.

`blink_test_integration.patch` is a self-contained alternative to the lightweight
Skia-only `test_integration.patch`. It puts the candidate, copy adapter, image
wrapper and both fixtures in Blink's `graphics/glint` test sources and registers
them in the existing `blink_platform_unittests_sources` target, using its normal
Blink test initialization. It explicitly adds the BoringSSL dependency and does
not make Blink depend on content/browser. There are 18 intended cases: ten raster
copy cases and eight image wrapper cases. Neither patch activates production
Canvas hooks. Choose one registration path for a given validation build; do not
treat duplicate copies of these candidate helpers as a production layout.

Pinned GN formatting and applicability checks passed without changing the active
checkout: `D:/CamouFlowNative/canvas-blink-test-registration-draft/proof.json`.
Graph generation, linkage and execution remain pending. Before applying this
alternative in an idle checkout, register its checksum in the build lock and
verify the exact sources. Intended execution after promotion:

```text
autoninja -C out/CamouFlowNative -j 1 blink_platform_unittests
out/CamouFlowNative/blink_platform_unittests.exe --gtest_filter=GlintCanvasCopyTest.*:GlintCanvasImageTest.* --single-process-tests --gtest_output=json:D:/CamouFlowNative/canvas-blink-native-tests.json
```

Inspect all 18 names and statuses in fresh output. Raster PNG equivalence does
not prove toBlob/OffscreenCanvas.convertToBlob behavior, GPU/lazy snapshot reads,
document/worker policy delivery or resistance to fingerprinting detectors.

## Experimental OffscreenCanvas export call site

`core_helpers_integration.patch` places the six candidate/adapter source files in
`core/html/canvas/glint`, registers them in the existing HTML source list and adds
an explicit dependency on Chromium's existing BoringSSL target. Helpers and the
export caller belong to the same Blink core component; this avoids making core
depend on a test-only content/browser target or requiring a new shared library.
GN formatting and applicability checks passed without active source changes:
`D:/CamouFlowNative/canvas-core-helper-registration-draft/proof.json`.
Do not combine this runtime registration with either alternative test-only
registration as though their duplicate helper definitions were one layout.

`offscreen_candidate_hook.patch` adds a native call from convertToBlob after the
existing detached/layer/taint/context/size checks and successful GetImage.
Only a WorkerGlobalScope with an owned bootstrap seed selects the experimental
edge-coherent image adapter. Current seed delivery is behind the explicit
developer-only `--glint-worker-canvas-bootstrap-test` startup draft; normal
profiles and window OffscreenCanvas exports have no seed and retain their
original behavior. The live image is not changed: only the owned export image
is handed to the existing CanvasAsyncBlobCreator. Unsupported formats, read or
allocation failures reject with NotReadableError instead of exporting an
unprotected fallback.

The additional-pixel budget is an explicit fixed **64 MiB test limit**, accounting
for both detached raster copies. It is not a total browser/encoder memory limit
or a finalized resource policy. It can reject large/high-precision canvases in
the experimental path. That compatibility needs measurement before admission.

The helper implementations and export caller passed isolated syntax checks with
actual Blink core flags:
`D:/CamouFlowNative/offscreen-canvas-core-module-cpp-check/proof.json`.
The final caller's ordered include layout has a separate syntax proof:
`D:/CamouFlowNative/offscreen-canvas-ordered-core-hook-cpp-check/proof.json`.
These are not linkage or Canvas API execution results. The complete worker/core/
hook patch stack is still unregistered and unapplied to the active checkout;
GN graph generation and real runtime compatibility tests remain pending.

This implements **one inactive experimental export hook**, not full Canvas
protection. getImageData/toDataURL/toBlob, document bootstrap and cross-API pixel
agreement remain incomplete; using only this hook can itself expose an
inconsistency with unprotected APIs. The algorithm's known-value detectability,
GPU/lazy snapshots, alpha/conversion/encoding behavior, errors and editor round
trips still require review. Do not advertise a protected Canvas capability or
detector/CAPTCHA success from this draft or its syntax checks.
