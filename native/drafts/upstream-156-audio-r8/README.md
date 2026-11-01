# Glint Chromium 156 R8: coupled Audio lifetime cleanup

**Source recipe only. Not built, runtime-verified or admitted for production.**

Preserves all 129 R7 patches byte-for-byte and appends two Chromium-owned patches:

| Patch | Purpose |
| --- | --- |
| 0130 | Erase masker seed/cache and temporary digests, preserving output and copy/move behavior |
| 0131 | Single-owner completion resolver; erase captured seeds on completion, failure and teardown; reject late publication |

The full recipe passed 131 forward and reverse applications in disposable copies:
400 composed files matched; 270 upstream files were restored. Canonical checkout
and R7 runtime remain unchanged. See [preparation](preparation.json).

The two [source packets](../audio-context-ownership/README.md) also passed a combined
four-translation-unit syntax check with actual GN flags. Masker helpers passed
real BoringSSL/reference, ASan and separate injected-failure checks. These are not
execution of the linked browser or its new lifecycle tests.

The native verifier exposes `--target audio-lifecycle` for this exact candidate:
seven required cases, including six new tests and the strengthened allocation
budget test. `audio-math` remains a separate regression gate. Build Windows with
at most j4, one heavy link and the unchanged 180 GiB free-space reserve. Execute
both native groups, affected browser event/promise/teardown checks and the unchanged
Audio compatibility/combined suites before considering integrated repair.

No Audio sample algorithm, tolerance or selector is changed. **Legacy Audio
fidelity/analyser/worklet mismatch remains unresolved.** External anti-bot,
device-cohort plausibility, privacy and production admission remain unproved.
