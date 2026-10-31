# Tagged-byte GPU scatter — standalone primitive

The GPU computes the existing keyed edge projection, copies only tracked pixel
bytes into a private buffer, then a second shader consumes that buffer. Padding,
unrelated bytes and the protected source are checked separately. **This is not
installed in Dawn bindings or the selected browser.**

| Gate | Measured result | Boundary |
| --- | --- | --- |
| Source prerequisite | Existing sixteen-packet / 81-path replay plus CPU contract gate | Not a seventeenth engine patch |
| Hardware normal / ASan | 58 cases, 176,704 assertions each; 21,501 changed channels | One local D3D12 hardware adapter, FXC `cs_5_0` |
| Partial data | RGBA/BGRA, clipped bytes/channels, row padding, prefix/guards, disjoint fragments | Constructed provenance metadata, not Dawn copy execution |
| Mapping arithmetic | Large 64-bit lineage offsets and near-uint32 row-pitch carry; two-dimensional dispatch | Huge original buffers are not allocated or tested through Dawn |
| Actual dataflow | GPU HMAC → split-only scatter → shader consumer; repeated writes idempotent; source unchanged | Not native immutable-snapshot registry or binding routing |
| Invalid parameters | 696 structural rejections per mode | Nonzero identity fields are not epoch/ownership authorization |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-buffer-scatter\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-buffer-scatter-check
```

Requires Windows, the pinned 001–076 checkout/SDK and a D3D12 hardware adapter.
The existing execution-input command first reconstructs the full source chain
outside the checkout. The GPU fixture reuses its real provenance/layout/CPU edge
code and the existing edge/HMAC shader. No downloads, WARP or compiler fallback.

`buffer_scatter.h` validates and normalizes structural mapping into sixteen DWORDs.
Current bounds are 64 MiB per destination/canonical plane and full dimensions up
to 8192, with RGBA8/BGRA8 UNORM geometry.
The HLSL handles byte masks atomically when adjacent threads share a DWORD.
Atomic operations are **not** a memory fence: ordered repeated dispatches use
[UAV barriers](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ns-d3d12-d3d12_resource_uav_barrier),
and state transitions precede shader consumption/readback. See also the
[HLSL atomic contract](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/interlockedand).

## Native integration still required

1. Capture an immutable canonical GPU snapshot at copy-execution time; retaining
   the mutable original texture is insufficient.
2. Bind snapshots to the native device/policy/epoch with bounded resource ownership.
3. Integrate the [standalone budgeted shadow helper](../webgpu-buffer-shadow/README.md); preserve dynamic offsets and
   aliases, route actual uniform/storage/control bindings and copy back writable ranges.
4. Prove validated-scratch ancestry for projected logical indirect/count inputs.
5. Verify DXC, actual Dawn/Wire execution, resource cancellation/device loss,
   combined browser consistency and compatibility before admission.

The primitive does not authorize reads or prove privacy. Loaded depth/stencil,
PLS, complete formats/raster outputs and production security rebasing also remain
open. The selected browser and its negative Canvas/GPU consistency result are unchanged.
