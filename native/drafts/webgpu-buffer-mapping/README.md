# Shared scatter mapping and physical-allocation preparation

The existing mapper now lives in a Chromium GPU-common header. The CPU observer
exports its checked sixteen-DWORD mapping in the native input plan; a future Dawn
consumer can use those constants without depending on Chromium's provenance
implementation. The standalone adapter only bit-casts that same mapping into the
existing 64-byte scatter ABI. Its fixture header is byte-identical to native source.

Channel conversion is source-layout XOR destination-layout. A native BGRA plane
copied to a BGRA buffer needs **no second swap**; the older RGBA-plane fixtures
retain their established BGRA conversion.

The native `EnsureGlintAllocationInitialized` API separately prepares logical
bytes and clears allocation padding. It refuses insecure lazy-clear configuration,
inaccessible/imported backing and inconsistent allocation sizes; it does not
equate logical full-overwrite initialization with initialized padding.
**The producer has not called this API yet.**

| Gate | Measured result | Boundary |
| --- | --- | --- |
| Replay / reverse | 23 packets, 86 paths | Unselected external staging |
| Native target-flag syntax | 15 units passed, including BufferD3D12.cpp | No component link |
| CPU normal / ASan | 110,776 assertions each, including 12,802 prior-plan checks; another 10,154 legacy-fixture checks retained | Actual CPU mapper/controller; fake allocation/device operations |
| Geometry oracle | Crops, clipped bytes, padding, large lineage offsets and both source/destination channel layouts | Compared with WebGpuCanonicalByte, not a native GPU dispatch |
| Allocation contract | Initialized logical bytes preserved; tail cleared; invalid/failing preparation denied | GPU ClearBuffer execution not measured |
| Prior GPU regressions | Scatter, budgeted shadow and immutable-plane normal/ASan passed with the shared mapper | Original standalone boundaries still apply |
| Changed inputs | 8 refusals before compilation | Not runtime attestation |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-buffer-mapping\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-buffer-mapping-check
```

The checker compiles the actual shared mapper/controller and reuses prior plan
and shader-capture fixtures. The extracted native initialization method runs with
fake buffer/device operations. It verifies that the public fixture header matches
the staged native header before compiling.

Native shadow production, binding-tracker installation, writable copyback,
real padding clears/queue cancellation, Wire/DXC and combined browser consistency
remain unfinished or unverified. Selected runtime and privacy/production admission
are unchanged.
