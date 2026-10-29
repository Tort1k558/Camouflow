# Audio compatibility fixtures

| Probe | Required coverage |
| --- | --- |
| Fidelity | 54 cases: nine graphs, two sample rates, three repetitions |
| Analyser | 12 cases: time/frequency reads, buffer agreement, array bounds and native errors |
| AudioWorklet | 12 cases: frame coverage, sample rate/timeline, exact pass-through and source immutability |
| Realtime | 11 checks: trusted activation, muted output, compressor/analyser and close lifecycle |

The reusable implementation passed against pinned official Chrome 156 on Windows.
That calibrates the diagnostic, **not Glint AudioMath or a hardware cohort**.
See [source-bound reference evidence](stock156-observations.json).

## Run against the selected Glint candidate

After the build and native AudioMath unit gate finish, from the repository root:

```powershell
New-Item -ItemType Directory -Path D:\GlintQA -Force
$env:CAMOUFLOW_DATA_DIR = 'D:\GlintQA\audio-data'
.venv\Scripts\python.exe -m scripts.verify_native_audio_compatibility `
  --workspace D:\Glint156Candidate `
  --executable D:\Glint156Candidate\chromium\src\out\CamouFlowNative\chrome.exe `
  --work-dir D:\GlintQA\audio67-first `
  --candidate upstream-156 --mode baseline --mode legacy --mode math
```

The evidence directory must be new. The gate validates the complete build receipt,
runtime cores, recipe and real revision stamp. A live builder is rejected before
profiles are created. Profiles and their private keys remain outside the checkout.

Legacy and math runs reuse one owned protected profile. Every requested mode runs
all four probes; failures are retained, not converted to successful skips. Any
failed requested mode makes the command return nonzero. The known legacy Audio-v1
failure is **not** excused by a passing math-only run. No mode grants privacy,
device-cohort, full audio-quality or release admission.

The worklet module uses an actual owned loopback HTTP server; it does not depend
on Playwright interception of worklet fetches. Realtime output is muted and uses
the native sample rate. No microphone, account or external page is involved.
