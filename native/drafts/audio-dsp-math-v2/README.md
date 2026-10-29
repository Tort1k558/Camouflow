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

### Unselected AudioContext integration

[0068](0068-native-audio-math-context-candidate.patch) targets **156.0.8078.36
after selected patches 001–065**. It does not depend on the separate 157-only
0066/0067 fixtures and is not part of either engine manifest.

| Prepared behavior | Boundary |
| --- | --- |
| Capture one const mode or error in the BaseAudioContext constructor | Not a process-global backend, lazy lookup or per-read random choice |
| Domain-separated HMAC of the existing Audio surface seed selects native/float32 math | Two experimental backends, not a real-device identity database |
| Compressor nodes pass the captured policy to their own processor | No new key/seed wire format; no public manager capability |
| Math-only offline rendering bypasses v1 post-read farbling | Missing policy still fails; no raw-result fallback |
| Eleven native fixtures cover capture, errors, context/handler isolation, literal DC, stopped-context precedence, frame detach and navigation | Test translation unit compiled; **not linked or executed** |

`GlintAudioMathCandidate` is **disabled by default**. The legacy branch preserves
the old readback path. Enabled contexts keep only the selected mode/error; the
local seed copy and derivation digest are cleansed after selection. This does
not prove operating-system memory sanitization or all-context lifetime safety.

[The descriptor](context-integration.json) binds the base manifest, patch,
before/after files and nine additional pristine inputs. A full isolated replay
of **65 selected patches + this draft** passed on **194 pinned source files**,
including GPU ordinal/GRIT checks. All 201 active-build inputs remained unchanged.
Seven isolated objects then compiled with the existing Chromium flags and a
private source/header overlay, serially at below-normal priority. Six production
objects initially passed; the test object exposed `destination()` instead of the
pinned C++ `destinationNode()` API. After correcting it and adding handler-backend
assertions, all seven compiled. Failed evidence is retained; no suppression or
compiler-flag workaround was added.
The earlier seven-fixture revision passed the full local Python regression:
**3,591 passed, one skipped** (297.61 seconds). That run predates the constructor
capture update and does not execute the native fixtures.
Current release-tool validators passed **1,074 tests, one skipped** (43.54 seconds).

Constructor capture replaces the initial lazy policy lookup. Real same-host
stock/Glint-off 148 controls (three repetitions each) allowed compressor creation
both after `AudioContext.close()` and on a retained OfflineAudioContext after its
iframe was removed. The latter still reported `suspended`, not `closed`.
Late seed lookup can therefore reject a previously legal node when its document
has disappeared; selection must happen while the creation document is available.
The immutable result survives teardown/navigation; new contexts capture the new
document policy independently. This also requires policy readiness at creation
and needs constructor-cost measurement before admission.

The [JS control](audio-context-lifecycle-control.js) and
[six baseline captures](audio-context-lifecycle-observations.json) are hash-bound.
They **do not execute the new 156 math policy** or prove its lifecycle correctness.

This is **not a complete GN build, link, native execution or runtime admission**.
The overlay does not verify graph/dependency completeness or every consumer of
the changed class layouts. Existing matrix/browser evidence above still measures the previous
standalone prototype/native baseline, not this integration.

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
Context integration evidence: `D:\Glint156Candidate\audio-math-context-full-replay-20261029-v6`
and `audio-math-context-objects-20261029-v5`; failed object evidence remains in v2.
Lifecycle baseline: `D:\Glint157ObjectCache\audio-context-lifecycle148-20261029-v1`.
Earlier failed adapter/link experiments and the initial power-category failure
remain retained separately. The active 156 build's 201 input hashes stayed unchanged.
