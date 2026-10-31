# Immutable projected pixel snapshots

The native texture projector now retains a tightly packed private GPU pixel
buffer alongside the typed shadow texture. Rows are copied from the GPU-computed
projection, excluding D3D12 footprint padding. Later writes to the original
texture cannot change this snapshot.

**Storage is native RGBA8 or BGRA8, not always RGBA.**
`canonical_pixel_format()` identifies the layout. When the source plane and
destination buffer both use that layout, the scatter channel-swap flag is zero.
A BGRA destination flag copied blindly from an RGBA-plane mapping swaps twice.
The regression fixture checks both formats and typeless storage explicitly.

| Gate | Result | Boundary |
| --- | --- | --- |
| Replay / reverse | 18 packets, 84 paths | Unselected staging; 001–076 unchanged |
| Native target-flag syntax | 14 translation units | No native component link |
| Hardware normal / ASan | 20 cases, 154,849 assertions each | Standalone D3D12 helpers, FXC |
| Dataflow | Texture projection → immutable pixel plane → budgeted buffer shadow; typed texture agrees | Not Dawn bindings, policy registry or Wire |
| Mutation | Original texture overwritten after capture; both outputs retain captured pixels | Ordered on one direct queue |
| Lifetime / quota | Dependent buffer keeps pixel snapshot and upstream quota alive after CPU cancellation | Not native device-loss/queue integration |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-canonical-plane\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-canonical-plane-check
```

The shared runner reconstructs source prerequisites in fresh external staging,
checks hashes/parameter ABI, then compiles actual native helpers and runs both
sanitizer modes on hardware. It does not modify the live checkout or runtime.

The snapshot buffer and its allocation charge share the projector's retirement
owner. Every consumer must retain that handle. All allocations occur before
recording; no allocation or CPU pixel transformation hides inside the row-copy loop.

## Remaining gates

The snapshot is a resource, **not an authorization token**. A native registry must
bind it to logical device, policy, epoch, source generation and copy identity;
then actual bindings, aliases, dynamic offsets and writable copy-back must use
those validated leases. Dawn/Wire, DXC, combined browser consistency and production
admission are still unverified. The selected browser's negative consistency gate
remains open.
