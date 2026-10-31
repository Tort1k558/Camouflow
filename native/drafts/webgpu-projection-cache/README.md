# Weak WebGPU projection cache

**Compiled standalone draft; not selected in Chromium.**

Scratch reuse alone still allocates a second large projection when a shader
samples a texture after CPU delivery. This draft reuses immutable projections
without increasing the 64 MiB budget.

- Texture-local weak cache, keyed by projector identity and native view format.
- Fence-retained leases keep snapshots alive only for actual CPU/GPU users.
- Write-state transitions invalidate reuse; old snapshots remain immutable.
- External/shared and swap-chain textures are excluded by source guards.

| Native check | Result | Boundary |
| --- | --- | --- |
| Existing Wire matrix | 54/54 | Same evaluator and negative mapping/no-filter controls |
| Large CPU read → shader → readback | 24 comparative runs passed | RGBA/BGRA, 1921/2048-square; 16 GPU samples span the colour boundary |
| Render/copy mutations | 12/12 | Uncached/cached libraries; new GPU/CPU values match, old snapshot unchanged |
| Live-device allocation drain | Passed in all mutation runs | Capture budget reaches zero before texture/device destruction |
| Deliberately disabled write invalidation | 6/6 expected stale-GPU failures | Exact mismatch marker required, not an arbitrary crash or OOM |
| Five-file source replay/reversal | Passed | Selected source tree unchanged |

[`next.patch`](next.patch) follows the sibling
[`webgpu-scratch-reuse/next.patch`](../webgpu-scratch-reuse/next.patch).
The original large-sampler failures remain recorded in
[`observations.json`](observations.json); they are not rewritten as successes.

## Fixture reproduction

Start with capture-retention `wire_probe.cc` and apply its `wire-byte-budget.patch`
and `wire-byte-budget-loss-diagnostic.patch`, then the scratch-reuse
`large-capture-fixture.patch` and `pattern-fixture.patch`.

1. Apply [`shader-consumer-fixture.patch`](shader-consumer-fixture.patch).
2. The pattern observation substitutions reconstruct all four large variants.
3. Apply [`mutation-fixture.patch`](mutation-fixture.patch) to the shared
   2048/RGBA fixture to obtain the small mutation fixture.
4. Run `--mutation-render` and `--mutation-copy` against both native libraries.

[`write-invalidation-negative.patch`](write-invalidation-negative.patch) is a
deliberately broken **test-only** native variant. Never include it in a browser
candidate. Its executable must fail specifically with `CACHE_MUTATION_STALE_GPU`.

The measurements use normal MSVC STL/no-op `raw_ptr`, not Chromium allocator or
ASan builds. External/shared exclusion, additional storage/view formats,
full Chromium embedding and browser recovery require separate
gates. Retained-budget exhaustion still loses the device; recoverable quotas,
privacy admission and production admission remain unverified.

## Write-only storage mutation

The subsequent [27-case matrix](storage-observations.json) passes render-target,
copy-destination and actual RGBA8 write-only storage-texture mutations against
uncached/cached libraries and the deliberately stale library. All 18 positive
runs preserve old snapshots, return new CPU/GPU values and drain the budget
before destroying the device. All nine negative runs report the exact stale-GPU
marker. Apply [the fixture extension](storage-mutation-fixture.patch) after the
mutation fixture. This does not admit readable storage textures or other formats.
