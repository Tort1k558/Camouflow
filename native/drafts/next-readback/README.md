# WebGL readback: bounded halo candidate

**Registered as 0046/0047; complete browser build and runtime verification pending.**
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
same typed result; the fixtures are still not compiled or executed.
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
and PBO paths in eight contexts before/after restart. The registered 0034 source
currently copies its whole zero-initialized private rectangle back, so that
candidate has a known clipping-compatibility issue. Its active build is untouched;
the correction is prepared here, **not yet verified in a protected browser**.

The linked 001-045 browser now confirms this failure with protection enabled:
`gpu-readback-001-045-v1.json` on D. Its feature-off initial/restart phases
passed, but protected profile-A reads replaced out-of-bounds CPU sentinel bytes
with zero in all eight document/worker contexts, on initial and resized
attachments. GL error state remained clear and bindings remained intact.
The boundary contract must not be relaxed to accept this output. The prepared
clipped-publication patch still needs optimized compilation, native execution
and a new protected browser run before claiming the defect is repaired.

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
11 region-planner and 6 clipped-publication cases. These have not executed yet.

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
| Native helper fixtures | 11 halo + 6 clipped-publication cases prepared; not compiled or run |
| Real CPU/PBO reads, exports, errors, contexts and restart | Pending new binary |
| Large attachments, memory use and GPU latency | Pending runtime measurements |

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

After the current build finishes: run its strict unit/browser gates,
compile and execute the 31-case native gate, then repeat
full-frame/crop/export equivalence and normal browser compatibility checks.
Apply `webgl_halo_readback_candidate.patch` before
`webgl_clipped_publication_candidate.patch`; the public replay command checks
both in order against an owned copy, including their canonical helper sources.
