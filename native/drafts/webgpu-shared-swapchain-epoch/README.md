# Shared-memory Canvas swapchain epoch prototype

**Compiled standalone; not in the measured Chromium browser.**

Blink marks WebGPU Canvas SharedImages as swapchain textures. Chromium forwards
that marker through the real shared-memory BeginAccess descriptor. R4 excluded
all such textures from projection reuse, even inside a known shared-memory epoch.
The correction permits reuse only with actual active shared-memory ownership;
unknown external textures remain excluded. Begin/end access and producer writes
still invalidate cached projections. The quota remains **64 MiB**.

| Native before/after evidence | Measured result |
| --- | --- |
| Same fixture object, original library | Expected `SHARED_EPOCH_CACHE_MISSING` failure |
| Single/two-reader shared-memory access | Six runs passed |
| 1921/2048 square, RGBA/BGRA | Twelve runs passed; CPU/shader agreement and zero capture bytes after destruction |
| Existing internal controls | 54 controls passed |
| Full patch composition | 124 forward/reverse; 270 upstream files restored |

The tests use the real BeginAccess swapchain descriptor, not a manually toggled
backend flag. All case invocations explicitly select their RGBA/BGRA CLI mode.
The first omitted-argument harness failure is retained separately from the actual
measurements. These imported resources are not real browser/compositor frames.

Swapchain-marked mutation/stale controls, unknown-external exclusion, live-device
drain, recoverable quotas and the real Chromium Canvas gate remain required.
R4's large Canvas E_OUTOFMEMORY is still a failed browser result; do not report
this prototype as its verified browser repair. [Exact observations](observations.json).
