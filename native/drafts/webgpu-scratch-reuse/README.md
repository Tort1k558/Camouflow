# WebGPU texture scratch reuse

**Compiled standalone prototype. Not selected in the Chromium runtime.**

The original 2048-square protected capture loses its device before the first
capture completes: its intermediate allocations exceed the 64 MiB budget.
This draft reduces copies without raising the limit or returning raw data.

- Copy into the existing private shadow texture and sample it as shader input.
- Keep neighbour reads immutable until the compute dispatch finishes.
- Reuse the output as canonical bytes only when rows have no footprint padding.
- Retain separate tight packing for padded rows and existing fence-owned lifetimes.

| Measured check | Result | Scope |
| --- | --- | --- |
| Existing Wire matrix | 54/54 | RGBA/BGRA sampling, render/bundle, indirect, mapping denial and no-filter controls |
| Same 2048-square fixture, before | 3/3 expected failures | Original Glint/E_OUTOFMEMORY before first capture completion |
| Same fixture, after | 3/3 passed | Full 16 MiB mapped RGBA verified against a GPU-cleared opaque reference |
| Tracked large-capture allocations | 50,397,184 bytes | Includes capture/projection accounting; not total physical VRAM |
| Retained-budget overflow | Device loss still occurs | Aborted mapping and zero retained capture allocations; not quota recovery |
| Source replay and reversal | Passed | Two exact Dawn source files; selected checkout unchanged |

[`next.patch`](next.patch) applies after the 118-patch revision-2 source.
The same prototype was linked with normal MSVC STL/no-op `raw_ptr`; it does not
establish Chromium allocator, ASan, renderer, worker or browser recovery behavior.
The native shader is recompiled; no JavaScript API replacement is used.

[`large-capture-fixture.patch`](large-capture-fixture.patch) applies after
the sibling capture-retention `wire-byte-budget.patch` and
`wire-byte-budget-loss-diagnostic.patch`. It verifies all first-capture bytes
before intentionally exhausting the retained-capture budget. This is a flat
large-surface check, not large patterned-surface coverage.

Source hashes, the complete case inventory and comparative observations are in
[`observations.json`](observations.json). Existing failures and candidate
manifests remain unchanged. Browser and production admission remain false.

## Large patterned surfaces

The separate [pattern observations](pattern-observations.json) cover 24 actual
before/after runs: RGBA and BGRA at both 1921-square and 2048-square dimensions.
The GPU renders two colour regions; every mapped pixel matches the native CPU
edge/HMAC reference. Padding in 1921-square rows is checked separately for zeros.
All 12 corrected-backend runs pass; all 12 original-backend runs reproduce the
expected budget failure. Tracked charges are 62,193,664 bytes for padded rows
and 50,397,184 bytes for tightly packed rows, below the unchanged 64 MiB limit.

[`pattern-fixture.patch`](pattern-fixture.patch) follows the large-capture
fixture. Exact dimension/format substitutions reconstruct each measured source.
Earlier invalid-row-alignment and over-specific control-classification attempts
remain failed observations. Large GPU shader-consumer routing, recoverable
quotas and Chromium runtime integration still require separate checks.
