# Budgeted GPU buffer shadows

Unselected native D3D12 helper for copying a logical buffer's complete allocation
to a private shadow, then replacing tracked pixel bytes from canonical GPU planes.
The original remains unchanged. **Not connected to Dawn bindings or the browser.**

| Gate | Result | Boundary |
| --- | --- | --- |
| Source replay / reverse | 17 packets, 84 paths | External staging only; selected 001–076 unchanged |
| Native target-flag syntax | 14 translation units | No GN recheck, component link or native device execution |
| Actual helper on hardware | 58 cases, 178,960 assertions per normal / ASan run | Standalone D3D12, FXC; not Dawn/Wire |
| Invalid input / budget | 696 structural and 812 helper/quota rejections per run | No raw fallback |
| Resource ownership | 26 pre-submit CPU cancellation cases; dependent quota retained | Fixture supplies queue leases; no native queue integration |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-buffer-shadow\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-buffer-shadow-check
```

Requires the pinned checkout/SDK, a hardware adapter and a fresh external output.
The shared runner reconstructs the prior sixteen packets, applies this extension
only in staging, verifies source hashes and the shared 64-byte parameter ABI,
then executes the actual native helper in normal and ASan standalone fixtures.

## Contract

- Fully initialized private original allocation, at most 64 MiB; preserve allocation
  capacity/padding rather than copying only logical bytes.
- At most 16 non-overlapping regions from private same-device canonical planes.
- Charge actual allocation size plus descriptor allowance against a shared budget.
- Retain original and canonical retirement owners, not just resource COM pointers.
  Dependent shadows keep upstream quota charged until the final consumer releases it.
- Validate, reserve and allocate before recording commands. Explicit UAV barriers
  order scatter dispatches. The caller restores clobbered compute state.

Caller must prove logical device, policy, epoch and canonical-plane immutability;
resource/device equality alone is not authorization. Every GPU consumer must retain
the retirement handle through completion. This helper is not a snapshot registry.

## Remaining integration

Immutable canonical-plane registry, binding/alias/dynamic-offset routing, writable
copy-back, validated indirect ancestry, real Dawn queue/Wire tests and DXC remain
open. No selected browser, privacy, CAPTCHA or production admission follows from
these standalone results. The browser's existing Canvas/GPU consistency failure
is unchanged.
