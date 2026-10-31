# Exact-scope GPU input receipts — unselected

The preceding routing packet installs one logical buffer shadow into every
compute-visible CBV/SRV/UAV alias, including dynamic uniform roots. Dynamic
storage offsets/lengths remain Tint-managed. Writable shadows enter UAV state;
only merged writable intervals are copied back before output capture. Original
buffers use Dawn's state/residency tracker. Ordinary cached tables are unchanged.

Output eligibility now has a separate native command-recording receipt:

1. Prepare an immutable input plan and retain its exact owned binding scope.
2. Successfully install transient tables and dynamic roots.
3. Record direct dispatch and writable-range copyback.
4. The named native `CommandBuffer` constructs a private receipt for that plan.
5. The CPU controller matches plan identity, epoch, policy generation, mutation
   sequence and every scope field, then consumes receipt eligibility once.

Missing proof does not authorize pixel inputs. Invalid, foreign, stale or replayed
proof fails closed without retrying legacy eligibility. Existing observers remain
source-compatible: their old two-argument operation is unchanged, while an
unsupported receipt operation is explicitly denied. **This is not binary ABI
compatibility:** updated components still require a matching native rebuild.

| Gate | Result | Boundary |
| --- | --- | --- |
| Replay / reverse | 27 packets, 87 paths | Unselected source composition |
| Native target-flag syntax | 15 units passed | No component link |
| Receipt controller, normal / ASan | 896 receipt cases; 15,735 assertions each, including 12,802 prior-plan checks | Actual CPU controller; native issuer and binding-getter surroundings mocked |
| Earlier controller fixture | Another 10,154 checks retained per mode | Not native GPU execution |
| Copyback normal / ASan | 24 cases / 21,534 assertions each | Extracted method on real D3D12 resources; failed cases stop before submission |
| Changed inputs | 12 refusals before compilation | Includes all imported fixture/checker dependencies |

## Reproduce CPU receipt checks

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-buffer-receipt\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-buffer-receipt-check
```

This replays all packets and runs the actual CPU controller plus extracted native
capture-admission getter. A test-only native friend issues receipts; this does not
execute the real `CommandBuffer`, descriptor allocator or Dawn queue. The command
does not repeat the separate hardware-copyback observation.

**A receipt witnesses command recording, not GPU completion.** Output snapshots
still require their existing submission-marker and fence checks before exposing
CPU bytes. No renderer/Wire command can construct this native receipt.

Still open: a combined actual Dawn producer → bindings → dispatch → copyback →
capture run, allocator retirement/cancellation/device loss, Wire, native padding
clears and combined browser consistency. Projected buffer inputs on indirect
dispatch remain explicitly denied pending scratch/original/count ancestry proof;
pass-wide render/bundle routing is unfinished. Runtime selection and privacy/
production admission remain unchanged.
