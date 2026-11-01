# Audio completion and iframe lifecycle

**R7 comparison baseline, not an R8 result or a Legacy Audio repair.**

| Fixture | Coverage per mode |
| --- | --- |
| Event / Promise | Two rates, three buffer lengths, ordinary and reentrant callbacks; same mutable buffer, unchanged input, exact repeat rejection |
| Pending iframe removal | Six cases; no completion event or fulfilled output within a bounded 150 ms window |
| Removal inside completion | Six cases; retained mutation and agreement with the Promise if delivered |
| Legacy allocation budget | Two rates, three attempts per case; reject before rendering, remain suspended |

The measured isolated collector passed **74 cases / 346 checks** across baseline,
legacy and math. Runtime/core, receipt and source postguards passed; all owned
runtimes closed. [Raw scoped observations and hashes](r7-observations.json).
The public validator revalidated those saved rows and the public JS fixture is
byte-identical to the measured one. The new public CLI has **not yet been run**;
its orchestration must also be exercised on the next independent runtime.

## Reproduce

Requires Windows, an existing pinned workspace, an independent receipted runtime
and the verified binding-close Playwright stage. Run only while the builder is
idle; this tool refuses the writable Chromium output. No download or deployment.

```powershell
.venv\Scripts\python.exe -B -m scripts.verify_native_audio_lifecycle `
  --workspace D:\Glint156Candidate `
  --candidate upstream-156-webgpu-r7 `
  --executable D:\GlintManagerQA\full-r7-runtime-qa-20261101-v2\runtime\chrome.exe `
  --driver-root D:\GlintManagerQA\full-r7-runtime-qa-20261101-v2\driver `
  --work-dir D:\GlintManagerQA\audio-lifecycle-new
```

For a built R8, select its exact candidate and independent runtime instead. The
tool reuses the existing guarded Audio configuration/startup and resource cleanup
paths; it does not alter the original compatibility collectors or their criteria.

The detach window does not prove all future scheduling. JS cannot prove native
seed erasure; the new native lifecycle tests must do that separately. Existing
Legacy fidelity/analyser/worklet disagreement remains unresolved even though these
lifecycle cases pass. No DSP quality, device cohort, privacy or production admission.
