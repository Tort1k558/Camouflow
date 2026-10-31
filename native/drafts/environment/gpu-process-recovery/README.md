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

## Not established

This is not the 001–116 candidate, protected-policy recovery, worker/iframe
recovery, a physical GPU reset/TDR, hardware-adapter certification or a general
application crash-recovery guarantee. The known protected WebGPU/PNG inconsistency
of the older runtime remains unchanged. New browser features, privacy and
production admission remain closed until their own full-runtime gates pass.
