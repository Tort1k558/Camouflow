# D3D12 full-texture capture draft

**Unselected. No automatic WebGPU interception or browser protection.**

| Check | Measured result |
| --- | --- |
| Actual hardware GPU | Eight cases; no software-adapter fallback |
| Pixel layouts | RGBA8/BGRA8, typed and typeless resources |
| Images | 7×3 and 65×5, padded rows, two successive texture versions |
| Snapshot reads | Original versions retained; repeated reads match exact bytes |
| Completion gates | Submission marker and GPU fence both required |
| Cancellation | Dedicated GPU allocation retained while CPU capture is cancelled |
| Normal / AddressSanitizer | **22,525 assertions each**, passed |
| Dawn source preparation | Three translation units passed syntax checks; seven-file patch round-tripped |

The [native patch](../environment/webgpu-d3d12-capture-next.patch) adds a Dawn
adapter that initializes/transitions the source, uses the real pending queue fence,
and retains the COM resource through `ReferenceUntilUnused`. Recording-context
markers publish only after `ExecuteCommandLists`; failed/abandoned contexts clear
their markers without admitting a read. **This Dawn glue has not run in a browser.**

Run the isolated hardware checks on Windows:

```powershell
python native/drafts/webgpu-d3d12-capture/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/d3d12-capture-check-fresh
```

Requires an existing hardware D3D12 adapter and pinned compiler/SDK. No download,
Chromium compilation or software-adapter retry. Output is a fresh external D: path.

## Still required

- Install the producer at trusted native copy execution, not renderer encoding.
- Attach device policy, snapshot/provenance tracking and protected mapped shadows.
- Account GPU budget until fence retirement, **not** CPU snapshot cancellation.
- Preserve taint after uncertain shader writes; lost provenance must not permit a
  raw mapping of potentially fingerprint-bearing data.
- Test actual Dawn submission, cancellation, device loss and map callback ordering.
- Resolve the measured Canvas/WebGPU export mismatch and run combined browser gates.

Current capture supports one mip, one layer and one sample of the listed formats.
It captures original pixels only; the existing protection algorithm is not invoked.
