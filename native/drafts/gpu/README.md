# GPU metadata minimization candidate

## Current source-bound diagnostics

The selected Chromium 156 candidate requires its own completed build and runtime
checks. The historical 001-027/034 notes below are not its current build status.

```powershell
.venv\Scripts\python.exe -m scripts.verify_native_gpu `
  --candidate upstream-156 --workspace D:\Glint156Candidate `
  --executable D:\Glint156Candidate\chromium\src\out\CamouFlowNative\chrome.exe `
  --work-dir D:\GlintQA\gpu67-profiles --report D:\GlintQA\gpu67.json `
  --minimized --require-webgpu
```

Use a new report path. Candidate mode holds the native workspace lock and rejects
a live builder before opening profiles. It requires the complete selected build
receipt, exact metadata patch and real CDP version/revision in every phase.
Runtime, receipt and source hashes are checked again after execution, including
failed runs. Failed profiles are retained for diagnosis.

The off/off-restart/on/on-restart phases share one measured persistent profile.
An isolated discovery launch measures driver feature defaults; A/B changes only
`GlintGpuMetadataMinimization`, preserving unrelated feature settings and verifying
the effective command line. `--enable-automation` is explicit in every launch so
CDP can report those arguments. **This is not an automation-concealment test.**

`--require-webgpu` requires working WebGPU in all eight document/worker contexts;
unavailable adapters fail rather than count as successful coverage. There is no
software/unsafe fallback. Coverage includes WGSL compute, buffer copies,
texture mip/layer copies and shader-rendered reads, with untouched pack padding.

The [source-bound stock156 calibration](stock156-runtime-observations.json)
passed both off/restart phases with 8/8 coverage for each API. This proves the
diagnostic, not Glint's policy. Metadata
minimization is not complete GPU protection, a hardware identity cohort or release
admission. See the [per-build matrix](../../../docs/GLINT_TEST_MATRIX.md) for
actual Glint results.

## Historical implementation notes

The canonical candidates below are now included in registered patch **0034**,
as part of the 001-034 source batch. Chrome is compiling on Windows; the last
verified browser remains 001-027. No new GPU protection is runtime-admitted.
Earlier preparation/replay notes below describe their pre-promotion stages.

The disabled-by-default `GlintGpuMetadataMinimization` Blink feature proposes:

| API | Candidate change | Preserved |
| --- | --- | --- |
| WebGL / WebGL2 | Do not offer WEBGL_debug_renderer_info | Actual backend, other extensions, limits, shaders and pixels |
| WebGL / WebGL2 debug shaders | Follow-up removes WEBGL_debug_shaders and translated driver shader text | Actual GLSL compilation, linking and drawing |
| WebGPU adapter info | Empty identification strings; omit developer-specific adapter details | Actual subgroup sizes, fallback status, device features, limits and rendering |

No different video card or operating system is fabricated. A later experimental
binary may opt in with `--enable-features=GlintGpuMetadataMinimization`; renderer
and worker propagation must be verified, not assumed. Feature-off behavior should
remain upstream behavior. A privacy setting can itself be observable.

Four-file source replay passed in an isolated overlay, with active files unchanged:
`D:/CamouFlowNative/gpu-metadata-candidate-overlay-v2/proof.json`.
The revised path preserves real experimental subgroup matrix configurations too;
it does not return before the upstream capability population loop.
This is not C++ compilation or runtime evidence.

## Diagnostic runner

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_gpu.py `
  --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe `
  --work-dir D:\CamouFlowNative\gpu-checks --report D:\CamouFlowNative\gpu-new.json
