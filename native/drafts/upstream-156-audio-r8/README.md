# Glint Chromium 156 R8: coupled Audio lifetime cleanup

**Windows browser built; all 26 native groups passed. Full browser admission pending.**

The [full native retry](native-all-observations.json) passed **554 executions /
397 distinct tests** over six test binaries, with final source/core/receipt,
SDK/GN and executable guards. Shared contract cases explain the larger execution
count. Its incremental test build took 71 Siso steps / 10m 27.38s, configured j4.
The original low-space rejection and earlier 135-case subset remain separate
historical records; this does not admit the full browser or repair Legacy Audio.

[Controlled browser rechecks](controlled-rechecks.json) passed hardware controls
R7 → R8 → R7 (nine checks each), eight fixture-AI workflow checks and both GPU
recovery modes. The unchanged GPU collector received its missing `watch.js`;
the AI result was validated from the public CLI's JSON stdout. The private
controller's incorrect report-file expectation and earlier failed attempts remain
recorded. Effective broader coverage is 14/14 named groups across attempts,
not a fresh full-suite pass. The hardware timeout root cause remains unknown;
its ten-second deadline was not changed. Legacy Audio and full admission stay open.

The [completed build](windows-build.json) executed **60 Siso steps in 16m 05.31s**;
the build stage including guards/GN took **21m 35.009s**. This was an incremental
R7-to-R8 transition, not a clean rebuild. All four official stages passed; the
receipt and measured runtime core are bound separately from the immutable recipe.
The [selected native batch](native-selected-observations.json) subsequently
passed all five groups: Audio lifecycle 7, AudioMath 12, surface launch 41,
identity transport 20 and worker surfaces 55. Final source/core/receipt/GN/SDK and
test-binary guards passed. Building the two test executables took 1034 Siso steps
in **1h 13m 44.78s**; this is not the browser build time. All-target native and
independent browser QA remain separate gates, not proved by these selected cases.

The terminal whole-controller observer sampled up to five compiler processes and
two linkers despite configured j4 and link-pool depth one. It does not establish
action attribution or an instantaneous scheduling guarantee; no limit was raised.
Keep the immutable partial browser-build resource record separate from this
completed controller observation.

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
budget test; all seven now passed in the linked test executable. `audio-math`
passed its separate 12-case regression gate. Build Windows with
at most j4 and the unchanged 180 GiB free-space reserve. GN link-pool depth is one,
but partial controller sampling observed two linker processes; the cause and
final maxima are not established, so single-link execution is not guaranteed by
this record. The active build was not restarted to change scheduling. Execute
both native groups, affected browser event/promise/teardown checks and the unchanged
Audio compatibility/combined suites before considering integrated repair.

No Audio sample algorithm, tolerance or selector is changed. **Legacy Audio
fidelity/analyser/worklet mismatch remains unresolved.** External anti-bot,
device-cohort plausibility, privacy and production admission remain unproved.
