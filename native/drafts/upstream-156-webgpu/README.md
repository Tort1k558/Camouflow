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
| Full Chromium binary for this variant | Compiled; core runtime/worker/surface checks pass | Protected WebGPU and legacy Audio compatibility fail; not admitted |

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

## Diagnose the completed binary

The runtime suite, worker/surface/GPU/audio/font diagnostics, unit batches,
Windows staging/packaging and upstream audit accept this explicit variant. They
still require its exact manifest, complete Chromium/V8/Dawn patch chain and measured
runtime receipt. A 001–076 receipt is not interchangeable with a 001–116 receipt.
Source inspection uses a disposable copy of the selected Git index, preserving
the real staged metadata even when a patched file returns to its original bytes.

The first completed browser is preserved independently. Its protected WebGPU
failure is diagnosed and corrected only in the separately measured
[revision-2 packet](../webgpu-srv-routing/README.md); this original candidate and
its observations are unchanged. Do not attribute revision-2 standalone results to
this browser.

After compilation, use an independently preserved runtime and fresh evidence
directories. For the owned WebGPU copy/shader/PNG consistency gate:

```powershell
.venv\Scripts\python.exe -m scripts.verify_native_webgpu_consistency --candidate upstream-156-webgpu --executable D:\Glint116QA\runtime\chrome.exe --driver-stage D:\Glint116QA\driver --work-dir D:\Glint116QA\consistency-run-1
```

The driver directory must already be prepared with the collector's pinned driver
manifest. This gate enables `GlintWebGPUPolicyTransportCandidate` **only** in the
new variant's protected test phase and checks the effective browser arguments.
The baseline phase and the older variant do not enable it. No production launch
configuration or readiness flag is changed by this diagnostic opt-in.

Historical source-bound observations retain their original hashes; the reversible
[tooling archive](../environment/webgpu-diagnostics-source-upgrade.json) reconstructs
their measured sources. New diagnostic code is not retroactively treated as having
passed those older browser runs. The narrow incremental builder remains restricted
to its original baseline; use the normal 180 GiB / j4 build path for this variant.
