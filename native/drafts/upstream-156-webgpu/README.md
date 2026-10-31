# Full Chromium 156 WebGPU candidate — not admitted

This explicit build variant combines the **001–076 baseline** with **30 WebGPU
draft packets**, split by Chromium/Dawn repository into **116 numbered patches**.
The existing `upstream-156` candidate remains unchanged and is still the default
156 research selection. Both variants retain the same pinned revisions, 180 GiB
normal build reserve and maximum four workers.

| Evidence | Result | Boundary |
| --- | --- | --- |
| Complete source replay and reverse | 116/116 each; 268 upstream files restored | Not compilation |
| Composed WebGPU source comparison | All 88 paths matched the measured 29-packet batch plus capture-retention correction | Includes expected absent paths |
| Standalone native/Wire tests | See [hardware matrix](../webgpu-capture-retention/README.md) | Not Chromium renderer/shared-memory integration |
| Full Chromium binary for this variant | Not built or admitted | Do not reuse the 001–076 runtime results |

`manifest.json` records the original draft hashes and their derived patch files.
Dawn is pinned separately to its Chromium DEPS revision. Chromium/V8/Dawn patches
are applied and checked in their own repositories.

## Verify source context

```powershell
$candidate = (Resolve-Path native\drafts\upstream-156-webgpu).Path
.venv\Scripts\python.exe scripts\fetch_native_rebase_sources.py --manifest "$candidate\manifest.json" --output D:\GlintWebGPUUpstream
.venv\Scripts\python.exe scripts\verify_native_rebase_draft.py --source D:\GlintWebGPUUpstream --output D:\GlintWebGPUReplay --manifest "$candidate\manifest.json" --patch-directory "$candidate\patches"
```

The normal build command explicitly selects `--candidate upstream-156-webgpu`.
The checkout family can reuse the existing pinned `upstream-156` workspace, but
sync/hooks receipts remain bound to the exact variant manifest. A patched baseline
must be preserved and cleanly transitioned before sync; the builder refuses dirty
or partially applied input rather than resetting it. Never rewrite stage receipts
to bypass these checks. Do not run a browser from the writable build directory.

No runtime selection, policy readiness, packaging or production admission is
granted by this source preparation. Preserve the independent 001–076 runtime and
the separately retained Chromium 148 rollback package before building.
