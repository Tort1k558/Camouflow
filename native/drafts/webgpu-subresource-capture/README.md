# Selected mip/layer D3D12 capture

**Hardware-tested draft. Not integrated into the browser.**

R4 and R5 reject protected WebGPU maps from a two-layer, three-mip texture,
including its first mip/layer. The existing capture and GPU projection only
support a single-layer, single-mip resource. This draft implements the CPU
capture prerequisite; it does **not** claim that the browser failure is fixed.

| Native check | Result |
| --- | --- |
| Hardware / AddressSanitizer | 32 cases, 97,072 assertions per run |
| Existing single-surface coverage | Eight original cases retained |
| Arrays / mip levels | Two layers, three mip levels, four typed/typeless RGBA/BGRA formats |
| Snapshot stability | Two source versions, repeated exact pixel reads |
| Invalid selection | Out-of-range mip/layer rejected without a snapshot |
| Ownership / completion / quota | Original cancellation, submission, fence and contention assertions retained |
| Source safety | Patch applies to frozen R5; reverse/forward restores exact source hashes |

The optional native mip/layer parameters preserve existing callers. Capture
uses the selected D3D12 subresource footprint and mip dimensions, not the base
resource's dimensions. It keeps the existing allocation accounting and retained
GPU ownership; no raw-data fallback or quota increase is introduced.

[Exact observations](observations.json) bind the source, fixture and runner.
`next.patch` is Dawn-root-relative. The full source copies make the isolated
check runnable without mutating the canonical Chromium checkout:

```powershell
python native/drafts/webgpu-subresource-capture/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/subresource-capture-check-fresh
```

Before candidate integration, extend the paired GPU projection, sampled array
views, copy notifications and provenance together. Then rerun actual document,
iframe and worker maps, all layers/mips and profile restarts. Merely enabling
the existing copy hook for arrays would leave the paired GPU path unsupported.
