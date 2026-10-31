# WebGPU ranged provenance — unselected source extension

This four-file delta extends the seven-packet source chain ending in
`webgpu-shader-scope-next.patch`. It is not part of the selected 001–076 browser.

## Changes

- Track shader-derived bytes as bounded opaque intervals, not pixel snapshots.
- Propagate clipped intervals through buffer copies, including source destruction.
- Allow trusted literal overwrites to clear only the overwritten interval.
- Coalesce adjacent opaque intervals; table overflow fails closed.
- Keep pixel snapshot references when unrelated opaque intervals coexist.
- Refuse opaque reads and reject forged pixel-shadow plans containing opaque data.

The native shader notification **still covers whole buffers**. This foundation
does not provide exact binding ranges or transform shader-produced pixels.
Refusal is an interim safety barrier, not compatible fingerprint protection.

## Measured evidence

| Check | Result | Scope |
| --- | --- | --- |
| New normal / ASan tests | 4,900,091 assertions each; 4,000 deterministic oracle operations | CPU provenance and synthetic controller handles |
| Existing isolated DLL suites | Five suites in both normal and ASan modes | Actual exports/imports, not Chromium component linking |
| Chromium-flag syntax | Three translation units; no diagnostics | Core provenance, snapshots and GPU-service observer |
| Patch replay | Forward and reverse byte hashes verified | Four-file extension only |
| Python baseline | 5102 passed, 1 skipped at `cca22d8` | Before this extension; not native evidence |

`ranged_test.cc` is the measured standalone test source. A public standalone
driver is not integrated yet. Hash-bound observations and ordered prerequisites
are in [the preparation record](../environment/webgpu-ranged-provenance-preparation.json).
Combined GN checks were not repeated for this extension. No new GN files or
dependencies are introduced.

## Remaining gates

Exact binding/dynamic-offset ranges, per-draw/bundle handling, real Dawn callbacks
and Wire tests, Chromium static/component linking, and actual GPU execution remain
unverified. The public copy/shader/PNG consistency gate still fails on the selected
001–076 runtime. Compatible protection must return matching pixels, not just deny
the read. No runtime, privacy or production admission is granted by these tests.
