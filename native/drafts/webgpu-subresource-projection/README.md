# Selected mip/layer GPU projection

**Hardware-tested draft. Not integrated into Dawn routing or the browser.**

Extends R5's GPU projection primitive to a selected mip/layer of a 2D texture
array. It creates a private single-slice texture using that mip's dimensions,
copies the selected producer subresource and runs the unchanged R5 Texture2D
projection kernel. Existing callers still select mip/layer zero by default.

| Hardware check | Result |
| --- | --- |
| Normal / AddressSanitizer | 32 cases, 99,158 assertions per run |
| Format / selection | Typed and typeless RGBA/BGRA; two layers and three mip levels |
| Shader consumption | Texture.Load output equals the CPU reference |
| Canonical byte buffer | Tight native-format bytes equal the same protected image |
| Producer texture | Original pixels remain unchanged |
| Invalid selection | Out-of-range mip/layer rejected before charging quota |
| Ownership / quota | Existing pending-fence, CPU cancellation and shared-budget assertions retained |
| Source safety | Applies to frozen R5; reverse/forward restores exact source hashes |

The [CPU capture prerequisite](../webgpu-subresource-capture/README.md) supplies
the shared budget and selected-subresource capture API. No CPU readback is used
between the actual GPU projection and shader consumption. Readbacks occur only
in the diagnostic harness to compare results.

[Exact observations](observations.json) bind the sources, fixtures, actual R5
shader and public reproduction. No raw-data fallback or quota increase is added.
`next.patch` is Dawn-root-relative; do not apply it to the Chromium root.

```powershell
python native/drafts/webgpu-subresource-projection/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/subresource-projection-check-fresh
```

## Integration still required

The [complete-array follow-up](../webgpu-array-projection/README.md) now passes
native array and narrow-view hardware checks. Dawn routing and actual browser
maps remain unverified; this earlier single-slice draft alone cannot provide them.

- Assemble compatible multi-layer/multi-mip sampled views; a single projected
  slice must not be passed off as a complete array view.
- Propagate validated selection through Dawn copies and paired CPU/GPU snapshots.
- Include subresource/view range in cache identity; preserve producer-write,
  shared-memory access-epoch and policy invalidation.
- Validate the complete packet in actual documents, iframe and workers,
  including repeat maps, mutations, restarts and resource failures.

R5's recorded browser map failure remains unresolved until that integrated
packet is compiled and passes the actual failing browser gate.
