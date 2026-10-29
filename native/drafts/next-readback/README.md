# WebGL readback: bounded halo candidate

**Registered as 0046/0047; limited browser checks passed on 001-047 and native fixtures passed on 001-048.**
This paired repair follows registered 001–045. It changes private readback allocation, not the fingerprint
algorithm, GPU identity, live framebuffer or JavaScript API.

## Changes

| Request | Private storage | Protection |
| :-- | :-- | :-- |
| Exact full framebuffer | One rectangle allocation | Existing edge-colour transform in place |
| Partial in-bounds read | Original rectangle + clipped one-pixel halo | Same transform, then guarded row overlay |
| Entirely outside framebuffer | Original rectangle only | Preserve the driver result; no in-bounds pixels exist |

The halo is valid **only** for the existing quantized-colour, four-neighbour
algorithm. Coordinate-dependent or global transforms cannot reuse this planner.
The CPU publication path retains patch 0037's explicit `base::expected`
`has_value()` check. All seven native clipped-copy fixture assertions use that
same typed result; the six clipped-publication cases have now executed successfully.
Attachment dimensions remain native; a viewport is not an attachment extent.
Checked arithmetic, a combined memory budget and pre-write alias/plan validation
bound the extra storage. CPU and PBO callers retain their existing pack/state
handling, validation and required-policy rejection.

The second patch fixes **publication of clipped reads**: protected CPU/PBO writes
cover only the actual in-bounds intersection. An outside read must not overwrite
the caller's existing destination bytes. Full request buffer-size validation is
retained even when the intersection is small or empty.

The owned feature-off 001–027 browser confirmed unchanged sentinel bytes for
negative, partially clipped, entirely outside and zero-sized reads, on both CPU
and PBO paths in eight contexts before/after restart. The unrepaired 0034
implementation copied its whole zero-initialized private rectangle back,
causing the clipping-compatibility issue observed on 001-045;
the correction is registered as 0046/0047. The later 001-047 protected browser
passed all six owned baseline/profile/restart phases, including the boundary
cases that failed on 001-045. This is limited owned-runtime evidence, not broad
GPU-driver compatibility or external acceptance.

The linked 001-045 browser now confirms this failure with protection enabled:
`gpu-readback-001-045-v1.json` on D. Its feature-off initial/restart phases
passed, but protected profile-A reads replaced out-of-bounds CPU sentinel bytes
with zero in all eight document/worker contexts, on initial and resized
attachments. GL error state remained clear and bindings remained intact.
The boundary contract was not relaxed. The later 001-047 optimized/browser
checks and 001-048 native cases passed; the old failed observations remain.

For a 1×1 crop inside a 4096×4096 attachment, planned storage is 40 bytes
(4-byte rectangle + 36-byte halo), rather than a whole-frame copy. An exact
4096×4096 RGBA8 read fits the existing 64 MiB budget in one private allocation.
These are allocation calculations, **not measured performance improvements**.

## Evidence and pending checks

Promotion replay passed across the complete 130-path registered chain:
`clipped-readback-replay-001-047-v2.json` on D. The existing 001-045 browser,
receipt and GN arguments remained unchanged. Draft composition tools reverse
the exact promoted pair only in their owned overlays before replaying future
candidates; partial promotion or different canonical bytes reject.
The native `--target gpu-readback` gate requires 31 exact cases: 14 pack-copy,
11 region-planner and 6 clipped-publication cases. All 31 passed on 001-048:
`gpu-readback-units-001-048-v2.json` and its raw `-tests.json` on D, with zero
failed/disabled/error cases and unchanged 001-047 browser core, source, GN and
receipt. The cached j4 test-target build took 1h30m44.64s; tests took 176 ms.

