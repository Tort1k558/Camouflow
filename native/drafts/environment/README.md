# Measured reference environments

## Pending-binding teardown: retained FAIL and isolated Python draft

The actual staged bundle passed a fresh [32-cycle stress repeat](staged-stress70-observations.json).
Its full committed staging/spec regression at `766d9b4` passed
[4364 tests, 1 skipped](canonical-python70-stage-observations.json).

An unresolved binding during cancelled driver-stop exposed a different Python-side
fault: a failed resolve spawned an unawaited reject against the closed channel.
[Paired evidence](binding-close70-observations.json) retains the overall baseline FAIL
(three loop errors) and the isolated draft PASS (eight BFCache cycles, four cancelled
stops, no recorded loop errors). Handler failures still reject; cancellation propagates;
non-closing delivery failures are not swallowed. Only delivery to a gone target is dropped.

The [Python patch](playwright-python-binding-close.patch) is **not** in the JS-only stage.
[Strict-gate patch](playwright-binding-close-strict-gate.patch) adapts the existing stress
runner in a disposable repository-layout copy; it must not modify an active measurement.
[Extracted-method model](first-script/binding_outcome_model.py) accepts explicit
`--source <prepared _page.py> --report <new output.json>` and passed ten controls.
This is not frozen Native admission, a peak-memory/leak proof or all-phase cancellation coverage.

## Explicit opt-in staging and actual desktop package — 2026-10-30

[Measured staging packet](driver-stage70-observations.json): the compatibility branch
activates only for an `ignoreDefaultArgs` array containing `--disable-back-forward-cache`.
**30 model controls**, **18 default Native runtime checks**, and **4/4 genuine BFCache
Recorder/replay phases** passed. The default manager launch still disables BFCache.

