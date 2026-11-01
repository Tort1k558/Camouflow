# Transactional array/mip GPU projection

**Native hardware-tested draft; not integrated into Dawn or the browser.**

`RecordAll` creates a complete private 2D array with every mip level protected.
Each subresource keeps its tight canonical byte buffer. Full array views and
views with a nonzero first layer/mip therefore read the same protected image.
Single-layer/single-mip resources retain the original fast path.

Preparation validates and allocates **all** slices and the aggregate before
recording the first projection command. A later-slice quota failure releases
the prepared allocations without recording a partial projection. The shared
device quota stays **64 MiB**; no raw-data fallback is added.

| Gate | Measured result |
| --- | --- |
| Full array / narrow views | 12 cases, six subresources each; **338,090 assertions** |
| Single-slice regression | 32 cases; **99,158 assertions** |
| Original-resource fast path | Eight cases; **19,206 assertions** |
| Atomicity instrumentation | 12 cases passed without recording during failed preparation |
| Injected partial recording | Exact rejection before GPU submission; not counted as GPU execution |
| Chromium target flags | Two translation units passed syntax checks; not linking or runtime |

Shader reads and canonical buffers match the CPU reference. Original pixels
remain unchanged; readback padding is preserved. Tests also retain fence/submission gates,
clone/CPU cancellation ownership, repeated maps and complete quota release.

The negative control records a counter at the projection-command boundary and
deliberately breaks late-quota atomicity. Its exact oracle exits **before**
`ExecuteCommandLists`, avoiding submission of invalid freed-resource commands.
Instrumentation is applied only to owned test copies, never the candidate source.

[Exact observations](observations.json) preserve an earlier integration failure:
standalone checks passed, but Chromium rejected three `try/catch` blocks because
exceptions are disabled. The final code uses checked `nothrow` arrays, and the
generated-target syntax gate passes without changing Chromium's compiler flags.

## Reproduce

```powershell
python native/drafts/webgpu-array-projection/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/array-projection-arrays-fresh --case arrays
```

Other explicit cases: `single`, `fastpath`, `atomic-positive`, `atomic-negative`.
Use a fresh external directory for each invocation. The final case validates
the expected pre-submit rejection, not a successful shader execution.

```powershell
python native/drafts/webgpu-array-projection/check_native.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/array-projection-native-fresh
```

`next.patch` applies inside Dawn **after** the selected-slice
[projection patch](../webgpu-subresource-projection/README.md), which also
requires the [capture prerequisite](../webgpu-subresource-capture/README.md).
The isolated runners do not modify the canonical Chromium checkout.

## Remaining integration

The [Dawn source packet](../webgpu-array-native-integration/README.md) now
composes these adapters and passes six native-target syntax checks. Linking
and actual browser verification remain pending; it is not an admitted runtime.

Carry mip/layer selection through native copy and paired CPU/GPU snapshots;
validate Dawn view descriptors and cache ownership/invalidation; then compile
the complete packet and rerun actual document/iframe/worker maps, mutations
and restarts. R5's browser map failure is **not yet repaired** by this draft.

Supported here: single-sample 2D RGBA/BGRA UNORM and compatible TYPELESS storage.
SRGB, FP16, depth, 3D and MSAA are not covered. The device quota is not a global
memory limit or a general CPU-memory recovery guarantee. Linux/macOS remain deferred.
