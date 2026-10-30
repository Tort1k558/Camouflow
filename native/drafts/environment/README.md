# Measured reference environments

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
