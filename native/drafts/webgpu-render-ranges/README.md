# Per-draw and render-bundle ranges — unselected source extension

This five-file native/service delta follows `webgpu-binding-ranges-next.patch`. It is not
part of the selected 001–076 browser and does not implement compatible shader
pixel protection.

## Prepared behavior

- Shared binding collection for compute, vertex and fragment stages.
- Per-draw storage/uniform/dynamic-offset/texel ranges, plus used vertex-buffer
  slices and the index-buffer slice for indexed draws.
- Six draw paths: direct/indexed, indirect/indexed-indirect and both multi-draw
  forms. Render bundles use the same native command encoder.
- Actual validated indirect argument buffer and offset, including the extra two
  DWORD root constants used by D3D12 signatures when vertex/instance indices are
  needed. Multi-draw also includes its optional four-byte count input.
- Read flags from currently bound sampled/storage/external textures, resource
  tables and the current pipeline's framebuffer-fetch flag. A texture read in a
  different draw no longer marks every draw in the pass as texture-dependent.
- No-op direct draws and zero-count multi-draws emit no dependency notification.
- Explicit execution-error notification invalidates speculative provenance after
  backend recording, command-list execution, serial/recycle or reopen failures.
  A failed pending overwrite must not make old data eligible for raw reads.

The error callback currently fails closed for the device's readback controller;
it does not roll back metadata or implement recovery. Early API validation errors
do not enter these backend cleanup paths. Real queue-failure injection is still
required to verify the native wiring and error ordering.

Ranges cover **bound slices**, not exact fetched vertex/index elements or arbitrary
shader instruction accesses. Sampled and external texture dependencies remain
conservative. This is source preparation, not a successful GPU draw test.

## Evidence

| Check | Result | Boundary |
| --- | --- | --- |
| Chromium-flag syntax | Native command buffer, queue and observer units passed, no diagnostics | No linking or native execution |
| Source replay | Ten ordered packets, 70 paths; extension reverse verified | Existing Chromium checkout unchanged |
| CPU normal / ASan | 4,969,123 assertions each, including explicit execution-error invalidation | Synthetic handles; not native queue-failure injection |
| Extracted stride calculation | 32 assertions in normal and ASan modes | Synthetic pipeline flags; not real D3D12 signatures or draws |
| Full Python baseline | 5112 passed, 1 skipped at `4420e6f` | Before this extension |

`stride_test.cc` contains the measured extracted lambda. The preparation record
binds its hash and the native source. No new GN files or dependencies are added;
combined GN was not repeated.

## Reproduce the CPU controller check

Requires the pinned source baseline, existing SDK/compiler and cached BoringSSL/
libc++ objects. It reconstructs the ten source packets into a fresh D: directory;
it does not build Dawn, execute draws or simulate a native queue exception.

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-render-ranges\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\render-ranges-fresh
```

## Required native tests

All six draw paths and bundles with nonzero binding/dynamic offsets; changed
pipelines/bind groups between draws; disjoint vertex/index slices; indirect
validation enabled/disabled; vertex/instance-index signature variants; multi-draw
count buffers and zero draws; texture-read/write-only stage visibility; framebuffer
fetch and resource tables. Verify dependency propagation through Dawn's internal
indirect validation compute, recording/submission failures, device loss and
default-disabled overhead. These are **not yet executed**.

Actual GPU output and the public copy/shader/PNG consistency gate must pass before
any compatible-protection claim. Chromium component linking, native callbacks,
runtime, privacy and production admission remain unverified.
