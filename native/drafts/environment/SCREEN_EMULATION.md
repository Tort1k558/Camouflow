# Cross-process screen consistency: next native integration contract

**Open compatibility finding, not an implemented patch or Glint runtime result.**
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

Pinned Chromium 156 separates physical/compositor screen data from the main
widget's emulated values:

- `EmulationHandler::UpdateDeviceEmulationState()` applies device emulation to
  main frames. `WebFrameWidgetImpl::EnableDeviceEmulation()` requires a main frame.
- `WebRemoteFrameImpl::InitializeFrameVisualProperties()` passes
  `GetOriginalScreenInfos()` to the remote child, not the emulated screen set.
- `WebFrameWidgetImpl::DidUpdateVisualProperties()` also propagates original
  screen info to remote frames. Original scale is used in compositor/layout paths.

These are relevant code paths, **not proof of the complete defect's cause**.
Replacing every original screen with the emulated screen risks double DPR,
incorrect child geometry, raster scale, hit testing and screenshot coordinates.
Attaching a full main-frame emulator to every iframe is not acceptable either.

## Coherent implementation package

1. Reproduce on the fully gated Glint 001–067 runtime with identical options;
   preserve the stock controls and unmodified no-emulation behavior.
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
not satisfy this contract. Active 001–067 sources and test builds stay unchanged.
