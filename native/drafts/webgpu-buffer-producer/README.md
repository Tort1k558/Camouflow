# Native buffer shadow producer — unselected

The native API prepares one private shadow per logical buffer from an immutable
input plan. Aliases share that shadow; writable binding ranges are merged without
bridging holes. Capability resolution is projector-local, and every projected
range must be covered by actual owned binding ranges.

Recording commits metadata before initialization, explicitly prepares allocation
padding, transitions original buffers through Dawn's usage tracker, and retains a
native buffer owner with the shadow's retirement lease. Failure invalidates the
observer transaction. **The binding tracker does not call this API yet.** No
metadata commit grants shader-byte eligibility or proves installed bindings.

The preceding pipeline packet shares compiler selection between edge projection
and buffer scatter. The buffer pipeline is lazy/cached; unavailable or failing
DXC/FXC is an error, not a reason to retry another compiler.

| Gate | Result | Boundary |
| --- | --- | --- |
| Replay / reverse | 25 packets, 87 paths | Unselected source composition |
| Native target-flag syntax | 15 units passed | No component link |
| Producer control flow, normal / ASan | 1,216 cases / 24,288 assertions each | Extracted native methods; observer, device, queue and GPU helper mocked |
| Compiler/cache, normal / ASan | 53 assertions each; FXC and DXC pipeline creation | Real D3D12 device, mocked Dawn device; no native submission |
| Projection → scatter → consumer | 58 cases per FXC/DXC × normal/ASan | Standalone hardware dispatch, not the new native producer |
| Changed inputs | 8 refusals before compilation | Packet, fixture, tool, extracted-method and baseline checks |

## Reproduce producer control flow

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-buffer-producer\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-buffer-producer-check
```

This command replays and validates all source packets before compiling the
extracted CPU fixture. It does **not** repeat the separate hardware observations
or execute Dawn's actual allocator/queue.

Still required: binding-tracker installation for every alias and dynamic root,
shader-use state transitions, writable-range copyback, exact-scope input receipts,
native queue/cancellation/device-loss checks, indirect ancestry and pass-wide
render routing. Actual padding clears, Wire and combined browser consistency
remain unverified. The selected runtime and production/privacy gates are unchanged.
