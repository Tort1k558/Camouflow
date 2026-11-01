# Glint Chromium 156 R8: coupled Audio lifetime cleanup

**Windows browser built. Selected native tests and browser admission pending.**

The [completed build](windows-build.json) executed **60 Siso steps in 16m 05.31s**;
the build stage including guards/GN took **21m 35.009s**. This was an incremental
R7-to-R8 transition, not a clean rebuild. All four official stages passed; the
receipt and measured runtime core are bound separately from the immutable recipe.
The selected native tests and independent browser QA are separate gates, not
proved by this build record.

Preserves all 129 R7 patches byte-for-byte and appends two Chromium-owned patches:

| Patch | Purpose |
| --- | --- |
| 0130 | Erase masker seed/cache and temporary digests, preserving output and copy/move behavior |
| 0131 | Single-owner completion resolver; erase captured seeds on completion, failure and teardown; reject late publication |

The full recipe passed 131 forward and reverse applications in disposable copies:
400 composed files matched; 270 upstream files were restored. The replay itself
did not modify the canonical checkout or preserved R7 runtime. Live transition
and build evidence remain separate. See [preparation](preparation.json).

The [full host regression](host-regression.json) passed **5581 tests / one skip**
on `fe5eb7a`, with unchanged inputs. It retains the earlier four target-order
failures and interrupted premature retry. This predates the public Audio lifecycle
CLI addition and is not native build/runtime evidence.

The two [source packets](../audio-context-ownership/README.md) also passed a combined
four-translation-unit syntax check with actual GN flags. Masker helpers passed
real BoringSSL/reference, ASan and separate injected-failure checks. These are not
execution of the linked browser or its new lifecycle tests.

The native verifier exposes `--target audio-lifecycle` for this exact candidate:
seven required cases, including six new tests and the strengthened allocation
budget test. `audio-math` remains a separate regression gate. Build Windows with
at most j4 and the unchanged 180 GiB free-space reserve. GN link-pool depth is one,
but partial controller sampling observed two linker processes; the cause and
final maxima are not established, so single-link execution is not guaranteed by
this record. The active build was not restarted to change scheduling. Execute
both native groups, affected browser event/promise/teardown checks and the unchanged
Audio compatibility/combined suites before considering integrated repair.

No Audio sample algorithm, tolerance or selector is changed. **Legacy Audio
fidelity/analyser/worklet mismatch remains unresolved.** External anti-bot,
device-cohort plausibility, privacy and production admission remain unproved.
