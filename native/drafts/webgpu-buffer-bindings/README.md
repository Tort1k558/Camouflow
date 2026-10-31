# Transient buffer descriptors and root uniform addresses

Native `BindGroup` methods now support dispatch-local buffer overrides for static
uniform CBVs, readonly raw SRVs and writable raw UAVs, including dynamic storage
bindings. Dynamic uniform bindings resolve a private root CBV address with the
original binding offset plus validated dynamic offset. Missing overrides fail;
they do not silently resolve to the original buffer.

One descriptor writer is shared with ordinary bind-group initialization. The
ordinary path still supplies `Buffer::GetVA()` explicitly; the shadow path uses
its private resource address. The existing sampled-texture overload remains.
Override validation precedes allocation and checks logical owner, private backing,
resource geometry/capacity, heap, descriptor alignment, UAV/SRV flags and CBV limits.

| Gate | Measured result | Boundary |
| --- | --- | --- |
| Replay / reverse | 22 packets, 84 paths | Unselected external staging |
| Native target-flag syntax | 14 units passed | No native component link |
| Standalone hardware normal / ASan | 20 cases, 21,728 assertions each | Extracted native methods, actual D3D12; mocked Dawn objects |
| View types | Uniform/static and root/dynamic; readonly/storage and internal raw types; offsets 0/256 | Valid-range test shaders, not Tint robustness validation |
| Invalid overrides | 244 rejections before allocation per run | Includes oversized CBVs and wrong logical owners |
| Resource/cache isolation | Shader sees shadow data, cached table still sees original; UAV changes only shadow | No writable copyback or actual dispatch producer |
| Heap replacement | Earlier transient table remains usable after allocator page switch | Allocator lifetime is mocked, not Dawn's live ring |
| Changed inputs | 10 refusals before hardware compilation; 9 before any compilation | Generated-method case first runs the separate CPU source gate |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-buffer-bindings\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-buffer-bindings-check
```

The checker reconstructs the twenty-one-packet input-plan source gate, applies
this extension externally, hashes the extracted writer/validation/population/root
methods, then executes those methods using real hardware resources. Shadow data
is CPU-initialized: this test measures binding semantics, **not fingerprint
transformation**. The existing GPU scatter, budgeted shadow and immutable-plane
fixtures are also rerun with the updated shared runner.

## Remaining integration

The native input-plan consumer must still build shadows from verified logical-owner
leases and install overrides in the actual binding tracker. Writable union
copyback, aliases across all input/control paths, validated indirect ancestry,
native queue/cancellation/device loss, Dawn/Wire/DXC and combined browser
consistency remain unfinished or unverified. No selected runtime or privacy/
production admission is changed by this packet.
