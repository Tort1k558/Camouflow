# Cross-process screen consistency: next native integration contract

**Open compatibility finding, reproduced on both stock156 and raw Glint 001–067.**
The [Glint runtime capture](glint67-screen-consistency-observations.json) used
the separately preserved browser, its complete 67-patch checkpoint/receipt and
unchanged manager context options. Both initial and restarted desktop/mobile
captures reproduced the table below; the no-viewport control passed twice.
All source/core/receipt/asset postguards passed. This is one headless Windows
host, not a physical-device cohort, installed-payload check or a fix.

The [stock156 control](stock156-screen-consistency-observations.json) collected
all three public CLI modes twice, with unchanged runtime and source hashes:

| Exact launch mode | Main document | Cross-origin frame | Initial + restart |
| --- | --- | --- | --- |
| Manager desktop options | 1366×768, DPR 1 | 800×600, DPR 1 | Inconsistent |
| Manager Mobile Web options | 390×844, DPR 3 | 800×600, DPR 1 | Inconsistent; touch remains enabled |
| Explicit no viewport emulation | 800×600, DPR 1 | 800×600, DPR 1 | Consistent headless control only |

The last mode is **not a fallback or a proposed fix**: dropping requested viewport,
screen or DPR would change the product contract. Mobile Web must remain honest
desktop Chromium emulation, not an invented Android/iOS runtime.

Reproduce with `scripts.capture_native_environment --mode manager-desktop` or
`--mode manager-mobile-web`, the pinned executable and a fresh D: work directory.
The public tool preserves both failed phases and their full observations. Initial
driver-default controls are also retained privately; they are not Glint results.

## Source evidence, not a one-line repair

### Source package 0069: selected for build, not browser-verified

[`screen-inheritance69.patch`](screen-inheritance69.patch) prepares a linked
19-file change against exact 001–068. The candidate manifest/checkpoint now
selects 001–069; the [preparation record](screen-inheritance69-preparation.json)
is the earlier unselected snapshot and remains unchanged. The package is
**not C++-compiled or runtime-verified**. The `screen-metrics` batch group
requires all nine native cases. The complete 001–068 runtime is preserved for
rollback; selection alone does not update the browser or its receipt.

- Browser-owned main-frame metrics feed an optional logical screen snapshot in
  widget visual properties, including their initial creation path. Remote-frame
  geometry continues to carry the original physical screen information.
- Main-frame emulation and browser snapshot calculation share the existing
  screen/viewport calculation, rather than maintain divergent formulas.
- DOM/CSS screen reads and child DPR use widget-scoped logical state; compositor,
  screenshot and input geometry keep the physical data. No JS getter patch or
  process-global identity cache is introduced.
- Clearing uses an absent snapshot. The draft also wires media-query, screen and
  orientation notifications, preserves native GPU/display restrictions and adds
  nine C++ cases for calculations, copy/isolation and nullable IPC validation.

Apply-check against the untouched active 001–068 source passed. The pinned Mojom
parser and native/Blink/shared typed C++ binding generators passed in a separate
D: output directory. **The nine C++ cases have not run.** Initial-script delivery
on process swaps, nested roots/BFCache, zoom/text-scale behavior, event ordering,
render/input compatibility and the complete linked-browser matrix below remain
required. Source preparation is not a screen/DPR fix result.

Pinned Chromium 156 separates physical/compositor screen data from the main
widget's emulated values:

- `EmulationHandler::UpdateDeviceEmulationState()` applies device emulation to
  main frames. `WebFrameWidgetImpl::EnableDeviceEmulation()` requires a main frame.
- `WebRemoteFrameImpl::InitializeFrameVisualProperties()` passes
  `GetOriginalScreenInfos()` to the remote child, not the emulated screen set.
- `WebFrameWidgetImpl::DidUpdateVisualProperties()` also propagates original
  screen info to remote frames. Original scale is used in compositor/layout paths.
