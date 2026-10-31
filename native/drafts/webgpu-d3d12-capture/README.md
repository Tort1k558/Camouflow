# D3D12 full-texture capture draft

**Unselected. No automatic WebGPU interception or browser protection.**

## Aggregate capture quota follow-up

The current core charges actual D3D12 allocation bytes to a shared quota before
creating a readback resource. An `IUnknown` retirement handle keeps the resource
and its quota together: cancelling the CPU capture does not free in-flight quota;
both the native retirement owner and remaining CPU owner must release their holds.

| Check | Measured result |
| --- | --- |
| Hardware / normal + ASan | **22,720 assertions each**, eight GPU cases |
| Cancellation / fence | Quota retained across CPU cancellation and actual GPU completion until the queued owner releases it |
| CPU owner after fence | Quota retained while the capture still owns the allocation |
| Contention | Eight concurrent allocators, one allocation-sized quota; exactly one admitted |
| Native source preparation | Four translation units passed syntax checks; nine-file packet round-tripped |
| Dawn runtime | Not executed; copy/map interception and device-loss paths still pending |

The [budgeted native packet](../environment/webgpu-d3d12-budget-next.patch) gives
each D3D12 `Device` one candidate **64 MiB** quota and reuses its existing
`ReferenceUntilUnused` queue. It **replaces**, rather than stacks on, the older
seven-file capture packet. This is not a GPU-process-wide quota or a shipped limit.
[Source hashes, hardware results and boundaries](../environment/webgpu-d3d12-budget-preparation.json).

The source-only upgrade is reversible; the original capture measurements below
remain bound to their reconstructed pre-budget sources, not rewritten as new runs.

## Original capture-only baseline

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
- Verify the prepared device-owned quota through actual Dawn retirement, failed
  submission and device loss; add a GPU-process/global budget separately.
- Preserve taint after uncertain shader writes; lost provenance must not permit a
  raw mapping of potentially fingerprint-bearing data.
- Test actual Dawn submission, cancellation, device loss and map callback ordering.
- Resolve the measured Canvas/WebGPU export mismatch and run combined browser gates.

Current capture supports one mip, one layer and one sample of the listed formats.
It captures original pixels only; the existing protection algorithm is not invoked.
