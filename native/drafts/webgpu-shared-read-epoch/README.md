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
