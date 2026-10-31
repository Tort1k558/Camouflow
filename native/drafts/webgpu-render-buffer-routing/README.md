# Render/bundle buffer routing — unselected

One source batch extends projected buffer inputs from direct compute to supported
direct render draws and render bundles:

- A metadata-only pass reuses the existing command decoder before GPU render-pass
  entry. An independent binding/vertex tracker prevents preview state leaking into
  execution; scoped cursor restoration preserves inline and bundle command storage.
- One pass-wide projected buffer map supplies shader CBV/SRV/UAV and vertex/index
  addresses. Original cached vertex views remain unchanged; index validation is
  deferred until an indexed draw actually uses the binding. With the observer
  active, zero-consumer direct/multi-draw commands do not project unused inputs.
- Writable ranges copy back only after `EndRenderPass`. Receipt issuance requires
  the executed scope to match the prepared owners, ranges and access flags exactly.
- Projected indirect inputs remain denied pending validated scratch/original/count
  routing. Unsupported typed texel projection is not enabled.

| Gate | Result | Boundary |
| --- | --- | --- |
| Source replay/reverse | 29 packets / 88 paths | No selected runtime changes |
| Native target-flag syntax | 16 units passed | No component link |
| Extracted checkpoint/scope predicates, normal/ASan | 125 cursor paths / 1,536 scope paths each | Storage/traversal/backend modeled, not actual native iterator or dispatch |
| Changed inputs | 8 refusals before compilation | Not runtime attestation |

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-render-buffer-routing\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-render-buffer-routing-check
```

Actual standalone Dawn command storage/pooling is now checked by the
[native iterator suite](../webgpu-command-iterator/README.md), using the official
standalone no-op raw_ptr rather than Chromium MiraclePtr. Chromium allocator
instrumentation, complete preview/execute state, descriptor heap rollover,
direct/bundle GPU reads and writable copyback, queue
failure/cancellation/device loss and Wire still need execution tests. Existing
standalone compute fixtures do not prove this render path. Browser consistency,
runtime selection and privacy/production admission remain closed or unverified.
