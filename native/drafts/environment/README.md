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

The current mode is explicitly **headless automation control, without viewport
emulation**. The default Playwright viewport produced different screen values
in the cross-origin frame during calibration; that failed run is retained.
The headless screen is not a measurement of the physical monitor or an ordinary
desktop-user identity. Successful owned profiles are removed; failed evidence
and profiles remain outside the repository. Nothing is uploaded automatically.

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
