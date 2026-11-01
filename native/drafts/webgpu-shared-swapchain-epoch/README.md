# Shared-memory Canvas swapchain epoch prototype

**Selected in R5; the actual browser large-Canvas recheck passed.**

[R5 browser measurements](../upstream-156-webgpu-r5/browser-observations.json)
record eight successful baseline/protected large-texture measurements. The
standalone measurements below are retained as their original, narrower evidence.

`next.patch` retains the original Chromium-root-relative prototype. For an
actual candidate, apply `dawn-owned.patch` inside `third_party/dawn`, not the
Chromium repository. [Repository form](repository-form.json) binds this path-only
conversion; it does not change the measured final C++ source.

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

Additional standalone controls now cover swapchain-marked producer mutation,
stale GPU data when access invalidation is deliberately removed, live-device
drain followed by another GPU operation, and rejection of an external wrapper
without SharedTextureMemory ownership. Nine positive runs and three expected
stale-data failures passed. [Resource supplement](resource-supplement.json)
includes reversible fixture patches and preserves the original observations.

An extra original-library large-input attempt observed device loss, but did not
capture its exact out-of-memory cause; it is retained as inconclusive, not PASS.
Recoverable quotas remain required. R4's original large Canvas E_OUTOFMEMORY
remains a failed historical result; R5's actual recheck is recorded separately,
not inferred from these standalone controls. [Exact observations](observations.json).
