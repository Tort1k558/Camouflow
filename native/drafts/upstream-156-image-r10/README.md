# R10: GPU source images, frame provenance and bounded raster copies

**Registered Windows research recipe. Not built or admitted.**

| Component | State |
| --- | --- |
| Base | Exact 132-patch R9 prefix, unchanged dependency/build pins |
| Extension | Three native packets, complete 135-patch chain |
| Added upstream inputs | GPUCanvasContext and exported-resource header/implementation, pinned to the same Chromium revision |
| Source replay | 135 apply / reverse, 406 final files matched, 273 original inputs restored |
| C++ scope | Composed eight translation units type-check; not link/runtime evidence |
| New native group | `gpu-image-sources`: 21 exact cases in blink_unittests |
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

The verifier registers 21 native cases; it has not executed them. The new group
requires this exact recipe before workspace access. Historical R9/R8 source
bindings are preserved by the reversible host-registration archive, not replaced
by current bytes or relabelled as R10 results.

Next: guarded source transition, one Windows build at maximum j4, all native
groups, then independent runtime/worker/large-image/format/resource and mixed
checks. The measured R9 copy failures are still failed; R10 has no detector,
privacy, installed-package or production verdict. Linux/macOS remain deferred.
