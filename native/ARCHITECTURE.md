# Glint architecture

## Unselected trusted native copy / write notifications

The [observer packet](drafts/webgpu-native-copy-hook/README.md) prepares a one-time
D3D12 embedder registration, a native full-snapshot ticket before ROI recording,
and post-recording delivery. Buffer-copy, literal writes, clears, uncertain mapped
writes and destruction supply adjacent provenance events. Snapshot/quota core bytes
are unchanged from the hardware-tested budget implementation. Nine translation
units passed syntax checks; the 16-file replacement packet round-tripped exactly.
No GPU-service observer is registered, map serialization is unprotected and shader
taint is not implemented. These notifications are not runtime privacy protection.

## Unselected device-owned capture quota

The [capture quota follow-up](drafts/webgpu-d3d12-capture/README.md) reserves actual
D3D12 allocation bytes and couples quota ownership to an `IUnknown` retirement
handle. Isolated hardware normal/ASan runs passed 22,720 assertions each, including
eight-way contention, CPU cancellation and lifetime across real GPU completion.
Four native translation units passed syntax checks. The nine-file Dawn packet
prepares one 64 MiB quota per D3D12 Device and uses its existing COM retirement
queue. Actual Dawn retirement, failed submission/device loss and process-global
budgeting remain unverified. This does not install the copy/map hook.

## Unselected WebGPU device/export seed coherence

The [export-seed packet](drafts/webgpu-export-seed/README.md) distinguishes Canvas,
WebGL and WebGPU and shares the disabled device-policy feature with export code.
Four translation units passed syntax checks. All three prerequisite/follow-up
packets were composed through patch replay, including overlapping GN edits; the
37-path result passed static/component GN and GPU-common, Blink core/modules and
GPU-service header checks. Sources and prior outputs were restored/unchanged.
Native linking, copy/map hooks and actual pixel coherence remain unverified.

## Unselected shared Canvas / GPU implementation

The [shared-core packet](drafts/shared-readback-core/README.md) moves unchanged
Canvas math into GPU common, removing the Blink implementation and avoiding a
GPU-to-Blink dependency. Five translation units passed pinned syntax checks;
five CPU suites passed normally and under ASan. The packet also retains uncertain
pixel-write provenance conservatively. Chromium linkage, native hooks, shader taint and
browser protection remain unverified; the selected chain is still 001-076.

The isolated shared-core DLL and five external consumers also passed normally and
under ASan. This checks the exported/imported API with the MSVC standard library,
not Chromium's GN/libc++ component ABI. Candidate source verification now replays
the complete chain in a private index and compares net paths and final bytes,
including files added then removed; live source/index contents remain untouched.

## Unselected D3D12 full-surface producer

The [hardware capture draft](drafts/webgpu-d3d12-capture/README.md) passed eight
actual GPU cases and **22,525 assertions** in each of normal/ASan runs: typed and
typeless RGBA/BGRA, padded rows, immutable successive snapshots, submit/fence
gates and resource retention during CPU cancellation. Three Dawn translation units
passed syntax checks. The seven-file Dawn patch is unselected; automatic native
copy interception, snapshot-store integration, GPU-budget retirement and actual
Dawn/browser submission remain unverified. No pixels are protected by this draft.

## Unselected private WebGPU transport

The [private policy transport draft](drafts/webgpu-private-policy/README.md) adds
an owned/cleansed packet, an internal command carrying no seed bytes, a dedicated
client allocation and an immutable per-device GPU receiver. Four translation units
passed syntax checks; codec checks passed 152 assertions normally and under ASan.
This is not browser integration, pixel protection or resolution of the measured
Canvas/WebGPU mismatch. The preceding full Python baseline passed **4967 tests,
1 skipped** at `1255aa7`, before this transport draft.

The coupled follow-up captures an owned policy before asynchronous device creation
and attaches it before exposing the device, behind a local disabled feature.
Six translation units passed syntax checks; five decoder rejection tests are
prepared but not executed. No browser/worker delivery claim is made. The previous
transport baseline at `18e094b` passed **4970 Python tests, 1 skipped** with guards.

## Measured Windows 001–076 screenshot transactions

All **506 native cases / 24 groups** passed, including twelve real-session
screenshot transaction units, with source/build postguards. The independently
preserved runtime passed six unchanged capture controls (including Playwright and
cross-session clip/no-clip), PNG/DPR bounds and actual six-document BFCache.
Twelve additional stress phases passed concurrent targets, same-value/permanent
updates, owner/capturer detach, full-page restoration, navigation and invalid
requests. Cancellations were observed; their exact race schedule is not guaranteed.

The integrated opt-in `retained-gpu-objects` CLI passed desktop/Mobile Web with
original WebGL1/2 resources in six BFCache documents. The exact public CLI default
and worker/service modes also passed again. This does not admit worker GPU-object
retention, WebGPU, complete profile isolation or privacy/release capabilities.
[Public GPU evidence](drafts/environment/retained-gpu-objects76-observations.json).
The integration baseline at `10230bd` passed **4854 Python tests, 1 skipped**,
with source/status guards. [Full result](drafts/environment/canonical-python76-retained-gpu-observations.json).
[Measured evidence](drafts/environment/screen76-runtime-observations.json).
Worker GPU retention is now opt-in via `--verify-retained-gpu-workers`. The public
CLI passed six classic/module classes in desktop/Mobile Web. The additional
`--verify-retained-gpu-service-restart` passed four exact-version stops/restarts:
new service/GPU globals, stable reads and intact document GPU resources/screens.
Dedicated/shared retain original objects; service lifetime is not guaranteed.
Default, document-only and legacy worker/service modes also passed again.
[Worker GPU evidence](drafts/environment/retained-gpu-workers76-observations.json).
The worker integration at `a05fbc6` passed **4886 Python tests, 1 skipped**, with
source/status guards. [Full result](drafts/environment/canonical-python76-gpu-workers-observations.json).

WebGPU compatibility now has **14 measured cases**: baseline/protected document
and classic/module dedicated, shared and service workers. Integer compute,
RGBA8 texture copies, padded rows, mapping detachment and invalid API operations
passed using the default adapter without unsafe flags or a fallback adapter.
[Measured probe source and evidence](drafts/environment/webgpu-readback76-observations.json).
The original standalone prototype is retained as history. The exact public CLI
also passed all fourteen cases, with effective argument checks, zero remaining
owned processes, released runtime resources and no service registrations left.
[Public CLI evidence](drafts/environment/webgpu-readback76-public-cli-observations.json).
This does not verify retained WebGPU resources, native WebGPU readback protection
or release admission.