- `ChromeClientImpl::GetScreenInfos()` reads the local-root widget, while
  `LocalFrame::DevicePixelRatio()` uses inspector scale times layout zoom.
  Changing screen metadata alone therefore does not repair the DPR contract.

These are relevant code paths, **not proof of the complete defect's cause**.
Replacing every original screen with the emulated screen risks double DPR,
incorrect child geometry, raster scale, hit testing and screenshot coordinates.
Attaching a full main-frame emulator to every iframe is not acceptable either.

## Coherent implementation package

1. Raw Glint 001–067 reproduction is complete with identical manager options;
   preserve both stock/Glint failed captures and unmodified no-emulation controls.
2. Trace initial creation and updates through frame visual properties,
   `CrossProcessFrameConnector`, widget visual properties and DOM/CSS consumers.
   Keep original physical/compositor data distinct from inherited logical
   screen information. Reuse existing frame-tree ownership and IPC validation.
3. Deliver logical data before a child's first script. Do not create a separate
   global process/profile screen cache: independent pages, popups and other
   profiles must not inherit a foreign page's emulation state.
4. Cover explicit updates and clearing, navigation/process swap, nested remote
   frames, renderer recreation and BFCache restore. Clearing must restore the
   real screen and update dependent media queries/events.
5. Gate the complete change with native serialization/lifecycle tests and the
   actual browser matrix below before registration or admission. No JS getter
   replacements, retries until PASS, cross-origin access tricks or hidden flags.

## Required linked-browser checks

### Main-root DPR is part of the same contract

The [preserved 001–068 first-script baseline](screen68-first-script-observations.json)
also observed main Mobile Web DPR **3 initially, 1 after nested local roots**,
on both persistent phases. Its four desktop/mobile phases captured all six
document contexts, but the whole control matrix remained incomplete after a
fixture click fell outside the native-control viewport. All results and errors
are retained; this is not 0069 browser execution or a complete fixture admission.

The [subsequent complete baseline](screen68-first-script-complete-observations.json)
finished all six phases and six document contexts. Both native-control phases
passed; the four manager desktop/mobile phases reproduced the screen/DPR
failures. Trusted clicks and screenshot dimensions passed. Only fixture HTML
escaping/layout was corrected; browser options and deadlines were unchanged.
The exact [fixture sources](first-script/server.py) and [first-script sampler](first-script/sample.js)
are included. This validates the controlled baseline fixture, not the pending
0069/0070 engine changes; the earlier incomplete record remains unchanged.

### Reproduce with the public command

```powershell
.venv\Scripts\python.exe native/drafts/environment/first-script/verify.py `
  --executable D:\Glint156Candidate\preserved-runtime68-20261030-v1\runtime\chrome.exe `
  --work-dir D:\GlintManagerQA\screen-first-script-new `
  --checkpoint 001-068
