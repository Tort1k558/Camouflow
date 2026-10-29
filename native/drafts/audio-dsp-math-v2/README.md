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

## Expanded signal/parameter matrix

[15 explicit configurations](cases.json) passed the isolated C++ checks and
**90 policy-off stock/Glint 148 browser captures** on the same Windows host.
All browser outputs exactly match the native calculation; all closed contexts
preserve completion-event/Promise buffer identity. This does **not** execute
the float32 variant in a browser or represent 90 independent devices.

| Controls | Coverage |
| --- | --- |
| Random, silence, constant, impulses, buffered triangle, attack/release bursts | Generated AudioBuffer inputs; not OscillatorNode spectra |
| Mono and independent stereo | 44100, 48000 and 96000 Hz |
| Compressed constant, ratio one, fast attack, zero release | Explicit compressor parameters, including legal zero endpoints |
| Direct constant, negative quarter, positive/negative zero | Literal sample controls with no compressor |
| Partial last render block | 8193 frames, with zero-padded internal processing |

The float32 calculation differs in **only 3/15 cases**, by at most `2.98e-8`.
Do not force variation in the other cases or infer fingerprint uniqueness.
[Compact observations](matrix-observations.json) retain hashes and results;
full raw samples and process records stay on D. Eight malformed driver commands
were rejected before writing samples. The matrix runner uses a separate process
and directory for every case, collecting failures rather than hiding them.

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

For the complete matrix, use `matrix.py` instead of `probe.py` with the same
arguments and a different fresh output directory. Its case manifest rejects
missing fields, unknown signals, invalid ranges and duplicate IDs; these are
workbench bounds, not a claim about the complete Web Audio API limits.
The [matrix browser control](compressor-matrix-control.js) accepts one explicit
case at a time. Browser calibration still needs an independently verified
runtime; running the C++ matrix alone cannot grant admission.

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
Matrix evidence: `public-compressor-full-matrix-20261029-v2`,
`compressor-matrix148-20261029-v1` and `compressor-matrix-driver-negatives-20261029-v1`
under the same cache directory.
Earlier failed adapter/link experiments and the initial power-category failure
remain retained separately. The active 156 build's 201 input hashes stayed unchanged.
