# Compressor math experiment

## 001–067 native fixture failure

The first 18-target native batch passed 17 groups but failed the AudioMath group.
Its float fixture used Audio seed `3`, identical to its WebGPU seed `3`.
`HasIndependentSurfaceSeeds` correctly rejected that policy; later node creation
with `ASSERT_NO_EXCEPTION` aborted the test process. That does not establish an
AudioMath DSP failure or a successful runtime gate.

[`audio_math_fixture_readiness.patch`](audio_math_fixture_readiness.patch) is an
**unregistered fixture-only repair**, prepared against 001–067. Seed `10` selects
the same float backend without colliding with Canvas/WebGL/WebGPU seeds 1/2/3;
native seed `4` is unchanged. The fixture now verifies actual document readiness,
and a new negative case requires duplicate-seed rejection before node/resolver
creation. All 11 existing cases are retained: the proposed gate becomes 12.
Isolated apply-check and HMAC vectors passed. The draft has not been compiled,
executed, selected in the source manifest or used to admit a capability.

## Actual Audio-v1 fidelity failure on 156

The calibrated 54-graph fixture passed **54/54** with Glint policy off. With
profile-identity Audio-v1 enabled, **42/54** passed; identity and half-gain
graphs failed (12 rows across two sample rates and three repetitions).
Repeated reads remained stable, copy mutation controls passed, resources closed
and source/core postguards passed. This is one owned profile/Windows host, not
all possible keys or device cohorts. It demonstrates why readback perturbation
cannot be admitted from fingerprint isolation or SNR checks alone. No flat-buffer
exception was added and AudioMath remains unselected/unverified at browser level.

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

**Fresh 156 stock control:** Glint-off → official CfT → Glint-off, 15 cases ×
three repetitions per phase = **135 captures**. All outputs were bit-exact, with
unchanged event/Promise buffer identity and closed Audio contexts. CfT reported
the exact upstream Git revision; Glint is bound by its compiled receipt/core
hashes because the current non-official GN build emits a dummy CDP stamp.
[Source-bound results and retained incomplete attempts](matched-stock-observations.json).

The float32 prototype matched 12 non-discriminating cases, **not** the other
three stock cases. This is not evidence that its variant represents an ordinary
device cohort; do not promote that mode from these baseline measurements.

### Broader Audio fidelity fixtures

[`audio-fidelity-control.js`](audio-fidelity-control.js) covers nine graph kinds
at 44.1/48 kHz: silence, identity, half gain, impulse, isolated stereo, positive
and negative constants, triangle oscillator and compressor. Three repetitions
also check whole/repeated/37-frame segmented reads, `copyFromChannel`,
`copyToChannel`, completion-buffer identity and closed state.

Two independent **official stock156** runs passed 54 renders each, with equal
channel hashes. Four fault-injection controls rejected wrong constant references,
segment/mutation offsets and unstable oscillator output. Known signals are
checked exactly; oscillator/compressor output is only checked for finite,
nonzero, repeatable samples, not theoretical DSP correctness.
[Scoped calibration](audio-fidelity-observations.json).

Evaluate the file on an owned secure/localhost page with Playwright:

```python
probe = Path("native/drafts/audio-dsp-math-v2/audio-fidelity-control.js")
result = await page.evaluate(probe.read_text(encoding="utf-8-sig"))
assert result["passed"]
```

These new fixtures have **not yet run against Glint policies or AudioMath 0068**.
They do not cover realtime playback, AudioWorklet, AnalyserNode or audible quality.

### Reproduce the browser gate

[`browser_matrix.py`](browser_matrix.py) is the public, source-bound runner.
Use the official CfT executable described by
[`stock-control-observations.json`](../upstream-156/stock-control-observations.json),
an exact source-build Native receipt and a fresh output directory:

```powershell
.venv\Scripts\python.exe native/drafts/audio-dsp-math-v2/browser_matrix.py `
  --native-executable D:\Glint156Candidate\chromium\src\out\CamouFlowNative\chrome.exe `
  --stock-executable D:\Glint156Candidate\stock-control156-20261029-v4\payload\chrome-win64\chrome.exe `
  --output D:\Glint156Candidate\audio-new-run `
  --allow-native-dummy-revision
```

The last flag is **explicit acknowledgement of the published native checkpoint**,
not a generic revision bypass. Other builds require a real runtime Git stamp;
do not use the flag to admit unknown binaries. Receipt, core DLLs, GN arguments,
manifest/patches, probe and relevant project-source inputs are checked. A wrong
stock binary rejects before browser launch. Numerical mismatch/nondeterminism
fails the exact-bit gate; there is no retry, silent substitution or zero-sample fallback.

Each phase owns a **fresh** profile, so A/B/A repeat stability is not persistent
profile-restart evidence. Raw channel-major little-endian `.f32` data and failed
observations remain under the owned D: output; existing output is never replaced.
These directories contain private fixture keys: do not commit/share their profiles.

The public CLI repeated all **135 captures**, matching prior case hashes, and
passed five rejection controls: wrong stock role, unacknowledged dummy revision,
existing output, a non-D output and output inside a source checkout (synthetic
layout control). [CLI proof](browser-cli-observations.json).
The runner requires an idle scoped native builder. An earlier attempt hit the
10-second navigation deadline while linking was active; its failed report is
retained, the deadline was not increased, and the cause is not proven.
This binds core code, not complete installed-payload integrity, protected policies,
device-cohort plausibility or production admission. Use the old control only on
owned fixtures, not for regular/account browsing.

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

Next: math-mode browser execution; more graph/parameter families and special
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
Matched 156 calibration: `D:\Glint156Candidate\audio156-matched-aba-20261029-v3`;
official stock control: `D:\Glint156Candidate\stock-control156-20261029-v4`.
Earlier failed adapter/link experiments and the initial power-category failure
remain retained separately. The active 156 build's 201 input hashes stayed unchanged.