```

The work directory must be fresh. Select a preserved runtime outside the active
Chromium source tree; the command never copies a binary or changes requested
settings automatically. It verifies the exact checkpoint prefix, source-build
receipt, core hashes and reported Git revision, then captures all three modes
and both persistent phases. It retains every failure, screenshots and source/
core/receipt postguards. Pages may contact only the owned loopback fixture.
A complete reproduction of the known 001–068 baseline returns exit code **1**
with `measurement_complete` true: completing the diagnostic is not the same as
passing screen consistency. The first public-command attempt hit the unchanged
10-second navigation deadline during native-control startup while compilation
was active; its earlier four manager phases and postguards were retained.
That attempt is **incomplete**, not a passing control or a diagnosed engine fix.
Failure reports include lifecycle events, pending request URLs and frame URLs;
the command does not increase deadlines or retry a failed phase.
Early child viewport sizes may be zero before layout/remote visual-property
delivery. The pinned `LocalDOMWindow::GetViewportSize()` forces layout for the
main frame and local parents, not for a remote parent. Such measured zeros are
retained and listed in `first_viewport_pending`; they are never replaced by
parent geometry. Main-frame and settled viewport sizes must remain positive.
This command covers six document contexts, not workers, BFCache or complete
package/privacy admission.

The [completed public-command run](public-first-script-cli-observations.json)
reproduced the same four failed manager phases and two passing controls with
source/core/receipt postguards and no owned Chrome processes left. Earlier
incomplete prototypes are recorded separately, including the observer callback
defect and the overstrict early-viewport validation. No deadline or requested
browser setting was changed to obtain the completed baseline.

## Additional lifecycle collector and stock control

[`first-script/lifecycle.py`](first-script/lifecycle.py) collects two pages with
explicit CDP metrics, update/clear, cross-site navigation and cache restoration.
This deliberately mixes a separate CDP controller with Playwright-owned pages;
it is **not the manager's context-options configuration path**.

The [paired calibration](screen-lifecycle68-calibration-observations.json) ran
preserved Glint 001–068 and official stock156 at the same Git revision. All
**78 screen/viewport/CSS snapshots matched**. Both runs completed all seven
stages and restored all **six documents** from BFCache, but both also failed the
same requested-state/independence checks. These failures are not attributed to
Glint: the next control must use manager-owned context options and supported
viewport changes, before changing native policy ownership based on this stress.

BFCache is measured with native `Page.frameNavigated` type
`BackForwardCacheRestore` plus retained `pageshow.persisted` evidence from every
document. The collector uses CDP history navigation and origin-checked owned
`postMessage` responders after restoration, not Playwright Page/Frame methods.
The [Playwright API explicitly does not support BFCache navigation](https://playwright.dev/python/docs/api/class-page#page-go-back);
the initial unsupported `go_back()` timeout is retained, not declared an engine
failure. [Chrome's event guidance](https://web.dev/articles/bfcache) explains why
`pageshow.persisted`, not an ordinary back navigation, is the cache signal.

The cacheable loopback response and removal of the driver's BFCache-disable
argument are explicit diagnostic settings, not product defaults. PID-level
process-swap proof, post-restore screenshot/input, actual 0069/0070 binaries,
protected workers/surfaces and installed-package admission remain open.

The frozen 0069 draft's logical DPR accessor still restricts its override to
subframes, leaving the main root on Page-global inspector state. The queued
[`main-dpr70.patch`](main-dpr70.patch) removes that restriction and adds three
Blink simulation cases. [Preparation record](main-dpr70-preparation.json).
Read-only apply-check against active 001–069 passed; the live build was not
modified. The correction is **unselected, uncompiled and runtime-unverified**.
Neither child-only consistency nor a passing pure screen-calculation test can
admit the complete package without stable main-root DPR.

| Contract | Checks |
| --- | --- |
| First-script consistency | Same-origin, cross-origin, inherited and nested frames; no late `framenavigated` repair |
| Web-facing identity | Screen/available rect/depth, DPR, orientation, touch and resolution/device-size media queries |
| Correct geometry | Child viewport keeps its own size; parent geometry is not copied into iframe layout |
| Rendering/input | CSS and canvas sizes, screenshots, click coordinates, scrolling, iframe clipping and text |
| Updates/disable | Change dimensions/DPR/orientation; clear override; compare untouched baseline |
| Ownership | Two independent pages and two profiles with different settings; new child and new renderer |
| Restart/lifecycle | Persistent restart, navigation, nested frames, crashes and BFCache |
| API boundaries | Workers keep absent screen/DPR APIs; OffscreenCanvas pixel dimensions are not silently rescaled |

Until those gates run, keep `screen_inheritance_fixed` and profile/cohort
admission false. Source preparation and a passing serialization test alone do
not satisfy this contract. Prepare screen changes in isolated overlays; do not
modify source files used by a live build or verifier.
