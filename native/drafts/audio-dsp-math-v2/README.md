# Compressor math experiment

**Windows-only, unselected prototype. Not a shipped profile option or a verified device cohort.**

Instead of changing completed samples, an immutable, instance-owned
`CompressorMathPolicy` selects existing fdlibm/CRT calculations at four nonlinear
compressor call sites. Unknown selectors are rejected; no process-global backend,
profile-key mapping, platform emulation or renderer transport is installed.

The workbench copies the complete pinned 148/156 compressor algorithms into a
fresh D: directory, preserving upstream notices. Small std-container adapters
replace Blink infrastructure. The linked fdlibm object is copied, not rebuilt or
modified. No Chromium source files or binaries are committed here.

## Measured result

One mono pseudorandom input, stereo output, 8192 frames at 44100 Hz.
[Exact source and evidence bindings](observations.json).

| Check | Result |
| --- | --- |
| Copied 148 versus 156 native calculation | Bit-identical |
| Stock/Glint 148 policy-off browser calibration | All 6 captures exactly match the prototype |
| Float32 variant versus native | 2 of 16,384 channel samples differ; one frame duplicated into stereo |
| Maximum absolute / RMS difference | `2.98e-8` / `3.29e-10` |
| Processing blocks of 32, 64, 128, 256 and 8192 frames | Identical within each backend; not arbitrary-boundary coverage |
| Interleaved independent instances | No difference from isolated processing |
| Explicit selector checks | 1025 values; only 0/1 accepted |
| Power-function special-value categories | Initial 5 mismatches corrected; 72 checked pairs now agree |
| Tool barriers | Existing output, source drift and invalid COFF object rejected |

The correction explicitly preserves fdlibm's unit-base power rules, rather than
silently dispatching a float32 request to another backend. NaN payloads, errno
and floating-point exception flags are **not** covered by category equality.

## Reproduce

Run from the repository root with the pinned source trees and a trusted existing
156 fdlibm object. Use a **new** output directory outside both checkouts:

```powershell
.venv\Scripts\python.exe native\drafts\audio-dsp-math-v2\probe.py `
  --source-156 D:\Glint156Candidate\chromium\src `
  --source-148 D:\CamouFlowNative\chromium\src `
  --fdlibm-object D:\Glint156Candidate\chromium\src\out\CamouFlowNative\obj\third_party\fdlibm\fdlibm\ieee754.obj `
  --vs-installation D:\CamouFlowNative\toolchain\BuildTools `
  --output D:\GlintDspExperiment
```

Exit zero means the isolated experiment completed, **not compatibility admission**.
Reports, logs, temporary compiler files and generated samples stay in that D:
directory. The [browser control](compressor-control.js) returns only its own
generated graph's samples; it must be run on a controlled local page.

## Still required

The float32 output has **not** been observed as a real device cohort. A changed
hash is not evidence of ordinary-browser plausibility. The experiment does not
repair or admit Audio-v1 farbling, and is not a complete Audio identity model.

Next: matched fresh-156 calibration; more graph/parameter families and special
values; empirical reference devices; profile/context capture and transport;
real-time audio, broader Audio APIs, audible quality and performance. No new
capability may be enabled from these measurements alone.

Local evidence: `D:\Glint157ObjectCache\public-compressor-math-prototype-20261029-v6`,
`compressor-baseline148-20261029-v1`, `compressor-workbench-negatives-20261029-v1`.
Earlier failed adapter/link experiments and the initial power-category failure
remain retained separately. The active 156 build's 201 input hashes stayed unchanged.
