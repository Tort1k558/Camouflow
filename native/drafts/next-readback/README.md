# WebGL readback: bounded halo candidate

**Unregistered, uncompiled; no runtime privacy capability is admitted.**
This patch follows the registered 001–034 batch and must not be applied during
its active build. It changes private readback allocation, not the fingerprint
algorithm, GPU identity, live framebuffer or JavaScript API.

## Changes

| Request | Private storage | Protection |
| :-- | :-- | :-- |
| Exact full framebuffer | One rectangle allocation | Existing edge-colour transform in place |
| Partial in-bounds read | Original rectangle + clipped one-pixel halo | Same transform, then guarded row overlay |
| Entirely outside framebuffer | Original rectangle only | Preserve the driver result; no in-bounds pixels exist |

The halo is valid **only** for the existing quantized-colour, four-neighbour
algorithm. Coordinate-dependent or global transforms cannot reuse this planner.
Attachment dimensions remain native; a viewport is not an attachment extent.
Checked arithmetic, a combined memory budget and pre-write alias/plan validation
bound the extra storage. CPU and PBO callers retain their existing pack/state
handling, validation and required-policy rejection.

For a 1×1 crop inside a 4096×4096 attachment, planned storage is 40 bytes
(4-byte rectangle + 36-byte halo), rather than a whole-frame copy. An exact
4096×4096 RGBA8 read fits the existing 64 MiB budget in one private allocation.
These are allocation calculations, **not measured performance improvements**.

## Evidence and pending checks

| Check | Status |
| :-- | :-- |
| Apply/replay against exact registered 001–034 source, without modifying it | Passed |
| Independent Python full-frame/crop reference | 58,860 comparisons passed |
| Native helper fixtures | 11 prepared; not compiled or run |
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

After the current build finishes: run its strict unit/browser gates first,
review and promote this separate patch, compile its native fixtures, then repeat
full-frame/crop/export equivalence and normal browser compatibility checks.
