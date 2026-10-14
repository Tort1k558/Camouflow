# Windows font rasterization candidate

**Registered/applied as patch 0062; browser binary remains verified 001–061.
No new capability admitted.**

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

Gamma, contrast, hinting, embedded bitmap and autohinter fields are preserved.
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
- Browser linking and actual visual/runtime effects are **not yet verified**.

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
Aliased/grayscale must produce a measured pixel difference; RGB/BGR are not
required to differ when normal rendering suppresses LCD text. Errors are retained
across modes, but retained browser resources stop additional launches. Core,
receipt, packs and probe sources are guarded after execution.

The verifier is prepared/tested, **not yet executed on the compiled candidate**.
A pass demonstrates this fixture's effects/coherence, not visual quality, true
OS/GPU emulation, fingerprint realism or release/capability admission.

## Admission work

The reviewed package is registered and its forwarding/startup C++/DEPS checks
passed in isolation, and the five policy fixtures passed in Chromium. Link the
browser and compare actual modes in
document/iframe/dedicated/shared/service workers, before-script and restart runs.
Check Canvas/DOM/SVG text and ordinary page rendering with real installed fonts.
Verify raw pixel fidelity, P3/float16 APIs, PNG/ImageBitmap/drawImage and screenshots
without the old Canvas readback candidate enabled. Combining both candidates is
a separate test and does not fix the old candidate's failures automatically.

ClearType may be suppressed by normal rendering rules on transparent surfaces;
RGB/BGR need not produce distinct Canvas output. Aliased rendering can visibly
degrade text. Do not randomly assign modes or expose selectable manager controls
until measured behavior, compatibility, profile persistence and platform-specific
capabilities are established. This does not emulate Linux/macOS/mobile hardware.
