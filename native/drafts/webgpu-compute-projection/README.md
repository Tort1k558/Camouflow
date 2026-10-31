# Native WebGPU compute projection — unselected source preparation

This packet connects the isolated shadow-texture helper to Dawn's direct and
indirect compute recording paths. **It is not in the selected browser.**

| Part | Evidence | Still required |
| --- | --- | --- |
| Profile-key delivery | CPU normal/ASan: 29 assertions and 8,000 concurrent reads each; errors clear output; independent policies stay separate | Native device lifecycle execution |
| Projection pipeline | Follows the device's existing DXC/FXC choice; no compiler fallback | Actual Dawn pipeline creation |
| Bundled DXC experiment | Standalone hardware normal/ASan: 8 typed-texture cases, 19,220 assertions and 8 quota cases each; original retained | This does not exercise Dawn bindings |
| Compute sampled inputs | Direct/indirect dispatch hooks, logical-owner checks and per-dispatch projections prepared | Actual dispatch, aliases and intervening writes |
| Descriptor tables | Copy original CPU descriptors into a dispatch-local allocation; replace sampled SRVs without changing cached BindGroup descriptors | Real heap rollover and binding isolation |
| GPU state | Restore heaps; invalidate pipeline/root/sampler/buffer/immediate bindings | Actual pipeline switching and indirect signatures |
| Lifetime | Keep the retirement owner with each texture reference; release the resource before its quota owner | Device loss and cancellation in Dawn |

Seven units passed syntax checks with the pinned Chromium target flags. The full
eleven-packet chain was replayed and this packet reversed exactly, without editing
the active checkout. GN generation and component linking have **not** been repeated.

## Reproduce the CPU policy check

From the repository root, on Windows with the pinned checkout and SDK:

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-compute-projection\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-compute-policy-check
```

The output must be a fresh external directory. The checker reconstructs all eleven
packets, verifies their hashes, and builds/runs the real CPU observer in normal and
ASan modes. **It does not run the shader, Dawn queue, Wire or a browser.** The DXC
hardware observation above is a separate recorded experiment, not this command's
result. The existing [shadow-texture checker](../webgpu-shadow-texture/README.md)
reproduces the standalone FXC hardware checks.

## Deliberate restrictions

- Supports the projector's full single-mip/layer 2D RGBA/BGRA UNORM sampled views.
- Rejects readable storage textures, external textures, resource tables and
  unsupported views rather than silently using raw inputs.
- Reprojects per dispatch; caching across writes is not implemented.
- Shader-derived mapped outputs **remain opaque and denied**. This packet does not
  relabel them as unrelated or enable a privacy admission bypass.
- Raster/bundles, all GPU formats and the complete Canvas/GPU consistency gate
  remain unfinished. The selected 001–076 browser's negative consistency result
  is not superseded by this preparation or by standalone hardware tests.

Next: execute native descriptor/state/rollover tests, implement trusted protected
shader-output provenance and raster routing, then link a candidate and repeat the
real browser gate. No privacy, production or CAPTCHA claims follow from this packet.
