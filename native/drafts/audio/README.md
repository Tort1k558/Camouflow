# Offline audio candidate

Unregistered and uncompiled. Helper and OfflineAudio API integration candidates
are prepared below; none is an enabled or verified browser protection.

`OfflineAudioMasker` takes an independently derived **audio** partition seed.
It must not reuse Canvas seed or touch a live AudioContext. The scalar candidate
uses domain-separated HMAC over a float's normalized bits and changes at most its
lowest mantissa bit. Equal stereo samples remain equal; repeat application is
intended to be idempotent. Signed silence, subnormals, non-finite values and
absolute amplitudes >= 1 retain their original bits. A fixed cache recomputes on
collision rather than aliasing samples; HMAC failure returns no value.

Eleven scalar/budget fixture definitions and four detached AudioBuffer fixtures
cover the candidate. None has compiled or executed. The detached adapter keeps
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
have **not executed**. Neither have the fifteen scalar/buffer fixture cases or
the integrated completion path. Event/Promise identity, bit compatibility,
numerical error, performance and real browser operation remain mandatory gates.

The 22-patch combined replay passed across 92 paths:
`canvas-audio-surface-guards-public-replay-v1.json` on D. This confirms source
composition and unchanged active sources/GN/receipt/browser core, not C++
compilation or Audio privacy. The existing Audio probe still measures only an
unprotected compatibility baseline unless a separate protected gate is added.
