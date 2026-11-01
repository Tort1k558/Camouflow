# Offscreen frame provenance — unselected extension

**Source/type checks pass. The extension has not been built or runtime-verified.**

Extends the exact [GPU image-source draft](../canvas-gpu-image-sources/README.md),
not the active R9 browser. The browser's transferred-frame bypass is separately
reproduced below; it is not presented as repaired.

| Layer | Implemented in this extension |
| --- | --- |
| Worker frame publication | Capture source type and readiness before dispatch; no pixel readback on every frame |
| Cross-thread resource | Immutable source descriptor and domain-separated SHA-256 commitment; no surface seed/profile key transported |
| Destination ownership | Re-derive from the ready owned profile policy; reject missing, stale/mismatched or wrong-kind commitments |
| Placeholder draw / bitmap | Hold the exact resource while resolving provenance and reading its image |
| Placeholder PNG exports | Apply the same source-domain policy to toDataURL/toBlob |
| Compatibility | Existing unselected constructor defaults and compositor pixels stay unchanged |

[Patch](canvas-frame-provenance.patch) · [source evidence](source-observations.json)

The composed parent + extension applies/reverses exactly. Six translation units
pass type checking, including platform resource transport and native fixtures.
Four new commitment cases are prepared, bringing the composed draft to eleven
new native cases. **None of those eleven has executed yet.** Existing Blink
Digestor is reused; no new library/dependency or page-visible metadata is added.

## Actual R9 reproduction — failed, not fixed

[Captured results](r9-observations.json) use a real dedicated worker and
`transferControlToOffscreen`, WebGL1/2 and both 2D backing requests.

| Copy route | Comparisons | R9 result |
| --- | --- | --- |
| Placeholder drawImage | 4 | FAIL |
| Placeholder createImageBitmap | 4 | FAIL |
| Placeholder toDataURL | 4 | FAIL |
| Placeholder toBlob | 4 | FAIL |
| PNG exported inside source worker | 4 | Exact agreement with direct GPU readback |

The first four routes expose raw colours, differing by **94/256 channels** from
protected readback in this one profile/pattern. The count is not a general score.
All twenty comparisons completed; source/core/driver/asset guards passed and
owned browser/server resources closed. No external detector was visited.

[Owned fixture](probe.js) · [strict validator](validate.py). Frame readiness
requires actual coloured content, not the alpha:false destination's opaque alpha.
A single changed channel fails equality; no error, timeout or unsupported API
is counted as success.

## Still required

- Resolve the detached-copy budget for large source images without raw fallback.
- Link/execute all eleven native cases and the composed browser; repeat direct
  and transferred-frame copies, retained/replaced frames and profile ownership.
- Test taint/error precedence, alpha, colour spaces, crop/scale and lifecycle;
  calibrate the protected WebGPU gate and repeat mixed-policy/package checks.

The R9 binary, manager admission and known-colour-fidelity limitations remain
unchanged. Source proof is not proof of a runtime repair or realistic identity.
