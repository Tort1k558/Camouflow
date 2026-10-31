# Logical-owner GPU snapshot leases

The paired snapshot can now export an owned, immutable native capability through
`GetGpuSnapshot()`. Its public API exposes dimensions and pixel format, **not**
backend resources, seeds or logical-device identity. Payload construction is
private to the native projector; no unchecked backend cast is needed.

Each projector owns a separate identity object. `ResolveSnapshot()` rejects
foreign leases even when a new device occupies the previous `Device*` address.
The identity and GPU resources remain alive through leases without retaining Dawn
Device/Buffer references or creating an observer ownership cycle.

| Gate | Result | Boundary |
| --- | --- | --- |
| Replay / reverse | 20 packets, 84 paths | Unselected staging; runtime 001–076 unchanged |
| Native target-flag syntax | 14 translation units passed | Not native component linking |
| Extracted normal / ASan | 512 iterations, 34,817 assertions each | Fake resources/backend, not hardware or native queue |
| Owner/lifetime | Foreign owner and reused device address rejected; leases retain GPU data after CPU ticket release | No policy/epoch plan/commit proof yet |
| Compatibility | Existing CPU-only implementations construct without new virtual overrides | Empty capability is not permission to use raw shader data |
| Altered inputs | 6 refusals before compilation | Not a runtime security audit |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-snapshot-lease\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-snapshot-lease-check
```

The checker reconstructs the complete source chain and executes extracted public
capability/base classes, private native payload/projector declarations, lease
creation/resolution and paired factory code with explicit fake dependencies.
It checks malformed dimensions/format/plane size, projection/readback failures,
native-layout metadata, raw CPU read and dependent ownership.

## Remaining gates

Logical-owner validation is only one condition. The existing observer still needs
to export token-bound input mappings and a commit ticket proving current policy,
epoch, source/copy version and ordered execution. Real bindings, aliases,
write-back, native device-loss/cancellation, Dawn/Wire, DXC and combined browser
consistency remain incomplete or unverified. No native resource is serialized to
renderer input. This packet neither enables the feature nor admits privacy or
production use; earlier hardware helper evidence does not prove this native API.
