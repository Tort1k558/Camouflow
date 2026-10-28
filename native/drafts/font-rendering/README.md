# Windows font rasterization candidate

**Registered as patch 0062. The reviewed Chromium 148 / 001-062 managed package
has experimental `font-rasterization` admission; 001-061 is a retained rollback
baseline, not the latest verified package. Chromium 156 is not runtime-verified.**

Current admission is restricted to the exact package and manifest hashes in
`app/core/native/admission.py`, with full payload verification before launch.
The earlier admission-work checklist below is historical; remaining compatibility
limits and newer text-tuning research are in the
[test matrix](../../../docs/GLINT_TEST_MATRIX.md). Nine bounded gamma/contrast
presets now have experimental manager admission for that exact reviewed 148
package, using upstream text-rendering switches with Native rasterization only.
See [configuration and limits](../../../docs/NATIVE_ENGINE.md#windows-text-tuning).
This does not admit Chromium 156 or combinations with non-native rasterization.

This candidate changes actual Windows text-rendering parameters, not Canvas
readback bytes, JavaScript APIs, installed font names, OS identity or GPU strings.
It is an alternative rendering experiment, **not a repair of the existing
Canvas readback candidate** or a promise of undetectable/unique fingerprints.

| Mode | Antialiasing | Fractional positioning | Pixel order |
| --- | --- | --- | --- |
| `native` | Host value | Host value | Host value |
| `aliased` | Off | Off | None |
| `grayscale` | On | On | None |
| `cleartype-rgb` | On | On | RGB |
| `cleartype-bgr` | On | On | BGR |

Patch 0062 preserves gamma, contrast, hinting, embedded bitmap and autohinter
fields. The separate manager text-tuning option changes gamma/contrast through
upstream Chromium switches, without modifying this patch.
The explicit switch is validated before copying it to renderer commands.
Windows cached font parameters apply the selected mode before Skia cache setup;
upstream renderer preferences already carry these parameters into Blink.
Cache refresh reapplies the same command-line choice. No host registry changes.

Explicit non-native modes also initialize Blink's antialiasing/LCD settings on
the main renderer thread after Blink initialization and before compositor/worker
startup. This avoids depending solely on a document's later preference update.
The `native` mode does not override this startup behavior. Actual before-script
worker effects still require execution of the candidate.

`windows_font_rasterization_candidate.patch` is the canonical source of registered
`0062-native-windows-font-rasterization.patch`. It includes the policy, Windows cache
hook, renderer forwarding and Windows-only build/test registration. Its five
GTest definitions cover parsing, invalid names/enums, native preservation, field
bounds and idempotence. All **five executed and passed** in Chromium's
`gfx_unittests` target; they do not prove actual renderer/worker effects.

## Current evidence

- Actual-source preparation and `git apply --check` passed on source 001–060.
- Two isolated C++ type checks passed with actual generated Chromium target
  flags: Windows parameter hook and policy fixtures. Active sources, core,
  compiler/target inputs and GN remained unchanged.
- Private proof: `windows-font-rendering-cpp-001-060-v1/proof.json` on D.
- Renderer switch forwarding passed an isolated C++ syntax/type check with the
  actual `content/browser` target flags on source 001–061. Active source,
  compiler and target inputs remained unchanged. Chromium's inherited DEPS
  checker accepted the added include with no violations.
- Private proofs: `font-renderer-forwarding-001-061-v1/proof.json` and `deps.json`
  on D. These checks do not bind or validate the concurrently built executable.
- Three Python preparation/replay/refusal tests passed.
- The expanded six-file candidate prepares and apply-checks on source 001–061.
  Its renderer initialization unit passed an isolated C++ syntax/type check with
  actual renderer-target flags; the three added includes passed inherited DEPS.
  Active source, compiler and target inputs stayed unchanged. Private evidence:
  `font-renderer-startup-001-061-v2/proof.json` and `deps.json` on D.
  Earlier C++ evidence above covers the preceding revision, not execution of
  this expanded package.
- The five selected native fixtures passed after an incremental j4
  `gfx_unittests` build in 8m15.14s / 138 steps. Browser core, GN, receipt and source
  postguards passed. Proof: `windows-font-policy-001-062-v1.json` and raw
  `-tests.json` on D.
- Browser linked at j4 in **29m02.24s**, 52 executed steps, with an exact 62-patch
  receipt (`browser-build-001-062-v1.json` on D). The compiled mode comparison
  below passed; fresh full runtime regression and broader compatibility remain
  separate gates.

The first 001–062 full runtime suite passed seven gates but failed the existing
font-selection gate with a font-download `NetworkError`. Two attributed repeats
passed the unchanged assertions (42 checks each), but the original cause remains
unresolved. The failure is retained and is not declared fixed by rerunning.

Regenerate only from a pre-0062 source tree into a fresh output outside Chromium;
the preparer intentionally refuses already-applied policy files:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_native_font_rendering.py --source D:\CamouFlowNative\chromium\src --output D:\CamouFlowNative\windows-font-rendering-new.patch
git -C D:\CamouFlowNative\chromium\src apply --check D:\CamouFlowNative\windows-font-rendering-new.patch
```

## Rendering observations

`scripts/native_font_rendering.py` measures three requested CSS font families on
opaque and transparent surfaces: text metrics, nonblank pixel coverage, repeated
readback, PNG encode/decode and direct ImageBitmap copies. It reports hash/metric
differences, not whether they represent a realistic identity. Requested family
names may resolve to fallback fonts; this is not installed-font verification.

Reuse `scripts.native_canvas_formats.WORKER_READ` for the dedicated-worker probe
and `app.core.native.canvas_fidelity` for raw-image controls. Raw-pixel fidelity
and colour/storage-format checks remain separate from text-hash changes.

An actual feature-off 001–060 diagnostic completed six cases in each of document
and dedicated worker, with no observed readback/PNG/ImageBitmap differences and
matching measurements between these two scopes. The opaque palette had zero
changed pixels in each scope. Core hashes stayed unchanged and cleanup completed.
Private evidence: `font-rasterization-probe-001-060-v1/report.json` on D.
Only temporary diagnostic profiles were placed on C; the executable remained on
D. This is fixture validation, **not execution of the rendering candidate**,
full lifecycle admission, colour/HDR fidelity, DOM/SVG or other-worker coverage.

A separate four-scope control then measured document, dedicated, shared and
service workers on feature-off Glint 001–060 and checksum-bound stock Chromium
148.0.7778.96. Each scope matched its stock counterpart. Generic `monospace`
resolved differently in shared/service workers versus document/dedicated workers
in **both** engines; named Arial/Times New Roman observations matched across
scopes. Do not mistake this upstream baseline for a Glint regression or require
unconditional cross-scope equality when the baseline differs. Private reports:
`font-worker-scopes-001-060-v1/report.json` and
`font-worker-scopes-stock-148-v1/report.json` on D. These are observations of the
unprotected baseline, not candidate execution or a complete font-policy test.

`scripts/native_font_contexts.py` adds owned first-script fixtures for eight
scopes: document, iframe and classic/module dedicated, shared and service workers.
Text measurement begins in the parser (`readyState=loading`) or worker global
script before any measurement request. Remaining asynchronous observations may
settle after that initial script; this does not claim every read precedes events.
Each scope retains text, raw-image fidelity and colour/storage-format results,
including observed API errors rather than converting them into compatibility PASS.

Actual calibration on the separate 001–061 rollback executable completed all
eight scopes: **48 text cases, 24 raw-image cases and 32 format cases**, with zero
format-operation errors. Startup markers, core stability and resource cleanup
were checked. Evidence: `font-first-script-001-061-v1/report.json` on D. Temporary
profiles were on C. This validates the fixture **without patch 0062 enabled**;
it is not the five-mode candidate comparison, restarts, DOM/SVG text, HDR fidelity
or fingerprint acceptance.

The expanded fixture now includes `scripts/native_canvas_hdr.py`: known float16
inputs below zero/above one, opaque/partial alpha, repeat reads and PNG-to-sRGB8
conversion observations. Matching-version stock Chromium and feature-off Glint
001–061 matched in document/dedicated-worker controls. Opaque inputs were exact;
four RGB channels under zero alpha were discarded in both engines. PNG conversion
is observed separately, **not asserted lossless or colourimetrically correct**.
Private proof: `canvas-hdr-controls-001-061-v1/report.json` on D.
Expanded first-script calibration also completed all eight scopes, including
**32 HDR colour/alpha cases**, with unchanged core and completed cleanup:
`font-first-script-001-061-v2/report.json` on D. This is still feature-off fixture
calibration, not a 0062 mode/restart result.

## Mode/restart comparison

After the 001–062 browser build finishes, run the compiled-candidate verifier:

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_font_rendering.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --output D:\CamouFlowNative\font-rendering-new
```

It requires an idle builder, matching core/0062 receipt and fresh private output.
It runs feature-off plus all five named modes, each with two starts of its own
persistent profile and all eight first-script scopes. No old readback protection
is enabled. Restart drift, raw-image metric changes, newly broken formats/exports,
unstable repeated reads and a changed `native` baseline fail the experiment.
Unavailable colour/storage or HDR operations fail even when the control is also
unavailable; changed HDR values/conversion results are not hidden by equal restarts.
Aliased/grayscale must produce a measured pixel difference; RGB/BGR are not
required to differ when normal rendering suppresses LCD text. Errors are retained
across modes, but retained browser resources stop additional launches. Core,
receipt, packs and probe sources are guarded after execution.

The compiled comparison **passed** on all six configurations/two starts/eight
scopes: `font-rendering-001-062-v1/report.json` on D. No cleanup, restart,
raw-image, format or HDR differences from required controls; all input and
screenshot guards passed. Aliased versus grayscale pixel effects were observed
in every scope. `native` matched feature-off. ClearType RGB matched this host's
baseline; BGR changed opaque on-screen Canvas but not the Offscreen samples.
This does not yield five distinct profile identities. Off/aliased/grayscale
screenshots were inspected: aliased visibly degrades smoothness and changes some
layout metrics, so modes must not be randomly assigned as an authenticity claim.
A pass demonstrates this fixture's effects/coherence, not visual quality, true
OS/GPU emulation, fingerprint realism or release/capability admission.

### Visible DOM/SVG/Canvas samples

`scripts/native_font_visuals.py` draws the same three requested fonts on actual
DOM, SVG and opaque on-screen Canvas surfaces. The mode verifier saves one
checksum-bound PNG per mode/start, retains layout/pixel observations and rejects
restart drift or a changed `native` baseline. Non-native changes are reported,
not automatically judged visually acceptable. Screenshots still need inspection.

The feature-off 001–061 scene was actually captured and visually inspected; its
measurements matched checksum-bound stock Chromium 148.0.7778.96. Arial/Times
Canvas text widths differed slightly from DOM/SVG in **both** engines, while
monospace matched. Do not force unconditional metric equality or call that
baseline a Glint defect. Private calibration proofs/screenshots:
`font-visuals-001-061-v1/` and `font-visuals-stock-148-v1/` on D. Requested font
names and successful rendering do not independently prove installed-family
identity. For actual 0062 mode observations, see the compiled comparison above;
the 001–061 baseline itself is not candidate validation.

## Admission work

The package is registered/linked; five native units and the initial eight-scope
mode/restart/raw/HDR/visible-text comparison passed. Continue with the fresh full
runtime regression, ordinary sites/editors, broader fonts/emoji/web fonts,
cross-site/process and nested worker cases, display/GPU paths and controlled
clone/restore integration. Do not promote manager controls or capability admission
from this initial fixture alone. Combining the old readback candidate is a
separate test and does not fix that candidate's failures automatically.

ClearType may be suppressed by normal rendering rules on transparent surfaces;
RGB/BGR need not produce distinct Canvas output. Aliased rendering can visibly
degrade text. Do not randomly assign modes or expose selectable manager controls
until measured behavior, compatibility, profile persistence and platform-specific
capabilities are established. This does not emulate Linux/macOS/mobile hardware.