Fixture-only follow-up 0048 corrects typed `base::expected` assertions in the
14 pack-copy and 11 region tests, retaining their names, rejection/error checks
and destination-preservation assertions. All three fixture translation units
passed actual generated-target C++ checks without changing the verified 001-047
browser core: `readback-fixture-cpp-001-048-v2/proof.json` on D. The complete
001-048 source chain replay passed across 130 paths; fixture execution has now
passed. Future overlays reverse this follow-up before canonical comparison
and reapply it afterwards, checking its exact registered hash and two-file scope.

The first full build exposed a typed-result error in the Blink halo call.
The unverified 0046 patch and its canonical candidate now explicitly check
`base::expected::has_value()`. The previously failed implementation compiled
to an isolated optimized object using the actual failed target command:
`halo-expected-compilation-001-047-v2/proof.json` on D. Source/compiler/runtime
guards passed. This does not prove linking or protected browser behavior;
the failed first build log remains recorded.

| Check | Status |
| :-- | :-- |
| Apply/replay against exact registered 001–034 source, without modifying it | Passed |
| Independent Python full-frame/crop reference | 58,860 comparisons passed |
| Native helper fixtures | 14 pack-copy + 11 region-planner + 6 clipped-publication cases passed on 001-048 |
| Real CPU/PBO reads, exports, errors, contexts and restart | Six owned phases passed on 001-047; not future-package admission |
| Large attachment data consistency | Four phases passed on preserved 001–068, one document/WebGL2 RGBA8 4096×4096 attachment: CPU/repeat/PBO hashes match, repeated crop matches full output, outside bytes and GL state preserved; protected restart stable, two protected profiles differ |
| Actual private/peak memory and isolated GPU latency | Pending; caller buffers were 64 MiB, not a measurement of private allocation or RSS; timings collected under an active j4 build are not an isolated benchmark |

### Large-attachment control on 001–068

[`large_attachment.py`](large_attachment.py) reuses the existing owned
`ReadbackConfiguration`, NativeRuntime, measured partitioning arguments and
profile-identity derivation. The [source-bound result](large-attachment68-observations.json)
covers baseline, protected A, A restart and protected B. Each phase reads an
explicit 4096×4096 RGBA8 renderbuffer while the GL viewport stays **2×2**:
full CPU reads twice, three 4×4 boundary crops, outside-only sentinel preservation
and full PBO publication. All full CPU/PBO/repeat hashes matched; every crop
matched the corresponding full-frame pixels. There is no API masking, smaller
attachment or software fallback. Private identities stayed exact across restart;
resources and immutable source/core/receipt guards passed.

This is one document/OffscreenCanvas/WebGL2 context and one host, not WebGL1,
workers, WebGPU, general driver compatibility or privacy admission. The measured
64 MiB is the requested caller buffer, **not actual private/peak memory usage**.
CPU/PBO/crop timings are retained as loaded-host observations only, because the
j4 Chromium build was active; no speedup or isolated overhead ratio is claimed.
The prior successful run is retained; the final repeat tightened JSON type
validation without changing native APIs, features, geometry or deadlines.

Fixtures cover clipped edges, transparency, unchanged out-of-bounds bytes,
full-frame handling, overflow, budget rejection, forged plans and aliases.
The Python model does not prove the C++ implementation or driver behaviour.
No texture/HDR/WebGPU readback support or CAPTCHA result follows from it.

## Reproduce source-only checks

Use new private report paths on D; neither command rebuilds Chromium or alters
the active source tree:

```powershell
.venv\Scripts\python.exe scripts/verify_native_halo_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\halo-source-new.json
.venv\Scripts\python.exe scripts/verify_native_readback_regions.py --report D:\CamouFlowNative\halo-model-new.json
```

Next: verify the coherent identity/GPU metadata package, then repeat
full-frame/crop/export equivalence and normal browser compatibility checks
against its exact linked binary. The 31-case success is not transferred to
future patches without the matching checks.
Apply `webgl_halo_readback_candidate.patch` before
`webgl_clipped_publication_candidate.patch`; the public replay command checks
both in order against an owned copy, including their canonical helper sources.
