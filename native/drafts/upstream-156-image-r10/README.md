# R10: GPU source images, frame provenance and bounded raster copies

**Windows build and all native groups passed. Browser repair not admitted.**

The [measured incremental build](windows-build.json) completed 66 Siso steps in
15m 57.96s. [All 28 native groups](native-all-observations.json) passed 581 case
executions (424 distinct binary/suite cases), including all 21 image-source cases.
The [full host suite](host-observations.json) passed 5897 tests with one skip on
the exact recorded source commit; this is not browser or release acceptance.

[Real runtime observations](runtime-observations.json) remain **failed/incomplete**:
opaque WebGL transferToImageBitmap rejects a protected source copy, worker-backed
placeholder frames are not observed, and one shared module-worker rendering
comparison differs on restart. All 11 malformed launch cases reject correctly.
The old GPU validator still expects raw texture pixels; a separate new matched
GPU harness also exposed a baseline-normalization bug. Neither failure is hidden
or reclassified as a repaired browser result.

| Component | State |
| --- | --- |
| Base | Exact 132-patch R9 prefix, unchanged dependency/build pins |
| Extension | Three native packets, complete 135-patch chain |
| Added upstream inputs | GPUCanvasContext and exported-resource header/implementation, pinned to the same Chromium revision |
| Source replay | 135 apply / reverse, 406 final files matched, 273 original inputs restored |
| Windows runtime | Built and preserved independently; browser repair checks failed/incomplete |
| New native group | `gpu-image-sources`: all 21 exact blink_unittests cases passed |
| Existing groups | All 27 R9 definitions and binary mappings retained |
| Resource gates | Maximum j4, 180 GiB full-build preflight unchanged |
| Manager / package admission | Unchanged, no new capability activated |

[Manifest](manifest.json) · [source preparation](preparation.json)

- [GPU source-image boundaries](../canvas-gpu-image-sources/README.md)
- [Immutable frame provenance](../canvas-frame-provenance/README.md)
- [Single private raster](../canvas-owned-raster/README.md)

Use the [normal Windows workflow](../../BUILDING.md) with explicit candidate
`upstream-156-image-r10`. Do not apply this full chain directly over the current
R9 changes: preserve/reverse the exact owned delta first, retain foreign changes
and bind the transition/rollback state. Existing R9 runtime stays independent.

The verifier executed all 21 native cases successfully. The new group
requires this exact recipe before workspace access. Historical R9/R8 source
bindings are preserved by the reversible host-registration archive, not replaced
by current bytes or relabelled as R10 results.

Next: diagnose source-copy formats and placeholder delivery as one repair batch,
correct the new GPU harness separately, then repeat independent runtime/worker/
large-image/format/resource and mixed checks. Preserve R9 and R10 evidence and
standalone runtime snapshots. R10 has no detector,
privacy, installed-package or production verdict. Linux/macOS remain deferred.
