# Shared-read access epochs

**Compiled standalone follow-up, not selected in Chromium.**

Chromium D3DImageBacking requests concurrent reading for initialized read-only
shared images. Exclusive-only caching cannot cover this path. This patch follows
[`webgpu-external-access-cache/next.patch`](../webgpu-external-access-cache/next.patch)
and allows cache reuse during explicit shared-memory access, including concurrent
readers. No-access, unknown external and swap-chain guards are unchanged.
Access boundaries and writes still clear the texture-local weak cache.

| Actual native check | Result |
| --- | --- |
| Existing internal Wire controls | 54 passed |
| Initialized concurrent reader, CPU read plus 64 shader values | Three runs passed |
| Two concurrent texture readers, both real GPU consumers | Three runs passed |
| Writer exclusion | Rejected with validation error while two readers remain and while one remains; accepted after both end |
| Cache lookup outside access | Excluded |
| Teardown | Zero tracked capture bytes |

The two fixture patches are alternatives against the sibling published
`wire-import-probe.cc`, not a stack. Initial pixels come from a distinct native
producer before read access; the consumer never writes to its read-only texture.
All readers and the producer share one native device/shared-memory object.

This variant has not repeated producer mutation, missing-invalidation GPU
controls or large-resource measurements. The sibling's exclusive-mode results
are not relabeled as this variant's results. Actual Chromium Canvas, external
device synchronization, live-device drain and resource-exhaustion recovery remain
open. No browser/privacy/production admission is claimed.

## Subsequent shared-read resource checks

The earlier observation snapshot remains unchanged. Independent later results
are bound in [`resource-observations.json`](resource-observations.json):

| Shared-read native check | Result |
| --- | --- |
| Producer writes between consumer epochs | Three passed; new CPU/all 64 shader values exact, old CPU capture unchanged |
| Remove only the two epoch invalidation calls | Three expected stale-GPU pixel mismatches, not arbitrary crashes/OOM |
| Imported 1921/2048-square RGBA/BGRA | Four passed; full CPU image and 16 spatial shader samples each |
| Live-device resource drain | Three passed; zero capture bytes before device destruction, later GPU copy/map still works |
| Swap-chain exclusion flag | Cache lookup/insertion excluded while flagged; not an actual OS swap chain |

Resource fixture patches are alternatives against the result of applying
`single-reader-fixture.patch` to the sibling `wire-import-probe.cc`. The negative
backend patch applies only after both native cache patches, never in a browser.
The fixed capture limit remains 64 MiB. No helper calls observer delivery manually.

Separate-device synchronization, unknown external ownership, actual OS swap
chains and recoverable quota exhaustion remain unverified. Chromium Canvas has
not yet run with these patches. These measurements do not admit a release.