The public [stage tool](../../../scripts/native_driver_stage.py) creates an isolated,
hash-pinned 176-file Playwright copy without changing `.venv`; the optional spec hook
overrides exactly one JS asset. Actual Windows desktop builds passed, as did packaged
Python launch/imports and expected timeout checks for both cached legacy engines.
[Build commands](../../BUILDING.md#experimental-desktop-driver-staging-not-a-chromium-build).

[legacy_transport.py](first-script/legacy_transport.py) compares original/staged drivers
using explicit cached browser paths: main/iframe forms, binding roles, screenshots and
five-store persistence across restart. Four provider/driver combinations passed; this
does not introduce CloakBrowser Recorder support or test fingerprint quality.

This driver remains **unselected and unsigned**. The 6 race cases / 32 cycles below
belong to the earlier reply bundle, not the newly gated one. Frozen Native BFCache,
cancelled teardown under load, resource limits and combined fingerprint admission
remain open. [Historical full regression at `87f74ea`](canonical-python70-races-observations.json)
passed **4334 tests, 1 skipped**, before the new staging code/spec edits.

## Current compatibility gate

[Real lifecycle gates](bfcache-races70-observations.json) passed **6/6 controlled
navigation/page-close/runtime-close cases** and **32 uninstrumented BFCache cycles**
with 224 role-verified Python binding calls. Same-profile key/storage restart and
observed-process exit checks passed. [Full Python repeat](canonical-python70-replies-observations.json):
**4330 passed, 1 skipped**. Driver selection, resource/package/privacy admission remain closed.

[bfcache_stress.py](first-script/bfcache_stress.py) accepts the same explicit paths/hash
as the replay runner and uses the unmodified reply draft (`39b80a…`).
[bfcache_races.py](first-script/bfcache_races.py) instead needs a separate copy with the
[test-only barrier patch](playwright-bfcache-test-barrier.patch) applied **after** the reply
patch, producing `69241956c0c94e480ada6bd232e9fa8f18571e60c213d07c5560a6b7668fcb57`.
The barrier holds a real reply; ready/continued/timeout markers prove the race timing.
**Never package or install that test barrier.** The fresh upstream audit remains
`behind-stable`; successful lifecycle tests do not resolve the release blocker.

[Binding reply draft](binding-replies70-observations.json) passes **4/4 complete
UI-ordered recording/replay phases**: desktop/mobile initial/restart, six documents,
all 13 recorded steps and nine clicks, genuine BFCache in recording and replay,
no pending replies or flush warnings. **25 modeled controls** and the **18-check
existing runtime baseline** passed with the draft. It remains **unselected**:
specific navigation/close races passed in the later gate above, but cancellation under
load, peak resource measurements and pinned package integration are still open.

The [patch](playwright-bfcache-replies-prototype.patch) binds one exact Playwright
bundle hash; it is not a replacement browser binary. Apply it only to an isolated
copy containing the full `playwright/` package. Prepare a separate application copy
with the [BFCache launch opt-in](manager-bfcache-launch-experiment.patch), not the installed application.
The [public runner](first-script/recorder_replay.py) checks the explicit driver hash
and measured browser-core reference before its four-phase flow:

```text
python native/drafts/environment/first-script/recorder_replay.py --executable D:/glint-qa/runtime/chrome.exe --runtime-reference D:/glint-qa/runtime/camouflow-build.json --application-root D:/glint-qa/app --driver-root D:/glint-qa/driver --driver-sha256 39b80ab30d21113e0b1169d53744661a98fc6fb12bde6bea95d9ecc22dba0043 --work-dir D:/glint-qa/fresh-replay
```

The work directory must be new and outside this checkout. The reference must contain
the measured `runtime_core_sha256_measured` map. No dependency is installed or selected
by the runner. Matching uses the system-unique context identity documented in
[CDP Runtime](https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#type-ExecutionContextDescription),
plus frame and binding sequence; numeric context ids alone are not used for queued replies.

[Recorder document.open repair](recorder-document-open70-observations.json) is applied
to the application: abort/rebind listeners without losing same-document in-flight work.
An unchanged-driver desktop control improved **5/6 → 6/6 captured clicks with six-role replay**;
the fresh complete runtime baseline passed **18/18 checks**. The complete BFCache recording
still **fails flush** after all nine clicks: one main-document binding acknowledgement is
pending. No warning was suppressed, and full history replay remains unverified.

[Multisession reconstruction](binding-driver70-multisession-observations.json) now
restores **all six roles in four desktop/mobile initial/restart phases**, recording
seven trusted clicks per phase with correct nested-frame selectors. **13 modeled
controls** and the **18-check existing runtime baseline** also passed with this driver.
The patch remains unselected: UI-ordered complete history-draft replay and real navigation/
close races still need verification. No installed dependency or active launch default changed.

The [public patch](playwright-bfcache-multisession-prototype.patch) applies only to
the exact driver bundle hash in the observation record, in an isolated package copy.
Run its exact-method controls with:

```text
node native/drafts/environment/playwright-bfcache-multisession-model.cjs D:/isolated-package/playwright/driver/package/lib/coreBundle.js
```

The model extracts the actual patched `FrameSession`; it does not simulate an entire browser.

[Native 001–070](../upstream-156/native-batch70-observations.json): **484 C++ cases,
20 groups**, final source guards passed. [Canonical Python](canonical-python70-owner-observations.json):
**4320 passed, 1 skipped**. Neither result admits combined fingerprint policies.

[Recorder diagnosis](binding-driver70-diagnosis.json) identifies a driver context-map
loss, not missing Chromium binding events. The [unselected reconstruction patch](binding-driver70-prototype-observations.json)
passes root-only capture in four phases but **fails six-frame coverage**: cross-process
`same` and `nested-return` roles are absent. This older failure is retained rather than
rewritten as the multisession result. The installed Playwright package and manager launch policy remain unchanged.

One coherent observation is more useful than independently invented OS, GPU and
CPU strings. This tool captures actual stock Chromium values; it **does not
generate, import or apply a fingerprint**.

| Captured together | Required validation |
| --- | --- |
| UA, low/high-entropy Client Hints, HTTP headers | Native getter shape, actual browser version, platform/version and emitted-header agreement |
| CPU/RAM, language, Intl/timezone | Same values across eight document/frame/worker contexts |
| WebGL1/2 and WebGPU | Real metadata/features/limits plus shader, buffer/compute, texture/mip/layer and padding checks |
| Screen, DPR, touch and plugins | Actual document observations; no invented worker screen/plugins |
| Persistent-profile restart | Same measured identity/capabilities and unchanged command-line configuration |

## Capture a control

```powershell
.venv\Scripts\python.exe -m scripts.capture_native_environment `
  --executable D:\Controls\chrome-win64\chrome.exe `
  --work-dir D:\GlintQA\reference-first
```

The executable must match all three core hashes of the pinned official stock156
control. No substitute browser, unsafe/software GPU override or identity policy
is selected. The evidence directory must be new, canonical, on D: and outside
Git checkouts. The tool uses only owned loopback pages and a fresh profile.

The default mode is explicitly **headless automation control, without viewport
emulation**. The default Playwright viewport produced different screen values
in the cross-origin frame during calibration; that failed run is retained.
The headless screen is not a measurement of the physical monitor or an ordinary
desktop-user identity. Successful owned profiles are removed; failed evidence
and profiles remain outside the repository. Nothing is uploaded automatically.

Use `--mode manager-desktop` or `--mode manager-mobile-web` with a new evidence
directory to reproduce the manager configuration. These apply its existing
`NativeConfiguration` context options **and launch arguments**, not an alternative
viewport or a spoofed GPU. The mobile test preset is explicitly 390×844 / DPR 3.
Both requested phases run even when identity validation fails; any failed phase
keeps the overall result failed. Cleanup failures stop further launches.

## Native differences are data, not fabricated matches

Pinned stock156 emitted all requested hints in three network documents, only
low-entropy hints in the inherited `about:blank`/`srcdoc` documents, and no CH
headers in the three worker fetches. The tool requires that measured presence
pattern and compares every emitted value. JS metadata is still checked in all
eight contexts. It never fills absent HTTP headers with JS values.

This distinction follows the document/commit-oriented CH implementation described
in [Chromium's Client Hints guide](https://chromium.googlesource.com/chromium/src/+/5a93aa59e3043e747eff68659dcf7d20193d160e/components/client_hints/README.md).
The exact observed pattern is specific to this pinned control and owned fixture,
not a universal promise about other versions, policies or sites.

GPU identity comparison uses metadata, extensions, features and limits. All real
render/readback results must independently pass their existing strict validators.
Shader translation length remains in the raw observation, but is not treated as
an identity parameter; native compilation produced differing lengths across
contexts without changing identity or rendered pixels.

## Evidence and remaining work

### 001–070 screen checkpoint

[First-script/restart checks](screen70-first-script-observations.json) passed all
six phases across six document roles, including Mobile Web DPR 3. The separate
[two-tab manager](manager-screen70-observations.json) and
[extra-CDP/BFCache](screen-lifecycle70-observations.json) stress results remain
failed; they are not replaced by the narrower successful gate.

[Restored-main interaction](history-interaction70-observations.json) confirms a
trusted click and a 1170×2532 screenshot after actual BFCache restoration.
`first-script/history_interaction.py::capture(session, owned)` uses the existing
owned CDP session after `restore_history`; it does not use Playwright Frame APIs
on restored documents or create another competing page session. All-frame input
and the cached-orientation repair remain unverified. An earlier navigation
timeout is retained; the retry used unchanged deadlines.

[Actual NativeRuntime managed history](managed-history70-observations.json)
separates normal manager behavior from the extra-CDP stress: 144 screen/CSS/
embedding snapshots agree across two tabs, navigation, peer close and desktop/
mobile persistent restarts, without resize or device-metrics commands. Its
BFCache gate remains failed. The owned native version page and CDP not-restored
reasons independently show that the current driver disables BFCache. A normal
history reload is recorded separately, never relabeled as cache restoration.
`first-script/managed_history.py` retains this failure and calibration attempts;
it does not silently remove driver flags or invoke Frame APIs after a real
BFCache restoration.

[The unregistered launch experiment](managed-bfcache-optin70-observations.json)
removes only that driver default in an isolated source overlay. Its four Glint
geometry/input phases pass with the existing Playwright owner screenshot and
six retained documents rechecked afterwards; the full 18-check runtime baseline
also passes in a complete tracked-source overlay. The active manager is unchanged.

An independent CDP screenshot does not necessarily inherit the owner's emulation
parameters: pinned Chromium `content/browser/devtools/protocol/page_handler.cc`
reads its own `emulation_handler_` in `CaptureScreenshot`. The control observed
390×844 mobile pixels both before and after history, while the owner API returns
1170×2532. Raw independent-session failures are retained separately, not silently
used to fail or admit the owner API.

[Repeated Recorder capture](managed-bfcache-recorder70-observations.json) passed
3/4 phases, then 2/4 with bridge tracing: trusted post-clicks sometimes never
enter Python despite active JS markers, without warnings. The same loss appeared
in all four stock156 control phases. This blocks launch integration despite the geometry result.
The probe attaches to an already-loaded page; complete UI-started draft replay
and all-frame input are still separate requirements.

[Source-bound calibration](stock156-capture-observations.json) covers two phases,
all eight contexts, exact request-header availability and three failure controls:
existing evidence, unknown runtime and fixture-server failure. Raw host values,
launch paths and profiles remain on D:, not in this public summary.

This is **one measured Windows control**, not a multi-device dataset. Fonts,
Audio quality, headed/native-manager configurations and mobile environments
still require their own combined captures. A future versioned cohort selector
must reject unverified hardware combinations and preserve profile ownership.
Profile generation, another OS, Glint policy execution, ordinary-user realism
and production admission remain explicitly false.

The separate [screen consistency finding](SCREEN_EMULATION.md) records failing
desktop/mobile manager configurations on the stock control and defines the next
native repair gates. A working no-emulation control is not substituted as a fix.
