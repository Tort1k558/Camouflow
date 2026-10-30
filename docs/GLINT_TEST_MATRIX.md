# Glint browser test matrix

## Current compiled 001–073 — 2026-10-30

**Selected source is now 001–074; compiled/qualified baseline remains 001–073.**
Latest full Python includes the nested HDR selector: **4608 passed, 1 skipped**,
382s, source/status guards passed at `1c9afd2`.
[Evidence](../native/drafts/environment/canonical-python74-nested-hdr-observations.json).
This does not compile 074 or execute its six new C++ cases.
Full Python after the storage and historical-binding repairs: **4593 passed, 1 skipped**,
398s; source/status guards passed at `bc66849`. This precedes the HDR selector added next.
[Full pass](../native/drafts/environment/canonical-python74-storage-repair-observations.json).

The shared nested collector now supports explicit `--probe formats` (default) and
`--probe finite-hdr`, with no fallback or duplicated runtime/cleanup pipeline. Both exact
public variants passed on frozen 073: **64 format cases / 8 finite HDR cases per profile/phase**,
four parent-child types, two worker creations and browser restart. Finite HDR covers the
bounded negative/HDR/subnormal/alpha/crop/re-put fixture, not general editor quality.
Targeted selector/HDR/storage tests: **88 passed**.
[Formats](../native/drafts/environment/nested-formats73-probe-selector-observations.json),
[HDR](../native/drafts/environment/nested-hdr73-observations.json).
Initial nested-probe evidence remains unchanged and bound to its reconstructed earlier collector.
Nested dedicated-worker follow-up on preserved 073 passed: four classic/module parent-child
paths, **64 Offscreen Canvas cases per profile/phase**, two worker creations per path,
baseline/protected profiles and browser restart. Document coherence, effect, repeated reads,
identity-file postguards and observed-process cleanup passed. This does not qualify selected
074, nested GPU/Audio, shared/service parents or arbitrary nesting depth.
[Exact public probe evidence](../native/drafts/environment/nested-formats73-observations.json),
[collector](../native/drafts/environment/first-script/nested_formats_runtime.py).

Full Python after the storage fix: **4576 passed, 4 failed, 1 skipped**, source/status guards
passed and both QML cases passed. All failures bind historical runtime records to the old
storage source. A reversible test-only patch reconstructs that source; no old observations
are rewritten. Targeted TLS/GPU/environment/storage follow-up: **605 passed**; nested probe
validator/server/evidence tests: **13 passed**. Full regression after this repair remains open.
[Retained failures](../native/drafts/environment/canonical-python74-storage-history-failure-observations.json).
Storage follow-up fixes a reproduced same-process Windows accounts read/replace race:
before, 214 empty reads and 247 failed writes; after, **500/500 writes, zero errors/empty reads**.
Accounts/settings readers share the existing writer RLock; no retry or deadline relaxation.
Targeted storage/QML: **56 passed**. [Evidence](../native/drafts/environment/storage-read-lock74-observations.json).
The preceding full run remains **4576 passed, 1 failed, 1 skipped**, with a QML save-time empty
account list; this is not the earlier profile-delivery deadline failure.
[Retained failure](../native/drafts/environment/canonical-python74-qml-save-failure-observations.json).
No full-suite or cross-process-locking admission after this fix is claimed yet.
Full Python at `568c934`: **4575 passed, 1 failed, 1 skipped**, source/status guards passed.
The failure was the 0070 historical-target assertion incorrectly rejecting later groups.
Its exact historical-prefix comparison was repaired; targeted follow-up: **180/180**.
No full-suite pass after this repair is claimed yet.
[Retained failure](../native/drafts/environment/canonical-python74-history-failure-observations.json).
The complete old checkpoint is retained. Two new native gates require all six new
cases, for **23 groups / 494 total required cases**. Selection/release Python checks:
**1179 passed, 1 skipped**. [Selection](../native/drafts/environment/screen74-selection-observations.json).
The build has **not started**: about 110 GiB free on D: is below the locked 180 GiB
reserve. No source refresh, deletion or reserve override was performed.
[Preflight](../native/drafts/environment/screen74-build-preflight-observations.json).

Full Python after the protected-history collector: **4568 passed, 1 skipped**, 383s,
source/status postguards passed at `f59e578`.
[Evidence](../native/drafts/environment/canonical-python73-protected-history-observations.json).

The [next linked screen patch](../native/drafts/environment/live-screen-linked-next.patch)
passes four isolated translation-unit checks and prepares six native tests. It adds
logical-screen invalidation to the browser visual-properties update predicate and
prefers live main-frame emulation over delayed transported metadata. Its preparation
record predates selection; it is now selected as 0074, but **not built and the new tests
have not executed**. The raw CDP failure is still open.
[Preparation only](../native/drafts/environment/live-screen-linked-next-observations.json).

Protected manager BFCache follow-up: **12 screen phases** and **32 top-document Canvas
format cases before/after restoration per desktop/Mobile Web mode** passed. All combined
feature flags were effective, but restored GPU/Audio output was not measured. Requested
screen/DPR values, six documents and actual BFCache navigation are required, not merely
self-consistency with an arbitrary baseline. Desktop/Mobile Web released all 14/13 observed processes.
[Evidence](../native/drafts/environment/protected-history73-observations.json),
[reproducible collector](../native/drafts/environment/first-script/protected_history_runtime.py).
Raw per-page CDP stress failures below remain unresolved and are not superseded by this pass.

| Gate | Result | Boundary |
| --- | --- | --- |
| Windows incremental build | **51 steps, j4, 43m55s Ninja**, 269 preserved assets | No clean/resync; controller 59m24s; not release admission |
| Native batch | **488/488**, 21 groups, all four strict orientation cases | Does not prove browser lifecycle/first-script/BFCache behavior |
| Baseline runtime | [**18/18**](../native/drafts/upstream-156/runtime-baseline73-observations.json) | Storage/proxy/permissions/Recorder/backup; not protected-policy admission |
| Canvas/WebGL/AudioMath | **18/18 phases**, eight protected profiles plus baseline, restart, both selectors | Not a verified device cohort |
| Canvas formats / worker formats | **32/32 / 96/96** | Six classic/module worker classes; no nested/restart coverage |
| PNG document / workers | **Passed / 24 worker cases per profile** | Pre-mutation pixels, async capture and color metadata; not HDR fidelity |
| Finite Float16 document / workers | **4 / 12 actual contexts per profile** | Bounded finite samples, alpha/crop/re-put; not broad HDR or nonfinite coverage |
| Concurrent protected profiles | **6/6 phases**, observed processes released | Not long-run leak/resource admission |
| New evidence/worker HDR validator tests | **26 passed** | Targeted Python run, not a full-suite replacement |
| Mobile Web 073 | [**18/18 phases**](../native/drafts/environment/combined-mobile73-observations.json), both selectors | Windows emulation, not Android/iOS or a verified device cohort |
| Browser first-script / manager context lifecycle | **6/6 / 12/12 phases**, observed BFCache in desktop/mobile | No raw per-page metrics updates or protected-policy lifecycle admission |
| Raw per-page CDP metrics stress | **Failed**, postguards passed; BFCache restored | Cross-page screen/DPR and screenshot mismatches retained, not waived |
| Full Python at `d0de567` | **4546 passed, 1 skipped**, 412s; source/status guards passed | Includes worker HDR; precedes the later screen/mobile evidence tests |

[Build](../native/drafts/upstream-156/build73-observations.json),
[native batch](../native/drafts/upstream-156/native-batch73-observations.json),
[combined](../native/drafts/environment/combined-math73-observations.json),
[formats](../native/drafts/environment/canvas-formats73-observations.json),
[worker formats](../native/drafts/environment/worker-formats73-observations.json),
[PNG](../native/drafts/environment/canvas-export73-observations.json),
[worker PNG](../native/drafts/environment/worker-export73-observations.json),
[finite F16](../native/drafts/environment/canvas-hdr73-observations.json),
[worker F16](../native/drafts/environment/worker-hdr73-observations.json),
[concurrent](../native/drafts/environment/combined-concurrent73-observations.json).

All records bind the preserved 001–073 core/receipt and measured collector sources.
Earlier failures remain historical evidence below, not rewritten passes.
Privacy, public anti-bot results, security and production admission remain unproven.
[Screen pass/failure evidence](../native/drafts/environment/screen73-browser-observations.json),
[full Python](../native/drafts/environment/canonical-python73-runtime-observations.json).

## Worker PNG, finite Float16 fidelity and Python follow-up — 2026-10-30

| Gate | Result | Boundary |
| --- | --- | --- |
| Worker PNG export | **24/24 cases/carriers per baseline and protected profile** | Six classic/module worker classes × four Offscreen cases; exact pre-mutation pixels, color metadata and document coherence |
| Finite Float16 fidelity | **4/4 HTML/Offscreen × sRGB/P3 contexts** | Negative/above-one/subnormal samples present; alpha, nonopaque colors, sign/exponent, bounded mantissa changes, crop/repeat/re-put checked |
| Full Python at `f4c8001` | **4503 passed, 1 skipped**, source/status guards passed | Includes worker PNG and historical QML binding repair; precedes the new finite HDR probe/tests |

[PNG evidence](../native/drafts/environment/worker-export72-observations.json),
[finite F16 evidence](../native/drafts/environment/canvas-hdr72-observations.json),
[Python](../native/drafts/environment/canonical-python73-worker-export-observations.json),
[retained earlier failure](../native/drafts/environment/canonical-python73-diagnostics-failures.json).
The exact public PNG collector ran from a local frozen **001–072** source layout,
bound to the preserved 001–072 core/receipt. No network clone or changes to the
active Chromium checkout were needed. This does **not** validate 001–073, worker
restart/nesting, broad HDR fidelity, security or release. The interrupted 001–073 build
stage is being resumed with its completed sync/hooks/patch and existing objects.
The first HDR effect oracle isolated every opaque pixel and therefore supplied
no eligible opaque edges; its [negative result](../native/drafts/environment/canvas-hdr72-initial-oracle-observations.json)
is retained. The revised fixture adds contiguous opaque HDR edges, without changing
the native policy or relaxing the fidelity bounds. Isolated/transparent drawings
are not claimed to change under the current edge-only policy.