```

The unprotected 001-027 binary passed two feature-off/restart phases: WebGL1,
WebGL2 and WebGPU were available in all eight document/worker contexts. Actual
clear/readPixels, buffer round-trip and WGSL compute operations passed, alongside
metadata/limit consistency. Evidence: `gpu-001-027-baseline-v3.json` on D.
This measures existing GPU behavior, not this candidate's privacy. Add
`--minimized` only for a binary actually containing the candidate; ignored flags
with exposed metadata fail the checks. Reports always retain
`privacy_admitted: false`; unavailable APIs are excluded from coverage.

Required tests: WebGL1/2 getSupportedExtensions/getExtension agreement, upstream
INVALID_ENUM behavior for unavailable debug parameters, document/iframe/worker
coverage, repeated adapter.info and device.adapterInfo observations, feature-off
regression, real device creation, rendering/compute and unchanged limits/features.
Unavailable WebGPU must be reported as unavailable, not a passing masking result.
GPU readback protection, extension/limit reduction and profile-policy admission
are separate unfinished work; metadata minimization is not complete GPU privacy.

## Shader and pixel-pack follow-up

`gpu_shader_metadata_minimization.patch` uses the same disabled-by-default
metadata feature at the extension support boundary. Enumeration and
`getExtension` therefore agree; it does not substitute a fake shader, vendor,
GPU capability or readback result. This is unregistered/uncompiled source.
The browser architecture reuses the existing extension registry and feature,
not JavaScript wrappers or a second preference system.

The expanded diagnostic compiles real GLSL1/GLSL3 vertex/fragment shaders,
links a program and renders a 4×4 nonuniform scene in WebGL1 and WebGL2. It
requires exact repeated full reads and an interior crop. WebGL2 additionally
reads through a pixel-pack buffer at a nonzero offset and through explicit
row-length/skip-row/skip-pixel layout. Prefix, suffix and row padding must remain
untouched; unavailable/incorrect methods cannot count as successful coverage.
Shader debug exposure is checked against the extension list. Metadata mode may
remove only the two debug extensions, while shader execution and other
extensions/limits stay unchanged.

The last linked **001–027, unprotected** Windows browser passed both feature-off
and restart phases in all eight document/worker contexts, with both WebGL
versions and WebGPU operations available:
`gpu-shader-pbo-001-027-baseline-v5.json` on D. This proves the fixture and current
upstream behavior, not execution of either metadata candidate or GPU masking.
Shaders/buffers/devices and owned profiles are cleaned up; core and probe-input
hashes stayed unchanged during the run.

Brave's [August 2026 engineering report](https://brave.com/privacy-updates/38-webgl-webgpu-fingerprinting-protections/)
distinguishes adapter descriptors, debug identifiers and extension-list entropy.
Our choices are not a copy of its session-based policy: Glint keeps profile
identity stable across restarts and currently preserves real non-debug
capabilities. Extension randomization and arbitrary GPU-buffer noise are not
admitted. In particular, WebGPU mapped compute/storage data must not be treated
as image pixels; the unchanged integer buffer/compute checks remain mandatory.

The combined 27-candidate source stack replay passed across 115 paths after the
registered renderer mock repair, with active sources/GN/receipt/core unchanged:
`gpu-shader-child-mock-public-replay-v2.json`. This is source composition, not
execution of the GPU metadata feature.

## RGBA8 pack-copy foundation

`rgba8_pack_copy_integration.patch` prepares an allocation-free native helper
for scattering an **already protected** tightly packed RGBA8 read rectangle
into a WebGL/PBO destination layout. It reuses Chromium's
`WebGLImageConversion::ComputeImageSizeInBytes` rather than duplicating pack
alignment, row-length and skip arithmetic. Checked sizes, exact source length,
capacity and disjoint storage are verified before any write. Only requested
pixel spans are copied; prefix/suffix, padding and skipped rows remain intact.
Zero-size reads are no-ops. This does not mask pixels, read a GPU, change GL
state, process arbitrary mapped buffers or activate a browser hook.

Fourteen C++ fixtures are prepared, **not compiled or executed**. They cover
offsets, skips, alignment-eight padding, exact last-row capacity, overlapping
layout arithmetic, source immutability, aliased storage, insufficient capacity,
invalid fields, overflows and empty reads. Layout arithmetic is not proof of
driver acceptance or GL error semantics; those belong to the caller's original
validation/read path and actual browser tests.

The next required integration is a bounded full-frame canonical readback,
surface-owned WebGL seed, crop/layout handling and row-wise PBO upload. It must
preserve framebuffer/pack bindings and all upstream failures, avoid mutation of
the live render target, and reconcile exports with the same canonical pixels.
Float/integer formats, custom framebuffers, context loss and Canvas colour-space
conversion remain explicit unfinished work, not raw fallbacks or admission.

Ordered replay of all 28 public candidates passed across 119 paths with active
sources, GN, receipt and linked core unchanged:
`rgba8-pack-copy-public-replay-v1.json` on D. Four aggregate candidate patches
independently reproduce that exact source (`surface-promotion-v7/proof.json`).
Neither run invokes a compiler or activates the helper in the current build.

## Default framebuffer readback candidate

`webgl_default_readback_candidate.patch` connects the pack-copy foundation to
native WebGL1/2 `readPixels`, including WebGL2 pixel-pack buffers. It remains
**disabled by default, unregistered and uncompiled**. No active build input is
modified. This is a partial research implementation, not GPU privacy admission.

| Path | Candidate behavior | Runtime proof |
| --- | --- | --- |
| ArrayBuffer / SharedArrayBuffer | Protect detached full frame, crop privately, then scatter into validated destination | Pending |
| Pixel-pack buffer | Restore original pack/buffer state, upload only requested pixel rows | Pending |
| HTML / Offscreen exports | Select the same owned WebGL seed instead of the Canvas domain | Pending |
| Live render target / WebGPU compute buffers | Unchanged | Must be rechecked |

The implementation requires the browser-owned WebGL surface seed. Missing or
invalid required policy rejects; it never publishes raw intermediate pixels.
Two detached RGBA8 allocations share the existing 64 MiB budget. Original API
validation executes before the hook; zero-size reads keep the upstream path.
Pack state is restored with scope cleanup, including failure paths. Existing
application GL errors are not drained. The core transform is accessed through
an exported bridge so component builds do not depend on a private core symbol.

**This patch alone:** only the default RGBA8/RGB8 sRGB framebuffer and
RGBA/UNSIGNED_BYTE output are implemented. Custom framebuffers, float/integer
formats, overlapping pack rows and wide-gamut/HDR currently reject in this
experimental mode; this intentionally prevents a raw fallback but is not API
compatibility. Cross-export orientation, premultiplication, driver read failure,
out-of-bounds reads, context loss, binding restoration and performance still
require actual browser tests. Full GPU support remains unfinished.

All 29 public candidates replayed successfully across 124 source paths:
`webgl-readback-public-replay-v1.json`. Four aggregate patches independently
reproduced that exact source (`surface-promotion-v8/proof.json`). Both private
reports are on D; active source, GN arguments, build receipt and linked runtime
core were unchanged. These checks prove source composition only.

### Prepared protected readback gate

`scripts/verify_native_gpu_readback.py` requires exact registered worker,
document, surface-readback and GPU patch hashes plus every linked core-file hash
**before** creating profiles or launching a browser. The old 001-027 runtime
was rejected (`gpu-readback-old-refusal-v1.json`), with no owned directory created.

The gate uses two independent owned profiles, initial/restart phases and all
eight document/worker contexts. It checks same-partition agreement, cross-origin
and cross-profile separation, bounded RGB low-bit changes with unchanged alpha,
full/repeat/crop/PBO/padding consistency, pack/framebuffer state and native PNG
export. PNG dimensions are bounded before decoding through the existing Qt
image library outside the browser; decoding through a protected 2D canvas
would incorrectly apply a second, different surface seed. WebGPU integer
buffer/compute behavior and real GPU capabilities remain independently checked.

The **old, unprotected** binary passed the PNG/pack-state fixture in both
initial/restart phases (`gpu-png-pack-state-001-027-baseline-v4.json`). The first
run exposed ANGLE's shorter translated debug shader text after cache reuse;
restart comparison now excludes only that length while separately validating
debug-extension presence/error behavior. It still compares pixels, exports,
state, metadata and capabilities. This is fixture evidence, **not execution
of the new WebGL patch**. Error/context-loss, custom framebuffer and other
formats remain separate unfinished gates.

### Error and context-loss fixtures

The readback gate additionally checks zero-sized reads, negative dimensions,
short destinations, mismatched typed arrays, invalid format, incomplete
framebuffers, preservation of a pending error during a valid read, WebGL2's
missing pixel-pack buffer and implicit row-length/skip constraints. Empty and
failed reads must leave sentinel destinations untouched. A deliberately lost
context must preserve the destination and expose `CONTEXT_LOST_WEBGL` once.
All fixtures ran successfully in both baseline/restart phases across eight
contexts on the old unprotected binary (`gpu-png-pack-state-001-027-baseline-v4.json`).

The [WebGL1 read operation contract](https://registry.khronos.org/webgl/specs/latest/1.0/#5.14.12)
and [WebGL2 pixel-store constraints](https://registry.khronos.org/webgl/specs/latest/2.0/#PIXEL_STORE_PARAM_CONSTRAINTS)
are compatibility requirements, not optional privacy features. Review exposed
two source-candidate mistakes: a missing-attachment framebuffer must retain its
upstream framebuffer error rather than receive a generic unsupported-format
error; row-length zero still means the requested width, so positive pixel skips
cannot create overlapping rows. The candidate now handles both before any
destination write. These C++ changes remain uncompiled.

The corrected 29-candidate stack passed source replay across 124 paths:
`webgl-readback-public-replay-v2.json`. Earlier replay/promotion evidence predates
this correction and must not be used as the final promotion source. The refreshed
four-patch aggregate replay independently reproduced those 124 paths
(`surface-promotion-v9/proof.json`); it is the current prepared source batch,
still not registered or compiled.

## Selected renderbuffer framebuffer candidate

`renderbuffer_readback_candidate.patch` extends the same bounded native path to
single-sample RGB8/RGBA8 renderbuffer attachments. The selected read attachment,
not necessarily attachment zero, supplies its native width, height and internal
format. The canonical full-frame transform must use that extent even when the
viewport or canvas dimensions differ. Existing framebuffer, read-buffer and
pack bindings remain unchanged. Multisampled attachments require an explicit
upstream resolve and retain an operation error instead of returning raw data.

This follow-up is **unregistered and uncompiled**; no custom-framebuffer browser
result is claimed. Texture-backed framebuffers, smaller packed formats,
floating-point/integer formats and HDR remain unfinished. In particular,
Blink's texture objects do not own authoritative per-level dimensions. Do not
substitute viewport dimensions or add incomplete JavaScript-visible metadata;
texture support needs a service-owned attachment description compatible with
both validating and passthrough GPU decoders.

With the corrected final-wire-origin baseline and this renderbuffer follow-up,
all 30 public candidates passed ordered replay across 125 paths
(`wire-origin-renderbuffer-public-replay-v1.json`). Earlier aggregate proofs
predate the origin fix and renderbuffer extension and cannot authorize this
promotion. Actual renderer/worker/browser execution remains pending.
The refreshed four aggregate patches reproduce that exact 125-path source
(`surface-promotion-v10/proof.json`). The corrected NavigationSimulator binary
passed all 12 cases (`document-navigation-001-030-j4-v3.json`); this prerequisite
is satisfied. The four aggregates are registered/applied as 0031-0034; compilation
and the prepared protected-browser gates remain unfinished.

## Prepared selected-framebuffer runtime gate

The owned GPU readback runner now measures **WebGL2 renderbuffer** frames in
every document/worker context alongside default-framebuffer reads and PNG
exports. This does not claim WebGL1 custom-framebuffer coverage.

| Check | Fixture |
| --- | --- |
| Selected read buffer | Gradient in attachment 1; distinct unchanged uniform colour in attachment 0 |
| Extent versus viewport | 8×8 attachment with the original 4×4 viewport |
| Resize | Same renderbuffer objects reallocated to 6×5 and read again |
| Readback consistency | Full/repeat/crop, offset PBO, row-length/skip layout and untouched padding |
| State preservation | Read/draw framebuffer, selected attachment and pack-buffer bindings |
| Multisample | Native operation error with an untouched sentinel destination |
| Isolation | Stable restart; same-partition agreement; separate origins and profiles |

Protected gradient checks require a single RGB choice per quantized colour,
including outside the viewport and across resize. A runner that merely masks
a viewport-sized prefix cannot pass by returning mutually consistent crops and
PBO copies. Alpha and upper colour bits remain exact; uniform fills remain
unchanged. This is a bounded compatibility gate for this candidate algorithm,
not a fingerprint-resistance or full-GPU admission.

The old **unprotected 001-027** binary passed the expanded fixture in all eight
contexts during both initial/restart phases:
`gpu-png-pack-state-001-027-baseline-v7.json` on D. Core and probe hashes remained
unchanged and owned profiles were cleaned up. Protected checks still wait for
the new binary. Fixture operations follow the
[WebGL2 multiple-render-target and readback contract](https://registry.khronos.org/webgl/specs/latest/2.0/#3.7.11).
