# Audio completion and iframe lifecycle

**R8 public CLI passed; R7 comparison baseline preserved. Not a Legacy Audio repair.**

| Fixture | Coverage per mode |
| --- | --- |
| Event / Promise | Two rates, three buffer lengths, ordinary and reentrant callbacks; same mutable buffer, unchanged input, exact repeat rejection |
| Pending iframe removal | Six cases; no completion event or fulfilled output within a bounded 150 ms window |
| Removal inside completion | Six cases; retained mutation and agreement with the Promise if delivered |
| Legacy allocation budget | Two rates, three attempts per case; reject before rendering, remain suspended |

The R7 isolated collector passed **74 cases / 346 checks** across baseline,
legacy and math. Runtime/core, receipt and source postguards passed; all owned
runtimes closed. [Raw scoped observations and hashes](r7-observations.json).
The public validator revalidated those saved rows and the public JS fixture is
byte-identical to the measured one. That predecessor record does not claim the
public CLI executed on R7.

The [actual R8 public CLI run](../upstream-156-audio-r8/audio-lifecycle-observations.json)
also passed **74 cases / 346 checks** in 34.911 seconds on the independent R8
runtime. Baseline: 24/114; Legacy: 26/118; Math: 24/114 cases/checks.
Core/receipt/source, all runtime assets and the staged driver passed postguards;
all owned resources closed. The remaining browser suite and compatibility gates
are separate; this lifecycle pass does not repair Legacy fidelity.

## Reproduce

Requires Windows, an existing pinned workspace, an independent receipted runtime
and the verified binding-close Playwright stage. Run only while the builder is
idle; this tool refuses the writable Chromium output. No download or deployment.

```powershell
.venv\Scripts\python.exe -B -m scripts.verify_native_audio_lifecycle `
  --workspace D:\Glint156Candidate `
  --candidate upstream-156-audio-r8 `
  --executable D:\GlintManagerQA\full-r8-runtime-qa-20261101-v1\runtime\chrome.exe `
  --driver-root D:\GlintManagerQA\full-r8-runtime-qa-20261101-v1\driver `
  --work-dir D:\GlintManagerQA\audio-lifecycle-new
```

For another supported candidate, select its exact receipted independent runtime.
The tool reuses the existing guarded Audio configuration/startup and resource cleanup
paths; it does not alter the original compatibility collectors or their criteria.

The detach window does not prove all future scheduling. JS cannot prove native
seed erasure; the new native lifecycle tests must do that separately. Existing
Legacy fidelity/analyser/worklet disagreement remains unresolved even though these
lifecycle cases pass. No DSP quality, device cohort, privacy or production admission.
