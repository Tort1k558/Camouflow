# Muted realtime AudioWorklet consistency — unselected fixture extension

| Preserved R2 check | Result |
| --- | --- |
| Two owned profiles × baseline / math / math restart | 6/6 passed |
| Analyser float window vs real worklet tail | All 2,048 samples bit-exact |
| Render-clock endpoint | 8,192 frames, 64 contiguous worklet packets |
| Byte conversion, frequency validity, muted output and lifecycle | Passed |
| Source, independent runtime and pinned driver postguards | Passed |

`fixture-extension.patch` changes only diagnostic fixtures and their validator.
Apply it to an independent disposable source tree, never an active source/build
or a measured canonical fixture. Run the normal Audio compatibility helper with
an explicit candidate, independent preserved runtime and idle owned workspace.
The first actual measurement used a separately hash-bound runner against preserved
R2 while the mutable R3 checkout was being prepared. No mutable binary was used.

This does not repair legacy post-render Audio noise, establish new Audio identity
classes, measure audible quality or admit R3. The six tested realtime hashes were
identical between modes; only live cross-API consistency was measured. R3 is queued
for an independent run. The original canonical fixtures and reports remain intact.

## R4: deterministic diagnostic branch coverage

The first R4 realtime run drew two random profile keys selecting the same
reference branch; its coverage failure is retained. Apply `selector-coverage.patch`
after `fixture-extension.patch` in an independent diagnostic tree to select both
owned fixture branches **before** browser measurements. Private key persistence
uses the existing locked Windows identity writer. No production key generator,
measurement tolerance or validator is changed, and no key is exported or logged.

The rerun passed both profiles and their baseline/math/restart phases, with all
source/runtime/driver postguards. This remains cross-API consistency evidence,
not proof of distinct hardware Audio identities or device-cohort realism.
See `selector-coverage-observations.json` for the portable patch and raw-report hashes.
