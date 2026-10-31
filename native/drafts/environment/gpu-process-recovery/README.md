# Owned GPU-process recovery control

The public collector passed **three actual runs** on the independently preserved
Chromium 156 **001–076** runtime, with protected policies **off**.

| Check | Observed result |
| --- | --- |
| Before crash | Direct pixels, shader output and decoded PNG match the exact reference |
| Fault | `Browser.crashGpuProcess` sent to the owned browser's CDP session |
| Existing device | One `device.lost` callback, reason `unknown` |
| Existing buffer | Mapping rejects with `AbortError`; state remains `unmapped` |
| Document | Marker and URL preserved; zero page crashes |
| After crash | New WebGPU device renders the same reference through all three paths |
| Cleanup | All 269 runtime assets unchanged, pinned driver and receipt unchanged, no owned processes/profiles remain |

[`observations.json`](observations.json) binds the collector, watcher, shared probe
and supporting sources. Its complete 226-input snapshot digest retains the scope
of the private raw reports, without publishing local machine paths.

## Reproduce

Use the existing project virtualenv, an independently preserved runtime with its
valid build receipt, and the project's exact pinned driver stage:

```powershell
python native/drafts/environment/gpu-process-recovery/collect.py `
  --candidate upstream-156 `
  --executable D:\packages\runtime\chrome.exe `
  --driver-stage D:\qa\driver `
  --work-dir D:\qa\fresh-gpu-recovery
```

The work directory must not exist. Canonical D: paths, an idle selected runtime
and driver, at least 2 GiB disk space and 4 GiB available RAM are required. The
collector refuses Chromium build-output paths and Python optimization. It uses
only a fresh profile and an owned loopback page, not user sessions or accounts.
No global GPU reset, process kill or security setting change is performed.

## Independent ready-mode extension

[`ready-mode.patch`](ready-mode.patch) extends a disposable source checkout, not
the measured baseline collector. It requires explicit `--mode baseline|ready`,
uses the existing partitioning/transport helpers and checks effective browser
arguments. The new transport feature is requested only for the explicit
`upstream-156-webgpu` ready phase with a matching receipt.

The [extension control](ready-mode-observations.json) ran both modes on preserved
001–076. Baseline passed. Ready recovered the document and retained the same
pixels after GPU crash, but PNG still differed from direct/shader output in
**384 channels by one level** for this profile. That gate correctly **failed**.
This is not repaired protected WebGPU delivery or latest-candidate admission.

Apply only in an independent source checkout on D:, after verifying its base hash:

```powershell
git -c core.autocrlf=false apply --directory=native/drafts/environment/gpu-process-recovery native/drafts/environment/gpu-process-recovery/ready-mode.patch
```

Verify the resulting collector hash before execution. These controls used a fresh
Windows LF checkout; the three baseline runs above used the original measured
working-tree layout. Source archives preserve both, without changing observations.

## Remaining boundaries

This is not the 001–116 candidate, protected-policy recovery, worker/iframe
recovery, a physical GPU reset/TDR, hardware-adapter certification or a general
application crash-recovery guarantee. The known protected WebGPU/PNG inconsistency
of the older runtime remains unchanged. New browser features, privacy and
production admission remain closed until their own full-runtime gates pass.