Security admission remains blocked: the pinned **156.0.8078.36** predates the
[156.0.8078.79/.80 stable update](https://chromereleases.googleblog.com/2026/10/stable-channel-update-for-desktop_02107719452.html).
[157.0.8103.26/.27](https://chromereleases.googleblog.com/2026/10/early-stable-update-for-desktop_01255863767.html)
was announced as early stable, not a general stable rollout. Resolve the current
stable source and replay/retest before release; individual CVE applicability is not verified.

## Completed 001–072 gates and corrective 001–073 selection — 2026-10-30

| Gate | Result | Boundary / next action |
| --- | --- | --- |
| Native batch, 21 groups | **485/488 passed, 3 orientation failures**; source/tool postguards passed | Existing 20 groups: 484/484. Batch remains failed; 0073 correction selected, not compiled |
| Mobile Web combined repeat | **18/18 phases**, 390×844, DPR 3, touch; same collector/deadlines | Earlier baseline navigation/shutdown timeout retained; Windows emulation, not Android/iOS |
| Worker Canvas formats | **96/96**, six classic/module dedicated/shared/service classes × 16 Offscreen cases | Matches document outputs within each profile; not nested workers, PNG export or HDR fidelity |
| Full Python at `4e838f4` | **4472 passed, 2 failed, 1 skipped** | Both QML profile-delivery deadlines failed; isolated unchanged follow-up: 2/2. Under-load gate remains open |

[Native failure](../native/drafts/upstream-156/native-batch72-observations.json),
[Mobile Web](../native/drafts/environment/combined-mobile72-observations.json),
[retained timeout](../native/drafts/environment/combined-mobile72-timeout-observations.json),
[workers](../native/drafts/environment/worker-formats72-observations.json),
[Python/UI failure](../native/drafts/environment/canonical-python72-ui-failures.json).

The correction exposes the main-frame logical screen without changing physical
screen APIs and disables Blink's forced web-test orientation only inside the test
fixture. Both changed source files pass isolated compiler checks. The four strict
orientation cases remain required; compilation alone does not establish a fix.
[Selected 0073](../native/drafts/environment/screen73-selection-observations.json).

## Protected 001–072: combined surfaces and Canvas formats — 2026-10-30

| Gate | Observed | Boundary |
| --- | --- | --- |
| Canvas + WebGL + AudioMath together | **18/18 phases**, baseline + 8 protected profiles, initial/restart; both AudioMath selectors | Sequential Windows profiles; not simultaneous sessions or a device cohort |
| Canvas format/readback matrix | **32/32**, no compatibility regressions; repeated reads stable and all differ from baseline | HTML/Offscreen in one document; not workers, PNG export or broad HDR quality |
| PNG export/capture coherence | **8/8 cases, 12/12 carriers per baseline/protected profile**; exact pre-mutation pixels, async snapshot and color metadata | Qt decoding, no second Canvas; not HDR fidelity or workers |
| Concurrent protected profiles | **6/6 phases**, both profiles live, peer closure and same-profile restart; no observed processes remaining | Two Windows desktop profiles; not long-run resource limits or Mobile Web |

[Combined evidence](../native/drafts/environment/combined-math72-observations.json),
[format evidence](../native/drafts/environment/canvas-formats72-observations.json),
[PNG exports](../native/drafts/environment/canvas-export72-observations.json),
[concurrent profiles](../native/drafts/environment/combined-concurrent72-observations.json).
The old **30/32 failures on 001–070** remain recorded below. They are no longer
reproducible on this exact 001–072 fixture; this does not establish general
image-editor compatibility, anti-bot acceptance or release readiness.

## Compiled 001–072 baseline — 2026-10-30

| Gate | Observed | Boundary |
| --- | --- | --- |
| Windows build | **PASS**, j4, 64 actions, 15m14s; 269 assets preserved separately | Not a policy or release gate |
| NativeRuntime baseline | **18/18**, including storage/restart/permissions/proxy/Recorder/backup | No protected-policy, installed-package or cloud isolation admission |
| Full Python after historical fixes | **4464 passed, 1 skipped**, guards passed | Before the new build-result tests |

[Build](../native/drafts/upstream-156/build72-observations.json),
[runtime](../native/drafts/upstream-156/runtime-baseline72-observations.json),
[Python](../native/drafts/environment/canonical-python72-export-observations.json).
The completed native failure and Mobile Web/worker results are above. The newer
format/combined/export/concurrent results do not erase older 001–070 evidence.

## Export capture reference and selection follow-up — 2026-10-30

The **unprotected preserved 001–070** passes eight HTML/Offscreen × sRGB/P3 ×
unorm8/F16 cases: all 12 PNG carriers match pre-mutation RGBA8 pixels, including
the async snapshot after changing the source canvas. Display-P3 profile metadata
is retained. Pixels are decoded with the existing Qt decoder, not another Canvas
that could apply protection a second time.
[Baseline](../native/drafts/environment/canvas-export-baseline70-observations.json),
[reusable page probe/validator](../native/drafts/environment/first-script/canvas_export.py).
Protected 001–072, workers and broad HDR quality are **not verified** by this baseline.

Full Python after source selection: **4448 passed, 2 failed, 1 skipped**. Both
failures were historical manifest bindings, not newly measured TLS/GPU failures;
the records stay unchanged and their tests now use the exact 001–070 checkpoint.
The targeted follow-up passed **392 tests**, not a full repeat.
[Retained failures](../native/drafts/environment/canonical-python72-selection-failures.json).

## Linked 001–072 source selection — 2026-10-30

| Gate | Evidence | Not yet proven |
| --- | --- | --- |
| Exact 001–070 prefix + two patches | 0071 orientation/visibility and 0072 extended Canvas selected; nine changed files | Source selection is not a compiled browser |
| Joint source preflight | Three additional C++ compiler checks passed on the same isolated overlay | Four orientation cases not executed yet |
| Existing native gate integration | 21 groups; all historical mappings preserved, four strict orientation cases required | New native batch not run yet |
| Full Python at `ba72a17` | **4447 passed, 1 skipped**, final guards passed | Before source selection |

[Selection](../native/drafts/environment/linked72-selection-observations.json).
The preserved browser is still 001–070. Owned j4 refresh and actual browser/native
regressions must follow; privacy, security and release admission remain unchanged.

## Expanded format and lifecycle gates — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Canvas HTML/Offscreen × context/read color spaces × unorm8/float16 | **FAIL: 30/32 compatibility regressions**; baseline supports 32, protected supports 2 | Only default sRGB/RGBA8 passes; `NotReadableError` is not successful protection |
| Two protected desktop profiles concurrently | **6/6** phases: both open, peer closure and each profile restart; Canvas/WebGL/Audio match prior captures | Opposite AudioMath selectors, not resource limits or Mobile Web concurrency |
| Combined Mobile Web | **18/18** initial/restart phases, baseline + eight profiles, both AudioMath selectors | Windows runtime, 390×844/DPR 3/touch; not Android/iOS or advanced Canvas format support |
| Full Python at `bd82e73` | **4405 passed, 1 skipped**, final source/status guards passed | Precedes these three new diagnostics; not native compilation |

[Retained Canvas FAIL](../native/drafts/environment/canvas-formats70-observations.json),
[concurrency](../native/drafts/environment/combined-concurrent70-observations.json),
[Mobile Web](../native/drafts/environment/combined-mobile70-observations.json),
[full Python](../native/drafts/environment/canonical-python70-combined-math-observations.json).
An [isolated P3/F16 draft](../native/drafts/environment/canvas-formats-next/README.md)
passes compiler checks and 12 linked transform controls including 65,536 half
encodings. Its adaptive variant also passes **283 native Skia copy/projection
controls**: four source/read color-space pairs retain 32 distinct F16/RGBA8 seed
outputs on the owned fixture. The prior LSB-only projection FAIL is retained.
It is not compiled into the browser; export/workers/runtime and broad HDR quality
checks remain open. [Full repeat at `4400f45`](../native/drafts/environment/canonical-python70-canvas-draft-observations.json):
**4446 passed, 1 skipped**, before the adaptive variant. Combined BFCache, full WebGPU,
quality/resources, security rebase and release/update/rollback gates remain open.
Earlier tables below describe their original, narrower measurements.

## Simultaneous native Canvas / WebGL readback / AudioMath — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Combined policies, profile-identity mode | **18/18 phases**, baseline + eight protected profiles, each initial/restart | Sequential Windows contexts, not concurrent profiles or Mobile Web |
| Canvas / WebGL readback | Context/export/restart checks and cross-profile isolation passed | Not WebGPU readback admission or anti-bot acceptance |
| Audio API compatibility | Five documents × 54 short fidelity cases per phase; analyser, worklet and trusted muted realtime controls passed | Not a physical-device cohort or broad perceptual quality gate |
| AudioMath effect | Both selectors observed; long compressor matches native baseline for 0 and differs for 1; all five documents/restarts agree | Two compressor pipelines, not eight unique Audio identities |
| Parser and lifecycle | Canvas/Audio first-parser/initial-child checks passed; keys stable, observed owned processes exit; guards passed | First-parser WebGL, concurrency, BFCache, mobile and long-run resources still open |
| Full Python at `9ca759a` | **4379 passed, 1 skipped**, source/status guards passed | Before the new combined collector |

[Measured packet and reproducible collector](../native/drafts/environment/combined-math70-observations.json),
[historical full regression](../native/drafts/environment/canonical-python70-python-js-observations.json).
No default privacy/runtime switch, package admission or release follows from this gate.

## Optional Python+JS desktop package — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Repository spec/tool build | **PASS**, pinned Python and JS packaged together; actual EXE bytecode matches the prepared BindingCall fix | Cached desktop build, not Chromium compilation or default driver replacement |
| Default Native runtime | **18/18**, installed driver/source unchanged | BFCache remains disabled in the default manager policy |
| Source-overlay Recorder/replay | **4/4** desktop/mobile initial/restart | Explicit opt-in, not frozen Native BFCache admission |
| Restoration race repeat on this package | **6/6**, plus four strict cancelled-stop controls without recorded loop errors | Separate test-only JS barrier; not every cancellation phase |
| Legacy engines | Both cached providers passed transport persistence and actual frozen launch/imports/expected timeout | No fingerprint score or new Cloak Recorder support |
| Historical full repeat at `0770c2e` | **4366 passed, 1 skipped**, guards passed | Before Python+JS packaging integration |

[Package measurements](../native/drafts/environment/python-js-stage70-observations.json),
[historical full repeat](../native/drafts/environment/canonical-python70-binding-close-observations.json).
The package is unselected/unsigned. Frozen Native BFCache, resource/leak checks,
combined fingerprint, security rebase and release/update/rollback admission remain open.

## Strict pending-binding teardown and staging regression — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Full canonical at `766d9b4` | **4364 passed, 1 skipped**, source/status guards passed | [Report](../native/drafts/environment/canonical-python70-stage-observations.json); includes staging/spec packet, precedes Python binding draft |
| Actual staged opt-in driver | **32 BFCache cycles / 224 handler calls**, desktop/mobile initial/restart, observed owned processes exit | [Fresh measurement](../native/drafts/environment/staged-stress70-observations.json), not transferred from old reply bundle |
| Strict pending-binding baseline | Functional rows pass, overall **FAIL**: three unhandled `TargetClosedError` reject tasks | [Retained negative control](../native/drafts/environment/binding-close70-observations.json) |
| Python BindingCall draft | Eight actual BFCache cycles, four driver-stop cancellations, same-profile key/storage restart and cross-process ownership; **zero recorded loop errors** | Same paired gate and 10 extracted-method controls; not in desktop stage, not every cancellation point or resource admission |

No production policy or CAPTCHA/fingerprint acceptance follows from these gates.

## Explicit-opt-in driver staging and Windows desktop package — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Pinned stage | 176 assets, source unchanged, legal notices retained; only JS overridden in optional desktop build | Unsigned, unselected; no installation replacement |
| Opt-in branch | **30 model controls**, **18/18 default Native runtime checks** | Default manager BFCache remains disabled |
| Actual staged Node/driver with Glint source overlay | **4/4 Recorder/replay phases**, desktop/mobile initial/restart, genuine BFCache, no pending outcomes | Not frozen Native BFCache integration |
| Original vs staged legacy engines | Both Camoufox and CloakBrowser passed initial/restart forms, iframe, bindings, screenshot and five-store checks | Transport compatibility, not fingerprint acceptance or new Cloak Recorder support |
| Actual frozen desktop EXE | Both providers passed packaged Python imports/browser and expected hard-timeout checks | No combined Native policy or release admission |
| Historical canonical `87f74ea` | **4334 passed, 1 skipped** | Before new staging script/spec edits |

[Measured packet and exact hashes](../native/drafts/environment/driver-stage70-observations.json),
[historical Python report](../native/drafts/environment/canonical-python70-races-observations.json).
Earlier 6 controlled races and 32 cycles below used the previous reply bundle; they
are not silently transferred to this opt-in bundle. Cancelled teardown under BFCache
load, resource checks, combined fingerprint, security rebase and release gates remain open.

## Real BFCache race/stress gates and complete Python repeat — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Navigation, page close, runtime close during restoration | **6/6 passed** across desktop/mobile; a real frame-tree reply held until the action finished; profile key/storage survive restart; zero surviving observed owned processes | [Evidence and public runners](../native/drafts/environment/bfcache-races70-observations.json); explicit test-only driver barrier, not artificial frame payloads |
| Uninstrumented reply draft | **32/32 genuine BFCache cycles**, four initial/restart phases; **224 Python handler calls**, including 32 delayed outcomes and 192 role-verified echoes | No handler replay; six screen snapshots unchanged per cycle; identity/storage survive restart; observed processes exit |
| Complete Python at `f99957d` | **4330 passed, 1 skipped**, 420.875s; all tracked-source/status guards passed | [Full repeat](../native/drafts/environment/canonical-python70-replies-observations.json); the skipped case rejects Schannel off Windows, not a browser capability gate |
| Fresh upstream audit | Development candidate still **behind-stable** | Same dated observation records the official response; release/security review remains closed |

These results do not install or select the driver. Cancelled teardown under BFCache
load, peak allocation/long-run resource limits, other-engine compatibility in a staged
package, combined fingerprint policies and release/update/rollback admission remain open.

## Complete UI-ordered BFCache recording and replay draft — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Public source-bound replay runner | **4/4 phases passed**: desktop/mobile, initial/persistent restart; record before first navigation → trusted link out/back → genuine BFCache → six documents | [Evidence](../native/drafts/environment/binding-replies70-observations.json); same preserved 001–070 binary, isolated application/driver copies |
| Entire unchanged recorded draft | **13 steps / 9 clicks per phase replayed**, including both navigation waits; replay also restores BFCache; main probe clicked twice, each child once | No skipped steps or rewritten recording; six pending-binding sets empty and no flush warnings |
| Reply identity and lifecycle models | **25 controls passed**, including numeric-id reuse, foreign frames, explicit destruction/dispose, duplicate acknowledgements, 1024-entry limit and late old-RPC failure | Exact-method models, not real rapid-navigation/close stress or allocation measurements |
| Existing full runtime suite with new reply driver | **18/18 passed**; source/package guards and installed-driver-unchanged check passed | Baseline policies only; not combined fingerprint or release admission |
| Full Python at `46c3b4d` | **4325 passed, 2 failed, 1 skipped**, source guards passed | [Retained result](../native/drafts/environment/canonical-python70-document-open-observations.json); two historical Recorder-source checks corrected, complete repeat still required |

The draft retains binding **outcomes**, not Python handlers, for the original unique
execution context. It also closes a modeled race where an old failed RPC completed
after context restoration. The old failing captures remain unchanged. The installed
driver and default manager launch policy are **not changed**. Specific navigation/page/runtime-close
races passed in the later gate above; cancellation-under-load and pinned package integration remain open.

## Recorder document.open repair — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Attach before first navigation, unchanged installed driver | Original Recorder captures **5/6** clicks; repaired Recorder captures **6/6** and replays all six frame roles with trusted input | [Paired desktop control](../native/drafts/environment/recorder-document-open70-observations.json); no BFCache or mobile-history admission |
| Listener reinjection model | Old registrations aborted, no duplicate clicks, same-document pending flush retained, replaced-document listeners removed | Executed exact `RECORDER_SCRIPT` in Node; model complements the real browser control |
| Current application runtime regression | **18/18 passed**, source and binary guards passed; installed Playwright and manager BFCache default unchanged | Fresh run of actual patched application source, not reuse of the older Recorder baseline |
| Earlier UI-ordered BFCache recording, before reply draft | Six roles restored, **9 clicks recorded**, but one main-document binding acknowledgement remains pending; stop emits a flush warning | **FAIL retained**; later isolated reply-draft result above is separate, BFCache opt-in remains unselected |

`document.open()` can clear listeners without changing the document/window object.
The Recorder now aborts previous listener registrations and reinstalls all four handlers,
preserving in-flight work for the same document. Historical evidence retains its original
source hashes; tests reconstruct the pre-repair normalized source with the reverse patch.

## Multisession BFCache compatibility draft — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Actual restored frame tree | **6/6 roles in 4/4 phases**: desktop/mobile, initial/persistent restart; genuine `BackForwardCacheRestore` | [Evidence and public patch](../native/drafts/environment/binding-driver70-multisession-observations.json); unselected D driver, same preserved 001–070 runtime |
| Trusted input and Recorder | **7 recorded clicks per phase**, correct five child-frame selector chains including nested OOPIF, no Recorder warnings | Root click before/after history plus five child clicks after history; initial navigation and full history-draft replay not included |
| Exact-method modeled controls | **13 passed**: context clear/destroy, dispose, changed sessions/generations, missing/cyclic ancestry and conflicting loaders | [Runnable model](../native/drafts/environment/playwright-bfcache-multisession-model.cjs); modeled races are not real-browser lifecycle proof |
| Existing complete NativeRuntime suite with new driver | **18/18 passed**, source/driver guards passed; includes attach-before-navigation Recorder → replay, cancellation, storage and crash cleanup | Baseline replay is verified separately; the complete six-frame history recording has not yet been replayed |

The main target omits remote frames from its own frame-tree snapshot. The new draft
collects current OOPIF-session trees after the main snapshot and validates the combined
ancestry before mutation. The failed root-only and premature-session attempts remain
retained; neither the installed dependency nor manager BFCache default was changed.

## Completed native 001–070 batch and driver boundary — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Native C++ batch | **484 cases / 20 groups passed**, j4, one build invocation; all 212 frozen input hashes and final guards passed | [Executed results](../native/drafts/upstream-156/native-batch70-observations.json); includes 9 screen-metrics and 7 screen-widget cases, not combined browser-policy admission |
| Full canonical Python at `2a59a24` | **4320 passed, 1 skipped**, 426.609s; tracked-source/status guards passed | [Result](../native/drafts/environment/canonical-python70-owner-observations.json); test of verifiers is not a passing Recorder integration |
| Recorder loss diagnosis | Driver received 13 binding calls, dispatched 11; two default contexts rejected before the frame was known | [Source-bound trace](../native/drafts/environment/binding-driver70-diagnosis.json); Chromium delivered the events, no demonstrated V8 callback loss |
| Unselected driver prototype | Root-only capture **4/4 phases**, two clicks each; extended six-frame gate **FAIL**, `same` and `nested-return` absent | [Retained result and patch](../native/drafts/environment/binding-driver70-prototype-observations.json); installed driver unchanged, no all-frame/replay admission |

## Selected 0070 source package — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Linked source selection | Single two-file main-DPR correction and seven Blink widget cases registered after 001–069; immutable 001–070 checkpoint created | [Selection](../native/drafts/environment/screen70-selection-observations.json); subsequent build and native batch above passed, combined lifecycle remains separate |
| Verifier integration | `screen-widget` active in existing tools, exact seven cases in `blink_unittests`, explicit upstream-156 and registered 0069/0070 required; batch now 20 groups | Python replay/result-rejection controls and all seven actual C++ widget cases passed; not complete browser compatibility |
| Baseline controls after selection | Preserved 001–068 crash/TLS/large WebGL controls rerun with current manifest/verifier source bindings | Still baseline-only evidence, not execution of new 0070 |

## BFCache launch-overlay / owner API calibration — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Glint genuine BFCache, owner-aware geometry/input | **4/4 phases passed**, six persisted documents rechecked after owner screenshot; desktop/mobile initial/restart | [Paired evidence](../native/drafts/environment/managed-bfcache-optin70-observations.json); unregistered launch overlay, no active manager change |
| Owner PNG vs independent CDP PNG | Owner mobile **1170×2532**; separate CDP **390×844**, already before history and also on stock | Different session-local emulation contracts; not evidence of BFCache-caused DPR regression |
| Paired stock156 comparison | 168 snapshots per runtime; **88 equal / 80 different**; stock strict screen gate fails | Exact screen/viewport/CSS observations, not detector scores or ordinary-user realism |
| Full existing runtime suite in tracked-source launch-overlay | **18/18 passed**, original/overlay source guards passed | Baseline policies; not proof of history-specific Recorder/replay or release admission |
| Repeated Recorder BFCache capture | **3/4**, then **2/4** with bridge tracing; trusted post-click sometimes never enters Python despite active JS markers, without warnings | [Retained failure](../native/drafts/environment/managed-bfcache-recorder70-observations.json); blocks launch integration; full recorded-draft replay unverified |
| Recorder stock156 control | Same missing post-click bridge event in **4/4** phases, despite trusted DOM input and no warnings | Same source-bound trace setup; not unique to Glint, still a required integration fix |
| Recorder listener/binding diagnosis | Recorder DOM listener retained in **4/4** phases; empty binding ping reaches Python in **1/4**, times out before Python in three | [Diagnostic](../native/drafts/environment/managed-bfcache-recorder70-observations.json); narrows the issue to binding/session delivery, not a proven implementation fix |

## Compiled 001–070 screen/DPR checkpoint — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Source build | **52 steps, j4, 17m02.68s**; source/SDK/core guards passed; 269 exact runtime assets preserved | [Build](../native/drafts/upstream-156/build70-observations.json); no package/release admission |
| Complete existing NativeRuntime baseline | **18/18 checks passed**, including permissions, owned authenticated proxy, scenarios/Recorder, backup/restore and crash/cancellation recovery; three three-profile crash rounds left **zero owned processes** | [Evidence](../native/drafts/upstream-156/runtime-baseline70-observations.json); unprotected policies, not installed-package/cloud-team/privacy admission |
| Actual NativeRuntime managed history, no metrics override/resize | **144 document screen/CSS/embedding snapshots consistent** over four desktop/mobile initial/restart phases | [Evidence](../native/drafts/environment/managed-history70-observations.json); BFCache gate remains **FAIL**: explicit driver flag and CDP `BackForwardCacheDisabledByCommandLine`; normal reload is not BFCache |
| First script, six document roles, persistent restart | **6/6 phases passed**; desktop/mobile/native control; Mobile Web DPR remains **3** at first and settled reads | [Evidence](../native/drafts/environment/screen70-first-script-observations.json); not full lifecycle or device-profile admission |
| Manager two-tab fixed-screen stress | **4/20 stages passed**, all failures retained; `set_viewport_size` resets screen by Playwright contract | [Evidence](../native/drafts/environment/manager-screen70-observations.json); no silent contract relaxation |
| Extra-CDP / BFCache stress | Overall **FAIL**; real BFCache restore with six persisted documents; peer-state/screenshot and cached-orientation inconsistencies retained | [Evidence](../native/drafts/environment/screen-lifecycle70-observations.json); not full lifecycle admission |
| Input/screenshot after BFCache restore | Main document trusted click passed; screenshot **1170×2532** matches DPR 3; screen stable across input | [Evidence](../native/drafts/environment/history-interaction70-observations.json); all-frame input and complete lifecycle remain unverified; earlier navigation timeout retained |
| Next orientation package | Three-file draft with four native regression cases; apply-check passed against 001–070 | [Preparation](../native/drafts/environment/orientation-visibility71-preparation.json); unregistered, uncompiled and unverified |
| Next orientation gate | Four exact `blink_unittests` cases; 16 Python selection/result controls passed, all current 20 mappings unchanged | [Preparation](../native/drafts/environment/screen-orientation71-gate-preparation.json); proposed 21st group, not integrated or executed C++ cases |

## Canonical Python regression — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Full main b6aa9c5 | **4254 passed, 1 failed, 1 skipped**; 655.156s; tracked-source guards passed | [Retained failure](../native/drafts/environment/canonical-python69-preparation-observations.json); not a full-suite PASS |
| QML race diagnosis/repair | Controlled 1500-ms model-delivery delay reproduces original failure; waiting for public `getProfile()` within the unchanged 3-second deadline passes; corrected full QML module **9 passed** | Test-only synchronization; production UI unchanged; full regression after repair still pending |
| Full main 8bbca7c after 0070 selection | **4268 passed, 5 failed, 1 skipped**; tracked-source guards passed; QML case no longer failed | [Retained full result](../native/drafts/environment/canonical-python70-preparation-observations.json); five stale release-test contracts, not full-suite PASS |
| Versioned release-test contracts | Current candidate checks updated to exact 70 and its patch list; historical 65/66 batch lists still exclude later groups; complete release-tools module **1131 passed, 1 skipped** | Test-only contract update; source/package/runtime guards unchanged; another full run pending |
| Full main 748e0f5 after contract corrections | **4274 passed, 1 skipped**, 689.171s; all tracked-source/status guards passed | [Complete result](../native/drafts/environment/canonical-python70-observations.json); not native C++ execution or runtime/package/privacy admission |

## Screen/DPR source package 0069, compiled / partial runtime checks — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Source build | **2079 steps, j4, 1h47m09.05s**, final source/SDK/core guards and receipt passed; 269 runtime assets preserved with exact hashes | [Build evidence](../native/drafts/upstream-156/build69-observations.json); not native-unit or complete browser/package admission |
| Actual first-script gate | Desktop and native-control initial/restart passed; mobile cross-origin roots retain DPR 3, but main/local documents settle at DPR 1 | [Six-phase evidence](../native/drafts/environment/screen69-first-script-observations.json); overall FAIL, 0070 still required; no screenshot/input errors in these phases |
| Linked source draft | 19-file browser/IPC/widget/DOM/CSS package; apply-check passed against exact 001–068; subsequently selected and compiled as 001–069 | [Historical preparation record](../native/drafts/environment/screen-inheritance69-preparation.json); source preparation alone is not browser admission |
| IPC generation | Pinned official parser and typed native/Blink/shared C++ generators passed in an isolated D: output | Not C++ compilation, serialization-test execution or browser delivery proof |
| Native cases | Nine cases required by the new `screen-metrics` group in `blink_common_unittests`; batch now has 19 groups | **Not executed**; first-script, lifecycle, geometry/input and combined browser gates remain open |
| Preserved 0068 first-script baseline | Six phases × six documents; both no-emulation controls passed, all four manager desktop/mobile phases reproduced defects; clicks and screenshot sizes passed | [Complete red baseline](../native/drafts/environment/screen68-first-script-complete-observations.json); not execution of 0069. Main Mobile DPR changes 3 → 1 after nested local roots |
| Queued main-root correction | Two-file 0070 draft, three Blink simulation cases, read-only apply-check passed against 0069 | [Preparation](../native/drafts/environment/main-dpr70-preparation.json); unselected/uncompiled; the live 0069 build is unchanged |
| Queued widget lifecycle cases | Four additional main/remote-root cases cover update, clear, physical-metrics separation and inspector/zoom/CSS independence; apply-check passed after queued 0070 | [Preparation](../native/drafts/environment/screen-lifecycle-native-tests-preparation.json); seven linked Blink cases prepared in total, **none executed**; not screen-event/BFCache/runtime admission |
| Consolidated next screen batch | Single two-file patch contains main DPR correction and all seven native cases; apply-check passed after exact 001–069 | [Preparation](../native/drafts/environment/linked-screen70-preparation.json); use instead of the two component drafts, never stack them; no header/IPC changes, no measured build/runtime result |
| Queued screen-widget gate | Existing verifier/batch integration requires seven exact widget cases, `blink_unittests`, explicit upstream-156 and registered 0069/0070; 12 Python parser/selection controls passed | [Preparation](../native/drafts/environment/screen-widget-gate-preparation.json); unintegrated draft, not native execution. Live batch remains 19 groups; proposed batch has 20 |
| Public first-script CLI | All six phases completed; four manager failures reproduced, both controls passed; core/receipt/source guards and final owned-process cleanup passed | [CLI execution](../native/drafts/environment/public-first-script-cli-observations.json); previous incomplete attempts retained; no retry loop or timeout increase; not 0069 execution |
| Paired lifecycle stress | Glint 001–068 and stock156 completed seven stages; **78 screen/viewport/CSS snapshots matched**; all six documents genuinely restored from BFCache in both | [Calibration](../native/drafts/environment/screen-lifecycle68-calibration-observations.json); both fail the same mixed-controller state checks, not a Glint-specific regression or supported-manager-path admission |
| Manager context-options control | Desktop/mobile-web, two tabs, viewport updates, navigation, peer close and persistent restart; **216 screen/viewport/CSS snapshots matched stock156**; both fail strict stable-screen identity checks | [Calibration](../native/drafts/environment/manager-screen68-calibration-observations.json); no extra page CDP sessions. `set_viewport_size` can reset screen by API contract; not full NativeRuntime, BFCache, new 0069/0070 execution or package admission |

## Chromium 156 / 001–068 — 2026-10-30

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Source build | Completed incremental browser build, j4; core bytes unchanged from 001–067 | [Build evidence](../native/drafts/upstream-156/build68-observations.json); patch 0068 changes fixtures only |
| Native batch | **18/18 groups passed**, including **12/12 AudioMath**; all postguards passed | [Native evidence](../native/drafts/upstream-156/native-batch68-observations.json); overlapping filters are not independent coverage |
| Owned TLS negotiation | TLS 1.3 and TLS 1.2 completed with ALPN/HTTP 1.1; unrelated-key certificate rejected before HTTP; source/core/receipt/cleanup guards passed | [Evidence](../native/drafts/network/negotiation68-observations.json); one ephemeral diagnostic SPKI allowlist, no system-store/global-ignore change. Not ordinary certificate-path validation, TLS impersonation, resumption or HTTP/2/3 |
| Large WebGL2 attachment | Four baseline/protected/restart phases passed on RGBA8 4096×4096 with a 2×2 viewport; full CPU/repeat/PBO hashes agree, three crops match full pixels, outside bytes and GL state preserved; two protected profiles differ | [Evidence](../native/drafts/next-readback/large-attachment68-observations.json); one document/OffscreenCanvas, caller buffers 64 MiB; not private/RSS memory, isolated latency, workers, other GPU APIs, 0069 or privacy admission |
| Actual NativeRuntime ownership/storage | **8 lifecycle checks passed** on two simultaneous desktop/mobile-web profiles; duplicate owner/double start rejected; cookies/localStorage and private identity survived peer closes and both restarts; resources released | [Evidence](../native/drafts/environment/runtime-ownership68-observations.json); **screen consistency FAIL**, 36 document snapshots. Same-process lock owners only; not cross-process/crash/server-team/policy or release admission |
| Separate-process profile ownership | Challenger Python process rejected while owner stayed usable; after orderly close another process acquired the profile; private identity retained and parent/children released resources | [Windows evidence](../native/drafts/environment/runtime-owner-process68-observations.json); current user, unprotected 001–068 only; not crash recovery, forced unlock, server/team isolation or release admission |
| Browser/controller crash recovery | Existing gates passed **3 rounds × 2 independent profiles**: owned browser crash, peer survival and five-store recovery; separate owned-controller kill exited its observed descendants and restored five stores | [Evidence](../native/drafts/environment/runtime-crash68-observations.json); zero remaining owned processes; checkpointed state, policies off. Not unsaved transactions, 0069/0070, protected-policy, screen or release admission |
| Fixed-profile Audio matrix | **8/8 profiles**, baseline / Math / Math restart; all 24 phases passed fidelity 54/54, analyser 12/12, worklet 12/12 and realtime 11/11 | [Runtime evidence](../native/drafts/upstream-156/audio-profile-matrix68-observations.json); exact key retention, closed resources and input/core/receipt postguards |
| Audio effect / diversity | Both reference selectors occurred, but every fidelity graph remained bit-exact to baseline | **Not established**: reference selector coverage is not internal DSP branch observation; discriminating compressor signals and transport need investigation |
| Long compressor effect | Same eight profiles/keys, **1080 captures**; five selector-1 profiles changed three cases and matched the float32 prototype on all 15; three selector-0 profiles stayed unchanged; all restarts exact | [Effect evidence](../native/drafts/upstream-156/audio-compressor-effect68-observations.json); **two output classes**, not eight unique Audio identities, direct internal tracing or real-device cohorts |
| Interrupted initial matrix | Producer disappeared before a report or logged measurement; original directory retained | No PASS/FAIL result assigned; completed matrix used a new fixed cohort, not retries of failed samples |

This does not resolve Legacy Audio-v1 failures or screen/DPR inheritance, prove
physical-device cohorts, admit the installed payload, or verify external anti-bot
services. The historical 001–067 failures below remain evidence, not current
0068 native results.

## Chromium 156 / 001–067 build and integration — 2026-10-29

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Source build 001–067 | **Build Succeeded**, 1966 actions, **1h28m46.46s**, j4; complete receipt and source/toolchain postguards passed | [Build-only evidence](../native/drafts/upstream-156/windows-build67-observations.json); AudioMath native/runtime gates and real CDP stamp are not verified |
| New manager/diagnostic regression | **4041 passed, 1 failed, 1 skipped**; tracked-source postguards passed | Failed cancellation test hit its one-second setup barrier; not a green suite |
| Cancellation control | Injected 1.2s identity persistence reproduced the setup failure; corrected setup barrier retains all lock/cancellation/deadline assertions | **623 runtime tests passed**, including slow persistence; no production timeout change; full canonical repeat pending |
| Canonical main regression after both setup fixes | **4047 passed, 1 skipped**, zero failures/errors, 401.39s; tracked-source postguards passed | Includes **625 runtime tests** with both slow-persistence cleanup paths; [source integration evidence](../native/drafts/upstream-156/canonical-app67-integration-observations.json); not browser or package admission |
| Strict GPU diagnostic calibration | WebGL1, WebGL2 and WebGPU **8/8 contexts each**, off and restart; effective feature arguments verified | [Stock156-only evidence](../native/drafts/gpu/stock156-runtime-observations.json); not execution of Glint's GPU policy |
| AudioMath 0067 | Compiled into the new candidate; experimental feature remains disabled by default | Native gate failed/incomplete, as recorded below; browser fidelity/analyser/worklet/realtime and combined checks remain pending; Audio-v1's 12 errors are not declared fixed |

### Completed native batch and subsequent controls

| Gate | Result | Boundary |
| --- | --- | --- |
| 001–067 native batch | **17/18 groups passed**, all source/SDK/core/receipt postguards passed; test build 1h20m44.41s / 726 actions | [Failed batch retained](../native/drafts/upstream-156/native-batch67-observations.json); overlapping filters are not independent coverage |
| AudioMath group | Failed/incomplete after policy rejected fixture Audio seed 3 duplicating WebGPU seed 3; no complete 11-case result | Fixture-only repair is unregistered; valid float seed 10 and duplicate-seed negative case propose 12 cases; no relaxed policy checks |
| Windows CI / `34583fc` | Python/QML, static checks, C++ policy and packaged-engine job passed | [CI run](https://github.com/Tort1k558/Camouflow/actions/runs/40933140951); upstream bootstrap/legacy-engine packaging is not custom Glint 0067 admission |
| Measured-environment source package | **4110 passed, 1 skipped** in isolated worktree; canonical main with draft control **4111 passed, 1 skipped**, 371.73s | Source postguards passed; no generated cohort or ordinary-user claim |
| Stock156 manager-mode controls | Desktop/mobile screen differs in cross-origin iframe in both requested phases; plain no-emulation control passed | [Reproducer and native repair contract](../native/drafts/environment/SCREEN_EMULATION.md); not Glint execution, not fixed by dropping requested settings |

### Actual 001–067 Audio/GPU diagnostics

The existing eight-gate **raw runtime suite passed 160/160** with unchanged
source/core/receipt: runtime 18, hardware 9, WebRTC 7, automation 55, fonts 42,
identity 18, CDP 6 and combined 5.
[Scoped runtime evidence](../native/drafts/upstream-156/runtime-suite67-observations.json)
does not admit the failed native AudioMath group, both math backends, the installed
package, remaining protected-surface combinations or external anti-bot results.

| Mode/gate | Fidelity | Analyser | Worklet | Realtime |
| --- | --- | --- | --- | --- |
| Baseline | **54/54** | **12/12** | **12/12** | **11/11** |
| Legacy Audio-v1 | **24/54 — failed** | **0/12 — failed** | **0/12 — failed** | **11/11** |
| Experimental Math, one owned profile | **54/54** | **12/12** | **12/12** | **11/11** |

The overall Audio command returned failure; all modes and failed observations
were retained. This key's Legacy counts differ from the older 42/54 fixture;
neither result is excused. Math fidelity hashes equalled baseline in this run;
**both backend branches and Float32 browser DSP execution are not verified**.
Resources closed and source/core/receipt postguards passed.

The strict GPU gate passed all four off/on/restart phases with **8/8 WebGL1,
WebGL2 and WebGPU contexts** each. Every phase reported the real selected CDP
revision, and unrelated driver feature flags were preserved. This covers metadata
minimization and real GPU operations, not WebGPU readback protection, a hardware
cohort, complete combined-policy admission or third-party anti-bot results.
[Source-bound failed overall scope](../native/drafts/upstream-156/canonical-audio-gpu67-observations.json)
retains the native AudioMath failure and all release/admission flags as false.

Ownership-bound resource monitoring and the Audio/GPU runners are now integrated
in main. No binary activation, release, CAPTCHA result or expanded capability
admission follows from this source integration.

## Python integration and additional 156 gates — 2026-10-29

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Canonical Python regression | **3862 passed, one skipped** after Runtime downgrade guard, failure retention and explicit 156 diagnostic support | Full `tests/`; source postguards passed; browser repeats are separate |
| Actual development payload | Official staging, archive and isolated install completed; **160 raw + 160 installed checks passed** | No activation; before the Python integration batch; compatible rollback not verified |
| Worker startup/denial | **60/60** classic/module dedicated/shared/service/nested cases passed, including restart and unavailable-policy rejection | Isolated candidate-aware CLI copy before canonical application; not worker pixel fidelity |
| Combined profile-identity surfaces | **12 phases passed**, including 24 nested Canvas cases, simultaneous profiles, restart and settled WebGL readback | Isolated CLI copy; not WebGPU or device-cohort admission |
| Audio-v1 fidelity | Baseline **54/54**; protected **42/54**, 12 identity/half-gain failures | **Failed gate** despite stable repeats, passing mutation controls and closed resources; no policy admission |

Canonical post-integration installed lifecycle **18/18**, workers **60/60** and
both derivation modes **12 phases / 24 nested Canvas cases each** passed with
source postguards. [Scoped evidence](../native/drafts/upstream-156/canonical-app66-observations.json)
retains the Audio fidelity failure; green isolation results do not erase it.

## GPU fixture 0066 — canonical native gates passed

| Checkpoint | Result | Boundary |
| --- | --- | --- |
| Full 001–065 native batch | 16/17 groups passed; GPU metadata retained 6 failures out of 33; all later groups collected | One Ninja invocation; source/SDK/core/receipt postguards passed; filters overlap |
| Applied/built 0066 | Real sync/hooks and full source replay; browser build 2m32.62s, one action; browser core unchanged, new complete receipt | Test fixture only; no new policy or package admission |
| Full 001–066 native batch | **17/17 groups passed**, including GPU **34/34**; one build invocation and all source/SDK/core postguards passed | Actual canonical executables; overlapping filters, not full worker-host or protected surface runtime coverage |

[Baseline batch evidence](../native/drafts/upstream-156/native-batch65-observations.json)
remains bound to the frozen 001–065 manifest. Do not reuse its receipt as 001–066.
The [new batch evidence](../native/drafts/upstream-156/native-batch66-observations.json)
binds `checkpoints/001-066.json`. Its browser/runtime/package gates are separate.

## Chromium 156 baseline and owned runtime results — 2026-10-29

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Chromium 156.0.8078.36 / 001–065 | Build Succeeded: 19,487 steps, 3h46m37.79s; browser owner exited zero | Not runtime admission; AudioMath 0068 excluded |
| Build postguards | Source/SDK/GN checks completed; `camouflow-build.json` records all three core hashes | No native fixture execution |
| Baseline manifest preservation | Byte-identical 001–065 manifest archived; all 65 referenced patch hashes checked; existing Audio/GPU-fixture records bind the frozen file | Reproducibility metadata only; no new source selection, runtime or package admission |
| First post-link identity queue | Stopped before tests because an unrelated project's live Ninja triggered the global compiler guard | Failed reports retained; downstream runtime/package queues did not run |
| Scoped guard correction | Workspace/binary scopes; unknown process details block; legacy unscoped calls stay conservative | Not a compiler lock bypass |
| Actual guard controls | Two owned sleeping Ninja processes: foreign scope accepted, own scope rejected with PID; both finished naturally | No foreign user processes modified; not native test execution |
| Resumed native identity-key target | 62 cases passed; native source/toolchain/browser-core postguards passed | Not document/worker identity or the remaining fixture targets |
| Native BrowserContext identity target | 37 cases passed; source/toolchain/browser-core postguards passed | Unit-level BrowserContext coverage; renderer/worker transport and browser policy admission remain unverified |
| Native identity transport target | 20 cases passed; source/toolchain/browser-core postguards passed | Unit-level transport coverage; not browser identity admission or native handoff completion |
| Native identity handoff target | 15 cases passed: three window-surface and twelve DocumentLoader inline-script policy units; source/toolchain/browser-core postguards passed | Native unit coverage, not full enabled renderer/worker lifecycle or browser-policy admission |
| Native document/worker delivery target | 34 cases passed with the corrected canonical verifier and independently with an identical isolated copy; full ordered patch-chain pre/postguards and ten delivery-source hashes retained | Old initial-draft comparison rejected later Surface Policy changes incorrectly; verifier-only correction, no Chromium-source change; not browser first-script/lifecycle admission |
| Native worker-surfaces / font targets | 55 endpoint/bootstrap cases and five font-policy parsing/field-preservation cases passed with postguards | Not actual worker-host first-script delivery, rendered text quality or capability admission |
| GPU metadata fixture diagnosis | Canonical target: 27/33 passed, six texture cases failed because the test base disables optional texture-query extensions. Corrected test-only shadow object linked against unchanged production libraries: all 34 named cases passed, including missing-extension rejection | Public patch is unselected; original canonical failure retained, native/package queues stopped; no runtime/driver/WebGPU or release admission |
| Chromium 156 full owned runtime suite | All eight gates passed: runtime 18, hardware 9, WebRTC 7, automation 55, fonts 42, identity 18, CDP 6, combined 5; 160 checks total | Source-build binary only; remaining native targets and installed-package gates are separate; no external anti-bot or complete Canvas/GPU/Audio admission |
| Disposable startup | 156.0.8078.36 opened the controlled page; sandbox requested, effective `--no-sandbox` absent; runtime resources closed | Regular raw/headless baseline, not concealed-automation admission |
| Extended baseline lifecycle | Two repeats each passed all 18 checks: isolation/five stores, permissions, crash/restarts, owned-process cleanup, controlled authenticated proxy, manager/scenarios, Recorder and backup/restore | One repeat had diagnostic logging, the other ordinary verbosity; not the full eight-gate policy suite |
| First extended baseline failure | Close timed out after five checks; temporary-directory cleanup then masked the primary failure | Negative retained; passing repeats do not explain or repair the timeout |
| Independent close diagnosis | 16 cycles across reviewed 148 and candidate 156, desktop/mobile, storage/diagnostics; 1.140–2.703s, owned processes exited | Same-host cross-version control, not matched stock156; no timeout increase or forced kill |
| Lifecycle during observed native build | Three serial runs each passed all 18 checks in 160.532 / 146.031 / 146.297 seconds; core/source postguards passed | Retention-patched verifier copy, ordinary logging; first close timeout remains unexplained; not a performance benchmark or the canonical policy suite |
| Native156 Audio calibration | 15 cases × three repetitions = 45 bit-exact native156 prototype matches; cleanup/postguards passed | Original unprotected baseline; the subsequent stock comparison is recorded separately below |
| Exact-version CfT source control | Official generation-pinned archive passed MD5/PE-version checks; live CfT reported 156.0.8078.36 / exact upstream revision | Per-version JSON 404 did not imply asset absence; not equal GN/toolchain/branding or full policy admission |
| Matched Audio Glint-off → CfT → Glint-off | 135 captures across 15 cases were bit-exact; all contexts closed and core/source postguards passed | One Windows host, policies off; float32 prototype differed on three discriminating cases; not math-mode/device-cohort admission |
| Public Audio browser CLI | Independently reran 135 captures matching all prior case hashes; five CLI rejections passed, including strict dummy-revision handling, output preservation and synthetic source-checkout protection | Idle builder required; prior 10s navigation timeout during linking retained without a proven cause; fresh profiles, not persistent restart or protected-policy admission |
| Broader Audio fidelity fixture calibration | Nine graph kinds at 44.1/48 kHz; two stock156 runs each passed 54 renders; exact known signals, repeated/segmented reads, buffer mutation and four fault-injection controls passed | Official stock calibration only; Glint-policy and AudioMath execution pending; oscillator/compressor checks prove repeatability, not complete DSP correctness |
| Native revision stamping | Current zero CDP stamp explained by upstream non-official GN default; isolated real-LASTCHANGE generation preserved version/branding and changed only stamp | Override staged, not applied/compiled; current native source binding is receipt/core hashes, not a runtime Git report |
| Compiled Glint branding | Main/app-list icons match project logo; ProductName in EXE/DLL and internal version-page heading are Glint; resource-pack postguards passed | Not OS taskbar/shortcut cache migration or fingerprint admission |
| Staged verifier evidence retention | Five actual held-file controls and an 18-check browser regression passed on a patched copy; original exception/profile retained on failure | Canonical verifier unchanged; underlying browser-close timeout is not fixed |
| Staged Windows profile-version guard | 22 owned marker/real-PE/mocked-launch controls; one real 148-to156 upgrade preserved five stores and identity; older selection rejected without changing files; isolated extended lifecycle passed all 18 checks, including backup/restore and cancelled startup | Unapplied Runtime patch; no older browser opened upgraded data; not general migration/rollback or Linux/macOS protection |
| Read-only Windows resource observer | 24 controls passed; one owned Glint sample covered seven OS-parent/creation-bound processes; 100 reads did not grow the handle count | Separate draft, not manager integration or a new memory limit; summed working sets are not unique RAM; not lifetime accounting or a performance benchmark |
| Read-only process-tree observer | 18 Windows controls passed; 100 subtree captures did not grow handles; two live Glint trees (nine/eight processes) were disjoint and covered their CDP-reported sets; child replacement invalidated CPU intervals | Stable observed topology, not an atomic/lifetime snapshot or profile authentication; no watchdog integration, limit change or performance admission |
| Current release-tool validators | 1,098 passed, one skipped in 61.40 seconds | Includes source/control and resource/tree checks; report validation is not additional native execution |
| Full desktop Python regression | 3,621 passed, one skipped in 467.85 seconds; 201 frozen inputs and 143 extra test/draft inputs unchanged | Full run at 01cdf4e, before the network-fixture additions below; not native fixture execution or remote CI |
| Initial ClientHello fixture | Public loopback capture parsed three fresh headless stock156 profiles; selected offer shapes repeated equally, original extension orders/message sizes varied; core/source/cleanup guards passed | Stock-only calibration; GREASE/order normalization is not full packet equality or JA3/JA4; TLS negotiation, Glint comparison, HTTP/2 and HTTP/3 remain unverified |
| Matched Glint-off / stock / Glint-off ClientHello | Nine fresh headless profiles had equal selected initial offer shapes; core/source postguards and runtime cleanup passed | Exact 001–065 receipt/core checkpoint; native CDP revision remains dummy; not full packet equality, TLS negotiation, HTTP/2/3, proxy/DNS or external detector acceptance |

Build evidence: `D:\Glint156Candidate\fixture-build-continuation-20261029-v2.json`;
core receipt: `chromium\src\out\CamouFlowNative\camouflow-build.json` below that workspace.
Guard process controls: `D:\GlintBuilderGuardProbe-20261029-v2\report.json`.
Context target evidence: `D:\Glint156Candidate\identity-after-link-20261029-v5\identity-contexts.json`.
Recovered handoff target: `D:\Glint156Candidate\identity-after-link-20261029-v6\identity-handoff.json`.
Full runtime evidence: [`runtime-suite-observations.json`](../native/drafts/upstream-156/runtime-suite-observations.json);
raw reports: `D:\Glint156Candidate\runtime-after-identity-20261029-v13\suite`.
Public CLI/runtime-evidence regression: `tests/test_release_tools.py` — 1101 passed,
one skipped in 90.72s; isolated log in
`D:\Glint156Candidate\public-audio-cli-python-regression-20261029-v2\pytest.log`.
Broader Audio calibration: [`audio-fidelity-observations.json`](../native/drafts/audio-dsp-math-v2/audio-fidelity-observations.json);
raw `D:\Glint156Candidate\audio-fidelity-stock156-20261029-v1` and
`audio-fidelity-stock156-controls-20261029-v1`.
After adding the fidelity fixture: `tests/test_release_tools.py` — 1102 passed,
one skipped in 105.31s; isolated log:
`D:\Glint156Candidate\audio-fidelity-python-regression-20261029-v1\pytest.log`.
Delivery correction: `D:\Glint156Candidate\delivery-composition-runtime-20261029-v1`;
isolated verifier regression: 242 passed (23.98s). Queue v8 stopped at the stale
delivery guard; recovery v9 stopped on a scoped compiler conflict. Both retained.
After checking that scope idle, v10 resumed the remaining targets; package v7 is
bound to its live process. Prior passing keys/contexts reports are explicitly reused.

Full desktop regression at `90ab928`: **3619 passed, one failed, one skipped**
(448.16s), unchanged source guards. Failure: the QML test read a profile-dialog
button before it existed. The original focused test then passed; its fixed
version now waits for dialog readiness with a bounded deadline. All eight QML
tests passed (36.60s). This does not turn the earlier full run into a pass.
Corrected canonical verifier and QML regression: **1111 passed, one skipped**
(107.59s), `tests/test_release_tools.py` plus `tests/test_qml_python_editor.py`;
log: `D:\Glint156Candidate\delivery-guard-python-regression-20261029-v1\pytest.log`.
Transport target: `identity-transport.json` in that directory; lifecycle repetitions:
`D:\Glint156Candidate\lifecycle156-under-build-20261029-v1\report.json`.
Sanitized evidence: [`windows-runtime-observations.json`](../native/drafts/upstream-156/windows-runtime-observations.json).
Staged fix and application boundary: [`runtime-verifier/README.md`](../native/drafts/runtime-verifier/README.md).
Per-profile version guard: [`profile-version/README.md`](../native/drafts/profile-version/README.md).
Resource observer: [`resources/README.md`](../native/drafts/resources/README.md);
raw owned evidence: `D:\Glint156Candidate\windows-resource-reader-20261029-v4\report.json`.
Tree evidence: `D:\Glint156Candidate\windows-process-tree-20261029-v2\report.json`.
Latest full Python regression: `D:\Glint156Candidate\python-audio-fidelity-regression-20261029-v2\report.json`.
Earlier full run: `D:\Glint156Candidate\python-resource-tree-regression-20261029-v1\report.json`.
Network fixture: [`network/README.md`](../native/drafts/network/README.md),
[`stock-clienthello-observations.json`](../native/drafts/network/stock-clienthello-observations.json);
32 parser/lifecycle/binding tests passed in 10.36s, independently of the earlier full run.
Raw capture: `D:\Glint156Candidate\stock-clienthello156-20261029-v2`.
GPU fixture diagnosis/correction: [`gpu-transport/README.md`](../native/drafts/gpu-transport/README.md),
[`optional-query-fixture-observations.json`](../native/drafts/gpu-transport/optional-query-fixture-observations.json).
Raw corrected tests: `D:\Glint156Candidate\gpu-texture-fixture-fix-20261029-v1\trace-tests.json`.
Patch/evidence and network regression: **1136 passed, one skipped** (64.67s),
`D:\Glint156Candidate\gpu-fixture-python-regression-20261029-v1\pytest.log`.
The unaffected worker-surfaces/font targets finished with postguards under
`native-tail-after-gpu-diagnosis-20261029-v1`; they cannot admit the failed full queue.
Frozen source contract: [`001-065.json`](../native/drafts/upstream-156/checkpoints/001-065.json).
Checkpoint/release-tools regression: **1105 passed, one skipped** (63.19s),
`D:\Glint156Candidate\native65-checkpoint-python-regression-20261029-v1\pytest.log`.
Batch orchestration and network/evidence regression: **1165 passed, one skipped**
(59.02s); final D:-temporary-directory batch controls: **27 passed** (1.47s).
Single-target APIs retain the existing regression coverage. The batch builds each
required executable in one Ninja invocation and collects case failures; its real
native replay is not yet an admitted gate.
Matched network evidence: [`matched-clienthello-observations.json`](../native/drafts/network/matched-clienthello-observations.json),
raw `D:\Glint156Candidate\matched-clienthello156-20261029-v1`.
Stock control: [`stock-control-observations.json`](../native/drafts/upstream-156/stock-control-observations.json);
matched Audio: [`matched-stock-observations.json`](../native/drafts/audio-dsp-math-v2/matched-stock-observations.json).
Public runner and scoped evidence: [`browser_matrix.py`](../native/drafts/audio-dsp-math-v2/browser_matrix.py),
[`browser-cli-observations.json`](../native/drafts/audio-dsp-math-v2/browser-cli-observations.json).
Raw CLI records: `D:\Glint156Candidate\public-audio-aba156-20261029-v4` and
`public-audio-cli-negatives-20261029-v3` below that workspace; failed navigation
attempt retained in `public-audio-aba156-20261029-v3`.

The old identity/runtime/native/package processes were confirmed missing after
handoff step 1062/1498; cause/exit codes are unknown, not labelled a compiler failure.
Source/core audit passed and cached objects remain. The resumed handoff invocation
initially scheduled 435 steps, not a clean 1498-step rebuild. Recovery queues are identity v6
→ runtime v13 → remaining-native v8 → package v6, still j4 and no activation.
Audit: `D:\Glint156Candidate\interruption-recovery-20261029-v1\report.json`.
Remaining identity/native targets, canonical eight-gate policy suite, installed
runtime, compatible rollback and shutdown reliability evidence remain required
before any candidate release claim. No detector/CAPTCHA outcomes are asserted.

## Unselected AudioContext math integration — 2026-10-29

| Check | Result | Boundary |
| --- | --- | --- |
| Full source replay | 65 selected patches + draft 0068 applied to 194 pinned 156.0.8078.36 inputs; GPU ordinals and GRIT preserved | Not a complete GN build |
| Context policy code | Captures a const mode/error in BaseAudioContext construction; domain-separated derivation; instance-owned compressor backend; math/readback paths exclusive | Feature disabled by default; manager admission unchanged |
| Isolated objects | Six production objects + test TU compiled with original Chromium flags and a private header/source overlay | No link; does not prove graph completeness or all changed-layout consumers |
| Native fixtures | Eleven: capture/caching, missing policy, context/handler isolation, seed preservation, invalid enum, direct DC, first-node ordering, stopped-context precedence, detach/navigation | Translation unit compiled; none executed |
| Earlier full local Python regression | Seven-fixture revision: 3,591 passed, one skipped in 297.61 seconds | Predates constructor capture; not C++ execution or remote CI evidence |
| Current release-tool Python regression | Constructor-capture revision: 1,074 passed, one skipped in 43.54 seconds | Metadata/source/probe validators, not execution of the native fixtures |
| Actual lifecycle API controls | Six same-host stock/Glint-off 148 captures allow nodes after close/detach; retained detached OfflineAudioContext reports suspended | Baseline only, not the new 156 math integration |
| Active build isolation | All 201 frozen inputs unchanged | Draft is outside both selected engine manifests |

Sources and hash-bound scope: [`context-integration.json`](../native/drafts/audio-dsp-math-v2/context-integration.json).
The first test-object compile found an invalid `destination()` C++ call; it was
corrected to `destinationNode()`. The failed evidence remains retained, not relabeled passing.
The later constructor-capture revision also compiled all seven isolated objects.
[`Lifecycle control evidence`](../native/drafts/audio-dsp-math-v2/audio-context-lifecycle-observations.json)
motivates removing lazy document-seed lookup but does not execute the new policy.
The earlier 90 stock/Glint-off 148 captures calibrate the standalone native DSP
baseline only; they do **not** verify this AudioContext integration or a float32
device cohort. Fresh-156 calibration, native execution, lifecycle, realtime,
AudioWorklet and audible-quality/performance checks remain required.

Living test register. Update after every linked Glint build; keep previous build
results rather than replacing them. A planned check is not a passing result.

## Matched 148 Audio DC calibration — 2026-10-29

The formerly source-derived conflict is now observed in **Glint 148.0.7778.96**.
The stock control used that same version and the same owned HTTP origin, launch
configuration and sandbox setting. Glint's flat runtime matched the immutable
managed package's three core hashes and exact compiled 62-patch receipt.

| Scope | Observed result | Meaning |
| --- | --- | --- |
| Stock baseline + Glint policy-off baselines for profiles A/B | All 12 value captures exact | 0 / 0.25 / -0.25 / 0.5 retain literal float32 bits |
| Glint protected A/B, partitioned and profile-identity modes, identity restarts | 14 / 24 captures have a one-bit difference | Count includes restart repeats, not 24 independent profiles |
| Identity-mode restart | Same output before/after restart | Stable output is not proof of fidelity |
| Every measured result | 256 frames, 44,100 Hz, mono; shared event/Promise buffer; context closed | Narrow document-only API/lifecycle observations |
| Owner cleanup + data/core guards | Ten owners released runtime handles; owned identity payloads, stock/flat/managed cores, receipt and all 201 active-build inputs unchanged | Not a broad OS-process/resource stress test |
| Collector versus compatibility | Measurement complete, no harness errors; compatibility **false**, no admission | Exit 1 preserves a measured negative result |
| Python evidence validators | Focused: 74 passed, 969 deselected in 13.14s; full local suite: 3,560 passed, one skipped in 288.14s | A passing validator preserves the negative browser result; not Audio compatibility admission |

Public sanitized evidence: `native/drafts/upstream-157-prefix/audio-constant-observations.json`.
Private full report: `D:\Glint157ObjectCache\glint148-audio-dc-ab-20261029-v1\report.json`.
No private profile keys, user data or machine paths are included in the public
record. The record and JS probe are hash-bound by the pending-fixture descriptor.
These results do not assert native 156/157 failure or any detector/CAPTCHA score.

Next: keep Audio-v1 as experimental farbling only; resolve the plausible-profile
Audio model against literal-signal, identity-graph and segmentation controls.
Do not promote distinct/stable hashes into a compatibility pass or use a
per-buffer flatness shortcut that changes results at chunk boundaries.

## Pending 157 chunked-Audio fixtures — 2026-10-29

`native/drafts/upstream-157-prefix/0066-native-chunked-audio-tests.patch` prepares
eleven native test bodies but is **outside the selected manifests and `patches/`**.
It modifies only `offline_audio_context_test.cc`; all 12 existing test cases remain.
The companion descriptor binds the patch and source input to the complete 001–065
157 manifest. Current selection stays at 65; compiled/executed/admitted stay false.

| Preparation check | Actual result | Limit |
| --- | --- | --- |
| Patch application | Applied to an isolated copy after full 65-patch replay | Not C++ compilation |
| API header provenance | Five exact pinned Git blob hashes verified; four match 156, one changed header fetched once from pinned Gitiles and validated | Not include-closure or ABI/codegen validation |
| Fixture coverage in code | Missing policy, native zero/overflow/closed-state precedence, rounded budget/retry, small chunk of large finite context, queued final event identity, nonzero signal vectors, flag-off indefinite close, protected suspend/resume and paused-close | Eleven cases prepared, none run |
| Independent signal vectors | Seed 4 maps `3e800000` to `3e800000`; seed 5 maps it to `3e800001` | Python HMAC calculation, not native rendering |
| Active-build isolation | All 201 sealed 156 inputs remain unchanged | The current browser build is still required |
| Earlier eight-case focused Python source/metadata checks | 73 passed, 969 deselected in 13.09s | Not execution of the C++ fixtures |
| Earlier eight-case full local Python suite | 3,559 passed, one skipped in 296.08s | Not a 157 compilation or native/runtime result |
| Current eleven-case Python source/metadata checks | 73 passed, 969 deselected in 13.52s | Fixture bindings and calibration separation only |
| Current full local Python suite | 3,559 passed, one skipped in 295.17s | Not execution of the eleven C++ fixtures |

The three-channel budget case deliberately uses 5,592,405 requested frames:
67,108,860 bytes fits, but 128-frame rounding requires 67,109,376 bytes and must
reject before allocation. A following 128-frame request exercises retry cleanup.
The queued event changes the final sample to test Promise/event object identity;
nonzero constant-source samples separately distinguish raw from protected output.
The final fixture also checks separate channel storage, exact 128-frame signal
shapes and seed order 4/5/4 so empty buffers or stale latest-policy state cannot
make the vector loops pass vacuously. Fatal source-setup assertions propagate
to the outer test instead of continuing with silence.

The protected pause/resume case checks both pending results before resuming,
then exact protected samples and the single final event. The paused-close case
checks both pending render Promises plus a future suspend: all reject after
closing, with no completion event even after draining pending tasks. Another
case preserves the native closed-state error before missing-policy lookup.

Copy-failure injection/queue cleanup and teardown lifetime still need fixtures;
all eleven cases still require real compilation/execution. No new pass
is claimed for any browser fingerprinting site or CAPTCHA service.
Evidence: `D:\Glint157ObjectCache\chunked-audio-fixtures-20261029-v5\report.json`;
patch SHA-256 `7af3d17d78f85dc138252f0fde80e111f26abe5d20c236ddc59930cbd8a927ca`.

### Constant-source fidelity control

The current v1 vector for seed 5 maps input `3e800000` (`0.25`) to `3e800001`.
That is a transform-mechanics check, **not a compatibility acceptance criterion**.
The [Web Audio model](https://www.w3.org/TR/2026/WD-webaudio-1.1-20260922/#ConstantSourceNode)
and inspected Chromium constant-source handler make literal-value calibration
an important separate control. The source-derived conflict needs matched-version
stock/native measurements; it is not yet an observed 156/157 browser failure.

| Actual runtime control | Result | Scope |
| --- | --- | --- |
| Stock Chromium 148.0.7778.96, fresh isolated D profile | 0 / 0.25 / -0.25 / 0.5 each returned exactly 256 expected samples, 44,100 Hz, one channel; event/Promise identity and closed state passed | Stock only; no Glint flags or user profile |
| Public JS probe and binary/core identity | Probe SHA-256 `6256225d885534402d4d6898c0fa6ea24cf2aace548df960cd2e1e01803f7b89`; stock core unchanged before/after | Not native candidate admission |
| Matched 156/157 calibration and revised Audio algorithm | Pending; production/compatibility gate explicitly false | Different hashes alone cannot satisfy it |

Evidence: `D:\Glint157ObjectCache\stock-audio-dc-control-20261029-v4\report.json`.
`audio-constant-control.js` is public and bound in the pending-fixture descriptor.
The final control requested Chromium sandboxing and verified the absence of
`--no-sandbox` via CDP. `--enable-automation` was explicitly supplied for that
inspection; an earlier inspection without it failed and is retained as failed
evidence, not a passing control. No global driver/security configuration changed.
The official CfT exact-version metadata URL for 156.0.8078.36 returned HTTP 404;
`stock-control156-20261029-v1/metadata-report.json` retains that result. No alternate
binary was silently substituted, downloaded or installed for a matched control.
Do not add a flat-buffer shortcut: it can make output depend on chunk segmentation.

## Current 001–065 compilation gate — 2026-10-29

The test-only 0065 repair is now selected and applied. Candidate manifest SHA-256:
`4df5b5d3ccc702376746ffe9c89020291c1b447136e327f7f3dbf2b5407b2be0`.

| Check | Measured result | Limit |
| --- | --- | --- |
| Production batch, 85 selected targets | Passed; zero executed steps, existing production objects reused | No new production sources in 0065; not 85 fresh compilations |
| Fixture batch, all 38 mapped targets | Passed; three repaired objects rebuilt in 27.34s | No test executable linked or run |
| Source/toolchain/GN postguards | Passed | Runtime remains unverified |
| Dependency stage rebinding | DEPS, gclient, dependency snapshots and pins unchanged; sync/hooks rebound | Neither stage was re-executed |
| Source replay, default .36 and refresh .75 | All 65 applications passed, GPU/GRIT invariants preserved | Refresh has no compiler/runtime proof |
| Full 157 source workbench | All 65 applications passed over 185 inputs, GPU/GRIT invariants preserved | No 157 compilation/runtime proof |
| Focused local Python selection | 72 passed, 969 deselected in 12.02s | Not native test execution |
| Full local Python suite after activation | 3,558 passed, one skipped in 295.18s | Not remote CI or native/runtime proof |

The browser build resumed at **j4**, log `build-20261029-074910.log` on D.
Source, GN, selected patches and `native_build.py` are frozen during it.
Fresh bound observers: browser continuation v2 → identity v4 → runtime v11 →
remaining native v6 → packaging v4. The packaging observer seals **201 inputs**;
staging/install tests remain isolated, with no activation or production release.

Evidence: `fixture-activation65-20261029-v2/{report.json,production.log,fixtures.log}`,
`default65-replay/report.json` and `refresh65-replay/report.json` under that root;
157: `D:\Glint157ObjectCache\public-full65-replay-v2\report.json`, manifest hash
`993a96741731d2e9dcfd214ec694be4ebdca47e60641be0692ceb1641806d7ed`.
The first activation observer incorrectly compared the list tail, although the
proof groups V8 last. Its failed report is retained; recovery verified the
unchanged 64 rows by patch identity before rebinding. This was an observer
assertion, not a new compiler error or an object-cache reset.

A fresh upstream audit bound to this 65-patch manifest still reports
`behind-stable`: selected 156.0.8078.36 versus observed 157.0.8103.27. Exit 1 is
the intended policy result, not an HTTP/build failure. Evidence:
`upstream-audit-candidate-20261029-v4.json` on D. `production_admitted` remains
false; the diagnostic build is not a security-reviewed production release.

## Chromium 156 fixture compilation — 2026-10-29

The 38-target keep-going probe finished in **48m45.34s**, with 3,349 graph steps
done, **three failed**, zero remaining. Source/toolchain/GN postguards passed.
These are compilation results, not executed native tests.

| Failed translation unit | Actual cause | Repair scope |
| --- | --- | --- |
| `worker_thread_test.cc` | Six calls to nonexistent `WorkerThreadForTest::WaitForInit` | Use the existing reporting proxy's post-evaluation wait |
| `privacy_worker_service_unittest.cc` | Storage-key calls omit the new opaque-origin flag; repairing them also exposes missing renderer-origin flags | Pass matching explicit false/true flags to both APIs in legacy/opaque cases |
| `gles2_cmd_decoder_passthrough_unittest_commands.cc` | Raw-pointer canary indexing rejected by unsafe-buffer checks | Typed result/guard storage with wire-offset and shared-buffer-bound assertions |

The browser continuation and all dependent native/runtime/package observers
stopped for inspection. **No browser build or runtime test started from this
queue.** Existing objects and all failed reports are retained.

The three repaired copies **all compiled** with the original Clang flags and
generated dependencies. Source/toolchain/GN postguards and `git apply --check`
against 001–064 passed. The initial probe failed to locate the relative compiler
before launching it; a second probe exposed the renderer-origin argument pair.
Both failed probes remain retained. The final successful evidence is
`D:\Glint156Candidate\fixture-portability-20261029-v2\probe-v2\compile-report.json`.
No test executable was run. The public follow-up
`native/drafts/upstream-156/0065-native-fixture-portability.patch` has SHA-256
`ff16a253d7630119e78db2b929d635ea81a7ccecf2340a899bd1eea9d763b6e8`.
It is outside the selected `patches/` directory and **not applied or included in
the current manifest**; the original 001–064 source tree remains unchanged.

## Chromium 157 complete source application — 2026-10-29

The explicit full manifest now applies **all 64 patches over 185 inputs**.
The separate 32-patch prefix remains available; its earlier results are unchanged.

| Check | Result | Limit |
| --- | --- | --- |
| Public verifier, full 157 manifest | 64 applications passed; input/patch postguards passed | No C++ compilation or runtime execution |
| GPU protocol invariant | 321 commands preserved; appended ID 577 | Not a GPU execution test |
| GRIT structure | Preserved | Not a resource compilation test |
| Audio API adaptation | Uses actual rounded chunk size; captures successful policy/flag-off once; protects chunks before Promise resolution; closes/rejects on failed copy | Uncompiled prototype; native chunk/queue/error tests still required |
| Upstream compatibility | Preserves optional total length, resolver/target queues, final-only completion event, and newly added GPU idle-trim tests | Runtime behavior unverified |
| Focused local Python selection | 47 passed, 993 deselected in 11.32s | Source/metadata assertions, not native Audio tests |
| Full local Python suite after this package | 3,557 passed, one skipped in 293.77s | Not remote CI or native/runtime proof |

Public reproduction uses `native/drafts/upstream-157-prefix/full-inputs-manifest.json`.
Evidence: `D:\Glint157ObjectCache\public-full64-replay-v3\report.json`;
manifest SHA-256 `09aeedfc25371d8535f1c8efc67f699fe863ff459389044e2257baa6628a163b`.
The initial relative-path CLI invocation refused noncanonical paths; its log is
retained, and the successful run used resolved absolute paths. Earlier 0033,
0055, 0056 and 0061 application failures remain retained, not rewritten.
The active 156 manifest/source/GN files were not changed, and all 200 queued
packaging input hashes still match. No 157 build target, release, activation,
runtime admission or CAPTCHA score is implied.

## Explicit candidate upstream audit — 2026-10-29

### Audio portability and keep-going object batches — 2026-10-29

The 001–063 browser run terminated after **16m35.57s**, with 1,706 graph steps
done, one failed and 31,133 remaining. The actual error was the direct `memcpy`
in `offline_audio_candidate.cc`, rejected as
`-Werror,-Wunsafe-buffer-usage-in-libc-call`; log `build-20261029-061558.log` on D.
All downstream observers stopped without native/runtime/package work.

Append **0064** copies the same non-NUL domain bytes through a bounded character
span and `std::ranges::copy`. HMAC calls, seeds, normalized samples, caches and
GN flags are unchanged. The current 156 manifest is
`f752426cf5435cf02f9d19cd648101ad8b0369ce8f611c9adcf6065f3bdbbdcb`.
Dependency identities were checked/rebound for this C++-only append; prior
records are retained and **sync/hooks were not re-executed**.

| Check | Actual result | Limit |
| --- | --- | --- |
| Patched production compile batch | 85 selected object targets covering all 83 mapped patched production sources succeeded, with postguards | Includes reused objects/dependencies; not 85 tests or a linked browser |
| Keep-going policy | j4, `-k 0`; 538 executed graph steps completed in 3m57.85s | Only selected object/dependency scope |
| Audio message-layout comparison | 65,536 guarded old/new byte-layout pairs matched | Standalone MSVC fixture, not HMAC/Audio runtime |
| Native fixture compilation | 38 mapped test translation units queued at j4, keep-going | No fixture executed; result pending |
| Validating-decoder fixtures | Two source files absent from effective Windows graph; GN query returned `enable_validating_command_decoder = false` | Zero coverage for those two files, not PASS |

Evidence on D: `audio-safe-copy-20261029-v1/{report,layout-report-v2}.json`,
`patched-production-objects-20261029-v1.json`,
`patched-fixture-compile-20261029-v1/report.json` and
`patched-fixture-effective-decoder-20261029-v1.json`. The first layout harness
invocation used an invalid VsDevCmd argument and remains failed; its corrected
version changes only that invocation and retains the same product bytes.

Final local Python regression after the 64-patch and 157-manifest updates:
**3,556 passed, one skipped**, 292.92 seconds. Log:
`pytest-audio-and-157-manifests-full-20261029-v1.log` on D; selected Ruff checks
passed. These are local checks, not a completed remote CI run or native fixtures.

Source replay of all **64 patches** passed for both .36 and .75; GPU ordinals
(321 preserved plus command 577), GRIT structure and input/patch postguards
passed. Reports: `audio-safe-copy-20261029-v1/{default-64-replay,refresh-64-replay}`.
This is not C++/runtime verification of .75.

The current process-bound sequence waits for the fixture compiler through
`fixture-build-continuation-20261029-v1.json`, then resumes the browser j4 build
only on passing compiler/postguard evidence. It is followed by identity v3 →
runtime v10 → remaining-native v5 → package v3. Package v3 guards 200 inputs.
All of these stages keep production/privacy admission false; compatible rollback
still needs independent evidence. A stale PID assertion refused the first v3
package observer before creating its report or starting children; the corrected
observer binds the actual current process and preserves that refusal log.

### Complete 157 input corpus, incomplete Audio port — 2026-10-29

The 90-second Gitiles continuation reached **84/185 inputs** before another
response-body timeout; `upstream-forward-preflight-20261029-v5/report.json`
retains that failure and all postguards. An isolated Git capability query
advertised filtering but was stopped while listing excessive refs. The later
filtered tree fetch hit its configured cache-size bound and remains failed.
Neither operation is reported as a successful clone/checkout.

A completed pack from that interrupted fetch contained the pinned commit/tree.
An offline, remote-free view verified the commit's actual Git object ID and
checked cached file bytes against tree blob IDs. That resolved **157 inputs**
without network access. A separate bounded request explicitly fetched the
remaining **28 verified blob IDs**; 709,293 cache bytes / 2,939,607 decoded bytes.
The final offline plan materialized all **185 checksummed pristine inputs**.
There was no checkout, active-source edit, retry loop or alternate origin.
The three V8 inputs retain their previously verified immutable Gitiles/DEPS pin.

Evidence under `D:/Glint157ObjectCache`: `capabilities.json`,
`pinned-tree-report.json` (failed), `offline-tree-proof.json`,
`sparse-plan-20261029-v1/report.json`, `blob-fetch-report.json`, and
`sparse-plan-20261029-v2/report.json`. Git cache jobs checked the active HEAD,
config and candidate manifest unchanged; a separate full replay attempt guarded
303 active inputs. Individual verified objects are reusable; the interrupted
operation itself is not relabeled as passing.

The public [157 workbench](../native/drafts/upstream-157-prefix/README.md) now
separates a verified **88-input / 32-patch prefix** from the complete
**185-input / 64-patch attempt**. Both public cache-fetch CLIs passed with zero
HTTP requests. The prefix replay passed; the full replay **failed at 0033 after
32 applications**, retaining input/patch postguards. Reports:
`public-prefix32-{inputs,replay}`, `public-full185-inputs` and
`public-full64-attempt` under that D: cache. GPU/GRIT invariants remain outside
the prefix's selected scope, not silently admitted.

The next real port is 157's chunked OfflineAudioContext: optional total length,
actual-chunk allocation budgets, stable captured policy and cancellation. Each
chunk Promise needs the transformed result; only the final chunk has the native
completion event, sharing that same object without changing event timing.
The old hooks cannot be made correct merely by forcing
an optional length or dropping upstream chunking/tests. No 157 C++ compilation,
native/runtime/security/package admission is established.

### Actual 156 build failure and safe-buffer append — 2026-10-29

The frozen 001–062 browser build terminated after **4h04m28.94s**: Siso reported
21,909 done, three failed and 35,571 remaining. These are that run's graph
counters, not an ETA or a runtime test count. The failed objects were
`navigator_concurrent_hardware`, `navigator_device_memory` and
`canvas_readback_candidate`. All diagnostics were actual
`-Werror,-Wunsafe-buffer-usage` errors in our hardware parsing/Canvas encoding,
not an out-of-memory or disk failure. Original log:
`build-20261029-015415.log` on D. Downstream controllers stopped without starting
units, runtime gates or packaging; their failed reports remain preserved.

Append **0063** replaces raw hardware-array indexing with typed option ranges,
gets the parse endpoint through the string-view iterator, and encodes Canvas
words through fixed-size spans. Both renderer/browser copies of the hardware
header are covered. The original 62 patch files, GN arguments, toolchain and
upstream pins remain unchanged. No unsafe-warning suppression was added.

| Check | Measured result | Limit |
| --- | --- | --- |
| Actual failed production objects | All three compiled; source/toolchain postguards passed | Formatted variant, not a linked browser |
| Final minimal-style refinement | C++ tokens match; all three final-form objects subsequently compiled in the resumed build | Full browser still building |
| Existing standalone MSVC fixtures | Passed against the fixed hardware header, including glyph controls | Not Chromium native fixtures |
| Old/new parser comparison | 24,025 input pairs matched, including overflow, embedded NUL and malformed values | Bounded corpus, not all strings |
| Canvas word/message layout comparison | 196,608 guarded pairs matched | Encoding only, not full HMAC/readback/fidelity |

Evidence on D: `safe-buffer-port-20261029-v1/{applied-probe,semantics-report-v2}.json`
and `safe-buffer-minimal-style-20261029-v1/applied.json`. The first MSVC comparison
fixture failed because its legacy header was included after Windows `min` macros;
that harness failure remains retained. The corrected fixture includes it before
Windows headers; it does not change product code or disable production diagnostics.

Dependency stage records were rebound to the appended C++ manifest only after
checking the prior stage identities and unchanged DEPS, gclient/dependency
snapshots and pins. Original records were saved; **sync/hooks were not rerun**
and no dependency re-execution is claimed. A second whitespace/comment-only
refinement preserved C++ tokens and the same dependency identities.

The final candidate manifest is
`e41540549bfec2cae38beb5cb78be70a7da36068241fcc12e24210b55ee9864a`.
The browser build resumes at j4 through
`safe-buffer-build-continuation-20261029-v1.json`, preserving compiled objects.
The new bound sequence is identity controller v2 → runtime v9 → remaining-native
v4 → package controller v2. Those are pending observations, not passing native,
runtime, relocated-payload or production evidence. Package v2 guards 199 inputs;
failed earlier controllers are not relabeled or reused.

`safe-buffer-minimal-style-20261029-v1/final-object-observation.json` records
the three actual final-form compile events and matching source hashes; 297
prior source/build hashes remain unchanged. Only the manifest and three named
C++ files differ from that prior cohort. Final public source replays also
passed: **63 patches on .36**, **63 on .75**, and the unchanged **29-prefix on
157**. Reports live under the same directory in `default-63-final-replay`,
`refresh-63-final-replay` and `157-prefix-final-replay`. Full 156 replays preserve
321 GPU IDs plus command 577 and GRIT structure. These are source invariants,
not 63 executed native tests or security admission.

Final Python regression: **3,554 passed, one skipped**, 294.14 seconds; selected
Ruff checks passed. The preceding full run retained one expected-count failure:
the manifest fixture assumed exactly 62 ported rows. Its update still checks
every original row/hash and LF payload, plus the explicit 0063 append. Both logs
remain on D as `pytest-safe-buffer-full-20261029-v1.log` and `v2.log`.

### Public pinned sparse-source fetch — 2026-10-29

| Check | Observed result | Limit |
| --- | --- | --- |
| Read-only cache fetch | 185 validated files, zero HTTP requests | Not a cold network download |
| Replay from fetched output | All 62 patches passed; postguards unchanged | No C++ compilation/runtime proof |
| Cold official HTTPS control | One pinned `chrome/VERSION` fetched and hash-checked | Not all 185 files |
| Failure controls | Cache/path/size/hash drift, redirects, HTTP 429/503 covered | Synthetic HTTP failures, not service availability |
| Active build inputs | 301 hashes unchanged, reviewed helper hashes checked separately | No build restart or new capability admission |

Evidence: `public-source-fetch-proof-20261029-v1/report.json` on D.
The public CLI uses fresh external output, prevalidates present cache files,
spaces requests by at least two seconds and never retries or switches mirrors.
Failed output/report is preserved. Manual resume requires a new output and
operator-managed server cooldown; no automatic resume is implemented.
Manifest LF checkout rules preserve raw hash bindings across platforms without
changing the original .36 candidate. Earlier reports retain their measured hashes.
Full local application regression: **3,553 passed, one skipped**, 328.04 seconds;
CI Ruff selection passed. These are local results, not a completed remote CI run
or Chromium 156 runtime proof.

The public upstream auditor now supports `--candidate upstream-156`, reusing
the existing canonical candidate loader rather than changing `build-lock.json`.
The base lock, candidate manifest and complete patch chain are guarded across
the official HTTPS request. Unknown candidates, cached-base mismatch, changed
base/manifest/patches, redirects and oversized responses refuse evidence.
Default 148 comparison remains unchanged. A nullable highest-observed
same-milestone row separates patch-line drift from a new major version, without
weakening the highest-Stable comparison or setting production admission.

Fresh calls to [ChromiumDash Windows Stable metadata](https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Windows&num=20)
observed **157.0.8103.27** (`f9d7b13a569b352a0267234ea5740fdecc83ffa2`),
published October 28 at 17:56:24.686 UTC. The bounded response also contains
**156.0.8078.75** (`861389936bf33ea77529ee5dcc0605e68f6bb620`). Both the default
148 pin and candidate 156.0.8078.36 return `behind-stable` and
`production_admitted=false`. This is version/revision evidence, not a CVE audit
or a claim that any observed release is already a usable fork target.

Evidence on D: `upstream-audit-default-20261029-v2.json` and
`upstream-audit-candidate-20261029-v2.json`. Candidate evidence binds manifest
`b62ae2c7a20b52461dfa5a7e1e68c8105813792c3e377e346f651f6e133f1875`;
the active Chromium build, inputs and default pin were not changed or restarted.
Finish and validate the frozen 156 baseline first, then select/review the next
immutable upstream target and repeat source/native/runtime/package gates before
publication. No automatic rebase, download or production activation was added.
Focused auditor tests passed **27 cases**. The full application suite passed
**3,507 tests, one skipped** in 293.48 seconds; CI Ruff selection passed.

### Isolated forward-source preflight

Sparse retrieval for observed 156.0.8078.75 stopped at **75 of 185 recorded
inputs** after Gitiles returned HTTP 429. Pending requests were cancelled;
there was no retry loop, mirror fallback or checkout update. The 157 target
was not fetched and the complete 62-patch replay was not attempted. The retained
failed preflight is `upstream-forward-preflight-20261029-v1/report.json` on D.
All **302 active source/build input hashes** stayed unchanged.

An offline follow-up reused only hash-validated cached files and applied the
supported **001–029 prefix** to the exact 156.0.8078.75 revision. Its Chromium
DEPS pins V8 `235050a0df6db2c9d92a419af2b72fbf3b2dd73b`; the three fetched
inspector inputs matched the old candidate bytes. Patch 0030 needs five source
files absent from this cache, so the prefix was explicitly bounded there.
No new network requests were made for this follow-up. Evidence:
`cached-forward-prefix-20261029-v1/{report,replay/report}.json` on D.
This is **29 source-context applications, not 29 compiled/native tests**, a
complete security update or a usable newer browser. Continue retrieval later
with cache validation and a lower request rate, respecting server cooldown.

### Rate-limited cache resume

A separate resume waited at least 15 minutes after the stopped attempt and
limited request starts to one every two seconds. It reused all 75 validated
cache entries without replacement requests. For **156.0.8078.75**, all **185
inputs** were retrieved and **all 62 unchanged draft patches** applied/check-
applied successfully. Seven upstream inputs differ from the .36 manifest.
The verifier preserved 321 GPU command IDs and appended the metadata command at
577; GRIT element structure/attributes were preserved. Chromium DEPS/V8 binding
and source/patch postguards passed.

The same job fetched **28 inputs for 157.0.8103.27**, whose DEPS pins V8
`a4889e05285021952e2ca9648c805a4c989345ae`, then stopped on HTTP 503 without a
Retry-After header. It made no mirror/fallback request or retry loop. The overall
job remains failed/incomplete; its successful .75 target is recorded separately,
not used to relabel the 157 target. All 302 active build/source inputs stayed
unchanged. Evidence: `upstream-forward-preflight-20261029-v2/report.json` and
`156.0.8078.75/replay/report.json` beneath that directory on D.

The .75 result is a **complete source-context replay of the existing patch
batch**, not a complete checkout, generated-target equivalence, compilation,
native test execution, runtime admission or security sign-off. Neither target
was registered/selected for building. The active .36 build remains frozen.
The next tooling step is a reproducible guarded sparse-cache/replay entry point;
the next engine step remains actual compilation and native/runtime validation.

### Chromium 157 bounded port — 2026-10-29

The resumed immutable-source discovery validated the previous 28 cache entries
before HTTP and reached **72 of 185 inputs**, then stopped on a read timeout.
Requests were serial, at least two seconds apart, after a cooldown exceeding
15 minutes. No automatic retry or mirror was used. The failed discovery remains
`upstream-forward-preflight-20261029-v3/report.json` on D. All 301 active build
inputs, the separately reviewed helper and prior cache stayed unchanged.

Offline replay exposed real porting failures at 0006, 0018, 0022, 0026 and 0029.
Five isolated adaptations now pass the **001–029 source prefix**. The worker
handoff uses upstream's current three-argument creation API; document bootstrap
and worker tests retain their seed ownership/checks. Earlier failed reports
remain under `cached-157-prefix-20261029-v1` and `ported-157-prefix-20261029-v1`
through `v4`; the successful isolated report is `ported-157-prefix-20261029-v5`.

The public [157 prefix draft](../native/drafts/upstream-157-prefix/README.md)
stores only the five changed patch payloads, with a manifest referencing the
24 unchanged originals. Public cache-fetch/replay passed **72 validated cache
files / zero HTTP requests / 29 patch applications**. Evidence:
`public-157-prefix-inputs-20261029-v1/source-fetch-report.json` and
`public-157-prefix-replay-20261029-v1/report.json` on D. Input/patch postguards
passed; this is not 29 compiled tests. GPU/GRIT invariants were unavailable in
this prefix. Eight missing inputs block 0030; **0030–0062 are unverified**.
There is no C++/runtime/security/package admission or target switch.

A later explicitly bounded continuation reused all 72 validated inputs and the
five reviewed overrides after another 15-minute cooldown. It reached **76 of 185
inputs**, then stopped on a read timeout while requesting the pinned
`third_party/blink/renderer/core/loader/document_loader.cc`. No retry or mirror
was attempted. `upstream-forward-preflight-20261029-v4/report.json` retains the
pending URL, failure and successful postguards for all 301 active inputs,
the helper, prior cache, port manifest and five overrides. This incomplete
discovery does not extend the public 29-patch replay result.

With the public 157 prefix present, the full local application suite passed
**3,553 tests, one skipped**, in 295.42 seconds. Log:
`pytest-157-prefix-full-20261029-v1.log` on D. This does not compile the new
C++ drafts or establish a completed remote CI run.

### Public 156 refresh replay evidence

The .75 input manifest is now public under
`native/drafts/upstream-156-refresh/manifest.json`, bound to the original manifest
hash and reusing its 62 exact patch files. No second patch payload directory is
committed, and the build command intentionally rejects this unregistered target.
The replay verifier accepts explicit paired `--manifest`/`--patch-directory`
paths instead of process-global constant overrides. Missing pairs, bad/oversized
metadata, duplicate inputs/patches, non-string paths, input drift and unsafe
output placement refuse or fail the gate; all original postguards remain.

Actual public CLI checks passed all **62 patches** for .75, then independently
for the unchanged default .36 target. The .36 input control reused 178 matching
cache files and read seven exact pinned Git blobs without a checkout or network.
The explicit .75 output tree matched the earlier private replay byte-for-byte.
The optional codegen gate reproduced **30 generated GPU files**, with unchanged
formatter bytes; `formatter_target_dependency_verified=false` remains explicit.
Initial selection of a nonexistent formatter was rejected before creating output;
the successful invocation used the actual `buildtools/win-format` executable.
None of these checks compiled C++ or admitted a browser/runtime capability.

Focused source-replay tests passed **39 cases**. Full application regression:
**3,524 passed, one skipped**, 295.28 seconds; CI Ruff selection passed.
Private proof: `public-refresh-replay-20261029-v1/report.json`,
`public-refresh-codegen-20261029-v1/report.json` and
`public-replay-compatibility-20261029-v1/report.json` on D. The latter checks 301
unchanged build/source inputs plus the separately reviewed replay-verifier hash;
the verifier itself was intentionally updated after the earlier 302-input proof.
The build pin, manifest, patch bytes, Chromium sources and GN inputs did not change.

### Queued native target coverage

The earlier process-bound sequence was: resumed 156 / 001–063 build → four identity
targets → full eight-gate runtime suite → **13 remaining/default native target
selections**, serially at j4. The final queue covers keys/contexts/delivery,
worker handoff, document partition/navigation, surface navigation, window
transport, GPU pack/readback/metadata, worker surfaces and font rasterization.
Some selections overlap earlier fixtures; do not add their counts as unique
tests. None of these queued 156 results is passing evidence yet.

`remaining-native-after-runtime-20261029-v4/controller.json` on D bound the
actual current runtime-controller process handle and requires its successful
exit/source postguards before building anything. A failed, retired or expired
observation starts no targets. Each selected native verifier retains its own
report/log and stops the queue on the first failed execution or postguard.
This queues work; it does not expand runtime capability or production admission.
The waiting runtime/native controllers were refreshed to the reviewed public
verifier cohort; old pending reports remain marked retired. The active browser
build and initial native identity controller were not stopped or restarted.
That chain stopped on the Audio compiler failure without running its queued work.
Its bound runtime report was `runtime-after-identity-20261029-v9/controller.json`;
it captures the reviewed shared replay helper used by the source fetcher.

### Queued installed-payload verification — 2026-10-29

The initial `package-after-native-20261029-v1/controller.json` on D was bound to the actual
remaining-native queue process handle. Only successful process exit, the exact
13 completed selections, each final native postguard and the original passing
runtime controller permit staging. Observation expiry or a failed/retired queue
starts nothing. A changed reviewed input stops the chain; **198 input hashes**
include the candidate patches, public verification/application code and the
private controller itself. It stopped after the 001–062 compile failure without
starting staging or any children. The subsequent v2 had 199 input hashes and
also stopped on the Audio failure. Current v3 links/200-input guards are recorded
in the Audio portability section above.

The planned chain reuses public commands: official mini-installer staging at
j4 → archive from the exact runtime report → checksum-verified installation in
a fresh isolated D: store → all eight runtime gates against that installed
candidate and versioned DLL directory. It does **not** activate the package,
touch the reviewed 148 store/user profiles, publish a release or bypass version
downgrade checks. Compatible rollback remains a separate unverified gate.

One positive and six negative prerequisite fixtures passed, as did selected
undefined-name/syntax checks for the controller. This validates only the queue
decision logic: **no actual 156 staging/archive/install/relocated runtime has
run yet**. Reproduction commands are in the
[candidate README](../native/drafts/upstream-156/README.md#verify-the-installed-development-payload).

## Windows private identity-file ACL — 2026-10-29

An actual disposable profile on D inherited Users/Authenticated Users data
access despite `QSaveFile.setPermissions(ReadOwner | WriteOwner)`. Qt documents
that this method does not manipulate Windows ACLs. Its
[`QFile.open(mode, permissions)` creation overload](https://doc.qt.io/qt-6/qfile.html#open-1)
does create a Windows ACL; an empty-file control already had protected ACL and
no foreign data grants before any secret bytes were written.

The Windows manager key writer now creates a new sibling file using explicit
owner read/write permissions and NewOnly, writes/flushes/fsyncs it, then publishes
with same-directory OS rename/replace. Qt's rename/copy fallback is not used.
The filesystem must report
[`FILE_PERSISTENT_ACLS`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationw).
Unknown/unsupported filesystem permissions or any publication failure abort
startup; no insecure write fallback or driver launch follows. Only an owned
temporary file is cleaned up, never an existing collision file.

Valid existing Windows key files are atomically republished with private creation
permissions whenever the manager loads them under its runtime owner lock.
**Their exact payload bytes and seed are preserved**, including legacy JSON
spacing. No automatic key rotation or invalid-key regeneration is performed.
Reads are bounded to 257 bytes, rejecting data beyond the 256-byte format limit.
POSIX writing is unchanged and not newly runtime-verified.

Actual ACL migration of one disposable legacy D profile changed two foreign
data grants to zero and enabled DACL protection, while preserving exact bytes,
both derivation modes for all four surfaces, and the parent directory ACL.
Private evidence: `identity-acl-finding-20261029-v1.json` and
`identity-acl-migration-20261029-v1/report.json` in the candidate workspace on D.
Windows new/existing-key tests inspect actual ACLs; failure tests cover volume
lookup/support, creation, short writes, flush/fsync, publication collisions and
runtime owner release before the driver starts.

The final focused runtime/backup run passed **638 tests**; the full application
run passed **3,497 tests, one skipped** in 319.93 seconds. CI Ruff selection
passed. Actual reviewed 148 manager backup/restore/original-restart passed all
six checks and three clean closes with the new writer; both final key files had
protected ACL and zero foreign data grants. The combined native
Canvas/Audio/WebGL run also passed **12 phases and 24 nested Canvas cases per
derivation mode**, proving the tested browser key-service/readiness path can
consume the protected files. Runtime core/receipt and reviewed source postguards
passed; this is not new 156 evidence. Private proofs:
`native-backup-owner-20261029-v3/{report,key-acl}.json` and
`expanded-combined-surfaces-20261029-v2/` on D.

This is **key-file content access protection**, not workspace ACL hardening,
protection against administrators/same-user processes or replacement through a
writable parent directory. It cannot undo earlier exposure. User profile keys
were not bulk-modified or rotated; only disposable fixtures were migrated here.
Standalone browser/test tools that bypass the manager key writer are not an
automatic ACL-migration path. These changes do not admit privacy surfaces or 156.

## Backup session owner exclusion — 2026-10-29

The backup service previously omitted `native-runtime.lock` from archives but
did not acquire it. Three new real-QLockFile tests reproduced that session
export could read an owned Glint profile, and a runtime could acquire ownership
while its files were being archived. The UI's in-memory running-profile check
was not sufficient protection for direct service callers or other processes.

Session export now holds the existing Native owner lock through enumeration,
hashing and ZIP writing. Active/unknown owners and invalid linked/non-file owner
metadata reject before creating an archive. Failed writes release ownership and
remove only the new partial archive. Metadata-only service export does not take
the session lock. A Native directory appearing during enumeration causes refusal,
not an unlocked copy of its newly created data. Existing engines' APIs and the
new-identity restore contract remain unchanged.

Actual reviewed **148 / 001-062** manager verification passed: live session
export rejected without changing five stores; metadata-only export contained no
browser files; a real NativeRuntime start was rejected while ZIP writing held
the lock; closed export omitted the private key and lock; restored profile
started with all five stores and a new private key; original restarted with its
unchanged key/stores. Three manager closes were complete without forced cleanup,
reported errors or retained runtime resources. Payload/source postguards passed.
Evidence: `native-backup-owner-20261029-v2/report.json` on D; child exit zero.
Backup/path regression tests passed **105 cases**; the full application suite
passed **3,475 tests, one skipped** in 292.59 seconds. CI Ruff selection passed.

The first private harness used the default keep-open setting, then incorrectly
expected a normal `close()` to terminate it. Its failed report is retained;
v2 explicitly disables keep-open. This was a harness error, not a product
shutdown fix. These checks do not prove cross-device encrypted-cookie portability,
key-preserving rollback, 156 runtime or Camoufox/CloakBrowser process exclusion.

## Windows text tuning and close observability — 2026-10-29

Experimental manager admission is limited to the exact reviewed **148 / 001-062**
package, not Chromium 156. Nine presets use native Chromium gamma/contrast
switches with Native rasterization. They are bounded rendering options, not
nine proven identities. [Configuration](NATIVE_ENGINE.md#windows-text-tuning).

| Gate | Observed result | Boundary |
| --- | --- | --- |
| Desktop, real manager | 18 starts, 144 first-script scope observations, 18 editing/export workloads; passed | Nine presets, two starts each; paired profiles, not arbitrary concurrency |
| Mobile Web, real manager | 18 starts, 144 scopes, 18 workloads; passed | Windows viewport 420×844 / DPR 3, not Android/iOS |
| Independent mobile control | Nine stock Chromium 148 starts, 72 scopes; matched corresponding glyph controls | One stock start per preset, no stock restart claim |
| Lifecycle | All 36 manager close reports complete, no forced cleanup/errors/retained runtime resources | Does not establish the cause of earlier intermittent failures |
| Crash recovery | Three profiles, three rounds; rotating crash/restart, five stores checked, zero remaining owned processes | One combined gamma-2.2 / contrast-0.5 policy with CPU/RAM/fonts/WebRTC/automation/UA controls, not all preset combinations |
| Excluded named font | Consolas excluded in all eight scopes; allowed Arial/Times measurements unchanged, two starts | One excluded family, not all installed-font combinations |
| UI and application regression | Real QML selection, conflict rejection, Save and profile pinning; **3,455 passed, one skipped**, 318.75s | Python/QML tests, not additional Chromium tests |

Desktop and mobile runs checked repeat/restart glyph consistency, actual
DOM/SVG/Canvas output, loaded-font use, Unicode editing/undo/redo/selection,
PNG round trips, UTF-8 download and bounded PDF header/size checks. These are
controlled fixtures, not IME coverage or semantic PDF validation. Raw-image,
format and HDR controls remained intact. Five stores stayed isolated and
persisted across restarts; complete package payload and reviewed application
source snapshots stayed unchanged. The mobile driver log contained none of
the checked teardown/cleanup/unretrieved-future warnings.

Private evidence on D: `managed-text-tuning-20261029-v5/report.json`,
`managed-mobile-text-tuning-20261029-v1/report.json`,
`mobile-text-controls-20261029-v1/report.json`,
`text-policy-recovery-20261029-v1/report.json`, and
`selected-font-contexts-20261029-v1/{report,validation}.json`.

Retained failures and limits:

- The first manager harness attempted the next Save before the existing busy
  guard cleared. It now waits for both persistence and readiness; this was not
  an engine bug or a reason to bypass the guard.
- Desktop v3 remains failed: its selected-font policy omitted Consolas while
  the reference was unfiltered. Generic monospace fallback changed even in
  Native mode. The corrected control retains Consolas; the excluded-family
  probe separately verifies filtering. Shared/service generic fallback already
  differs in the native baseline; unconditional cross-scope font equality is
  not a valid assertion. The new Privacy preset retains normal serif/monospace
  families; existing profile font lists are not silently migrated.
- Desktop v4 passed rendering but logged a teardown timeout and forced owned
  process cleanup. Its original result and separate `close-audit.json` remain;
  **v4 is not accepted as graceful lifecycle evidence**. The cause is still
  unknown. Passing desktop v5/mobile runs do not prove it fixed.

`BrowserInterface.native_close_report` now exposes completion, kept-open state,
forced cleanup, teardown/cleanup error categories, elapsed time and runtime-owned
resources. `complete` alone is not success: strict gates reject forced cleanup,
errors, kept-open sessions and retained resources. It is observability, not a
new shutdown fallback or a global process detector. Close remains idempotent,
cancellation propagates, and no raw error message is stored in the report.

Unknown/modified binaries remain blocked; default policy serialization and
launch arguments remain compatible. Non-native rasterization combinations,
Canvas/GPU/Audio privacy experiments, OS/GPU simulation, external anti-bot
acceptance and Chromium 156 admission are not established by these runs.

### Follow-up shutdown diagnosis

A separate bounded comparison used the unchanged reviewed 148 package and
application source: minimal pages versus workers/editing/export, Native versus
contrast 0.5 versus gamma 2.2 / contrast 0.5. Each combination used two persistent
profiles and two starts: **24 real manager starts**. All 24 browser processes
reported graceful exit code zero; actual child launcher exit was zero. Owned
process snapshots (19–21 observed descendants per pair) found no survivors after
each close round. No forced cleanup, retained runtime resources, loop exception
or checked unretrieved-future/teardown warning occurred. Close durations ranged
from **0.687 to 13.625 seconds**, mean 1.982 seconds. This is an observed range
under the concurrent build workload, not a shutdown latency guarantee.

This did **not reproduce or fix** the earlier v4 timeout. Do not change the
shutdown budgets or remove fallback based on this negative reproduction. The
diagnostic retains close-phase samples and Python task locations when a close
takes more than two seconds; driver logs and observed process identities remain
private. Evidence: `manager-close-diagnostic-20261029-v2/{report,launcher}.json`
and its adjacent `-driver.log` on D. Payload, fixture font and source postguards
passed. The first diagnostic's assertions passed, but its PowerShell stderr
redirection returned status one without recording the Python exit code; its
report/log are retained and not used as a clean launcher gate. V2 captured the
actual child exit via subprocess rather than treating shell status as browser
failure or silently rewriting v1.

## Canvas taint propagation and reset baseline — 2026-10-29

The existing `verify_native_canvas.py` now checks 14 additional security/reset
observations without changing browser code: origin taint survives `clearRect`
and propagation through ImageBitmap, same-width resize resets taint/pixels/
transform/fill/alpha, PNG export works again after reset, and another foreign
draw taints the surface again. Both HTMLCanvas and OffscreenCanvas paths are
covered in document, same-origin iframe and cross-origin iframe. Worker taint
propagation is not claimed by these document-owned foreign-image fixtures.

Stock **148.0.7778.96** and reviewed Glint **148 / 001-062** each passed initial
and persistent restart: **12 security-scope observations, 22 fields each** across
both engines, with identical security/reset results. The existing eight-scope
readback/geometry/export checks also passed, 32 scope observations across these
four starts. Both verifier child exits were zero. Complete managed payload and
verification source postguards passed. Private evidence:
`canvas-reset-contract-20261029-v2/{report,stock/report,managed/report}.json` on D.
Focused Canvas validator tests passed **57 cases**; the full release-tool module
passed **979 tests, one skipped**. The full application suite passed
**3,469 tests, one skipped** in 294.30 seconds; CI Ruff selection passed.
These are **feature-off compatibility controls**, not enabled Canvas protection,
156 runtime proof, JPEG fidelity or a new product capability admission.

The first control remains failed: it expected `IndexSizeError` for zero-width
reads on a tainted surface, following the current
[HTML algorithm](https://html.spec.whatwg.org/multipage/canvas.html#dom-context-2d-getimagedata).
Actual stock 148 returns `SecurityError` first. The checked 156 source also tests
origin cleanliness before zero dimensions in `getImageDataInternal`; source
inspection is not 156 runtime proof. The baseline now explicitly preserves that
measured upstream Chromium ordering, rather than silently claiming current HTML
exception-order conformance. Untainted zero dimensions still require
`IndexSizeError`. Original `canvas-reset-contract-20261029-v1` evidence is retained;
no Chromium exception handling was changed to satisfy the verifier.

### Combined protected-surface regression

The expanded security/reset fixture also passed with the existing experimental
Canvas/OfflineAudio/WebGL readback paths together on the preserved flat-layout
**148 / 001-062** binary. Both `partitioned-privacy` and `profile-identity` runs
completed with child exit zero: **12 named phases each**, including baseline and
two protected profiles before/after restart, concurrent ownership, symmetric
peer close/restart isolation and missing-document-policy rejection. All six
baseline/protected sequential phases in each mode checked the new security/reset
fields in three document/frame scopes. Native core, exact receipt and verifier
source snapshots remained unchanged.

Each mode additionally passed **24 nested classic/module Canvas cases** across
the six sequential phases. Canvas/Audio and GPU cross-profile isolation passed;
WebGL1/2 readback was measured in the same contexts/profiles. Audio float32/SNR
observations remain in the raw reports, not a listening-quality guarantee.
GPU results are settled reads, not first-script/nested GPU or WebGPU protection.
Evidence: `expanded-combined-surfaces-20261029-v1/report.json` and its two
mode-specific `report.json`/`driver.log` files on D.

These are **24 combined phase checks, not a repeat of the full eight-gate
runtime suite or new native unit tests**. The runs keep `privacy_admitted=false`.
The known explicit-pixel fidelity/detectability limits of the old Canvas
readback transform remain: passing reset/security/isolation does not repair
those pixels, admit product capabilities or prove Chromium 156 behavior.

## Manager same-origin frame diagnostics — 2026-10-29

The running-profile diagnostic now checks its own document and dedicated worker,
plus a same-origin iframe and that iframe's dedicated worker. Each scope uses
the existing native observation/validation path. Sixteen identity groups are
also compared across the two documents: navigator/Client Hints, CPU/memory,
locale/timezone, screen/DPR/touch, media preferences, WebGL and WebGPU metadata.
This catches disagreements that could independently satisfy a configured ceiling.
Frame mismatches join the existing top-level list with scope labels; detailed
results are retained under `contexts.same_origin_frame`.

Only the diagnostic page owns the routes and service-worker bypass. Its two
explicit loopback URLs are fulfilled locally; every other request is aborted.
The disposable page closes on success and on missing-frame/inspection failures.
It does not navigate or attach routes to the user's original page. Standalone
binary/settings probes retain their existing document/worker coverage.

Installed **Glint 148 / 001-062** passed **eight real manager starts / 32 scope
observations**: desktop and Mobile Web Emulation, pinned/inherited configurations,
initial/restart phases. All document-pair identity groups agreed, all existing
scope validators reported zero mismatches, original pages/URLs were retained,
all runtimes released their resources, and the complete payload/core stayed
unchanged. Evidence on D: `frame-diagnostics-summary-20261029-v1.json`,
`frame-diagnostics-runtime-20261029-v2/` and
`frame-diagnostics-mobile-20261029-v1/`.
Focused health/consistency tests passed **56 cases**, including all 16 field
groups with drift/missing values, frame failure/cancellation cleanup and route restrictions.
The full Python run passed **3,331 tests, one skipped** in 292.07 seconds;
the final native runtime module passed **519 tests**, including a cancellation
case added after the full run had collected its tests. The CI Ruff selection
also passed. These are application tests, not additional Chromium runtime cases.

These are **post-load same-origin** checks, not first-parser-script,
cross-origin, shared/service-worker coverage, Android/iOS identity or 156 proof.
They do not admit Canvas/GPU/Audio experiments or establish anti-bot acceptance.

## Pinned profile environment — 2026-10-29

Profiles → Settings → Browser JSON → **Pin environment** copies the effective
requested viewport, DPR, locale, timezone, media preferences, privacy policy
and headless mode into the current draft. Existing explicit overrides stay
intact. The action does not save, start a browser or change global defaults;
normal Save and runtime admission remain required. Inherited permission grants,
binary/store paths, headers, storage paths and private identity keys are not
copied. Those settings still inherit unless already explicitly overridden.

Real QML interactions covered preview without mutation, invalid-draft retention,
explicit Save and persistence after global defaults changed. A separate real
manager run used installed **Glint 148 / 001-062**: two profiles, two starts each,
36 document values covering viewport/DPR, locale/timezone, media and CPU/memory.
Pinned values remained stable while the unpinned profile inherited new defaults.
All owners closed without retained resources; the complete managed payload and
executable/DLL core stayed unchanged. Evidence on D:
`pinned-environment-runtime-20261029-v2/report.json` and
`pinned-environment-ui-20261029-v3/` (real QML screenshot).
The first private runtime probe read the account before asynchronous Save
completed; v2 waits for persistence. The first offscreen screenshot had no
registered fonts; later captures load installed fonts in the harness only.
The focused configuration/preview suite passed **20 tests**, including denied
access, oversized/deep JSON, invalid identity inputs and preservation of explicit
overrides; the real QML configuration/profile test passed separately. Browser
JSON now scrolls internally and keeps Save/Cancel visible at the normal dialog
size. Screenshot validation does not replace the runtime checks above.
The complete Python run passed **3,291 tests, one skipped** in 324.77 seconds.
The final runtime/toolchain/QML subset passed **554 tests**, including four
input-bound cases added after that full run had already collected its tests.
The repository's CI Ruff selection (`F821,F822,F823,E9`) also passed.

This pins requested configuration, **not an entire fingerprint**: browser/OS
updates, host GPU, network, permissions and other inherited settings can still
change observable results. It does not admit experimental privacy controls,
prove worker consistency, test 156 or establish anti-bot acceptance.

## Context media preferences — 2026-10-28

Manager configuration now persists explicit color scheme, reduced motion, forced
colors and contrast. Empty/default selections leave the old launch options
unchanged; invalid values reject. These are native browser context media
emulation options, **not new Chromium patches or OS/GPU identity admission**.

Owned fixture checks passed **32/32 observations**: matching stock Chromium 148
and installed Glint 148 / 001-062, two simultaneously configured opposing
profiles, initial/restart phases, document, same-origin frame, cross-origin
loopback frame and new tab. First-parser-script values, subsequent `matchMedia`
results and CSS custom properties selected by real media rules all agreed.
Measured executable/DLL cores and the complete installed payload remained
unchanged. Evidence: `media-preferences-20261028-v2/report.json` on D; the initial
fixture-only v1 report is retained separately. The v2 run also called the real
manager diagnostic eight times across both runtimes/profiles/phases: zero
mismatches, with exact observed media values in every call.
QML interactions/save persistence passed; a private manager screenshot was
visually checked. The complete Python suite passed **2918 tests, one skipped**.
This does not transfer these observations to 156, cover worker APIs or establish
anti-bot acceptance.

## Native text-tuning research — 2026-10-28

Before adding another Chromium patch, the existing upstream `text-gamma` and
`text-contrast` launch controls were inspected and measured. Source 156 already
forwards both controls to renderers and applies them through Skia surface
properties. No source, registered patch, GN or manager admission was changed.

Owned **148** calibration completed with unchanged stock and installed Glint
cores/payload: baseline plus two joint gamma/contrast settings, two starts per
profile, both runtimes, all eight first-script document/frame/worker scopes:
**96 scope observations**. Evidence: `text-tuning-research-20261028-v1/report.json`
and twelve checksum-bound screenshots on D.

Both explicit settings changed all six text samples in each scope in both
runtimes. Text metrics, explicit-pixel fidelity, format/HDR observations and
repeat/PNG/ImageBitmap consistency retained their controls. Restart comparisons
had no drift. Corresponding stock/Glint screenshots were byte-identical for
each setting and unchanged across restart; baseline and tuned screenshots were
visually inspected. This measures real rendering, not a readback-only mask.

These are joint-control experiments, not isolated causal tests of each flag,
proof of natural device distributions, general application compatibility or
anti-bot acceptance. Manager controls/admission are **not enabled** by this
research. Next: isolate gamma/contrast effects, repeat on the linked 156 runtime,
check combinations with existing policies and ordinary text/editing/web-font
workloads, then decide the supported profile contract. Reuse verified upstream
controls instead of duplicating them in a custom patch unless a measured gap
requires one.

### Independent gamma/contrast controls — 2026-10-29

The public rendering verifier now provides `--series text-tuning`: baseline,
two gamma-only cases, two contrast-only cases and four joint cases. A run on
the unchanged **Glint 148 / 001-062** output passed **144 scope observations**
(nine cases, two starts, eight scopes). Gamma-only and contrast-only changes
each affected text pixels independently in every scope. Assessment failures
and screenshot restart differences were both zero. Core, resource, source,
receipt and screenshot guards passed. Evidence on D:
`text-tuning-factorial-001-062-20261028-v1/report.json`.

This does not establish natural hardware distributions, general application
compatibility or a result on 156. Manager admission remains disabled. The same
verifier can explicitly bind `--candidate upstream-156` to the complete
candidate receipt, manifest and patch chain, but that runtime run is pending.

### Editing and export workloads — 2026-10-29

The public rendering verifier optionally accepts `--workload-font` for a real
explicit TTF/OTF input. It retains the existing idle-builder, receipt, source,
core and resource guards, and additionally binds the font response, helper
source, screenshots, downloaded text and PDF artifacts. Default invocations
without this option are unchanged. Editing uses real browser input operations;
no browser API getters or Canvas functions are replaced.

Owned matched **stock/Glint 148** research passed **36 session observations**:
nine baseline/independent/joint gamma-contrast cases, two starts each, both
runtimes. Verified Unicode insertion, native undo/redo and selection, a genuine
loopback-served Ahem font, matching DOM/SVG/Canvas font widths, nonblank Canvas,
lossless PNG decoding, exact multilingual UTF-8 download content, PDF header/
size and return to screen media. Semantic differences and paired font-pixel
differences were both zero; core/resource/input/artifact guards passed.
Evidence on D: `text-workloads-matched-20261029-v2/report.json`. Earlier v1 and
measured source snapshots are retained. Stock and tuned Glint screenshots were
visually inspected; Ahem's square glyphs are intentional test-font output.

A separate **managed Glint 148 / 001-062** follow-up passed four workload runs
and **32 first-script rendering scope observations** with admitted CPU/RAM
ceilings (2/2), WebRTC routing policy, dark scheme and reduced motion. An
unrestricted positive control reached the owned loopback STUN observer; every
protected run completed gathering without direct UDP. Actual CPU/RAM/media
values agreed with configuration. Default/joint text tuning remained restart-
stable, changed text pixels in all eight scopes and preserved image/format/HDR
controls. The complete installed payload and measured core stayed unchanged.
Evidence: `text-workloads-admitted-20261029-v2/report.json` (v1 retained). The
follow-up also corrected an initial channel-coverage statistic into a true
integer ink-pixel count; this was diagnostic math, not an engine change.
The developer
rendering configuration now forwards the base admission keyword rather than
rejecting otherwise reviewed combinations; no admission checks were removed.

Limits: this is controlled-page compatibility, not third-party app coverage,
IME/composition testing, PDF text/glyph equivalence, device-distribution
realism, combined readback-experiment admission or an observation on 156.
Manager text-tuning controls remain disabled. The first smoke fixture expected
double-click selection without Windows' trailing word space; punctuation now
delimits the sample. Failed smoke reports are retained; no engine patch or
weaker word-selection assertion was used to hide that fixture mistake.
The complete desktop Python suite passed **3,245 tests, one skipped** after
these changes. Public verifier failure matrices cover both rendering series,
148/candidate receipt selection and optional workloads, including changed font,
helper source, artifacts, semantics and failed cleanup.

### Concurrent rendering and five-store isolation — 2026-10-29

`verify_native_font_rendering.py --profile-concurrency 2` now starts bounded
batches of private profiles before measuring either peer. Default concurrency
remains one. The existing storage fixture checks cookies, localStorage,
IndexedDB, Cache Storage and service-worker registrations before writes, after
both peers write, after workloads and at the final peer barrier. Restart must
recover the same per-mode marker. A failed owner does not prevent attempting
cleanup of its peer; retained resources stop subsequent batches. Storage,
font-response and download operations have explicit deadlines.

An isolated **Glint 148 / 001-062** run passed all nine text-tuning cases with
two starts each: **18 profile starts, 144 rendering scope observations and 18
editing/export workloads**. Peak live profiles was two; the odd final case ran
alone. Every mode's rendering matched its earlier sequential measured baseline.
Independent gamma/contrast effects held in all eight scopes; restart, raw pixel,
format/HDR and workload semantics stayed consistent. Five-store markers remained
private and persisted correctly. Core/resource/source/font/artifact guards
passed. Evidence: `concurrent-rendering-text-tuning-20261029-v1/report.json` on
D; the preceding extreme off/high-pair smoke is retained separately.

The full Python suite passed **3,268 tests, one skipped**. Failure fixtures
cover partial startup, storage sharing/loss, late peer writes, storage timeout,
source/font/artifact drift and cleanup failure while proving every owner gets
a cleanup attempt. These are 148 observations, not a 156 runtime pass,
exhaustive pairing of every setting or new product capability admission.

## Chromium 156 runtime-suite provenance — 2026-10-29

`verify_native_suite.py --candidate upstream-156` now binds the runtime cohort
to the selected manifest and full ordered Chromium/V8 receipt chain, measured
EXE/DLL core and each gate's exact reported browser version. The hardware gate
uses its existing `browser_version` field; the other seven retain `version`.
No child schema is renamed and no automatic field/version fallback is used.
The shared receipt validator is also used by packaging.

Flat builds require their adjacent receipt and compiled GN arguments; installed
copies require consistent embedded receipt/candidate/version metadata and the
explicit package/store/DLL layout. Candidate inputs are rechecked before and
after gates. Initial receipt/argument read races, missing/incomplete receipts,
wrong versions, input drift and active builders fail closed. Ordinary child
failures remain recorded; changed inputs stop later gates with partial evidence.
Candidate reports explicitly retain `privacy_admitted: false` and do not prove
publisher authenticity or source replay from a receipt alone.

**22 candidate-suite fixture tests passed**, including flat and installed
eight-gate runs, version rejection, initial-read/inter-gate drift, conflicting
installed metadata, active-builder refusal and CLI selection. The actual retained
148 build receipt was also rejected for the 156 selection. These are validation
and fixture results, **not a passing 156 runtime suite**. A private process-bound
controller waits for the four native identity targets before starting the full
suite; failure or changed reviewed code stops it without retrying or admission.
The final Python suite passed **3,379 tests, one skipped** in 303.71 seconds;
the CI Ruff selection passed. Draft READMEs now distinguish current 148 / 001-062
and its experimental font admission from historical 001-015/027/061 checkpoints
and the still-unverified 156 port.

## Chromium 156 delivery tooling — 2026-10-29

Official Windows staging and archive packaging now require an explicit
`--candidate upstream-156` for 156. Default invocations retain the original 148
lock; candidate workspace markers prevent implicit staging. Staging holds the
OS workspace lock and binds the candidate manifest, sync/hooks, ordered source
chain, receipt, executable/DLL core, GN arguments and prepared local toolchain,
with postguards on success and failure. A conflicting compiler selection or
changed toolchain/marker/source fails closed.

Packaging requires the same manifest and complete ordered Chromium/V8 receipt
chain, the exact passing lifecycle report and staged core/files. Candidate
manifest/patch hashes are checked again before publication. The archive records
candidate provenance and keeps `native_patch_runtime_verified: false`.
Synthetic-file, CLI and installation fixtures passed: **36 staging tests**;
the staging/release-tools modules together passed **979 tests, one skipped**.
This includes candidate/default separation, omitted/reordered/changed patches,
wrong V8 revision, manifest drift, concurrent ownership and toolchain drift.
The real active 156 build also excluded a competing staging invocation: both
builder handles remained live, no staging report/log was created, and GN/receipt
state plus held-lock size/mtime stayed unchanged. Evidence:
`active-staging-lock-refusal-20261029-v1.json` on D. The first private probe tried
to read the Windows byte-locked marker and failed before invoking staging;
the corrected probe measures its permitted metadata instead. This proves active
builder exclusion, not successful staging or a new browser runtime.
The complete Python suite passed **3,357 tests, one skipped** in 298.06 seconds;
the repository's CI Ruff selection also passed on the final code.
These are fixture results: **no real 156 staging, archive, installed-copy or
rollback result exists yet**. Commands and remaining gates are in the
[candidate guide](../native/drafts/upstream-156/README.md#development-staging-and-packaging-after-linking).

## Chromium 156 compilation checkpoint — 2026-10-29

Dependency sync, hooks and the complete 62-patch Chromium/V8 chain completed.
GN succeeded using installed VS 2026 MSVC and the checksummed official SDK
assembly in a workspace-local layout. The first j4 compilation stopped after
140 completed actions with errors in two unified system module targets, not
an engine test failure or a completed browser build. Remaining actions at that
failure: 88,298; this is not an ETA.

Aligning MSVC include paths with the projected toolchain namespace exposed a
separate Siso dependency-resolution failure at the VC junction. Neither
diagnostic passed compilation. Original SDK/compiler files and the reviewed
148 runtime remain untouched; compiler modules have not been disabled.
Retained evidence: `build-20261028-235508.log` and
`toolchain/system-module-namespace-20261029-v1/1.log` in `D:\Glint156Candidate`.
Follow-up: the VC junction was retained, and a regular owned copy of all
**3,637 MSVC files** was created with source/destination SHA-256 checks. Both
modulemap actions and both failed PCM targets then completed successfully in
the isolated j4 probe; neither modules nor engine checks were disabled.
The process finished saving its filesystem state, exited zero and passed the
wrapper's final toolchain/source guards. The complete browser build then
resumed at j4 (`build-20261029-004248.log`). PCM outputs alone are not a linked
browser or a completed native-test gate. Evidence:
`toolchain/local-msvc-sdk-28000-v1/materialization-v1.json` and
`toolchain/system-module-materialized-20261029-v1/1.log`.

That full attempt later exited nonzero after **49m34.89s**: 11,839 completed
actions, 19 failures, 71,178 remaining. Every failure reported missing `dia2.h`
in Dawn DXIL DIA sources; this was an incomplete toolchain layout, not a passed
build or a reason to disable WebGPU/DXC. The installed DIA SDK was copied to the
owned composite with hash checks (24 files), leaving the installation intact.
The real Dawn `lib_dxildia.lib` target then compiled and the before/after
source/toolchain guards passed. Evidence:
`toolchain/dia-sdk-compile-20261029-v1/report.json` and
`toolchain/local-msvc-sdk-28000-v1/dia-materialization-20261029-v1.json`.
The full j4 build resumed with existing objects; the controller remains
`dia-build-continuation-20261029-v1.json`. A passed library target is not a
linked browser or permission to enable any new runtime capability.

Public follow-up tooling: `scripts/native_windows_toolchain.py` prepares a
fresh canonical copy and refuses existing config/output, links, insufficient
space, bounds violations, input drift and concurrent workspace ownership.
It now requires/copies installed DIA SDK and measures its essential headers,
GUID libraries and runtime DLLs; missing or changed DIA fails closed.
Real-file fixture tests cover generated x86/x64 environments, copied hashes,
failure evidence, lock contention and preservation of concurrent config edits.
It has not yet been used for a new full-size candidate checkout/build; the
existing candidate uses the retained diagnostic preparation above.
The SDK/toolchain test module passed **57 tests**; the complete desktop Python
suite passed **3,134 tests, one skipped**. Neither result substitutes for native
compilation or runtime admission.

## Follow-up Windows regression — 2026-10-28

This is another run of the installed **148 / 001-062** package, not a new linked
browser or evidence for the 156 candidate. The full payload and three core
hashes remained unchanged. All eight gates ran: **seven passed, 142 checks**;
the runtime gate stopped after 17 completed checks with
`Native browser context close timed out` during multi-profile restart cleanup.
The run **failed**; do not describe it as a new 160/160 pass. Retained evidence:
`rollback-regression-20261028-v2/suite.json`, `runtime.json` and `runtime.log` on D.

Chromium source recovery was running concurrently on the same HDD. A live
sample showed approximately 95% disk activity, but this observation does not
establish the timeout's cause. The failure remains unresolved. The restart
verifier now records round, profile slot, close phase and elapsed time in
exception notes, without changing the timeout, retrying, skipping checks or
converting failures/cancellation into success. Further repeats must retain this
failure and distinguish idle from concurrent-I/O conditions.

The context-instrumented runtime-only repeat **passed 18/18 checks** on the same
installed payload: `rollback-runtime-context-20261028-v3/suite.json` on D.
Concurrent source recovery was still active. Runtime deadlines/assertions were
unchanged; only diagnostic exception notes were added. This is **not a new full
suite pass**, does not isolate cold-cache versus I/O effects and does not fix or
explain the earlier close timeout. Both reports are retained separately.

A separate, bounded **10-round / three-concurrent-profile** lifecycle stress
also passed on the same installed 148 package, with fingerprint policies off.
Each round checked five-store persistence, a graceful checkpoint, one deliberate
browser crash, unaffected surviving profiles, recovery and owned-process exit.
All ten rounds recorded zero remaining owned processes; full payload/core
postguards passed. Evidence: `rollback-restarts-20261028-v4/report.json` on D.
The run took approximately 3m29s while the isolated 156 dependency sync was
active. It reused the existing assertions and deadlines without retries. This
is neither a full-suite rerun nor evidence for 156 or enabled privacy policies;
it did not reproduce or establish a fix for the earlier close timeout.

## Latest linked build: 001-062 — 2026-10-14

Patch 0062 is registered/applied to source: Windows font parameter policy,
validated renderer forwarding, early renderer initialization and five native
fixtures in the existing `gfx_unittests` target. The complete reviewed package
passed preparation/apply-check and isolated renderer startup C++/DEPS checks;
it is **not yet a runtime-admitted browser**.

The browser linked successfully at j4 in **29m02.24s**, 52 executed steps, with
an exact 62-patch receipt (`browser-build-001-062-v1.json` on D). This is an
incremental build, not a clean build. Core hashes:

| Runtime file | SHA-256 |
| --- | --- |
| chrome.exe | `275ad4eaa4b51b3e53a9a57496ecb17f6bc90b8c687e252567ce7d2050c0088c` |
| chrome.dll | `9b65965659f4ba78f2da12d18c858519a68066df232f0cd67a92bdb004e7a24a` |
| chrome_elf.dll | `f26f09cadfc9fbfe1384c2df2a7549151e4afa988568e6468d296d4fd61303fb` |

The exact 001-061 executable, DLLs, resource/locale packs and receipt were copied,
checksum-checked and actually launched before source promotion. Rollback proof:
`standalone-runtime-backup-001-061-before-062-v1/proof.json` on D.
The new `--target font-rasterization` verifier builds/selects exactly five named
tests, rejects missing/skipped/failed/duplicate cases and guards baseline browser
code, GN, receipt and source state. All **five native cases passed** after an
incremental j4 `gfx_unittests` build: **8m15.14s**, 138 executed steps. Browser
core/GN/receipt/source postguards passed. Proof:
`windows-font-policy-001-062-v1.json` and its raw `-tests.json` on D; test EXE
SHA-256 `3edc3eb7a3dd2997c51e4c42206f6224727e9347c766b5f5e5c2c25d1ed41a96`.
This proves parsing/field-preservation behavior, not renderer startup or pixels.
The compiled mode/restart/first-script/HDR/visual comparison **passed**:
`font-rendering-001-062-v1/report.json` on D. Six configurations (feature-off plus
five modes), two starts per persistent profile and eight scopes completed:
96 context observations, 576 text cases, 288 raw-image cases, 384 format cases
and 384 HDR cases. All core/receipt/resource/probe/screenshot postguards passed;
cleanup and repeated-start comparisons had no errors. Twelve PNGs were retained;
off/aliased/grayscale scenes were visually inspected.

| Mode | Measured effect and boundary |
| --- | --- |
| `native` | Matches feature-off in all eight scopes and visible samples |
| `aliased` | Changed all six text samples in every scope; visible DOM/SVG/Canvas changed, with sharper/jagged text and layout differences |
| `grayscale` | Changed all six text samples in every scope; visible Canvas pixels changed, recorded layout metrics retained |
| `cleartype-rgb` | Matches this host's baseline; no distinct-identity claim |
| `cleartype-bgr` | Visible opaque Canvas changed; Offscreen measurements matched baseline, so not five distinct Canvas identities |

Aliased/grayscale raw pixel differences were confirmed separately in **each** of
the eight scopes. Raw-image fidelity metrics, format operations and HDR results
retained their controls. This is rendering/compatibility fixture evidence, not
HDR colourimetry, broad application compatibility, fingerprint realism or
capability admission. The first fresh full runtime suite **failed**:
seven gates passed (**118 checks**), but the font-selection gate stopped after
eight completed checks with `Page.evaluate: NetworkError` while entering the
legacy path. Proof: `browser-verification-001-062-v1/`. External sites are not
yet retested and no full 160/160 claim is made for this run.

An instrumented repeat of the **unmodified** font gate passed all **42 checks**,
without request failures or changed core/source inputs:
`fonts-network-trace-001-062-v1/report.json`. A second attributed diagnostic run
also passed 42 with no failed requests (`fonts-attributed-001-062-v1.json`). These
repeats do **not establish the cause or fix** the original intermittent error.
The gate now retains bounded owned-font HTTP responses/failures, identifies the
mode/restart/context and preserves completed frame checks before later failures;
assertions were not weakened, retried or skipped. Full suite continuation v2
**passed all eight gates, 160/160 checks** on the unchanged binary:
`browser-verification-001-062-v2/suite.json`. This successful repeat does not
resolve the original NetworkError or establish reliability under all loads.

Fresh compiled branding verification also **passed** for this exact 001-062
runtime: project main/app-list icons, executable/library product names and the
version-page product label. Core/receipt/resource postguards passed. Proof:
`branding-runtime-001-062-v1/report.json` on D. This is not taskbar/shortcut
migration or fingerprint admission.

The manager now exposes five Windows text-rendering choices as **saved drafts**.
Existing policies default to `native`; reset restores it. Non-native choices
require the separate `font-rasterization` capability and remain blocked before
driver startup until verified activation is implemented. They are not silently
enabled by a successful diagnostic run.
The actual offscreen QML flow passed selection/save/invalid-value rejection,
native reset and pre-launch refusal; its rendered green UI was inspected at
1280x1100 (`font-policy-manager-001-062-v2/manager.png` on D). The offscreen
plugin had no system fonts, so the private capture explicitly registered this
host's Segoe UI/Consolas files; production font settings were not changed.
The full application/tooling regression after this integration passed
**2506 tests in 99.63s**. These tests do not admit experimental runtime policy.

The future mode gate also requires an aliased/grayscale pixel effect in **every**
scope, not merely one. A separate stricter assessment of the unchanged saved
actual measurements passed all eight scopes; original proof was not rewritten:
`font-rendering-001-062-v1-all-scope-audit.json` on D. This is a saved-data audit,
not another browser execution.
After manager integration, a **new actual browser execution** also passed:
`font-rendering-001-062-v2/report.json` on D. All six configurations completed
two starts and eight scopes with zero assessment/cleanup errors, unchanged
core/receipt/resources/probe inputs and stable visible/native comparisons.
This run includes configuration/privacy/runtime/identity source hashes and the
stricter every-scope pixel-effect requirement; it still grants no capabilities.
**598 Python tests passed in 20.58s**
for the updated release tooling and rendering helpers.
After adding the eight-context first-script fixtures, the full Python regression
completed: **2422 passed in 93.97s**. This is application/tooling test coverage,
not a linked 001-062 browser result.

### Windows package preparation

The public `stage_native_windows.py` command now invokes Chromium's official
`mini_installer_archive` target, with pinned source/receipt/GN/core/patch-chain
checks and postguards. It does not regenerate GN or replace the browser receipt.
The 001-062 j4 v2 attempt was interrupted without a terminal proof. On October 18,
no builder or surviving tool handle remained; the same target was resumed with
fresh `official-staging-001-062-v3*` evidence on D. No relocated-package or
capability admission follows from staging alone. The official archive target
**succeeded in 8m49.48s, two executed steps**; pinned source/core/GN/receipt
postguards passed. This is the archive action's time, not end-to-end source
validation or a clean browser build.
The first preflight refused equivalent LF/CRLF GN text before any compiler ran;
the corrected text comparison retains exact receipt and post-run byte guards.
That refusal is preserved in `official-staging-001-062-v1-preflight.json`.

The packager now checks the receipt's full core against the measured browser and
postguards receipt, GN, report, licenses and compiled payload sources after final
archive hashing. Mutation/removal tests require refusal without publishing an
archive. This is prerequisite integrity work, not policy activation.
The complete Python regression passed **2543 tests in 107.44s**, including 23
staging cases and packaging failure/postguard coverage. The local Retype build
also passed: 37 pages, zero errors/warnings. A previous docs CI run failed inside
Retype with `InvalidOperationException` concerning concurrent collection updates;
verbose CI logging is enabled to diagnose recurrence, not claimed as a fix.

The suite now accepts paired `--release-store` / `--release-sha256` arguments,
checks every installed payload file around each gate and stops on drift. The
runtime child must bind its own observations to that exact release. Evidence
and disposable profiles cannot be placed inside the binary store. Identity now
supports the explicit versioned DLL directory and rejects a directory whose
version differs from the running browser. These are package verification
mechanisms, not new fingerprint capabilities or a completed relocated 001-062 run.
An actual relocated **001-010 control** passed all 18 identity checks with the
new explicit DLL-directory support (`relocated-identity-001-010-v1/report.json`
on D). Its core was measured before/after; no DLLs were copied beside the EXE.
This is a control for the verifier, not 001-062 evidence, strict Client Hints,
TLS or third-party acceptance. The 52671fa desktop/docs CI runs both completed
successfully; the earlier Retype concurrency exception remains historical.
The full Python regression for the relocated-package support passed **2552
tests in 147.11s**. Resource/manifest mutation stops, release-bound child reports,
versioned identity DLL checks and refusal to write inside the store are covered.

The official 001-062 payload was packaged and installed into a new owned store:
**261 files**, **231,686,185 archive bytes** (220.95 MiB), complete payload hashes
verified. Proof: `managed-package-001-062-v1/proof.json` on D. Archive SHA-256:
`84e8d2369be630825afbff2732b09d5d81bb699e3c60025b73756c3fc305c10a`.
This is an unsigned local development artifact, not a published production release.
The installed-copy eight-gate run **passed 160/160 checks**:
`relocated-suite-001-062-v1/suite.json`. Runtime 18, hardware 9, WebRTC 7,
automation 55, fonts 42, identity 18, CDP 6 and combined 5 all passed, bound to
this archive digest and its complete installed payload. This is not external
anti-bot acceptance or publisher-signature verification. Activation/rollback
and same-Chromium profile continuity checks also **passed**:
`managed-package-001-062-v1/activation-rollback.json`. The owned store activated
001-010, activated 001-062, rolled back to 001-010 and reactivated 001-062.
Cookies, LocalStorage, IndexedDB, Cache and Service Worker registration survived
all four starts of one owned profile. Both immutable payloads retained their
hashes; no temporary health profiles remained. Both builds use Chromium
148.0.7778.96: this does not establish arbitrary Chromium downgrade compatibility.
The final active release is 001-062 in this diagnostic store only; user settings
and profiles were not switched. Binary-version activation does **not** admit
experimental fingerprint policies.

### Experimental manager policy admission — October 18

Selected controls now have a separate, explicit local review: CPU/memory
ceilings, installed font selection, WebRTC routing, webdriver exposure, native
headless-UA handling and Windows font rasterization. Only archive
`84e8d2369be630825afbff2732b09d5d81bb699e3c60025b73756c3fc305c10a`
and exact manifest SHA-256
`465b32ab5ad0488543ac3d9410e3f8576faa621e87399fa1d5db9959b5c0ed27`
are reviewed. The application pins these bytes independently of manifest
booleans, verifies every payload file off the event loop before each policy
start, and refuses unknown/changed runtimes before creating a user profile or
starting the driver. Native/default launches retain their existing behavior.
This is experimental local admission, not publisher signatures, security rebase,
general fork admission or a complete coherent-device generator.

`admitted-policy-001-062-v2/report.json` **passed** using NativeRuntime rather
than raw Playwright flags: two concurrently running profiles, initial/restart
phases, eight combined document/frame/worker contexts per phase and eight
first-script rendering scopes per phase. Native/grayscale effects were measured
in every scope; repeated reads, raw-image controls, colour/HDR operations,
WebRTC positive/restricted controls, security errors and owned profile markers
retained their contracts. Manager health diagnostics found zero mismatches;
runtime/probe input postguards and cleanup passed. The earlier v1 run also passed
and remains retained; v2 adds explicit unavailable-API/repeated-read and early
server-failure handling.

The actual manager/scenario path also **passed** with the UI privacy preset plus
grayscale: CPU 4, memory 4 GiB, real Arial/Segoe UI/Tahoma selection, webdriver
false and native Chrome/148 UA. Execution, Recorder capture and replay succeeded;
proof: `manager-admitted-policy-001-062-v1/report.json` on D. The green QML settings
flow was rendered/inspected at `font-policy-manager-001-062-v3/manager.png`.
The full Python regression passed **2576 tests in 131.27s**. Neither these results
nor the `identity` capability admit Canvas/Audio/GPU protection, TLS emulation,
arbitrary OS/device identities or external anti-bot acceptance.
Mobile Web health with all six controls also passed: 390x844, DPR 3, touch 1,
CPU/memory ceilings 2/2 and webdriver false, zero diagnostic mismatches
(`mobile-admitted-policy-001-062-v1/report.json`). It remains desktop Windows
Web Emulation, not Android/iOS identity or a mobile anti-bot result.

## Previous verified baseline: 001-061 — 2026-10-14

Continuation v2 completed at j4 in **23m48.21s**, 247 executed steps, with an
exact 61-patch receipt. This is incremental build time, not a clean build.
Proof: `browser-build-001-061-v2.json` on D.

| Check | Actual outcome |
| --- | --- |
| Compiled main/app-list icon payloads | Match the project ICO |
| Executable/library ProductName | **Glint** |
| `chrome://version` product and screenshot | **Glint**, project logo/wordmark visually inspected |
| Core, receipt, patches and resource/locale pack postguards | Unchanged during branding probe |
| Full eight-gate runtime suite | **160 checks passed**: runtime 18, hardware 9, WebRTC 7, automation 55, fonts 42, identity 18, CDP 6, combined 5 |

Branding proof: `branding-runtime-001-061-v1/report.json` and `version-page.png`
on D. Core executable/DLL hashes match 001-060 below: this package changes the
external UI resources/locale packs. The branding gate binds their separate
hashes; executable hashes alone do not identify the new UI package. Cached
taskbar icons, existing shortcuts, all UI screens and privacy admission remain
outside this branding gate. The receipt's runtime/privacy admission flags remain
false. Full-suite proof: `browser-verification-001-061-v1/suite.json`, with all
eight checksum-bound child reports. This passing fixture suite does not admit
the experimental rendering candidate, external anti-bot acceptance or a release.

The original **001-060** three-profile HDD lifecycle case was separately rerun
after the build finished: **three rounds passed in 64.047s**, with unchanged core
and production close deadlines. Proof: `shutdown-060-hdd-idle-v1.json` on D.
This supports an I/O-pressure explanation for the earlier shutdown timeout; it
does not erase the failed full-suite report or prove reliability under concurrent
build/storage pressure. No timeout extension, profile relocation or BTM disabling
was introduced.

## Previous linked build: 001-060 — 2026-10-14

Chrome continuation v2 linked successfully at j4 in **17m47.10s**, 177 executed
steps after the earlier OOM attempt and isolated object recovery. This is not
clean-build time. Receipt binds all 60 patches; a separately launched,
checksum-bound 001-060 copy is retained before the next UI-resource build.

| Runtime file | SHA-256 |
| --- | --- |
| chrome.exe | `275ad4eaa4b51b3e53a9a57496ecb17f6bc90b8c687e252567ce7d2050c0088c` |
| chrome.dll | `429bc5964bef552be528b4e6039529bef9cde0b18b079532ffa6b6a76c0216fc` |
| chrome_elf.dll | `f26f09cadfc9fbfe1384c2df2a7549151e4afa988568e6468d296d4fd61303fb` |

| Check | Actual outcome |
| --- | --- |
| Seven policy/runtime gates | Hardware 9, WebRTC 7, automation 55, fonts 42, identity 18, CDP 6, combined 5: **142 checks passed** |
| Full lifecycle gate | **Failed** after 17 completed checks, at graceful checkpoint close in the three-profile test; no 160/160 claim |
| Compiled Windows icons | Main/app-list payloads match the existing project ICO |
| Executable/library ProductName | Both report **Glint** |
| Version-page product | **Chromium**, so full branding gate failed |

Proofs on D: `browser-build-001-060-v2.json`,
`browser-verification-001-060-v1/suite.json`,
`branding-runtime-001-060-v1/report.json` and
`standalone-runtime-backup-001-060-before-061-v1/proof.json`.
The failed branding gate was not weakened: patch 0061 now updates the actual
UI message bodies and 14 scaled light/dark/favicons, retaining IDs, dimensions,
copyright authors and ChromiumOS naming. Its source preparation/reversal tests
passed. The first 001-061 process disappeared without a terminal receipt/report;
continuation v2 was started at j4 with cached objects and unchanged inputs.

Shutdown diagnosis narrowed the lifecycle failure: close/disconnected events
arrive, but native shutdown waits for ThreadPool; an owned process stack shows
`BtmDatabase::InitImpl` / SQLite commit blocked in Windows `WriteFile`. One-profile
diagnosis completed; three-profile diagnosis needed a longer diagnostic-only
deadline. These stack runs are **not runtime admission**. The speculative
disconnected-browser shortcut did not fix the graceful checkpoint failure and
was removed. Production timeouts remain unchanged; SSD-profile comparison and
HDD/I/O investigation are separate from the failed lifecycle gate.
Private evidence: `multi-profile-close-060-debug-v1/`,
`shutdown-stack-060-v2/`, `shutdown-stack-060-v3/` and
`runtime-001-060-crash-close-v2.json` on D.

An isolated storage-volume comparison then passed **three rounds / three profiles
in 42.516s** with temporary profiles on the local C: SSD and the exact unchanged
001-060 binary still on D:. Default production close deadlines were retained.
Proof: `shutdown-060-ssd-v1.json` on D. This supports investigating profile I/O
pressure rather than an unresponsive disconnected browser; it is **not a
replacement for the failed HDD gate**, nor proof that every HDD configuration is
broken. Recheck the original D: profile case after build I/O is idle before
changing native scheduling or runtime shutdown contracts. No automatic profile
relocation, forced shutdown or disabled BTM protection was introduced.

The compiled branding verifier now also binds both branding patches and runtime
resource/locale pack hashes, rejects changed/removed packs and retains failed
evidence. **2376 Python tests passed in 87.79s** after these changes. No privacy
capability or production release was admitted from this partial result.

## Previous verified baseline: 001-059 — 2026-10-14

Chromium 148.0.7778.96 linked at `j4` in **16m35.44s**, 244 executed steps,
reusing the prior source/test builds. The initial planned graph shrank as cached
dependencies were skipped; its 3016 estimate is not a fresh compilation count.
Receipt binds all 59 patches, GN arguments and the complete runtime core:

| File | SHA-256 |
| --- | --- |
| chrome.exe | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` |
| chrome.dll | `b78314a9b158d60729b85a30a0dbbf449d6391c3352b1f8fa7b4da463adbe384` |
| chrome_elf.dll | `3468b145cea9de7df386ad58c0daedba0d39c71bac58b0136486a36a2037b74d` |

| Gate | Result | Boundary |
| --- | --- | --- |
| Eight-gate runtime suite | **160 passed** | Runtime 18, hardware 9, WebRTC 7, automation 55, fonts 42, identity 18, CDP 6, combined 5; owned fixtures, not universal CDP invisibility |
| Combined profile-identity | **12/12 phases + 24 nested Canvas cases** | Canvas/Audio/WebGL in the same profiles and contexts; stable identity across tested origins, separate profiles, restart and simultaneous ownership |
| Combined partitioned-privacy | **12/12 phases + 24 nested Canvas cases** | Original partitioned derivation retained, with the same combined lifecycle/API checks |
| External fingerprint sites | **Mixed observations; see below** | Four public sites tested under proxy in headless/CDP mode; not CAPTCHA or human acceptance |
| CAPTCHA sites | **Not verified for this build** | No challenge completion or human-score claim |

Private proof: `browser-build-001-059-v1.json`,
`browser-verification-001-059-v1/suite.json`,
`combined-identity-surfaces-001-059-v2.json` and
`combined-partitioned-surfaces-001-059-v1.json` on D. Combined reports bind the
runtime core, receipt and probe source hashes; cleanup reported no error.

The first combined identity attempt is retained as failed evidence in
`combined-identity-surfaces-001-059-v1.json`: protected framebuffer reads returned
zeros/GL_INVALID_OPERATION because the harness enabled readback without enabling
its new GPU metadata transport dependency. The corrected harness requests both
features only in ready profiles; the same unchanged binary then passed both
combined modes. No native patch, fabricated metadata or weakened pixel validator
was used to obtain that result. First-script coverage is Canvas/Audio; nested
coverage is Canvas, not nested Audio/GPU. WebGPU is observed but not protected.
Product capability admission, branding, broader compatibility and external-site
verification remain separate outstanding gates.

### Repeatability and external observations

Profile-identity extended runs v2, v3 and v4 each passed **12/12 phases + 24
nested Canvas cases**. Runtime, receipt and probe-source hashes agree across
all three; no cleanup error was reported. Proofs on D:
`combined-identity-surfaces-001-059-v2.json`, `-v3.json` and `-v4.json`.

Four public sites returned HTTP 200 through authenticated SOCKS egress verified
inside the browser. Test profile: native Windows/GPU, de-DE, Europe/Berlin,
headless Chromium 148 with CDP attached and profile-identity surface candidates.
Two runs used the same persistent profile and unchanged core. The first omitted
the existing native UA flag; the second enabled `--camouflow-native-user-agent`.
No JavaScript API overrides or engine rebuild were used for this comparison.

| Service | First run, native UA flag off | Same-profile run, native UA flag on | Boundary |
| --- | --- | --- | --- |
| BrowserScan bot detection | **Robot**, UA highlighted | **Normal**; webdriver/UA/CDP/navigator sections not flagged | One observed visit per configuration, not universal CDP invisibility |
| Sannysoft | `HEADCHR_UA` failed on HeadlessChrome | `HEADCHR_UA` ok, webdriver advanced passed, Chrome object present, five plugins; no FAIL row found in captured scanner text | Some deliberately invalid API calls produced page errors; not a CAPTCHA test |
| Device and Browser Info | `isBot: true`; bot UA and timing resolution flagged | **Still `isBot: true`**; only timing resolution flagged in captured details | Worker/document CDP, Client Hints, WebGL and GPU consistency flags were false in this observation |
| CreepJS | 67% headless; 44% like-headless; reported 14% RGBA noise | 0% headless; **44% like-headless and reported 13% RGBA noise remain** | Its own diagnostic metrics, not a human score or a pass/fail certification |

Private bodies, screenshots and core/cleanup evidence:
`external-identity-probes-001-059-v2/` and `-v3/` on D. Initial discovery failure
is retained in `-v1/`: Browser.getBrowserCommandLine requires the diagnostic
automation flag. All test-owned browser resources were released. No proxy
credentials or raw profiles are published.

### Matching-version stock control

Unmodified Playwright Chromium **148.0.7778.96** was tested on the same machine
and authenticated proxy route, with de-DE/Europe/Berlin, a fresh persistent
profile, headless mode and CDP attached. Its three core hashes matched the
previous stock calibration and remained unchanged after the run. Four page
observations completed with HTTP 200; test-owned resources were released.

| Observation | Glint 001-059, native UA enabled | Matching stock Chromium | Interpretation |
| --- | --- | --- | --- |
| Device and Browser Info timing flag | `hasInconsistentTimingResolution: true` in the recorded visit | **True on all three visits** | Not isolated to Glint patches; no timer root cause established |
| Overall bot verdict | `isBot: true`, timing flag only in captured details | `isBot: true`, also expected UA/WebDriver/CDP flags | Different launch features; do not compare overall verdicts as an equivalent clean-browser control |

Private proof: `stock-site-control-148-001-059-v1/report.json`, screenshots and
captured same-origin diagnostic scripts on D. This control is automated and
headless, **not a manual human-browser baseline**. The captured same-origin
scripts did not expose the named timing check; an external fingerprint script
was listed but not captured. Do not infer the detector's implementation from
its flag name or change browser timer semantics on this evidence alone.

Next: isolate launch/instrumentation factors before changing timer semantics;
investigate detectable Canvas perturbation and ordinary graphics compatibility.
A green BrowserScan observation does not close these gaps or imply
Turnstile/reCAPTCHA success.

### Controlled Canvas pixel fidelity

`scripts/native_canvas_fidelity.py` measures bounded 32x24 RGBA fixtures:
explicit `putImageData`, repeated/full/single-pixel reads, PNG export/decode and
writing the returned image into another canvas. It reports changed channels,
pixels, alpha and maximum absolute error; it does not call pixel mutation a PASS.
Stock Chromium and feature-off Glint had matching metrics on all three fixtures.

| Input fixture | Feature-off Glint vs supplied pixels | Profile-identity candidate vs supplied pixels | Repeat / single pixel / PNG / rewrite |
| --- | --- | --- | --- |
| Opaque palette | Exact | **720/768 pixels, 1056 channels changed**, maximum error 1 | No differences relative to the first read |
| Opaque gradient | Exact | **667/768 pixels, 1150 channels changed**, maximum error 1 | No differences relative to the first read |
| Half-transparent palette | 768 pixels / 1344 channels changed, maximum error 1 | Same metrics as stock and feature-off Glint | No differences relative to the first read |

All alpha bytes were preserved. The transparent control's rounding is retained,
not misclassified as a Glint regression. Matching counts do not prove identical
pixels. These three document fixtures do not cover workers, HDR, every colour
space or image-editor compatibility. Protected opaque `putImageData` is **not
pixel-exact**; deterministic repeat/export consistency alone does not establish
ordinary-browser plausibility or fidelity. Do not admit this candidate as fully
compatible based on the earlier combined gates.

Private proof: `canvas-fidelity-001-059-v1/report.json` on D; exact matching
browser versions, measured effective launch flags, probe/receipt hashes and
unchanged runtime cores/receipt; no cleanup errors. The measurement/validator has
29 passing Python tests; the full Python regression suite passed **2321 tests
in 82.88s** after this addition. No Chromium source change or rebuild was made.

The measurement now lives in `app/core/native/canvas_fidelity.py`; the script
re-exports the same implementation. Manager diagnostics run it in the document
and dedicated worker and report opaque mutation/readback inconsistencies as
mismatches. Actual baseline/protected 001-059 profiles verified this integration:
baseline had no mismatches; protected had exactly four opaque-mutation warnings
(two per scope), with matching document/worker metrics and no alpha mutation.
This new owned profile measured 672 palette and 655 gradient pixels changed;
different profile keys mean these counts need not equal the earlier profile.
The routed health probe also passed with its real CSP, worker lifecycle and
disposable-profile cleanup. Proofs: `product-canvas-fidelity-001-059-v1/report.json`
and `product-canvas-health-001-059-v1/report.json` on D. No capability was admitted.
After integration, all **2335 Python tests passed in 81.51s**; 43 cover the shared
measurement, malformed metrics, product audit and worker probe composition.

### Branding source preflight

The prepared Glint branding patch passed the new nonmutating source/asset replay
against actual source 001-059. All 16 resulting file hashes matched freshly
generated product/logo assets; reversing the patch restored the owned copy,
and the actual source files remained unchanged. Proof on D:
`branding-replay-001-059-v4/report.json`. The gate rejects extra paths, changed
branding assets and reuse of an existing evidence directory. The first v1
attempt failed in the verifier on an incorrect report-key lookup before replay;
its artifacts were retained and the generator contract was corrected.

This is **not compiled branding**: the current executable remains unbranded,
and these preflight results do not prove UI behavior. Product/about
strings, Windows icon resources and shortcut migration still need the next
linked build and actual UI checks.

The same patch is now registered as `0060-native-glint-branding.patch` and was
applied to the idle source checkout after preserving and actually launching a
checksum-bound standalone copy of verified 001-059. Its normalized registered
artifact passed replay again (`branding-replay-001-059-v5/report.json`). The
001-060 build was started at j4; it is not yet a verified runtime. Build state
must be checked from live processes and its terminal report, not this paragraph.
Hardware/identity CHECK-message verifiers retain exact historical and branded
diagnostics; generic launch errors remain rejected. Release-tool tests passed
571/571 before starting the new build.
The full Python regression suite then passed **2337/2337 in 85.30s**.

The first 001-060 build attempt terminated after **12m51.40s**, with 123 finished
steps, two failed C++ objects and 4044 remaining graph steps. Both failures
reported **LLVM ERROR: out of memory**, in `paint_preview_client.obj` and
`connectors_service_base.obj`; this is not evidence of a source/type error.
The graph estimate had already shrunk from its initial plan, so it is not a
fresh-compilation count or a reliable completion-time estimate. First-attempt
evidence is retained in `browser-build-001-060-v1.json` and archived
`heavy-objects-001-060-isolated-v1/siso_output` / `siso_failed_commands.bat` on D.
Both object targets then compiled successfully, sequentially with the same j4
setting: **1m53.00s** and **19.16s**, one executed step each. The terminal proof
`heavy-objects-001-060-isolated-v1/proof.json` binds both object hashes and confirms
unchanged sources, runtime core, GN, receipt state and toolchain. Compiler flags,
pagefile and caches were not changed. Chrome continuation v2 was started at j4;
its terminal receipt and runtime tests are still required. A recovered object
is not a completed browser or evidence that memory pressure cannot recur.

### Canvas colour-space and storage compatibility

The bounded `native_canvas_formats.py` probe measures four actual context/output
combinations, in document and dedicated worker. It checks requested context
colour space/storage, returned ImageData format/type, finite samples and PNG
export status. An ignored float16/P3 request is rejected by the verifier rather
than treated as supported. Different PNG byte lengths are not an API failure.

The separate, checksum-bound 001-059 rollback runtime was used while 001-060
compiled; no browser was opened from the active build output. Unmodified Chromium
148.0.7778.96 and feature-off Glint supported all four combinations. Their
document/worker observations agreed. Current profile-identity protection has
**six API compatibility failures per scope**, not a passing format gate:

| Actual context / requested ImageData | Stock and feature-off Glint | Protected getImageData | Protected PNG export |
| --- | --- | --- | --- |
| sRGB/unorm8 / rgba-unorm8 | Both operations supported | Supported | Supported |
| Display-P3/unorm8 / rgba-unorm8 | Both operations supported | **NotReadableError** | **NotReadableError** |
| sRGB/float16 / rgba-float16 | Both operations supported | **NotReadableError** | **NotReadableError** |
| Display-P3/float16 / rgba-float16 | Both operations supported | **NotReadableError** | **NotReadableError** |

Proof: `canvas-formats-001-059-v3/report.json` on D, including worker rows,
measured effective launch flags, unchanged copied runtime cores/receipt and no
cleanup errors. Earlier v1 measured float16 output conversion from an unorm8
backing; v2/v3 explicitly verify float16 backing as well. This is API coverage,
**not HDR tone-mapping, out-of-range sample fidelity, every browser context or
editor compatibility**. Broad Canvas capability admission remains blocked;
the next implementation must address these failures without silently changing
the requested format, losing alpha/colour semantics or bypassing policy.
The full Python regression run passed **2350 tests in 98.92s** before the final
worker-cleanup assertion was added; all **14 format tests** passed afterward.

### Next rendering candidate (not part of the active build)

The new public `native/drafts/font-rendering/` package prepares actual Windows
font-rasterization modes, with native cached-parameter application, validated
renderer switch forwarding and five native fixture definitions. Preparation and
apply-check passed on source 001-060 without modifying it. Two isolated C++ type
checks passed with actual gfx/gfx-unittest target flags: Windows parameter hook
and fixtures; active inputs/core stayed unchanged. Private proof:
`windows-font-rendering-cpp-001-060-v1/proof.json` on D.

This is not optimized compilation, fixture execution, renderer forwarding
validation or browser protection. The candidate is unregistered, unapplied and
not selectable in the manager. It does not repair the old readback algorithm by
itself; verify pixel fidelity and text/rendering coherence before admission.
After adding the preparation tests, **2354 Python tests passed in 110.26s**.

## Test destinations

Priority: **Core** for each build; **Extended** before release; **Reference** for
research. Availability and detector behavior must be rechecked at test time.

| Service | What to inspect | Priority | Evidence to retain |
| --- | --- | --- | --- |
| [CreepJS](https://abrahamjuliot.github.io/creepjs/) | JS API inconsistencies, Canvas, Audio, fonts, workers | Core | Report, reported lies and context differences |
| [Pixelscan](https://pixelscan.net/) | Fingerprint/environment consistency and network observations | Core | Exact findings, configuration and screenshot |
| [BrowserScan](https://www.browserscan.net/bot-detection) | Automation signals; use other sections for IP, WebRTC and fingerprint | Core | Bot verdict and individual signals |
| [Sannysoft](https://bot.sannysoft.com/) | WebDriver, headless and automation indicators | Core | Every individual check, not only green tiles |
| [BrowserLeaks](https://browserleaks.com/) | Canvas, WebGL, WebRTC, fonts and Client Hints | Core | Surface values and repeat/context comparisons |
| [IPhey](https://iphey.com/) | Browser and network consistency | Core | Individual findings and route label |
| [Fingerprint Playground](https://demo.fingerprint.com/playground) | Visitor recognition and available bot/tampering signals | Core | Same-profile revisit and different-profile observations |
| [Rebrowser Bot Detector](https://bot-detector.rebrowser.net/) | Automation/CDP-related behavior | Core | Individual tests; manual-only checks remain unverified |
| [Incolumitas](https://bot.incolumitas.com/) | Headless, API and behavioral bot checks | Core | Individual findings and observation duration |
| [Device and Browser Info](https://deviceandbrowserinfo.com/are_you_a_bot) | Browser automation indicators | Core | Individual flags, browser mode and CDP connection state |
| [TLS Peet](https://tls.peet.ws/) | TLS/HTTP fingerprints, including available JA3/JA4 data | Core | Browser-originated request; compare same-route stock Chrome |
| [IPify](https://api.ipify.org/?format=json) | Actual browser request egress | Core | Private expected-egress comparison; redact public IPs |
| [BrowserLeaks WebRTC](https://browserleaks.com/webrtc) | ICE candidates and address exposure | Core | Compare with expected proxy route; redact addresses |
| [DNS leak test](https://www.dnsleaktest.com/) | Resolver exposure during browser requests | Extended | Resolver observations; distinguish proxy and OS behavior |
| [Cover Your Tracks](https://coveryourtracks.eff.org/) | Tracking protection and fingerprint uniqueness in its sample | Extended | Sample size/date; uniqueness is not a bot verdict |
| [AmIUnique](https://amiunique.org/) | Fingerprint uniqueness in its participating population | Extended | Sample/date; results are population-dependent |
| [Fingerprint Demo](https://fingerprint.com/demo/) | Vendor demo entry point and visitor recognition | Extended | Record actual redirected destination and enabled product |
| [PrivacyTests](https://privacytests.org/) | Published browser privacy comparisons and test methodology | Reference | Not an interactive Glint certification; run applicable source tests separately |

## CAPTCHA destinations

| Service | Test | Priority | Acceptance boundary |
| --- | --- | --- | --- |
| [Google reCAPTCHA demos](https://recaptcha-demo.appspot.com/) | Available v2 checkbox/invisible examples | Extended | Record challenge outcome and actual backend response separately |
| [Google reCAPTCHA v3 scores](https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php) | Official sample score request | Core | Backend success, score, action and hostname; sample score is not production quality |
| [Google reCAPTCHA v2](https://www.google.com/recaptcha/api2/demo) | Manual checkbox/challenge flow | Extended | Widget completion alone is not server verification |
| [Cloudflare Turnstile demo](https://demo.turnstile.workers.dev/) | Widget and integration smoke check | Core | Check current key/source: dummy keys cannot demonstrate real anti-bot acceptance |
| [Turnstile testing documentation](https://developers.cloudflare.com/turnstile/troubleshooting/testing/) | Controlled pass/fail integration fixtures | Reference | Separate guaranteed dummy outcomes from real production keys |
| [hCaptcha developer guide](https://docs.hcaptcha.com/) | Authorized controlled widget and backend verification | Extended | Requires a controlled deployment; test keys prove integration only |

Real Turnstile managed/non-interactive, hCaptcha and reCAPTCHA acceptance tests
require an authorized deployment with real keys and backend verification. Until
available, mark them **Not verified**, not PASS. Do not use paid solvers, token
substitution or unrelated account workflows. Do not publish CAPTCHA tokens,
secret keys, proxy credentials or identifying fingerprint payloads.

## Repeatable run protocol

First calibrate the existing local probes against stock Chrome. Distinguish
value changes, API behavior regressions and expected context-specific absences.
Add repeatability/isolation comparisons and record CDP attach vs Runtime.enable
separately. The [implementation roadmap](GLINT_ROADMAP.ru.md) defines these gates;
external green tiles do not replace them.

1. Record build ID, Chromium version, applied patch range, executable/core-DLL
   hashes, date, Windows version and policy configuration.
2. Run headed manual, headed automation and headless automation separately.
   Record CDP connected/disconnected state and effective launch arguments.
   Do not use JS API overrides or framework stealth flags as engine evidence.
3. Test the direct route and each configured proxy separately, using disposable
   profiles. Direct means no configured browser proxy, not necessarily no VPN.
   Verify HTTPS egress and DNS/WebRTC expectations without a direct fallback.
4. Compare with unmodified Chrome under the same route and mode. Repeat at least
   three times; compare same-profile restart and separate-profile observations.
5. Save raw reports/screenshots privately, then add a redacted results section
   below. Keep screenshot failures separate from detector observations.
6. Use **Observed**, **Failed**, **Unavailable**, **Not run**, or **Not verified**.
   Never convert a timeout, missing field or test-key CAPTCHA into PASS.

## Build history

### Native identity keys/service 001-058 — 2026-10-14

**62/62 cases passed**: 19 new identity derivation/immutable-mode cases and
43 legacy key/loading/readiness cases. Zero failed, disabled or error cases;
318 ms execution. The cached j4 build completed in **11m15.62s**, 201 executed
steps. Test EXE SHA-256:
`f9a9f48fab2224cf760ed1c24ff5d1186392431369c96da1670954fd2c479eaf`.
Source, browser 001-047 core, GN and receipt remained unchanged after execution.
Private proof/raw results/log: `identity-keys-001-058-v1.json`, `-tests.json`
and `-build.log` on D. This is key/service proof, not BrowserContext, IPC,
first-script delivery, GPU-driver coverage or linked identity-mode admission.

### BrowserContext build recovery 001-058 — 2026-10-14

The first `identity-contexts` build stopped after **5m49.15s**, 152 completed
steps, with `LLVM ERROR: out of memory` while compiling generated
`navigation_params.mojom-blink.cc`. **The 37 cases did not execute.** Failed
report/log remain in `identity-contexts-001-058-v1.*` on D.

The exact failed object subsequently compiled alone under the unchanged
production flags, diagnostics and `j4` setting: **2m21.31s**, one executed step.
Source, browser core, GN and receipt remained unchanged; object SHA-256:
`5cbdc33f47b63a38fe0ead6d581e3955aa029fbfc8137d73e6e642d1e7f3624b`.
Private proof, log and saved Clang reproducer:
`navigation-object-001-058-isolated-v1/` on D. The full cached j4 retry uses
`identity-contexts-001-058-v2.json`; object compilation is not a passing
BrowserContext gate or linked browser result.

The full v2 retry also stopped on memory exhaustion after **56.39s**, five
completed steps. This time `core_probes_impl.cc` failed with LLVM OOM; another
compiler reported Windows **0x5AF** (insufficient paging capacity). The 37
BrowserContext cases still did not execute. Failed v2 evidence is retained.
Known heavy `core_probes_impl` and generated `shorthands` objects then compiled
successfully as separate single-object targets with the original `j4` option and
unchanged flags: **50.43s** and **26.92s**, one executed step each. Proof on D:
`heavy-objects-001-058-isolated-v1/proof.json`. Source, browser core, GN, receipt
and toolchain remained unchanged; no diagnostic was suppressed or paging
configuration changed. The full cached retry now uses
`identity-contexts-001-058-v3.json`. This proves two objects, not the 37 cases or
that every remaining parallel compile will fit memory.

The v3 retry stopped after **4h23m01.48s**, with 3169 completed steps and
477 remaining, at the V8 context snapshot action: `WriteFile of 3918880
snapshot has failed`. The same generator successfully wrote a separate
3918880-byte probe file. A manually opened browser was still using this build
directory, so a mapped-file conflict is suspected; no browser was forcibly
closed and no snapshot was replaced. Failed proof remains in
`identity-contexts-001-058-v3.*` on D. **The 37 cases still did not execute.**

To make progress without touching the live browser's snapshot, all **631
content unittest object targets** were successfully checked/built in bounded
command batches with `j4`. Cached objects were reused; 631 is the target count,
not the number of freshly compiled objects or executed tests. Source, browser
core, GN, receipt, toolchain and existing snapshot hashes remained unchanged.
Private proof: `context-objects-001-058-v2/proof.json` and `build.log` on D.
This is object compilation only: full linking, snapshot generation and the
context/transport test executions remain pending.

The additional **418 object targets** recorded as unfinished in the v3 failure
log then completed in guarded `j4` batches: 34, 0, 30, 100 and 18 executed
steps, with earlier cached objects reused. These overlap the 631 targets above
and must not be added together as distinct compilations. Source, browser core,
GN, receipt, toolchain and existing snapshot hashes remained unchanged. Proof:
`remaining-context-objects-001-058-v2/proof.json` and `build.log` on D.
The browser session is still open; the original snapshot action, final linking
and all 37 context tests remain unverified.

### Identity contexts/transport and snapshot recovery 001-059 — 2026-10-14

Patch **0059** makes the actual V8 snapshot generator avoid writing only when
the existing file matches every generated byte, using a size-bounded read.
The old and freshly generated snapshots both hashed to
`790ea6e0d2b5b1f91cf3e922b0347c7372151c5e728467b95323466755c15905`.
The blocked action then succeeded without closing the manual browser or
rewriting its snapshot. The content target linked at `j4` in **7m36.91s**,
24 executed steps, retaining earlier compiled objects.

**37/37 BrowserContext cases passed** in 153 ms, followed by **20/20 transport
cases passed** in 3.524 seconds, with no skipped, disabled or failed cases.
Source, browser core, GN and receipt guards passed. Content test binary SHA-256:
`a27bca9c279bff13fc7316f8443f7c56553f02f6b813b2e0cfd744b4d375b7bc`.
Proof/raw results/logs: `identity-contexts-001-059-v1.*` and
`identity-transport-001-059-v1.*` on D. These are content-layer fixtures, not a
new Chrome binary, actual renderer IPC or profile-identity capability admission.

Five actual generator controls passed: missing file creation; identical readonly
file accepted without changing bytes or timestamp; different readonly bytes
rejected; an extra-byte readonly file rejected; different writable file replaced
with the generated bytes. Failed writes retained their input bytes and returned
exit code 1. Proof: `snapshot-idempotence-001-059-v1/proof.json` on D, with
source/core/GN/receipt/snapshot/generator hashes unchanged during those controls.
The two Blink identity-handoff fixture objects also compiled in **42.15s**,
but their 15 cases have not executed: `identity-handoff-objects-001-058-v1/`.

### Blink identity handoff 001-059 — 2026-10-14

The actual `blink_unittests` target compiled and linked at `j4` in
**2h1m54.83s**, 948 executed steps. **15/15 cases passed** in 520 ms with no
skipped, disabled or failed cases: three DocumentLoader fixture definitions
each ran in four parameter modes (12 cases), plus three worker-thread fixtures.
The final source/core/GN/receipt guards passed. Test binary SHA-256:
`a358e707622e2c5cff70a4eb331dd5cfb30938e20878c8d83596f387284f5dd6`.
Proof/raw results/log: `identity-handoff-001-059-v1.*` on D.

The selected cases cover policy ownership before inline document execution and
worker evaluation, clone isolation, rejection of unknown modes and retention
of the authenticated final origin. They do not prove Chrome ProfileImpl startup,
complete renderer-to-browser IPC or the new profile-identity browser runtime.
The current browser core remains 001-047; capability admission remains closed.

The key/service gate was subsequently repeated on 001-059 and passed **62/62**:
`identity-keys-001-059-v1.*` on D. All four identity selections now have executed
proof on the same registered source chain: **134/134** cases (50 new, 84 legacy).
This does not promote source-only results into a browser runtime admission.

Before rebuilding Chrome, an isolated 001-047 rollback copy was created on D:
`standalone-runtime-backup-001-047-before-059-v2/`. Its **509 files**, totaling
690878774 bytes, match recorded hashes; the copied runtime launched headlessly
as Chromium 148.0.7778.96 and released runtime ownership. The first attempt is
retained as failed evidence: it omitted the versioned assembly manifest and
Windows reported SideBySide error 14001. The v2 copy includes that manifest.
This is a local rollback copy and launch check, not a new published package or
a repeat of the full browser verification suite. Chrome 001-059 is now building
at `j4`; there is no verified new browser binary yet.

### Native GPU metadata 001-058 — 2026-10-14

The actual Chromium `gpu_unittests` target compiled and linked at `j4` in
**6m42.46s**, 120 executed steps. **33/33 cases passed**, without skipped or
disabled cases: codec 14, passthrough protocol 5 and attachment 14. Execution
took **937 ms** in the first run. The public verifier repeated the same exact
selection successfully using the cached target. Source, browser core, GN and
receipt remained unchanged; the first guarded run also bound the toolchain and
existing snapshot hashes. Test binary SHA-256:
`78119b90a44733b5ded4b0f9937f14c7b78a36b362d03d2d78e3bbf47986330d`.

Proof/raw results/logs on D: `gpu-metadata-units-001-058-v1/` and
`gpu-metadata-001-058-v2.*`. Reproduce the exact registered target with:

```powershell
.venv\Scripts\python.exe scripts/verify_native_privacy_units.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\gpu-metadata-new.json --vs-installation D:\CamouFlowNative\toolchain\BuildTools --jobs 4 --target gpu-metadata
```

This proves the selected codec and passthrough command/attachment fixtures,
including buffer bounds, feature-off behavior, selected attachment dimensions,
formats, mip/face/layer selection, bindings and pending client errors. It does
not prove the excluded validating decoder, renderer-to-GPU IPC, protected
browser readback, WebGPU, profile-identity mode or capability admission.

A broader exact-suite regression run then passed **74/74 cases** in 272 ms:
the 33 selected metadata cases plus 41 existing GLES2/GLES3 passthrough cases.
No skipped, disabled or failed case was accepted; source/core/GN/receipt,
toolchain and snapshot hashes remained unchanged. Private proof/raw results:
`gpu-passthrough-regression-001-058-v1/` on D. The filter covered
`GLES2DecoderPassthroughTest.*`, `GLES3DecoderPassthroughTest.*`,
`GlintReadbackMetadataTest.*` and `GlintPassthroughAttachmentTest.*`; it does
not cover every typed/parameterized GPU suite. These 74 include the earlier
33 and must not be added as disjoint tests. The full Python suite after adding
the public metadata verifier passed **2292 tests** in 82.72 seconds.

### Additional owned browser gates 001-047 — 2026-10-14

| Gate | Result | Scope and limits |
| --- | --- | --- |
| Nested Canvas | **24/24 + 7/7 phases passed** | Four classic/module parent-child combinations across baseline/two profiles and restart; first-script and repeated pixel/PNG reads, exact fetch/body counts. No nested Audio, independent child denial or early-termination claim |
| Strict Client Hints | **18/18 passed** | Eight document/frame HTTP-versus-JS comparisons, six worker JS checks, four invalid-UA rejections. Worker HTTP hints, TLS and cross-platform identity are not covered |
| Combined future Identity/GPU C++ preflight | **22 + 6 units passed** | One composed tree with fresh Mojo/GPU generation and no omitted units; parsing/type checks only, not fixture execution or a linked identity-mode browser |

Private reports on D: `combined-surfaces-nested-001-047-v4.json`,
`identity-strict-001-047-v2.json` and
`identity-readback-combined-cpp-001-048-v3.json`. Browser EXE/DLL core hashes
remained unchanged; candidate preflight also preserved active source and GN.
Strict v1 failed cross-origin HTTP hints because the owned fixture lacked
Permissions-Policy delegation. The fixture now grants only its exact localhost
origin and iframe features in strict mode; the failed evidence remains retained.
These are controlled gates, not external detector or CAPTCHA acceptance.

### Unregistered GPU codec execution — 2026-10-14

**14/14 actual `GlintReadbackMetadataTest` cases passed**, zero failures,
disabled cases or errors. The standalone executable uses real GoogleTest and
GL types from the pinned Chromium source, compiled with MSVC C++20 `/O2 /W4 /WX`.
It checks schema/status, exact wire length, dimensions, format/sample validity,
byte-colour eligibility and producer rejection. It is not the Chromium GN test
target, GPU protocol/attachment execution, a driver test or a new browser build.

Proof and raw logs/results remain on D:
`gpu-metadata-codec-001-048-v3.json` and its `-artifacts` directory.
Browser core, GN and receipt remained unchanged. The original `/WX` failure on
signed/unsigned fixture expectations remains recorded; expected GL enums were
typed explicitly, without suppressing a warning or removing a test. Full draft
composition and fresh Mojo/GPU generation passed after that fixture-only repair:
`identity-readback-codec-fixture-001-048-v1.json`.

### Windows native readback units 001-048 — 2026-10-14

The cached j4 retry linked `blink_unittests.exe` in **1h30m44.64s**, 654 executed
steps, then passed **31/31 cases** across pack copy (14), region planning (11)
and clipped publication (6). Zero failures, disabled cases or errors; 176 ms
test execution. Source, GN, receipt and the 001-047 browser EXE/DLL core stayed
unchanged. Test binary SHA-256:
`44ac3b7c8e178db08130c62762e323e73077af6f4b9b7e30f5c47bebfb0c90c0`.

Private proof/raw tests/log: `gpu-readback-units-001-048-v2.json`,
`gpu-readback-units-001-048-v2-tests.json` and `-build.log` on D.
The first build failed with LLVM OOM after 302 steps; its evidence remains.
This proves the selected native copy/planner fixtures, not a new browser build,
GPU-driver execution, WebGPU, identity mode or external detector acceptance.

### Windows development candidate 001-047 — 2026-10-13

Corrected j4 incremental build succeeded in **12m46.29s**, 76 executed steps.
The first attempt failed on a typed `base::expected` call, not OOM; its log
remains retained. The corrected caller also passed isolated optimized object
compilation before retrying the whole browser.

Measured `chrome.dll` SHA-256:
`f70a287dc74fbb8788c0b94ac55f48169de7fc79a7c500d463cb1d47f1bd59d7`.
The receipt binds all 47 exact patch hashes, EXE/DLL core and GN configuration.

| Owned check | Result | Boundary |
| --- | --- | --- |
| Protected WebGL readback | **Passed: six phases** | Baseline and two independent profiles before/after restart in eight document/worker contexts; CPU/PBO clipping, untouched padding, renderbuffer resize, exports, errors and profile isolation |
| Eight-gate suite | **Passed: 160 checks** | All eight gates completed on the unchanged 001-047 EXE/DLL core |
| Combined Canvas/OfflineAudio | **Passed: three consecutive 7/7 runs** | Same measured EXE/DLL core, restart/profile/context consistency, exact missing-policy abort and completed cleanup; older intermittent timeout remains unexplained |
| Worker startup/restart/shared clients | **Passed: 40/40** | Default contract, surfaces bootstrap |
| Extended nested dedicated workers | **Passed: 60/60** | Includes default 40 and 20 additional classic/module parent/child combinations across modes and restart; not independent child-policy denial or protected child pixels |
| Native readback fixtures | Not executed; C++ preflight failed | Pack-copy and region fixtures misuse typed results; clipped-publication fixture parsed successfully. Exact 31-case execution remains required |
| External detectors and CAPTCHA | Not rerun | No third-party acceptance claim |

Private evidence: `browser-verification-001-047-v1/gpu-readback.json`,
`combined-surfaces-001-047-v2.json`, `combined-surfaces-001-047-v3.json`,
`halo-expected-compilation-001-047-v2/proof.json` and
`nested-fixture-validation-001-047-v1/proof.json` on D:. Source replay is
`clipped-readback-replay-001-047-v2.json`; the earlier failed build is
`clipped-readback-001-047-chrome-j4-v12.log`. No release or broad GPU capability
is admitted by this single owned readback run.

Completed browser evidence: `browser-verification-001-047-v1/verification.json`,
`suite/suite.json`, `surfaces.json`, `worker-startup.json`, and
`worker-nested-001-047-v1.json` on D:. The nested run binds the same core and
probe hash, with independent parent/child fetch and execution counters.
Native fixture preflight failure is retained separately as
`readback-fixture-cpp-001-047-v1/proof.json`; no test was skipped or declared passed.

### Windows development candidate 001-045 — 2026-10-13

j4 incremental build succeeded in **5m29.58s**, four executed build steps.
The receipt now directly binds EXE and both core DLLs. Measured `chrome.dll`
SHA-256: `0e2e217ebcfe59adf15da09ec6d95ac7c65e9258d77bca523c96036f7340e894`.
EXE and `chrome_elf.dll` hashes are unchanged from 001-039; the engine code
changed in `chrome.dll`.

| Owned check | Result | Boundary |
| --- | --- | --- |
| Eight-gate ordinary runtime suite | **Passed: 160 checks** | Runtime, hardware, WebRTC, automation, fonts, HTTP/JS identity, CDP and combined existing policies; unchanged EXE/DLL core |
| Classic/module worker startup/restart | **Passed: 40/40** | Surface bootstrap, shared clients and unavailable-policy rejection; not nested-worker or early-termination admission |
| Combined Canvas/OfflineAudio, initial run | **Failed: timeout** | Four phases passed; profile-B initial frame evaluation timed out; cleanup completed |
| Combined Canvas/OfflineAudio, v2 retry | **Passed: 7/7** | Includes cross-profile/restart checks and exact missing-policy abort; does not resolve initial intermittent timeout |
| Combined Canvas/OfflineAudio, v3 retry | **Passed: 7/7** | Second consecutive passing retry on unchanged core; first failure remains open |
| Protected WebGL readback | **Failed** | Baseline initial/restart passed; profile-A initial failed boundary semantics: out-of-bounds CPU bytes changed from sentinel 165 to zero across all eight contexts, before/after attachment resize |
| Native fixtures | **Passed: 136/136** | Navigation 42, contexts 26, window/child 13, worker surfaces 55 on one test binary; distinct from browser runtime |
| External detectors, proxy routes and CAPTCHA | Not rerun | No third-party result or acceptance claim for this build |
| Next identity/readback batch | Source checks passed | Twelve unregistered patches, 113 paths, isolated Mojo/GPU generation; not compiled or enabled |

Private evidence on D: `browser-verification-001-045-v1/suite/suite.json`,
`browser-verification-001-045-v1/worker-startup.json`,
`browser-verification-001-045-v1/surfaces.json` (failed run),
`combined-surfaces-001-045-v2.json` (passing retry) and
`combined-surfaces-001-045-v3.json` (second passing retry),
`gpu-readback-001-045-v1.json` (protected readback failure) and
`identity-readback-001-045-batch-v1.json`. All failures remain recorded.
The overall first browser-verification run remains failed; no release or
surface capability is admitted from a passing retry alone.

### Windows development candidate 001-039 — 2026-10-13

j4 incremental build succeeded in **8m15.04s**, five executed build steps.
Measured `chrome.dll` SHA-256:
`3c9b71a91ccba24b97e151ed9d63a053b41eb61a0852aa13c6393f9237479c06`.
The EXE and `chrome_elf.dll` hashes remain the same as 001-038.

| Owned runtime check | Result | Boundary |
| --- | --- | --- |
| Combined baseline/profile/restart phases | Passed: 6/6 | Repeated on the linked 001-039 engine |
| Missing required document policy | **Failed: persistent-context launch timeout** | No earlier fatal transition in the saved log; denying initial about:blank prevents the driver's startup wait from completing |
| Revised combined gate v2 | **Passed: 7/7** | Same 001-039 core; controlled document execution plus denied-profile CDP observation independent of startup-page commit |
| Missing-policy browser-level CDP check v2 | Passed | Control: one request/one script execution; denied: one request/zero execution, exact Document request correlated to `ERR_ABORTED`, unchanged frame/loader/history and no commit event; browser remains responsive |
| General manager/runtime gate | **Passed: 18 named checks** | Persistent five-store isolation/restart, owner locks, crash/controller/teardown recovery, permissions, authenticated loopback HTTP proxy, scenarios, Recorder and Mobile Web Emulation |
| Worker checks and external detectors | Not rerun for this build | Do not transfer 001-038 results |

Private evidence: `combined-surfaces-001-039-v1.json` (failed persistent-driver
probe), `no-policy-cdp-v1/proof.json` (prototype), and
`combined-surfaces-001-039-v2.json` (revised full gate passed; cleanup passed).
This is not persistent-driver startup recovery or anti-bot admission. The reviewed
finish-observer lifetime guard and its eight native cases still require promotion
and execution before release.

General runtime evidence: `owned-runtime-suite-001-039-v1/runtime.json` and
`suite.json` on D, bound to the same measured three-file runtime core. This run
requested only `runtime` (`full_suite=false`), not all eight standard gates.
The proxy is an owned local fixture, not proof for the user's external proxies;
Mobile Web Emulation is not an Android/iOS runtime. It does not admit 0040/0041.

### Windows development candidate 001-038 — 2026-10-13

Chromium **148.0.7778.96**; j4 incremental build succeeded in **31m11s**.
Receipt includes all 38 exact patches. Windows browser behavior changed in
`chrome.dll`; an unchanged launcher EXE hash does not imply an unchanged engine.

| Core file | Measured SHA-256 |
| --- | --- |
| `chrome.exe` | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` |
| `chrome.dll` | `68e539371a0b0064f455ca7277b66be9cabbd408f79fcf656702e8c59b970211` |
| `chrome_elf.dll` | `3468b145cea9de7df386ad58c0daedba0d39c71bac58b0136486a36a2037b74d` |

| Owned runtime check | Result | Boundary |
| --- | --- | --- |
| Surface-policy worker startup | Passed: 40/40 | Classic/module dedicated, shared and service workers; ready, absent-policy and restart phases |
| Combined Canvas/OfflineAudio | Passed: 6 baseline/profile/restart phases | Two protected profiles plus baseline; document/frame/worker observations where APIs apply |
| Cross-profile isolation | Passed | The owned fixture's observations only; not general anti-bot acceptance |
| Missing required document policy | **Failed: browser crash** | Illegal `READY_TO_COMMIT` failure transition; full combined gate failed |
| External detector/CAPTCHA destinations | Not run for this build | Earlier build observations cannot be transferred |

Private evidence on D: `worker-surfaces-startup-001-038-v1.json` and
`combined-surfaces-001-038-v1.json`. Registered repair 0039 and the subsequent
observer-lifetime drafts are not validated by these results. This candidate is
**not release-admitted**; retain failed evidence and rerun after repairs.

### Windows development baseline 001–010 — 2026-10-12

Chromium **148.0.7778.96**; executable SHA-256:
`61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222`.
Headless automation, no JS API overrides; CLI automation masking suppressed.
One observational round, not the complete repeatable protocol above.

| Check | Direct | SOCKS5 route 1 | SOCKS5 route 2 | SOCKS5 route 3 | Limits |
| --- | --- | --- | --- | --- | --- |
| BrowserScan bot detection | Observed: Normal | Observed: Normal | Observed: Normal | Observed: Normal | Route 2 screenshot failed; DOM observation available |
| Fingerprint Playground | Observed: bot/tampering/devtools not detected | Same observation | Same observation | Same observation | Not a complete tracking/isolation test |
| Official reCAPTCHA v3 sample | Observed: backend success, score 0.9 | Not verified | Not verified | Not verified | Proxy backend responses absent within observation window; sample only |
| Real Turnstile / hCaptcha | Not verified | Not verified | Not verified | Not verified | No real-key authorized backend verification |
| Other destinations above | Not run | Not run | Not run | Not run | Pending expanded matrix |

Private evidence: `external-probes-strict-baseline-001-010/external-proxy-matrix.json`
in the external build workspace. Earlier framework-masked observations must not
be substituted for this strict round.

### Windows development candidate 001–015

Windows link completed on **2026-10-12**, build process exit code 0, jobs 4;
the build log records **1h51m49.40s** for this incremental compiler/linker run,
not the entire development history or a clean build. Receipt includes 15 patches.
The eight runtime gates, 33 named native-unit cases, external observation round
and eight-context Canvas baseline completed. Baseline
observations above must not be transferred to this candidate.

| Measured code | SHA-256 |
| --- | --- |
| `chrome.exe` | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` |
| `chrome.dll` | `2bf8b1504afec16c841b761432fd914e20fe358fc284bde4955b515774e4ad77` |
| `chrome_elf.dll` | `3468b145cea9de7df386ad58c0daedba0d39c71bac58b0136486a36a2037b74d` |

The launcher hash is unchanged from 001–010; the changed implementation is in
`chrome.dll`. An executable-only hash cannot distinguish these two builds.

An additional actual Chrome startup smoke with
`--camouflow-native-privacy-key-service=1` passed initial/restart phases:
persistent localStorage survived, two separate OTR contexts did not inherit it,
and the owned identity file remained unchanged. Private report:
`key-bootstrap-001-015/report.json`. This is limited startup/storage evidence,
**not** observation of key loading/readiness/derivation, OTR key separation or
fingerprint protection. The real context/readiness drafts still need execution.

| Candidate 001–015 runtime gate | Completed checks | Result |
| --- | --- | --- |
| Runtime/lifecycle/storage | 18 | Passed |
| Hardware | 9 | Passed |
| WebRTC | 7 | Passed |
| Automation | 55 | Passed |
| Windows fonts | 42 | Passed |
| Identity consistency | 18 | Passed |
| CDP Error-serialization scope | 6 | Passed |
| Combined policies | 5 | Passed |
| **Total** | **160** | **8 gates passed** |

Private report set: `verification-context-chrome-001-015-user-j4/runtime/`.
An independent recheck validated all child report hashes, gate coverage/counts
and the current three runtime code hashes. This is owned-fixture evidence, not
real CAPTCHA acceptance, prepared-draft coverage or production release admission.

The public `verify_native_privacy_units.py` also rebuilt/executed the native target
and passed all **33 exact required cases**, independently revalidated from its
GoogleTest JSON. Browser code remained unchanged. Private evidence:
`verification-context-chrome-001-015-user-j4/privacy-units.json` and
`privacy-units-tests.json`. This covers key primitives/loading/service ownership,
not the unapplied real-BrowserContext/readiness drafts or renderer IPC.

| External check, 001–015 headless observation round | Direct | SOCKS5 route 1 | SOCKS5 route 2 | SOCKS5 route 3 |
| --- | --- | --- | --- | --- |
| BrowserScan bot detection | Observed: Normal | Observed: Normal | Observed: Normal | Observed: Normal |
| Fingerprint Playground bot/tampering/devtools/incognito labels | Observed: Not detected | Observed: Not detected | Observed: Not detected | Observed: Not detected |
| Official reCAPTCHA v3 sample backend | Not verified: navigation failed | Observed: success, score 0.9 | Not verified: no response within 60 seconds | Not verified: no response within 60 seconds |
| BrowserScan screenshot artifact | Saved | Failed | Failed | Saved |
| Real Turnstile/hCaptcha verification | Not verified | Not verified | Not verified | Not verified |

Private report: `verification-context-chrome-001-015-user-j4/external/external-proxy-matrix.json`.
All four browser sessions were closed after observation. The CLI automation
masking flag was suppressed; native policy flags remained explicitly configured.
One round and the public sample score do not establish production CAPTCHA
reliability. Failed screenshots do not erase available DOM observations.

The candidate's separate Canvas run completed all four groups across eight
readback contexts and the original three security contexts. Code hashes match
the candidate table. Report: `verification-context-chrome-001-015-user-j4/canvas.json`.
This remains a compatibility baseline, not an implemented Canvas privacy policy.

### Local Canvas calibration — baseline 001–010, 2026-10-12

An additional run of `scripts/verify_native_canvas.py` against the preserved
001–010 executable above completed all four checks. This tests **unmodified
Canvas consistency**, not fingerprint masking or anti-bot acceptance.

| Check | Observed scope | Result |
| --- | --- | --- |
| Initial readback | Document, same/cross-origin iframe, dedicated/shared/service workers; repeated reads, PNG export and crop geometry | Passed |
| Initial security/empty images | Document and same/cross-origin iframe; expected security exceptions and empty-image behavior | Passed |
| Persistent-profile restart | Same six contexts and readback observations compared with initial run | Passed |
| Restart security/empty images | Same three document/frame contexts | Passed |

Private report: `canvas-calibration-001-010-round2.json` in the external build
workspace. Executable hash and browser version match the baseline header.
This is not a same-version stock Chrome comparison, an AudioWorklet/srcdoc
check, a transformed-Canvas acceptance gate or evidence for candidate 001–015.

### Code-bound Canvas control comparison — 2026-10-12

A subsequent run used the strengthened verifier measuring `chrome.exe`,
`chrome.dll` and `chrome_elf.dll` before/after capture. Both the preserved
001–010 runtime and unpatched Playwright SDK Chromium reported version
**148.0.7778.96**; each completed the four Canvas checks above successfully.
Their captured Canvas/security observations were equal, as expected for this
unmodified-Canvas baseline. This does **not** demonstrate profile unlinkability.

| Runtime | Executable SHA-256 | Private report |
| --- | --- | --- |
| Glint 001–010 baseline | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` | `canvas-core-calibration-001-010.json` |
| Unpatched SDK control | `290fa7018fda22c52ada5eddb0113baf3ebc41fd0fde6085eddb19793606c635` | `canvas-stock-calibration-20261012.json` |

Reports retain all three measured code hashes. The control is SDK Chromium,
not a branded consumer Chrome installation or a commercial-engine benchmark.
Coverage remains limited to the tested Canvas paths and contexts; it does not
validate other surfaces or certify the new 001–015 build.

### Eight-context calibration and combined-policy run — 2026-10-12

The probes now include `about:blank` and `srcdoc` frames in addition to the
previous six readback contexts. Security/WebRTC frame observations are resolved
by owned frame IDs rather than relying on frame enumeration order.

| Run | Coverage | Result | Private report |
| --- | --- | --- | --- |
| Unpatched SDK Chromium 148.0.7778.96 | Four Canvas baseline groups; eight readback contexts; original three security contexts | Passed | `canvas-stock-eight-contexts.json` |
| Glint 001–015, all existing policy arguments combined | STUN positive control plus two profiles before/after restart; eight readback/identity contexts per profile phase | Five named checks passed | `combined-eight-contexts-001-015.json` |

The Glint run's code hashes match the linked candidate above. Native Canvas
protection is still absent. This does not test AudioWorklet, prove renderer
process separation for the cross-origin frame, or validate future key IPC.
The original 160-check suite was captured before this extension; these are
additional results, not retroactively expanded coverage of older reports.

### Source-only readiness progression, chain 001–016

Patch 0016 was registered/applied after the 001–015 verification pipeline ended.
Its first native compilation rejected capturing lambdas in `BindOnce`; test
callbacks were corrected to the upstream `BindLambdaForTesting` helper.
The retry completed all **43 exact native cases**, including ten readiness cases,
with browser code/receipt unchanged. Private report:
`privacy-readiness-001-016-bindings-fixed.json`. The linked browser remains
001–015; these service tests do not establish readiness bridge runtime, renderer
IPC or Canvas protection. Real-context tests were subsequently promoted to
registered/applied patch 0017; their execution remains pending.

The production readiness bridge translation unit also compiled successfully
without changing the linked browser or receipt; private object proof:
`readiness-bridge-object-001-016.json`. Object compilation is not browser linkage
or execution of the real-context tests.

### Source-only real-context progression, chain 001–017

The public native verifier now supports a separate `--target contexts` mode,
building `content_unittests` and requiring exactly 20 named
`NativePrivacyBrowserContextTest` cases. Key/service mode still requires its
original 43 cases; neither mode accepts the other mode's results as coverage.
Patch 0017 is registered/applied and the target is building. No passing context
execution or newly linked 001–017 browser is claimed. The preserved 001–015
runtime remains the last linked/verified browser.

The first context-target build stopped at 380/2361 with LLVM `out of memory`
and Windows error `0x5AF` (insufficient paging file). No context cases executed.
Its log is retained as `privacy-contexts-001-017-build.log`; the interrupted
verifier did not produce a terminal JSON proof. An incremental retry uses one
job and a new evidence path `privacy-contexts-001-017-retry-j1.json`, preserving
completed objects, GN arguments and source inputs. Retry success remains pending;
do not interpret the original four-job invocation as a passing result.

### Linked worker-startup builds, 001-026 and 001-027 (2026-10-12)

Both Windows builds pinned Chromium 148.0.7778.96. The 001-026 build completed
in 29m17.54s; the incremental 001-027 shared-worker rejection fix completed in
15m28.62s, each with four jobs. No external result from 001-015 is carried forward.

| Build | Measured chrome.dll SHA-256 | Local evidence |
| --- | --- | --- |
| 001-026 | `a055fecb73db29c0ababa0cb3da2f4d7d3942253d82453ce6b58e24f938927e2` | Eight runtime gates / 160 checks passed; full worker gate failed on unavailable shared-worker timeout |
| 001-027 | `ec1e8ad8a87bea6e448d0c5f117a561c7f1bf3b6a9db330626dc4e538124d350` | All eight normal runtime gates / 160 checks, 40 worker startup/restart/shared-client/rejection checks and four unprotected Canvas baseline phases passed |

Both executable stub hashes remain
`61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222`;
matching only chrome.exe would incorrectly identify these builds as the same code.
Private evidence: `worker-startup-runtime-001-026-build.json`,
`runtime-001-026-regression-suite/suite.json`,
`worker-startup-001-026-runtime-partition-fixed-v3.json`,
`worker-startup-001-026-runtime-service-first.json`,
`shared-worker-bootstrap-failure-001-027-build.json` and
`worker-startup-001-027-runtime-40-first.json`.
The exact worker check set, receipt checksum and core hashes were revalidated.
These controlled runs use explicitly enabled partitioning and diagnostic
`--enable-automation`; they are not external anti-bot score observations.

| Core destination | 001-026 | 001-027 |
| --- | --- | --- |
| CreepJS | Not run | Not run |
| Pixelscan | Not run | Not run |
| BrowserScan | Not run | Not run |
| Sannysoft | Not run | Not run |
| BrowserLeaks fingerprint surfaces | Not run | Not run |
| IPhey | Not run | Not run |
| Fingerprint Playground | Not run | Not run |
| Rebrowser Bot Detector | Not run | Not run |
| Incolumitas | Not run | Not run |
| Device and Browser Info | Not run | Not run |
| TLS Peet | Not run | Not run |
| IPify browser egress | Not run externally; owned proxy fixture passed | Not run externally; owned proxy fixture passed |
| BrowserLeaks WebRTC | Not run externally; owned WebRTC fixture passed | Not run externally; owned WebRTC fixture passed |
| Google reCAPTCHA v3 | Not run | Not run |
| Cloudflare Turnstile | Not run | Not run |

The four-case Blink worker-seed handoff gate subsequently passed with test-only
fixture correction 0028, as recorded below. Document
first-script bootstrap, protected Canvas/WebGL/WebGPU/audio and privacy
admission remain incomplete. Neither build is a new verified production release.

### Blink worker-handoff test target, 001-027 / fixture correction 0028

The 001-027 `blink_unittests` build succeeded in **2h24m55.18s**, jobs 4.
This builds a test executable, not a newly verified browser release.

| Case | First execution |
| --- | --- |
| Seed arrives before evaluation | Passed |
| Seed absent without bootstrap | Passed |
| Sequential scopes do not reuse seed | Aborted during fixture destruction |
| Immediate termination retains owned seed | Not executed after process abort |

The sequential fixture created a never-started worker after its last iteration;
the upstream destructor correctly rejected its `kNotTerminated` exit state.
Patch 0028 moves recreation to the next iteration, preserving seed comparisons,
shutdown waits, mock expectations and the destructor DCHECK. It changes only the
test fixture; the last verified browser remains 001-027. The failed report is
retained as `worker-handoff-001-027-j4.json` in the private build workspace.
The full four-case incremental retry **passed** under the new
`worker-handoff-001-028-fixture-lifetime-j4.json` evidence path. All four exact
cases completed, with no skipped cases. Incremental build: **12m19.98s**, two
steps; test execution: 149 ms. Test executable SHA-256:
`c12081c58b2370f43f4f2e7ce27f9465f58205c45c298c1e71c442bb2ea273af`.
The exact case set, test executable checksum and unchanged browser core,
receipt and GN arguments were independently verified. This is fixture-level
seed ownership/timing evidence, not real browser-partition derivation,
Canvas protection, external anti-bot acceptance or a new browser release.

### Registered document partition validator, source patch 0029

The exact nine `GlintDocumentCanvasPolicyTest` cases passed via the public
`verify_native_privacy_units.py --target document-partition` command.
Build: **1m22.26s**, two incremental steps; no new browser release.
The exact completed case set, actual unit executable checksum and unchanged
browser core/receipt/GN hashes were independently rechecked.
Private evidence: `document-partition-001-029-registered-j4.json`.
The original **43 key/service cases also passed** through the same registered
native unit target, separately: `privacy-keys-001-029-regression-j4.json`.

This covers partition equality/rejection and owned seed return, including
opaque identity, retained partition fields, nonce and binary commitment data.
It does not prove pre-teardown cancellation, actual first-script delivery or
Canvas protection. Those document runtime gates remain incomplete.

## Frozen desktop integration gate - October 18, 2026

The Windows PyInstaller manager package passed all three engine checks from
the actual frozen executable, not source Python. Evidence on D:
`desktop-validation-001-062-v1/reports/20261018-140938/`.

| Engine | Fixed browser/Python imports | Hard-loop timeout | Admitted Glint health |
| --- | --- | --- | --- |
| Camoufox | PASS | PASS (3 seconds) | Not applicable |
| CloakBrowser | PASS | PASS (3 seconds) | Not applicable |
| Glint 001-062 | PASS | PASS (3 seconds) | PASS, six reviewed capabilities |

Glint used the reviewed installed archive digest `84e8d2369be630825afbff2732b09d5d81bb699e3c60025b73756c3fc305c10a`.
The frozen health and worker paths confirmed the requested policy; the worker
also checked the CPU ceiling, webdriver value and absence of HeadlessChrome
in UA. No owned frozen/browser processes remained after the gate. The clean
manager build took about **88 seconds**; its pre-build regression passed
**2580 tests in 107.26 seconds**. The completed release-tool regression including
additional path/health rejection cases passed **612 tests** separately.
Private build log: `desktop-validation-001-062-v1/release.log`.
This is local Windows development-package evidence, not website publication,
signed updates, external CAPTCHA acceptance or Linux/macOS runtime evidence.

## Admitted-policy crash recovery - October 18, 2026

`verify_native_admitted_policy.py` now reuses the existing multi-profile crash
gate with the reviewed policy, rather than testing recovery only with native
defaults. Actual proof: `admitted-policy-recovery-001-062-v1/report.json` on D.

| Check | Result |
| --- | --- |
| Three concurrent profiles / independent drivers | PASS in all three rounds |
| One real browser crash per round, rotating victim | PASS; unaffected profiles kept their own data |
| Cookies, LocalStorage, IndexedDB, Cache, Service Worker | PASS after crash/restart and across rounds |
| Six admitted controls after crash recovery | PASS; actual diagnostics had zero mismatches |
| Owned process cleanup | 52 / 52 / 54 observed process identities; zero left per round |
| Full package and verifier inputs unchanged | PASS |

The existing concurrent rendering/restart phases and final manager health gate
also passed in the same run. A graceful checkpoint precedes each deliberate
crash: this proves recovery of checkpointed state, not durability of the most
recent unflushed write or recovery from power loss. No customer profiles or
unrelated browser processes were terminated. Existing default-policy coverage
remains unchanged; Linux/macOS and external anti-bot acceptance are not claimed.

## Sources and maintenance

### Upstream metadata audit - October 18, 2026

`upstream-audit-20261018-v1.json` on D records the official Windows Stable
metadata snapshot and unchanged build-lock checksum. Pinned Glint base:
**148.0.7778.96**, revision `8625e066febc721e015ea99842da12901eb7ed73`.
Highest observed Stable version in that response: **156.0.8078.36**, revision
`5a93aa59e3043e747eff68659dcf7d20193d160e`, published October 14.
Other rollout versions are retained in the report; this is not an assertion
that every user receives the highest listed version. Result: **behind-stable**,
exit 1, production admission false. Sources/binaries were not changed.
An upstream rebase and fresh build/runtime/security review are required before
publishing Glint as a production engine. This metadata comparison does not
enumerate CVEs, prove exploitability or replace a security review.

A separate, bounded source-context assessment fetched only the files needed
for patches 0001-0006 at that exact 156 revision into an owned D: directory.
`upstream-156-compatibility-v1/report.json` records source URLs/file hashes,
patch hashes, failures and whether preceding patches failed. Hardware build
registration/DEPS, MIDL, automation feature registration and Windows font
service contexts need adaptation. WebRTC and headless-UA patches passed
`git apply --check` and were applied only in that assessment directory.
This is **not** a successfully rebased six-patch stack, compile/API validation
or runtime proof: four earlier context checks failed and dependencies were
not fetched. The active 148 checkout, build lock and binaries remain unchanged.

The subsequent [six-patch draft port](../native/drafts/upstream-156/README.md)
now passes sequential source-context replay on the exact 156 inputs:
`upstream-156-replay-v2/report.json`, **6/6**, inputs unchanged. The port preserves
upstream font-service cache/local-matcher initialization and covers the new
DirectWrite unique-name path using the restricted collection's font set.
Standalone Windows C++ controls verified real collection-to-font-set conversion,
an allowed Arial match and an excluded Segoe UI match with unrestricted positive
controls. No 156 Chromium translation unit or browser was compiled; patches
0007-0062 and actual dependency/API/runtime compatibility remain unverified.
The full application regression after this draft/verifier and standalone
font-set coverage passed **2610 tests in 118.92 seconds**. Source/patch checksum
rejection, failed application and changed/deleted-input postguards are covered;
successful draft replay never sets compilation/runtime/production flags.

The next draft batch extends the exact-source replay through **0010: 10/10**,
`upstream-156-replay-v4/report.json`. Chromium DEPS pins V8
`8ce248ef8f7f71c04f7faaac249a37d340279f52`; the verifier rejects a different
dependency revision and applies the Inspector patch in that separate repository.
The port retains upstream `isBuiltinGetter` protections while adding the
existing bounded descriptor walk/no-JavaScript Error handling. LevelDB, SQL
and profile-namespace patches pass source-context replay unchanged. Application
now explicitly disables autocrlf and rejects BOM/CRLF patches; an initial V8
draft's line-ending churn was removed before publication. This remains a
source-context result, not compiled V8/SQL tests or a Chromium 156 runtime.

The key/context batch extends replay through **0017: 17/17**,
`upstream-156-replay-v5/report.json`, bound to 35 upstream input files.
Key derivation, owned-file loading, service lifetime, BrowserContext ownership,
readiness and test registration are retained; the derivation target's BUILD.gn
insertion was adapted to the new upstream layout. Four resulting BUILD.gn files
parsed with the installed GN tool without changing bytes
(`upstream-156-gn-syntax-v1.json`). Regression checks bind the draft hashes to
their originals and retain all new key/context implementation/test-file bodies.
These are source/syntax checks only: no new GN graph, compiled key/context tests
or Chromium 156 profile-isolation runtime result is claimed.

Document/worker delivery drafts extend replay through **0030: 30/30**,
`upstream-156-replay-v6/report.json`, bound to 80 upstream source inputs.
The port preserves the new dedicated-worker PolicyContainer in immediate and
deferred startup, current shared-worker string APIs, upstream test-scope
creation/mock signatures and both navigation-throttle registration paths.
The UI-thread CHECK remains before service-worker binder registration.
Eight resulting GN/GNI files passed read-only syntax parsing with the installed
tool (`upstream-156-gn-syntax-v2.json`). These checks do not prove generated Mojo
bindings, a valid target dependency graph, startup ordering or runtime policy
delivery on 156. All those gates remain required after the complete port/build.
The full application regression with this batch passed **2623 tests in
109.48 seconds**; these Python tests do not execute the 156 C++ runtime.

Surface/readback/navigation drafts extend replay through **0045: 45/45**,
`upstream-156-replay-v7/report.json`, bound to 109 upstream inputs. The port
retains InitiatorStateToken in the custom child-frame Mojo call, renderer
branches, browser delegation and fixtures; new worker mock/factory APIs and
the upstream OfflineAudio resolver cleanup remain intact. 13 GN/GNI files
passed read-only syntax parsing (`upstream-156-gn-syntax-v3.json`). GPU candidate
features remain disabled by default. These are research/source checks only;
known readback fidelity/HDR limitations are not repaired or admitted by rebasing.
Chromium 156 compilation, generated bindings and actual lifecycle/readback
behavior remain unverified.
The full local Python regression with this batch passed **2624 tests in
101.80 seconds**. This does not execute Chromium 156 or admit research policies.

The complete draft chain now replays **0062: 62/62** against 165 upstream
inputs, including original branding binaries (`upstream-156-replay-v8/report.json`).
Missing downloads after an HTTP 429 were recovered only from the owned Git
baseline and verified against the previously recorded source hashes. The
source audit preserves all 321 original GLES2 command IDs and appends the private
command as **577**, not the old 148 value 580; GRIT XML structure and attributes
remain unchanged (`upstream-156-abi-resources-v1.json`). 15 GN/GNI files passed
read-only parser checks (`upstream-156-gn-syntax-v4.json`). Identity fixtures use
the current worker API, branding changes retain current upstream message content.
No GPU code generation, target compilation, resource build or runtime claim is
made. Default build selection and reviewed manager admission still target 148;
candidate build tooling and complete 156 build/gates are the next requirements.

The complete local Python regression for this draft batch passed **2625 tests
in 128.98 seconds**; the release-tool subset passed **652 tests in 22.88
seconds**. These are tooling/manager tests, not Chromium 156 runtime evidence.

The replay verifier now enforces GPU append-only command ordinals and preserved
GRIT structure/attributes itself. `upstream-156-replay-v9/report.json` passed
all 62 patches and both invariants; altered ordinals, names, duplicate IDs,
extra commands, changed resource IDs/structure and malformed XML are rejected
by negative tests. This remains source-only evidence, with no compiler started.

`upstream-156-replay-v10/report.json` adds actual GPU source regeneration:
**30/30 generated files are byte-identical**, all 62 patches apply and source
invariants/input guards pass. The public manifest now pins 185 upstream inputs,
including the exact target generator library/style and all generated files.
The supplied existing clang-format 21 executable is hash-bound before/after;
it is **not verified as the target's pinned formatter**. Negative tests cover
modified/removed/unexpected generated outputs, generator errors and formatter
mutation. This does not compile C++, build GRIT or establish runtime readiness.
The complete local Python regression with this gate passed **2643 tests in
124.01 seconds**.

Candidate build selection is now explicit via `native_build.py --candidate
upstream-156`: separate empty-workspace claim, exact Chromium/V8 revisions,
complete patch-chain checks, post-build guards and manifest-bound stage/receipt
identity. Tests reject mixed default/candidate workspaces, wrong revisions,
partial patch chains, changed pins and reduced resource limits. Compiler dispatch
and receipts are covered with mocks, not a real 156 build. The only real candidate
command executed was read-only preflight: 300.6 GiB free on D:, no workspace
created. Default 148 pins, manager admission and production remain unchanged.
The manifest including these build pins was replayed again in
`upstream-156-replay-v11/report.json`: 62/62 patches, 30 unchanged GPU-generated
files and source/input invariants passed. Formatter target provenance remains
unverified; `compiled`, `runtime_verified` and `production_admitted` stay false.
The full local Python regression passed **2660 tests in 132.70 seconds**;
the final targeted build/preflight/candidate subset passed **88 tests**.

The explicit candidate `patch` action now prepares the entire Chromium/V8 batch
in temporary indexes before source changes, preserves real indexes and records
private deltas/results. Failure reverses only exact owned states; concurrent
edits block rollback rather than being overwritten. Real tiny Git fixtures cover
binary/new files, invalid second-repository preparation, second apply failure,
rollback, repeat invocation and preservation of unrelated edits. No full 156
checkout mutation, compiler invocation or runtime result is claimed by these
fixtures; the reviewed 148 checkout and build lock remain unchanged.
The full local Python regression passed **2666 tests in 180.33 seconds**.
The final focused patch-action/real-Git subset passed **6 tests in 13.85
seconds**, including raw binary deltas without text-conversion/color filters.

Mutating build-tool stages now hold an OS-backed workspace lock. Windows tests
cover same-process/cross-process contention, release after an exception or owner
termination, and refusal before tool/source mutation; read-only preflight still
works while locked. This is coordination between script invocations, not proof
that manual tools/orphaned compiler children are stopped, and not Linux/macOS
runtime evidence. No Glint build was started by these tests.
The complete local Python regression passed **2669 tests in 160.20 seconds**.
The targeted lock/build/candidate subset passed **96 tests**. Ruff found no
diagnostics in the new lock functions/tests; its two complete files still have
the same **67 pre-existing diagnostics** as the committed baseline, not a clean
project-wide lint result.

### WebGPU texture compatibility expansion — existing 001–062 Windows package

`verify_native_gpu.py` now writes distinct rgba8unorm data to three mip levels
and two array layers, then reads every subresource twice into padded buffers.
The validator checks exact texels, layer/mip selection, repeated reads and all
untouched prefix/row/suffix sentinel bytes. Missing/duplicate cases, malformed
metadata, altered pixels/padding and boolean/float byte substitutions fail.

Real private report: `D:\CamouFlowNative\gpu-textures-001-062-v1\report.json`.

| Phase | WebGL1 / WebGL2 / WebGPU contexts | Texture cases | Result |
| --- | --- | --- | --- |
| Feature off | 8 / 8 / 8 | 48 | Passed |
| Feature off, restart | 8 / 8 / 8 | 48 | Passed |
| Metadata minimization on | 8 / 8 / 8 | 48 | Passed |
| Metadata minimization on, restart | 8 / 8 / 8 | 48 | Passed |

**192 texture cases**, each read twice, ran on the unchanged measured
Chromium **148.0.7778.96** 001–062 core. Input/core postguards passed; no user
profile, manager setting or production package was changed. The test uses only
owned loopback fixtures. This does not cover texture sampling/filtering, mipmap
generation, every format/GPU/OS, WebGPU fingerprint protection, CAPTCHA or the
uncompiled 156 candidate. GPU metadata minimization remains a research feature,
not a newly admitted manager capability.
The complete local Python regression passed **2688 tests in 131.22 seconds**;
the GPU verifier itself passes Ruff. Its tests file retains four existing
import-order diagnostics outside the new cases, not a clean full-file lint run.

### WebGPU fragment-shader texture reads — existing 001–062 Windows package

The texture probe now also binds the real array texture, selects its mip/layer
through a uniform, reads texels with WGSL `textureLoad`, renders a full-screen
triangle to a separate rgba8unorm attachment and reads that attachment back.
Rendered pixels and untouched packed-buffer padding must match the independent
known pattern, not merely the earlier direct-copy output. Missing shader results
and corrupted shader pixels/layer/mip/padding are rejected by negative tests.

Real private report:
`D:\CamouFlowNative\gpu-shader-textures-001-062-v1\report.json`.

| Phase | WebGPU contexts | Shader-render subresources | Result |
| --- | --- | --- | --- |
| Feature off | 8 | 48 | Passed |
| Feature off, restart | 8 | 48 | Passed |
| Metadata minimization on | 8 | 48 | Passed |
| Metadata minimization on, restart | 8 | 48 | Passed |

**192 shader-render cases**, alongside the two direct reads per subresource,
passed on the unchanged measured **148.0.7778.96** core. The existing WebGL and
WebGPU buffer/compute gates also passed in all contexts; source/core postguards
passed. `textureLoad` does not test filtered sampling, sampler behavior or mipmap
generation. This is not WebGPU fingerprint protection, a capability admission,
a 156 runtime result, or a new compiled browser. No compiler was launched.
The full local Python regression passed **2694 tests in 127.32 seconds**.
The GPU verifier itself passed Ruff; current probe hashes match the saved
runtime evidence. The final missing/duplicate/malformed coverage subset passed
all **9 negative-control cases**.

### Upstream calibration and failed-report integrity

The same GPU probe passed on the installed unpatched Playwright Chromium
**148.0.7778.96**: two baseline/restart phases, eight WebGL1/WebGL2/WebGPU
contexts each and **96 shader texture cases**. Requesting Glint metadata
minimization on that unpatched binary was correctly rejected after both good
baseline phases: `Translated shader metadata still exposed: document/webgl`.
This is an expected negative control, not a failed ordinary-browser operation.

Failed GPU probes now run runtime-core and source-input postguards too; previously
an exception skipped those checks. Reports explicitly record both unchanged flags,
and changed/deleted inputs invalidate the evidence even if the original error
looks like the expected policy rejection. Ten Python cases cover success/failure
with changed/deleted runtime and probe inputs.

| Private report | Actual result |
| --- | --- |
| `gpu-upstream-guarded-v2/positive.json` | Unpatched baseline passed; both postguards true |
| `gpu-upstream-guarded-v2/negative.json` | Expected policy rejection; both postguards true |
| `gpu-shader-guarded-001-062-v2/report.json` | Glint 148: all four phases passed; both postguards true |

Reports live on D: under `CamouFlowNative`. Desktop CI now includes upstream
GPU calibration/negative control and archives their JSON. An unavailable runner
WebGPU API remains zero coverage, not a WebGPU PASS; no alternate backend or unsafe
flag is enabled. CI also checks undefined names/syntax in `scripts/` as well as
`app/`. These checks do not compile/admit Chromium 156 or publish a new runtime.
The full local Python regression passed **2704 tests in 127.93 seconds**;
selected undefined-name/syntax checks passed and all eight workflow Python
blocks parsed. The updated workflow still requires a fresh completed CI run;
local calibration is not a claim that the full remote pipeline is green.

## Reference sources

- [GitHub detector directory](https://github.com/TheGP/untidetect-tools): discovery only, not proof of Glint results.
- [Rebrowser detector source](https://github.com/rebrowser/rebrowser-bot-detector): automation checks and their prerequisites.
- [Google sample source](https://github.com/google/recaptcha/tree/master/examples): client and backend verification examples.
- [Cloudflare Turnstile demo source](https://github.com/cloudflare/turnstile-demo-workers): inspect current keys and backend behavior.
- [Cloudflare dummy-key rules](https://developers.cloudflare.com/turnstile/troubleshooting/testing/): fixture outcomes are not real challenge acceptance.

For every linked build, add a new build-history section with all Core checks,
including unavailable/not-run entries. Extended checks are required before a
release claim. This document is maintained alongside saved evidence; it is not
an automatic certification or an unattended scheduler.
