# Offline audio candidate

Unregistered. The scalar/budget helper has passed isolated native compilation;
the Blink adapter and OfflineAudio API integration remain uncompiled. None is
an enabled or verified browser protection.

`OfflineAudioMasker` takes an independently derived **audio** partition seed.
It must not reuse Canvas seed or touch a live AudioContext. The scalar candidate
uses domain-separated HMAC over a float's normalized bits and changes at most its
lowest mantissa bit. Equal stereo samples remain equal; repeat application is
intended to be idempotent. Signed silence, subnormals, non-finite values and
absolute amplitudes >= 1 retain their original bits. A fixed cache recomputes on
collision rather than aliasing samples; HMAC failure returns no value.

Thirteen scalar/budget fixture definitions and four detached AudioBuffer fixtures
cover the candidate. All thirteen scalar/budget cases compiled and executed;
the four detached AudioBuffer cases have not. The detached adapter keeps
the original channels untouched, preserves format and normal result mutability,
caps the additional sample allocation at 64 MiB with overflow-safe arithmetic,
and returns no result on invalid views/allocation/transform failure. A caller
must not expose a partial copy or fall back to unprotected output.
Required before an API hook: exact numerical/NaN compatibility, cache/error tests,
performance and audible-compatibility measurements, dedicated audio seed delivery
to documents/workers, and detached offline-result ownership before both event and
Promise exposure. Modifying getChannelData's live backing array or returning an
unconnected copy would break WebAudio mutation semantics and is not proposed.

This does not cover analyser APIs, sample-rate emulation, real-time audio, complete
audio fingerprint protection or undetectability. It deliberately leaves many
values unchanged and may itself introduce detectable statistical patterns.

`audio_helpers_integration.patch` adds helpers and fixtures to Blink module GN
targets without connecting an API hook. It replayed with the GPU and policy
batch in an isolated overlay; active Chromium sources remained unchanged.

## Diagnostic baseline

`scripts/verify_native_audio.py` measures repeat/restart hashes, equal stereo
channels, event/Promise result identity, live getChannelData mutation,
copyFromChannel/copyToChannel visibility, silence, format and IndexSizeError.
The unprotected 001-027 binary passed initial/restart phases in five document
contexts. Dedicated/shared/service workers correctly reported API unavailable,
not passing Audio protection. Evidence: `audio-001-027-baseline-v2.json` on D.

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_audio.py `
  --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe `
  --work-dir D:\CamouFlowNative\audio-checks --report D:\CamouFlowNative\audio-new.json