The `--probe retained-webgpu-objects` mode now verifies original resources across
six genuine BFCache documents in desktop/Mobile Web. With the existing worker
and service-restart flags it also passed all six worker classes and four exact
owned service restarts. Dedicated/shared resources persist; restarted service
workers get new device/resource instances. The shared worker validator keeps
the WebGL default API, whose real forced-restart repeat also passed.
[Public resource lifecycle evidence](drafts/environment/retained-webgpu76-observations.json).
Full Python at `26082fe`, before this resource packet: **4925 passed, 1 skipped**.
[Full result](drafts/environment/canonical-python76-webgpu-cli-observations.json).

A controlled WebGPU canvas draw exposed an open inconsistency: direct GPU copies
match the exact reference, but protected PNG export differs in 403 channels by
one unit; baseline differs in zero channels. PNG repeats are stable. Existing
Canvas export protection must not be mistaken for coherent WebGPU protection.
[Retained mismatch and probe source](drafts/environment/webgpu-canvas-export76-observations.json).

Next: fix the native WebGPU pixel-readback/export path with explicit provenance.
An unselected C++ layout foundation is now [public](drafts/webgpu-readback-layout/README.md):
detached RGBA8/BGRA8 transfer, checked mappings and unchanged padding/source bytes.
Its exact sources passed 1024 deterministic variations and boundary cases in
isolated normal and AddressSanitizer builds. There is no Dawn/Chromium hook or
pixel transform in that initial layout-only revision; the canvas mismatch remains open.
[Foundation evidence](drafts/environment/webgpu-readback-layout-preparation.json).
The current unselected component package adds an executed-write provenance model
and bounded full-surface snapshot/shadow cache. Buffer copies retain source ROI
coordinates; writes remove affected provenance. The cache uses the existing native
Canvas transform, checks original bytes and rejects stale/missing captures or
ambiguous plans. Its exact public checker passed all three components normally and
under AddressSanitizer: 18 provenance cases + 256 oracle variations, and 26 snapshot
cases + 64 crop/partial-read variations. [Current evidence](drafts/environment/webgpu-readback-provenance-preparation.json).
No trusted GPU execution/capture hook, context transport or mapped-JS lifetime
integration is installed. These component checks do not resolve the runtime mismatch.
Pending capture issuance and completion are now separate. Tickets and memory are
reserved in native execution order; completions may arrive in any order. The
isolated normal/ASan checks passed ten lifecycle cases and all six completion
orders of three captures, retaining the earlier component checks.
[Pending model evidence](drafts/environment/webgpu-capture-lifecycle-observations.json).
The preserved 076 browser independently passed reverse-order reads of two texture
copies, unmap detachment, cancellation and device-loss AbortError behavior in both
probe modes. A prior OperationError expectation was a harness error, not a browser
failure. [API reference](drafts/environment/webgpu-map-lifecycle76-observations.json).
This reference does not prove the new native components are installed.

