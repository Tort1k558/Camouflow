# GPU projection through native buffer descriptors — standalone

This combines previously separate GPU checks:

**Native seeded projection → immutable pixel plane → budgeted buffer shadow →
extracted native transient buffer descriptors → hardware shader consumer.**

The descriptor consumer reads a buffer produced from the GPU pixel plane, not a
different CPU-initialized pattern. Both the earlier typed-texture consumer and
the new buffer consumer match the seeded CPU oracle after the source texture is
overwritten. Native RGBA/BGRA layout, typeless texture storage, shared quotas,
CPU-owner cancellation and dependent retirement remain checked.

| Gate | Measured result | Boundary |
| --- | --- | --- |
| Normal / ASan hardware | 20 cases / 193,424 assertions each | Real D3D12 projection, scatter, descriptors and shader |
| Source gate | Producer packet 25, then checked routing/receipt packets 26–27 | Not actual Dawn execution |
| Native descriptors | Extracted `WriteBufferDescriptor` / `PopulateGlintViews` | Dawn objects and descriptor allocator mocked |
| Changed inputs | 12 refusals before hardware compilation | 10 before any compilation; 2 after the CPU source gate |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-buffer-chain\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-buffer-chain-check
```

The runner checks fixture/shader/tool dependencies, runs the CPU producer source
gate, applies the two source-extension packets and verifies their pre/post hashes.
It then extracts native descriptor methods and compiles/runs normal and ASan
hardware fixtures. The shared descriptor fixture is reused, not forked.

This does **not** execute the actual Dawn `GlintTextureProjector::RecordBuffers`,
binding tracker, descriptor allocator, native receipt issuer or Dawn queue.
The combined buffer consumer is read-only; dynamic roots and writable copyback
have separate checks, not this combined hardware proof. Submission/fence handling
and lease retention here are fixture-managed, not actual Dawn retirement tests.
The [receipt controller](../webgpu-buffer-receipt/README.md) has its own CPU gate.

Full native producer/bindings/dispatch/copyback/capture, cancellation/device loss,
Wire and browser consistency remain required. No runtime selection, privacy
admission or production release follows from this standalone result.