```

This is an unprotected compatibility baseline, not evidence that the C++
candidate works. Reports retain `privacy_admitted: false`.

## OfflineAudio API candidate

`offline_audio_surface_hook.patch` captures the independent audio seed at
`startRendering`, after upstream stopped/running/duplicate-start validation but
before a Promise resolver, destination allocation or rendering thread starts.
Missing/invalid required policy rejects instead of using raw output. A protected
copy exceeding the 64-MiB additional allocation budget rejects at this point.
Flag-off contexts keep the original behavior and allocation limits.

Completion never re-queries the current document's policy. It transforms one
detached buffer using the captured snapshot **before** exposing it to either
`oncomplete` or the Promise. Both receive the same normally mutable AudioBuffer;
an event-listener mutation remains visible to the Promise as in upstream.
Copy/transform failure rejects the Promise without a completion event or raw
fallback, then reaches the existing common cleanup. Realtime audio, analyser
APIs and sample-rate behavior are unchanged and not protected by this candidate.

`offline_audio_surface_guard_tests.patch` prepares two native fixtures checking
missing-policy and allocation-budget rejection before a resolver/thread. They
have **not executed**. Neither have the four detached-buffer fixture cases or
the integrated completion path. Event/Promise identity, bit compatibility,
numerical error, performance and real browser operation remain mandatory gates.

The 22-patch combined replay passed across 92 paths:
`canvas-audio-surface-guards-public-replay-v1.json` on D. This confirms source
composition and unchanged active sources/GN/receipt/browser core, not C++
compilation or Audio privacy.

## Native scalar evidence

`audio-scalar-public-native-v2.json` on D records **13/13 actual C++ Gtest
cases passed**, with exact case names independently checked. This used the
pinned checkout's clang-cl, real built BoringSSL objects and its actual libc++
verbose-abort dependency copied to an isolated temporary directory. The scalar
and Gtest translation units use the VS standard library; this is not a full
Chromium ABI or Blink integration check. No crypto replacement or stub was used.

The checks cover exceptional float bits, signed silence, subnormals, peaks,
one-bit bounds, idempotence, equal stereo samples, different seeds, cache
collisions and allocation-budget arithmetic. Two additional cases verify six
independently calculated HMAC vectors and the one-bit bound plus **130-dB SNR**
on a 4096-sample generated signal. This numerical scalar check does not measure
WebAudio rendering, audible compatibility or runtime performance.
Canonical sources, original crypto
objects, active browser binaries and GN settings remained unchanged.
`privacy_admitted` remains **false**. Failed v1/v2 probe logs are retained;
they were toolchain/archive-linking failures, not passing runtime evidence.

The public repeatable gate snapshots actual COFF `.obj` and assembly `.o`
members from both existing BoringSSL archives; all members must be measured,
ordinary files inside their source directory. It records hashes of compiler,
linker, headers, fixtures, dependencies and active runtime/GN. All thirteen
exact case names must complete; skipped, duplicate or foreign cases fail.
Compilation happens in an owned temporary folder, not the active build output.

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_audio_scalar.py `
  --workspace D:\CamouFlowNative `
  --vs-installation D:\CamouFlowNative\toolchain\BuildTools `
  --report D:\CamouFlowNative\audio-scalar-new.json
```

Requires the pinned checkout's previously built BoringSSL and libc++ abort
objects; the gate does not launch another Chromium builder or download tools.

The integration patch includes the updated fixtures. The initial full replay
against registered 001-036 failed because the historical reversal omitted
follow-ups 0035/0036. The corrected verifier reverses the complete reviewed
chain, proves an exact registered-source round trip, applies current candidates
and reapplies those follow-ups. Unknown successors are rejected.
`audio-scalar-quality-public-replay-v2.json` passed across **125 paths**, with
canonical candidate equality and unchanged active source/browser/GN guards.
This proves source composition only, not integrated compilation or runtime.

## Prepared numerical runtime gate

`scripts/verify_native_surfaces.py` combines Canvas and Audio in one owned run
for two independent protected profiles, baseline, restarts and missing-policy
rejection. It rejects the old browser before launch. Protected runtime results
have **not been obtained**.

`scripts/verify_native_audio_quality.py` checks 4096 actual float32 sample bits
against their measured SHA-256, then compares protected and baseline signals.
Only one least-significant mantissa bit may change; signed silence, subnormals
and samples at/above unit magnitude remain exact. Unchanged nonzero output is
not masking. The signal must satisfy a 130-dB SNR budget. Reports retain changed
sample count, maximum absolute error, SNR and measured render durations.
Durations are observations, not a passing performance threshold.

The baseline command accepts `--sample-quality` to retain bits and timings
without enabling protection. The existing 001–027 browser passed this capture
in five document contexts over initial/restart phases: 30 measured offline
renders plus ten independent completion-listener mutation checks. The mutation
must be visible through the Promise's buffer; quality signals are not modified
by this separate check. Sample hashes and API semantics stayed stable.
Measured render durations were 1.1–17 ms (median 1.75 ms) during the concurrent j4 build; this is an
**unprotected baseline**, not transform overhead or a portable performance claim.
Evidence: `audio-001-027-quality-baseline-v4.json` on D.

Realtime playback/analyser quality, longer clips,
protected completion-listener mutation and full workload performance remain
separate gates. Python validator fixtures do not execute the C++ transform.