Integration constraints: use existing wire device ID/generation lookup and an
opaque, non-logging private policy transfer, not secret-bearing printed device
descriptors. Capture only after native command validation/execution. Shadow work
must complete before Dawn's mapped-completion notification, preserving the
[WebGPU promise-ordering rules](https://www.w3.org/TR/webgpu/#promise-ordering).
Full lifecycle Python at `8e46cb2`: **4956 passed, 1 skipped**, source/status guards
passed, before this unselected foundation publication.
[Full result](drafts/environment/canonical-python76-webgpu-lifecycle-observations.json).
Do not apply pixel noise to arbitrary mapped buffers: compute/storage results,
mapping errors, offsets and padding must remain exact. Device cohorts and the
remaining combined/release gates stay open.

## Historical source selection 001–076

The five-file screenshot transaction draft is now registered as
`0076-native-screenshot-transactions.patch`, preserving the exact 001–075 prefix
and all non-patch settings. A separate required native group adds twelve cases;
the previous 494 cases remain required (24 groups / 506 cases total).
The cached rebuild controller admits only the five named DevTools files, not
neighboring protocol/session sources. Its 256-command, 16-file, 16-MiB and four-job
limits remain unchanged, as do the normal 180-GiB full-build requirements.
Selection/package/controller tests passed **1215, with 1 skipped**. Compilation,
native execution and the six-factorial browser repeat were pending at this stage.
[Selection](drafts/environment/screenshot76-selection-observations.json).

The next unselected diagnostic package adds opt-in `retained-gpu-objects`, with
original WebGL1/2 resources and reads across six BFCache documents. Exact replay
and 36 synthetic validator cases passed; **no browser execution is claimed**.
Existing modes/defaults are unchanged; unavailable/lost/recreated resources fail.
[Preparation](drafts/environment/retained-gpu-objects76-preparation.json).

## Document-bound screenshot transaction draft

The unselected five-file native package shares effective emulation ownership and
FIFO screenshot leases across sessions of the same target. Leases bind both the
frame and document token; cross-document navigation cancels pending work before
commit, and late callbacks cannot restore state into a replacement document.
Only capture-owned view/preference changes are restored. Twelve real-session
native unit cases are prepared. Both production translation units and the unit
fixture passed pinned syntax checks; exact patch replay and source/build guards
passed. **The tests have not executed and the draft is not selected or linked.**
[Preparation](drafts/environment/screenshot-transaction76-preparation.json).

The integrated worker/service Python baseline at `2953274` passed **4801 tests,
1 skipped**, with source/status guards. This is not native screenshot runtime
proof or release admission.
[Full regression](drafts/environment/canonical-python75-worker-service-observations.json).

## Integrated worker and service-controlled lifecycle

`retained-workers` adds six actual classic/module worker classes to the protected
retained-document probe. `--verify-service-lifecycle` additionally verifies scoped
service-controlled clients, real BFCache and per-version worker stop/restart.
Both desktop/Mobile Web passed; four stops have observed running/stopped/running
events, new worker identity/epoch and stable normalized Canvas/WebGL observations.
Full six-document screens are checked again after restart. Worker OfflineAudioContext
is unavailable and is not counted as Audio readback. Cleanup and source/core guards passed.
[Exact evidence](drafts/environment/worker-service75-observations.json).

Default `canvas` and existing modes remain opt-in compatible. The primary retained
document itself is outside the service scope; separate scoped clients prove control.
Native cross-session screenshot state ownership is next. Retained GPU objects,
WebGPU readback, device cohorts and complete privacy/release admission remain open.

## Historical unselected worker lifecycle preparation

[Prepared package](drafts/environment/retained-workers75-preparation-observations.json)
adds six real classic/module worker classes to the retained-document probe.
Its D-only prototype passed desktop/Mobile Web; the stricter staged record verifier
also passed 16 positive/fault replay controls. **It is not yet integrated or admitted**.
Service control of the restored document, forced service restart and retained GPU
objects remain open; unavailable worker Audio is not counted as readback coverage.
The source-bound full regression found 28 historical-hash mismatches; exact archive
reconstruction passed 291 targeted tests, with the full repeat still pending.

## Retained six-document surface diagnostics

The integrated `retained-documents` probe extends existing protected BFCache checks
to recreated WebGL1/2 and OfflineAudio reads in six real documents, with shared
single-context validators rather than fabricated copies of eight-context matrices.
The original full-matrix validators retain their context/partition requirements.
The responder binds actual WindowProxy/origin/nonce/URL/timeOrigin and rejects
replacement documents. Both desktop and Mobile Web passed on preserved 001–075;
20 synthetic routing controls and 460 related unit cases passed.
[Evidence](drafts/environment/retained-document-surfaces75-observations.json).

This does not retain GPU objects or test worker BFCache restoration/WebGPU readback.
The screenshot ownership conflict remains open; no full-policy/release admission.

## Current implementation boundary

**Selected, compiled and independently preserved: Windows Chromium 156.0.8078.36, 001–075.**
All **494 native cases / 23 groups** passed with postguards; 269 runtime assets are preserved.
The fixture-only 075 corrects the retained 074 crash without removing assertions.
Full Python at `6ad4ff9`: **4709 passed, 1 skipped** with source/status guards intact.

Scoped browser gates pass first-script initial/restart (three modes, six document roles),
protected screen/Canvas BFCache, and recreated top-document WebGL/Audio after BFCache.
This does not prove retained GPU objects, worker restoration, WebGPU readback or device cohorts.

**Open: same-target, cross-CDP-session screenshot state.** Independent controls isolate
session ownership from clip: same-session captures pass; another session without clip
preserves screen but returns wrong DPR bounds, while another session with clip immediately
resets that page's six document screens. This also reproduces without Playwright screenshots.
The previous cross-page attribution was confounded by capture side effects; the original
negative report remains unchanged. Byte-identical diagnostic modules on exact-version
stock also reproduce the cross-session clipped reset; stock has additional cross-origin
screen failures even in the same-session control. Equal GN/toolchain flags are not proven.
Next fix effective-state ownership and
restore semantics without hiding failures or relaxing PNG/screen checks.
[Exact 075 evidence](drafts/environment/screen75-runtime-observations.json).

The ordinary 180 GiB build reserve is unchanged. Cached j4 build retained objects,
with 1 browser step / 2m40s and 2 native-build steps / 7m16s; no sync/hooks repeat.
See [cached rebuild boundaries](BUILDING.md#bounded-cached-chromium-156-rebuild).
No complete privacy/release admission; older 073 and 148 are retained.

| Boundary | Verified scope | Still open |
| --- | --- | --- |
| Native identity | Private profile keys and browser-owned document/worker policy delivery | Complete plausible device cohorts; not arbitrary OS/GPU impersonation |
| Combined surfaces | Canvas/WebGL/AudioMath, eight protected desktop profiles, initial/restart; Mobile Web separately | General compatibility and full protected lifecycle |
| Canvas formats/export | HTML/Offscreen, sRGB/P3, unorm8/F16; document and six worker-class PNG paths | Broad HDR/nonfinite/perceptual quality |
| Nested dedicated workers | Four classic/module parent-child paths; 64 Canvas format cases or 8 finite HDR cases per profile/phase; recreation and browser restart on frozen 073 | Selected 074, broad HDR quality, nested worker GPU/Audio, shared/service parents and arbitrary depth |
| Manager BFCache | Requested screen/DPR in six documents and stable top-document Canvas after actual restoration | Raw per-page CDP metrics stress still fails; restored GPU/Audio output not measured |
| Local storage | Account/settings readers share the existing writer RLock; Windows same-process race reproduction is fixed | No new cross-process locking guarantee |

[Current matrix](../docs/GLINT_TEST_MATRIX.md),
[073 native batch](drafts/upstream-156/native-batch73-observations.json),
[nested format measurements](drafts/environment/nested-formats73-probe-selector-observations.json),
[nested finite HDR measurements](drafts/environment/nested-hdr73-observations.json),
[074 selection](drafts/environment/screen74-selection-observations.json).
The nested collector ran byte-identical diagnostic overlays on a local frozen 073
Git layout; inherited source bindings retain both measured raw and normalized text
hashes. It is not evidence for the changed 074 selection or the installed package.
The older 148 package/runtime remains available for comparison/rollback. No universal
CAPTCHA result, full CDP invisibility, current security or production admission is implied.

## Historical implementation notes

The following snapshots describe their recorded checkpoints, not the current selection.

Worker PNG capture now passes **24/24 cases/carriers per baseline and protected
profile**, using the existing independent Qt decoder. Pixels match pre-mutation
reads and document outputs, including async capture and color metadata. The exact
public probe ran from a local frozen 001–072 source layout with the preserved
001–072 receipt while 001–073 was building; this is not a 001–073 result.
[Worker PNG](drafts/environment/worker-export72-observations.json).
The full Python repeat after the historical-source reconstruction repair passes
**4503 tests, one skipped**, with source/status guards and both QML profile-delivery
cases passing. It precedes the new finite HDR probe/tests.
[Full repeat](drafts/environment/canonical-python73-worker-export-observations.json),
[retained earlier failure](drafts/environment/canonical-python73-diagnostics-failures.json).
Four finite Float16 contexts additionally pass bounded bit/alpha/crop/repeat/re-put
controls on preserved 001–072, with negative, above-one and subnormal signals present.
[Finite fidelity](drafts/environment/canvas-hdr72-observations.json).
These extend the existing `scripts/native_canvas_hdr.py` conversion observer;
they are not broad image-editor quality or 001–073 admission. The edge-only policy
does not promise an effect on every isolated or transparent drawing.

The compiled browser remains **001–072**. Its 21-group native batch completed with
**485/488 passing cases**: all 484 existing cases pass, but three new orientation
cases fail. [Retained failure](drafts/upstream-156/native-batch72-observations.json).
**001–073 is selected, not compiled:** main logical-screen exposure plus an accurate
non-web-test orientation fixture, with the same four strict cases and two isolated
compiler checks. [Selection](drafts/environment/screen73-selection-observations.json).

Fresh Mobile Web passes 18 phases after native linking, without relaxed deadlines;
the previous aborted timeout remains recorded. Six classic/module worker classes
pass all 96 Offscreen format cases and match document output in each profile.
[Mobile](drafts/environment/combined-mobile72-observations.json),
[workers](drafts/environment/worker-formats72-observations.json).
Full Python at `4e838f4`: 4472 passed, two QML profile-delivery deadline failures,
one skipped. The unchanged isolated follow-up passes both; the full under-load
failure is retained, not reclassified as fixed.
[UI evidence](drafts/environment/canonical-python72-ui-failures.json).

**001–072 is now compiled and separately preserved on Windows**: j4, 64 actions,
15m14s, 269 assets. The new binary passed all 18 baseline NativeRuntime checks.
[Build](drafts/upstream-156/build72-observations.json),
[baseline](drafts/upstream-156/runtime-baseline72-observations.json).
Fresh protected tests on the same exact core/receipt passed **18/18 combined
Canvas/WebGL/AudioMath phases** (baseline + eight profiles, both AudioMath selectors,
initial/restart) and **32/32 Canvas format/readback combinations** (HTML/Offscreen,
sRGB/P3, unorm8/F16). [Combined](drafts/environment/combined-math72-observations.json),
[formats](drafts/environment/canvas-formats72-observations.json).
The independent PNG gate also passes eight cases / 12 carriers per baseline and
protected profile, with exact pre-mutation pixels and color metadata. Two live
profiles pass all six peer-closure/restart phases with observed-process cleanup.
[PNG](drafts/environment/canvas-export72-observations.json),
[concurrent](drafts/environment/combined-concurrent72-observations.json).
The corrective native batch, worker restart/nested cases, HDR quality, security and
release remain open; historical 001–070 results do not carry forward automatically.
The full Python repeat after historical-binding fixes passed 4464 tests, 1 skipped.

The previous **001–072** selection linked orientation/
visibility and extended Canvas, nine changed files. Three joint-overlay compiler
checks passed, and the existing native verifier gains a strict four-case orientation
target (21 groups total). [Selection](drafts/environment/linked72-selection-observations.json).
That selection record predates the completed 001–072 build above; the separately
preserved **001–070** remains the comparison/rollback binary. The full Python repeat at `ba72a17` passed
**4447 tests, 1 skipped**, before this source selection.

**Retained regression, fixed on the 001–072 format fixture:** protected Canvas on preserved **001–070** fails 30 of 32 tested
HTML/Offscreen sRGB/Display-P3/unorm8/float16 combinations, while the same binary
without the policy supports all 32. Only default sRGB/RGBA8 succeeds. The error is
fail-closed, but still a compatibility regression, not a passing privacy gate.
[Measured failure](drafts/environment/canvas-formats70-observations.json),
[format-preserving fix contract](drafts/environment/CANVAS_FORMATS.md).
A source-format extension is now an [isolated native draft](drafts/environment/canvas-formats-next/README.md),
with compiler checks and 12 transform controls including 65,536 half encodings.
The adaptive replacement for the single-LSB variant also passes 283 linked Skia
copy/projection controls: four source/read color-space pairs and distinct F16/RGBA8
outputs for 32 native seeds on the owned fixture. This extension is compiled into
001–072; fresh format and PNG gates pass, while worker tests and broad HDR quality remain open.
The full repeat at `4400f45` passed **4446 tests, 1 skipped**, before that extension.

The subsequent [concurrent desktop gate](drafts/environment/combined-concurrent70-observations.json)
passed six controls across two protected profiles and peer closure/restart.
[Mobile Web](drafts/environment/combined-mobile70-observations.json) passed 18
combined-surface phases with eight profiles and both AudioMath selectors, using
Windows touch/viewport emulation, not Android/iOS. These positive results cover
default Canvas formats only, not the failure above. The full Python repeat at
`bd82e73` passed **4405 tests, 1 skipped**, before these new diagnostics.

The current preserved Windows candidate is **Chromium 156 / 001–070**, compiled
and checked with **484 native cases in 20 groups**. Logical-screen desktop/mobile
and profile-restart checks passed. The first [combined surface gate](drafts/environment/combined-math70-observations.json)
also passed: Canvas/WebGL readback/AudioMath, eight protected Windows profiles and
baseline, 18 initial/restart phases. Both AudioMath pipelines were exercised, not
eight real-device Audio identities. Combined BFCache, mobile concurrency, full
WebGPU/quality/resources and release admission remain open.
[Native results](drafts/upstream-156/native-batch70-observations.json).

The default manager still disables BFCache. An explicit-opt-in driver has a pinned,
unselected staging/build path and passed four Recorder/replay phases plus paired
Camoufox/CloakBrowser transport/frozen Python checks.
[Staging](drafts/environment/driver-stage70-observations.json),
[actual staged stress](drafts/environment/staged-stress70-observations.json).
The full Python repeat at `766d9b4` passed **4364 tests, 1 skipped**.

A stricter pending-binding teardown control exposed unhandled Python reject tasks.
The [paired BindingCall draft](drafts/environment/binding-close70-observations.json)
is now available in an **optional Python+JS package**, separate from the historical
JS-only stage. [Package evidence](drafts/environment/python-js-stage70-observations.json)
confirms the actual EXE's patched Python bytecode, four Recorder/replay phases,
18 default-runtime checks, six restoration races and both frozen legacy providers.
Neither the default driver nor the manager BFCache policy is switched.
Security rebase, verified device-cohort generation and package/update/rollback
admission still block a complete release. Linux/macOS remain deferred.

### Historical checkpoints before 001–070

The latest source-built Windows candidate is **Chromium 156 / 001–069**.
The j4 build completed 2079 steps in **1h47m09.05s**, with final source/SDK/core
postguards and an exact 269-asset preserved runtime.
[Build evidence](drafts/upstream-156/build69-observations.json).
Actual first-script checks passed both desktop and native-control initial/restart
phases. Mobile cross-origin roots retain DPR 3, but the main/local documents
settle at DPR 1: the overall gate remains failed and queued 0070 is still needed.
[Runtime findings](drafts/environment/screen69-first-script-observations.json).
The new native unit cases and full combined/package gates have not executed.

**001–070 is selected for the next source build**, with the main-DPR correction
and seven linked widget cases. Its verifier integration is now active:
`screen-widget` maps to `blink_unittests`, requires exact 0069/0070 source names,
and brings the batch to 20 groups. [Selection](drafts/environment/screen70-selection-observations.json).
Neither source selection nor Python gate controls admit the new binary or policy.

The native-unit-verified baseline remains **001–068**. Its fixture-only repair
compiled without changing the 001–067 browser core;
all **18 native groups passed**, including **12/12 AudioMath**, with complete
source/SDK/core/receipt postguards.
[Build](drafts/upstream-156/build68-observations.json) and
[native results](drafts/upstream-156/native-batch68-observations.json) are scoped
evidence, not package or privacy admission. Failed 001–067 evidence is retained.

An actual `NativeRuntime.start()/close()` run on preserved 001–068 passed eight
ownership/storage lifecycle checks with two simultaneous profiles and both
persistent restarts. Profile keys stayed distinct and unchanged, cookies and
localStorage stayed isolated, duplicate owner/double start were rejected, and
resources were released. [Scoped evidence](drafts/environment/runtime-ownership68-observations.json).
The overall run remains failed because screen consistency still fails. That
run's lock owners were in one Python process. A separate real-process control
subsequently rejected a challenger while the owner stayed usable, then acquired
the same profile after orderly close, retaining its private identity and releasing
resources. [Windows process evidence](drafts/environment/runtime-owner-process68-observations.json).
The existing crash gates also passed three two-profile rounds and a separate
owned-controller kill, recovering cookies/localStorage/IndexedDB/CacheStorage/SW
with zero remaining observed owned processes.
[Checkpointed recovery evidence](drafts/environment/runtime-crash68-observations.json).
This covers committed checkpoint state with policies off, not unsaved
transactions, enabled-policy recovery, server/team storage isolation or the
new 0069/queued 0070.

Eight fixed profiles passed baseline/Math/Math-restart Audio API compatibility.
A separate **1080-capture** long-compressor run on the same keys observed two
stable output classes matching the expected native/float32 distinction; short
512-frame fidelity graphs were non-discriminating.
[Effect evidence](drafts/upstream-156/audio-compressor-effect68-observations.json)
does not establish eight distinct Audio identities or real-device cohorts.
Legacy Audio-v1 failures remain open.

**001–069 is compiled and partially runtime-checked, not fully admitted.**
Its browser-owned logical screen snapshot is separate from physical compositor
and input geometry; widget-scoped DOM/CSS/DPR and update/disable behavior need
the complete linked-browser gate. The new `screen-metrics` group requires nine
cases in `blink_common_unittests`; its historical batch had 19 groups before
the separate 0070 widget gate was selected.
[Screen integration contract](drafts/environment/SCREEN_EMULATION.md).
Both the 001–068 and 001–069 runtimes are preserved separately on D: for rollback.

The existing raw **001–067** suite passed eight gates and 160 checks. The last
installed-package baseline remains **001–066**. Neither historical result
verifies the newly selected screen package, remaining protected-surface
combinations, external anti-bot services or production admission.

The manager resource monitor and source-bound Audio/GPU diagnostic runners are
integrated in main. Canonical Python regression passed **4047 cases with one
skipped** and tracked-source postguards; 625 runtime tests include real slow
profile-persistence cancellation controls. Later Windows CI passed after isolating
ACL verification from foreign PowerShell modules; production ACL checks remain
unchanged. Python integration does not validate
the new native AudioMath implementation or expand browser capability admission.

An earlier canonical source regression passed **4111 cases with one skipped**
and tracked-source postguards after integrating measured-environment capture
and the fixture-repair draft. Detailed
[Audio/GPU evidence](drafts/upstream-156/canonical-audio-gpu67-observations.json)
keeps the overall scope failed: native Math fixture repair, Float32 browser
coverage, the complete browser suite and release gates are still required.

The reviewed Windows runtime is **Chromium 148 / 001-062**. Its exact managed
package admits only the individually reviewed experimental capabilities;
source ports, Python tests and diagnostic reports cannot expand that admission.
Chromium **156.0.8078.36 / 001–065** linked successfully in its separate D:
workspace: 19,487 build steps in 3h46m37.79s, followed by passing source/toolchain
postguards and a three-core-file build receipt. Disposable startup passed; two
repeats passed all 18 baseline lifecycle/integration checks. An earlier shutdown
timeout remains unexplained and retained as failed evidence. Baseline lifecycle
alone is **not full policy-suite, browser-identity or release admission**.
The first identity verifier stopped before running tests because its global
process guard detected an unrelated project's Ninja. Guards now support an
explicit workspace/binary scope; unreadable process identity remains a conflict,
and default unscoped checks remain conservative. Real owned sleeping-Ninja
controls distinguish foreign and conflicting scopes without terminating either.
The recovered identity targets passed 134 C++ cases with postguards: keys 62,
contexts 37, transport 20 and handoff 15. The selected 001–066 build subsequently
passed all 17 native target groups, including the corrected GPU fixture's 34
cases, with shared source/SDK/core postguards. Filters overlap. The installed
package suite remains separate; the historical source-build eight-gate result is below.
The unprotected 156 Audio baseline also matched the standalone native156 DSP
matrix bit-for-bit in 45 captures. This does not execute AudioMath 0068.
An official CfT archive now provides the exact 156.0.8078.36/upstream revision
control: 135 Glint-off/CfT/Glint-off Audio captures matched bit-for-bit across
15 cases. CfT reports the real Git revision; current non-official Glint uses the
upstream dummy-CDP-stamp default and is bound by its source receipt/core hashes.
The real-stamp GN override is staged only. These measurements do not equate
build flags or admit math-mode/device-cohort plausibility.
The public `audio-dsp-math-v2/browser_matrix.py` repeats this exact-bit gate with
explicit source/recipe/core bindings and strict default revision handling.
It never substitutes a browser or overwrites output; A/B/A uses separate fresh
profiles and does not replace the persistent-restart or installed-package gates.
The eight-gate owned runtime suite passed all 160 checks on the source-build binary
(`upstream-156/runtime-suite-observations.json`). This is not external anti-bot,
installed-package or complete Canvas/GPU/Audio admission.
Compiled 156 main/app-list icons match `logo.ico`; EXE/DLL ProductName and the
internal version page identify Glint. Taskbar/shortcut caching is not covered.
The verifier evidence-retention fix is now integrated; it is not a browser
timeout/root-cause fix. The integrated Windows Runtime guard rejects per-profile downgrades
before identity loading/driver startup, including explicit EXE selection.
Its owned 148-to156 upgrade preserved five stores and the private identity;
the subsequent older selection was blocked without opening the upgraded data.
This is one controlled transition, not general migration or rollback admission.
The full canonical Python regression passed 3862 cases with one skipped. Explicit
candidate diagnostics now bind workers/combined surfaces/WebGL to the complete
156 receipt, every core file and the selected GN recipe. The installed 001–066
development payload passed all eight baseline gates (160 checks), without
activation. Canonical post-integration installed lifecycle (18), worker startup
(60), profile-identity and partitioned-privacy surface modes (12 phases / 24
nested Canvas cases each) subsequently passed with source postguards; see
`upstream-156/canonical-app66-observations.json`. This does not expand admission.
Owned pre-integration diagnostics passed 60 worker startup/denial cases and 12
combined profile-identity phases with 24 nested Canvas cases. These are not
device-cohort or external anti-bot admission. The additional Audio fidelity
fixture passed 54/54 baseline graphs but failed 12/54 protected identity/half-gain
graphs; Audio-v1 therefore remains outside admission despite the combined pass.
The isolated guard-enabled Runtime passed the extended 18-check lifecycle CLI,
including backup/restore, manager/Recorder and cancelled startup. Separately,
three baseline lifecycle repeats passed during observed native-build activity;
the original close timeout remains unexplained. Native context (37) and
transport (20) units passed with postguards, not browser identity admission.
The first browser used 001–065; the current candidate chain is 001–066.
Test-only 0066 enables the native optional texture query in its GPU fixture and
adds an absent-extension negative control, without changing production GPU code.
Actual sync/hooks/replay retained 256 byte-identical source timestamps; the
browser rebuild took 2m32.62s / one action. Its core hashes remained unchanged,
while the new receipt and `upstream-156/native-batch66-observations.json` bind
the full 66-patch source checkpoint. Native units do not admit protected surfaces.
0063–0064 address the actual unsafe-buffer compilation failures without disabling
diagnostics. Test-only 0065 updates worker synchronization/API calls and the GPU
canary layout; all 38 mapped fixture object targets now compile, but the full
fixture suite has not executed. The two system module targets and their
source/toolchain guards passed; object compilation is not execution of the
fixture suite. Linux/macOS runtime work remains deferred.

Persistent profiles own their separate browser processes/contexts; tabs inside
one profile share its identity and storage. The rendering verifier can keep at
most two private profiles live for bounded cross-profile checks, reusing the
existing five-store persistence fixture. This is a verification-runner limit,
not a two-profile product restriction. Current evidence and open gates live in
the [test matrix](../docs/GLINT_TEST_MATRIX.md) and
[roadmap](../docs/GLINT_ROADMAP.ru.md).

## Manager integration

`app/core/native/` owns configuration, identity, diagnostics, browser lifecycle
and local binary distribution. The existing browser interface dispatches to this
runtime while preserving Camoufox/CloakBrowser. Engine IDs and profile schemas
remain compatible; the display/product name is Glint.

The runtime launches an explicit installed executable or a selected managed
release. It never substitutes another engine or adopts its profile directory.
Profiles use persistent Chromium contexts with process-owner exclusion and
bounded teardown. Recorder, scenarios and AI use the common browser contract.

Local session backup takes the same Native owner lock for the complete ZIP
snapshot, not just an in-memory UI check. A live runtime blocks session export;
an export blocks runtime start. Metadata-only export does not read browser files.
Restore remains a new local identity: private profile keys and owner locks are
excluded, not transferred as a key-preserving rollback.

Running-profile diagnostics use a disposable, page-routed loopback document and
same-origin iframe, each with a dedicated-worker observation. Existing document
and worker checks run independently, then document identity groups are compared
across the frame boundary. Original tabs/routes remain untouched. The extra
scope is recorded under `contexts.same_origin_frame` and its mismatches join
the root report. This post-load fixture is not cross-origin or first-script
coverage; standalone binary probes still use their original two scopes.

## Configuration and privacy

### Product contract: coherent browser identity

The primary objective is a plausible, stable browser environment, not blanket
suppression of every exposed value. Treat OS, UA/Client Hints/HTTP, graphics
capabilities, fonts, display, language and timezone as one versioned identity.
Document, frames and workers must agree; profile restart must preserve identity,
while independent profiles retain independent keys and storage.

GPU metadata minimization is an optional privacy experiment, not the default
identity strategy. Missing extensions or empty identifying fields do not prove
plausibility. Future identity presets require measured reference environments
and native capability/behaviour checks; do not independently randomize hardware
strings while retaining contradictory driver capabilities. Cross-OS and mobile
identities remain unverified until their complete observable environment agrees.
Current Mobile Web remains desktop Chromium viewport/touch emulation.

The canonical `drafts/profile-identity` sequence separates partitioned privacy
derivation from stable profile identity and prepares an immutable browser-owned
selection per key service. Invalid selections reject initialization; installed
owners cannot switch modes. Initial source replay prepared twenty-six native
fixture definitions; their later execution is recorded below. A fourth, eight-file
candidate integrates selected derivation into the surface producer and a v3
wire mode with five more fixture definitions. Unknown modes and v2 reject before
seed copies; final-partition validation remains mandatory. Pinned Mojo parsing
and C++ binding generation passed in an isolated copy. The later native and
linked-browser checks are recorded below; product UI capability admission remains separate.
The fifth candidate adds six Blink fixture definitions for before-script mode
retention, independent document clones, invalid mode rejection and worker-origin
binding. These were initially source-only checks; their native execution is recorded below.
The sixth candidate prepares browser-only launch selection with strict service,
full document/worker surface and legacy-conflict checks. Persistent/incognito
initialization passes the immutable mode to its own service; renderer command
lines do not receive it. The four launch fixtures subsequently executed in the
001-059 BrowserContext target; linked Chrome ProfileImpl behavior remains unverified.
The manager key utility now has a separate profile-purpose derivation reference.
Its four fixed vectors, persisted reload and root/surface separation are executed
in Python tests; existing partitioned privacy vectors remain unchanged. It does
not activate either mode or replace native BrowserContext/IPC checks.
All six candidates are now registered exactly as 0049–0054, alongside GPU
transport 0055–0058. Integrated source 001-058 matched the reviewed composition
and passed full ordered replay. The key/service native target subsequently
passed **62/62 cases** (19 new, 43 legacy), with unchanged browser core/GN/receipt:
`identity-keys-001-058-v1.json` on D. The complete native selection is 134 cases;
41 new definitions expand to 50 new cases because DocumentLoader has four modes.
Context **37/37** and transport **20/20** cases subsequently passed on 001-059.
Blink handoff **15/15** also passed on 001-059: 12 document cases across four
modes and three worker-thread cases. Keys also passed 62/62 on 001-059, completing
134/134 on that source. The linked 001-059 browser subsequently passed extended
profile-identity and partitioned-privacy combined checks, including simultaneous
profiles and restart. This does not admit product privacy capabilities or prove
first-script GPU/nested Audio/GPU coverage; see the current test matrix.
Historical source-only preparation below is not current admission.

Manager diagnostics also compare measured WebGL/WebGL2 extensions, six limits and
context attributes between document and dedicated worker. A feature-off 001-027
browser passed en-US/de-DE loopback checks with unchanged core hashes; these
observations do not validate metadata spoofing, the new policy batch or presets.
Identity diagnostics reject contradictions between known navigator platform
values, explicit Windows/macOS/Chrome OS UA markers and Client Hints OS. They do
not infer OS versions from reduced UA text or treat Linux navigator.platform as
proof of desktop Linux: Android and Chrome/Chromium OS also use that family.
Windows en-US/de-DE observations passed on the unchanged 001-027 baseline;
synthetic platform cases are not Linux/macOS/Android runtime validation.
`verify_native_identity_readback_batch.py` composes all six identity candidates
with the six halo/clipping/GPU metadata candidates in one isolated source tree.
The exact combined source and pinned Mojo/GPU generation passed before
integration. C++ type checks covered 22 identity and six GPU units. These
preflight results do not replace the remaining native/runtime gates or admit
protection. At that stage the earlier browser was 001-047 and the next linked
baseline was 001-059; subsequent 001-062 evidence is recorded in the test matrix.

Configuration validates viewport, DPR, locale, timezone, permissions and privacy
requests before startup. Unsupported requests fail rather than silently falling
back. Diagnostics observe actual document/worker browser values; they do not
replace APIs or invent hardware/GPU values.

`canvas_fidelity.py` is shared by runtime diagnostics and the verification helper.
Document and dedicated-worker probes measure explicit opaque ImageData fidelity,
repeat/single-pixel/PNG/rewrite consistency and alpha preservation using bounded
32x24 inputs. Diagnostics report opaque pixel mutation, malformed observations
and inconsistent operations as mismatches; half-transparent RGB rounding alone
is not treated as a regression. These metrics do not certify fingerprint
plausibility or replace stock calibration. Real 001-059 observations confirmed
zero baseline issues and four protected opaque-mutation warnings across the two
scopes, with unchanged core/receipt. The actual routed health probe also passed
its baseline document/worker checks and removed its disposable profile.

Persistent identity uses an owned profile-root file containing a versioned
private key. On Windows the manager uses owner-permission QFile creation and
same-directory atomic OS publication on an ACL-capable filesystem. Loading a
valid legacy key republishes its exact bytes with the creation ACL, without seed
rotation. This protects key-file contents, not writable parent directories or
against privileged/same-user processes; it does not bulk-harden workspace ACLs.
Export excludes the key; restored/cloned profiles obtain a distinct
identity. Cryptographic domain strings and filenames are compatibility contracts,
not branding text, and must not be renamed without migration analysis.

Chromium patches provide hardware ceilings, real installed-font selection,
WebRTC routing, automation/headless policy and Windows storage-path handling.
Newer patches derive per-surface keys from a trusted browser StorageKey and own
the key service per BrowserContext. Off-the-record contexts have independent
ephemeral identities; they must never redirect to the persistent original.

Key loading is asynchronous on a blocking worker; derivation fails until ready.
Readiness callbacks are registered in patch 0016 and passed 43 native cases.
Real-context tests are registered in
patch 0017 and all twenty passed in the linked content unit target.
Patches 0018-0020 register lifetime-bound document/worker endpoints using
browser-owned partition state and an independently timed worker consumer.
Their 34 native cases passed, as did a combined 54-case context/delivery run.
Patches 0021-0026 register dedicated/shared/service-worker startup gates and owned
seed transport into Blink scope creation, plus four handoff unit definitions.
Startup gates require the developer-only `glint-worker-canvas-bootstrap-test`
switch; normal launches retain the upstream path. Patch 0027 adds host failure
notification before shared-worker rejection teardown. The linked 001-027 browser
passed 40 owned startup/restart/shared-client/rejection checks, with exact receipt
and core-code measurements. This is not proof of internal Blink seed bytes or
cross-partition key equality. The first four-case Blink handoff run passed two
cases, then aborted on an extra never-started worker in the sequential fixture.
Test-only patch 0028 corrects that fixture lifetime; all four cases passed on
retry with the baseline browser core, receipt and GN arguments unchanged.
Document
bootstrap and Canvas/WebGL/WebGPU/audio protection remain incomplete.

Patch 0029 registers a shared final-partition validator header and nine native
cases, all passed through the public document-partition target. Registered
document commit/renderer candidates reuse that header rather than defining a
second copy. The validator checks exact native partition encoding, not IPC
sender authentication or safe cancellation after document teardown.

Patch 0030 registers the developer-only document commit prototype: shared
StorageKey resolution, final wire-origin payload construction and token-bound rejection of the
selected pending navigation. The public `--target document-navigation` gate
requires twelve exact NavigationSimulator cases. That gate uses real browser
navigation machinery with simulated renderer/network behavior; first-script
Blink execution, previous-page usability and candidate Canvas hooks require
separate checks. Source registration is not browser linkage or privacy admission.

## Source reproducibility

### Registered surface batch (not admitted)

| Candidate | Prepared behavior | Evidence boundary |
| --- | --- | --- |
| Surface policy v2 | One owned partition snapshot with independent Canvas/WebGL/WebGPU/Audio seeds; bounded preflight, typed browser partition, binary Mojo schema and owned codec | Source replay and generated bindings; 25 native fixture definitions, not compiled |
| Worker surface delivery | Shared endpoint readiness, explicit v2 consumer/modes, all three launchers, immutable Blink scope and first-script rejection | Source replay; 8 browser, 22 consumer/mode and 4 Blink fixture definitions, not compiled |
| GPU metadata minimization | Disabled-by-default native feature; remove WebGL debug extension and identifying WebGPU info without fabricating hardware | Source replay; candidate runtime not verified |
| Offline Audio | Deterministic scalar prototype and bounded detached AudioBuffer copy; no live processing or JS method replacement | Registered API integration; native fixtures and protected runtime pending |

Canonical public source and historical integration inputs live under
`drafts/policy`, `drafts/gpu` and `drafts/audio`. They were promoted together into
registered patches 0031–0034 after the corrected 12-case document gate passed.
Exact registered-source replay passed across 125 paths in that earlier batch.
The current compiled-candidate boundary is listed above; earlier source gates
do not admit subsequent binaries. Do not modify a live batch's frozen inputs.
Document/worker v2 transport and final-owner handoff have
candidate code, not compiled/runtime proof. Canvas and OfflineAudio API candidates
consume explicit owned seed results; API admission and GPU readback
admission remain unfinished. Existing profile-key derivation domains must stay
stable across a transport-version change.

`verify_native_gpu.py` and `verify_native_audio.py` provide local compatibility
diagnostics before enabling new hooks. Their successful 001-027 baseline runs
do not verify the drafts or claim anti-bot acceptance. Worker APIs unavailable
in upstream remain explicit exclusions, not fabricated coverage.

`verify_native_next_batch.py` replays thirty canonical integration inputs
in an owned temporary overlay, checks exact canonical copies and rejects source,
receipt, GN-input or browser-core drift. Run it with a new evidence path outside
both repositories; it never runs GN, compilation or modifies active sources.
For the promoted state it reverses 0031–0034 only in that owned copy, then
recomposes the canonical inputs and requires equality with registered source.
Partial registration is rejected.

The document v2 candidate owns the browser-selected partition and independent
surface seeds, and requires validation against Blink's final StorageKey, not
only its provisional key. The browser producer uses the existing context key
service without regeneration or another root-key store. Its 30 content fixture
definitions are source-only. Additional handoff/readiness/navigation fixtures
bring the expected document v2 case set to 112; none has executed.
Final handoff does not use `CalculateOrigin` as a read-only pre-unload probe:
origin privilege changes and sandbox-token consumption must retain upstream
semantics. The current late Canvas prototype check does not prove old-document
rollback. Early renderer rejection precedes teardown; the late final-key guard
creates an inert replacement, not restoration of the previous document. Blank
and srcdoc inheritance requires exact partition matching. Root initial empty
documents and different-partition children need authenticated delivery rather
than parent-key borrowing. No document v2 policy or new readback hook is admitted
by source replay or generated bindings.

The shared surface reader treats flag-off and invalid required policy as
different results. All candidate Canvas web entry points reject the latter;
they do not export an unprotected image. OfflineAudio captures its independent
seed before rendering starts, checks the additional-copy budget and produces
one detached mutable buffer before both completion event and Promise. Native
seed-reader and startRendering rejection fixtures are prepared, not executed.
No realtime Audio or analyser protection, complete ImageData-format support,
complete GPU readback protection or verified fingerprint-resistance claim is implied.

The registered WebGL hook covers default sRGB RGBA8/RGB8 and single-sample
RGB8/RGBA8 renderbuffer attachments, using actual selected attachment extents.
CPU/PBO pack handling, pending GL errors, resize and export consistency have
prepared gates. The next-readback notes record earlier protected 148 checks;
those results do not admit the current 156 candidate.
Texture, float/integer/HDR attachments and WebGPU readback remain unsupported.
The subsequently registered 0046/0047 `drafts/next-readback` pair replaces redundant
full-frame allocation with an exact full-frame private transform or a clipped
one-pixel halo. Its notes record 58,860 model comparisons, source replay and
earlier native/browser checks. Current-version fixture execution, broader driver
compatibility and performance measurements remain separate gates.

`scripts/native_build.py` pins upstream revisions, records sync/hooks dependency
snapshots and checks applied changes by replaying registered patches into a
temporary Git index. Patch 0007 belongs to the separate V8 checkout. Unknown
changes and changed build inputs prevent generation of a successful receipt.

Next-batch replay owns its temporary Git configuration and disables `autocrlf`:
composed-source hashes use LF regardless of the developer's machine settings.
Regrouping candidate patches must reproduce those exact bytes and preserve all
source/build/runtime input hashes; source equivalence is not compilation proof.

Do not edit an active checkout, GN arguments or registered patch content while
compilation is running. An object build proves only those translation units;
production linking and actual browser execution are separate gates.

The first compiled NavigationSimulator commit/rejection run passed 11 of 12
cases; its browser-initiated `about:blank` case exposed an opaque-origin mismatch.
Policy construction had run before `ReadyToCommitNavigation` selected the origin
stored in the commit parameters. Recomputing an opaque origin can change its
nonce. The corrected source binds both the Canvas prototype and prepared v2
policy to the exact final wire origin, after upstream weak-lifetime and selected
frame checks. It does not change Chromium's origin selection or weaken the test.
The corrected binary passed all 12 cases (`document-navigation-001-030-j4-v3.json`
on D). This proves simulated content-layer commit/rejection behavior, not actual
Blink first-script execution, full renderer/worker policy or browser admission.

## Combined surface runtime gate

`scripts/verify_native_surfaces.py` prepares seven owned-browser phases for the
next compiled surface batch: baseline and two independent profiles, each with a
persistent restart, followed by missing-document-policy rejection. It combines
all four Canvas readback entry points with OfflineAudio completion in the same
eight document/frame/worker contexts. OfflineAudio is expected in five document
contexts; worker unavailability is not audio coverage.

The gate requires repeated reads, export/crop/transparent-pixel consistency,
existing Canvas security checks, Audio event/Promise buffer identity and mutation
semantics, same-partition agreement, different cross-origin/profile results and
stable restarts. A fetched owned page must abort without its script beacon when
document policy is unavailable; timeouts are not accepted as rejection.

Before creating profiles or launching a browser, the gate requires exact
registered surface patches and a build receipt binding **every runtime core
file**, not just `chrome.exe` while Blink resides in `chrome.dll`. Reserved patch
names 0031 (worker policy), 0032 (document policy) and 0033 (surface readback)
are registered and compiled as part of the current 001–065 candidate, **not
admitted by the pending full protected-runtime suite**.
An old 001–027 browser is deliberately rejected before launch.

Measured float32 bit arrays are bound to each Audio digest. The combined gate
compares them against the unprotected baseline: at most the lowest mantissa bit
may change, signed silence/subnormals/out-of-range samples remain exact, a signal
must actually change, and measured signal-to-noise must be at least 130 dB.
Render durations are retained separately and excluded from restart identity;
they do not prove a performance budget. The baseline Audio runner accepts
`--sample-quality` to capture the same bits and durations without enabling policy.

These are prepared checks, not executed protected-browser results. Performance
budgets, GPU readback, malformed-policy injection,
root-initial/sandbox delivery and public anti-bot diagnostics remain separate
work. `privacy_admitted` stays false even if this functional gate passes.

The combined gate also measures Canvas and OfflineAudio from the owned page's
first inline parser script, rather than injecting the first measurement after
load. All six baseline/profile/restart phases require `readyState == loading`,
one fetched fixture, one completed execution beacon and matching settled-document
results. The parser script also creates a connected iframe and starts a read in
its initial `about:blank` immediately, without awaiting a navigation or readiness
event; that same-partition child must match both readings. Audio float bits remain
bound to their digest; render durations are not identity. The 001–027 unprotected
baseline passed the expanded fixture on actual initial/restarted browsers
(`first-script-initial-child-001-027-baseline-v2.json` on D). This checks the probe,
not v2 protection. Root-initial about:blank, popup and sandboxed child first-script
delivery still require separate lifecycle tests.

## Resource observation

`drafts/resources` contains a read-only Windows process reader, not a watchdog
replacement: creation-bound CPU/working-set/private-commit samples, explicit
errors and query-handle cleanup. Its 24 controls and one seven-process owned
Glint observation passed. Process churn/profile ownership, sampling overhead
and memory-limit semantics still require integration; summed working sets
must not be represented as unique physical RAM.
The subsequent tree reader uses bounded Toolhelp snapshots, root/member creation
anchors, parent-age checks and observed topology agreement. Its 18 Windows
controls and two disjoint Glint-root observations passed, including child churn
and handle cleanup. It is not atomic/lifetime accounting or profile-root
authentication; changed membership invalidates the complete CPU interval.

## Distribution

`distribution.py` manages checksum-verified local bundles and release selection.
`scripts/package_native_windows.py` checks official staged files against compiled
output, retains licenses/credits and requires matching runtime evidence.
`scripts/native_release.py` provides install, activate, inspect and rollback.

Complete payload integrity includes executable code, DLLs and resources.
Activation checks compatibility/health; compilation alone is not release admission.
There is no signed online update catalog. Development bundles are unsigned.

## Known boundaries

Python startup rejects hard-linked privacy-key files before starting the browser
driver, matching the native key-loader contract. A shared filesystem inode must
not silently become the identity of two independently locked profiles. Rejection
does not replace the key and releases the acquired profile lock. ZIP export and
restore continue to omit/discard this private identity: restored profiles receive
new keys, while ordinary restarts preserve existing owned keys.

- Graceful close/reopen commits are tested; abrupt crashes may lose pending writes.
- Thread/owner checks do not prove operating-system memory sanitization.
- Unpartitioned shared/service workers need explicit partition policy before
  cross-site privacy protection can be activated.
- Own-fork Linux/macOS runtime, GPU/audio/Canvas protection and production
  security rebasing are not complete.
