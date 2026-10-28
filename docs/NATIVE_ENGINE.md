# Glint: status and limitations

Glint is the independent Chromium engine developed for CamouFlow. It is
experimental, not a released replacement for Camoufox or CloakBrowser.

| Capability | State |
| --- | --- |
| Independent persistent runtime, profiles and owner exclusion | Implemented; Windows baseline runtime tested |
| Proxy/permissions, Recorder/automation and observed diagnostics | Windows baseline runtime tested |
| Local checksum-verified bundles, activation and rollback | Implemented; development delivery tested |
| Current linked Windows browser | 001-062; incremental j4 build, 29m02s. Full continuation v2 passed eight gates / 160 checks; first font NetworkError remains unexplained |
| Hardware/font/WebRTC/automation/headless policies | Experimental manager activation for the reviewed 001-062 package only; complete manifest/payload checked before each policy launch |
| Profile keys, partition codec and browser-owned key service | Native identity/context/transport/handoff fixtures passed on stated historical builds; see per-build matrix |
| Document/worker startup and readiness | Dedicated/shared/service, classic/module and nested-worker checks recorded per build; not universal page compatibility |
| Glint product name and existing CamouFlow logo in Chromium | Compiled 001-062 icons, ProductName and version-page branding verified; not all cached shortcuts/taskbar surfaces |
| Windows text rendering | Five native cases; standalone and combined rendering checks passed. Available experimentally in the reviewed package; not five distinct identities |
| Native Canvas/WebGL/audio protection | Experimental combined/readback checks recorded per build; fidelity limitations remain. Not advertised as production-active |
| WebGPU protection | Incomplete; metadata diagnostics do not prove protected rendering/readback |
| Linux/macOS own-fork runtime | Deferred; not released |
| Mobile Web | Desktop viewport/touch emulation, not real Android/iOS |
| CSS page preferences | Profile-configurable color scheme, motion, forced colors and contrast; checked on stock/Glint 148, not yet 156 |
| Signed online engine updates | Not implemented |

The manager uses the Glint display name while technical engine IDs, profile
schemas, cryptographic domains and historical build paths remain compatible.
Nonempty privacy requests still require verified runtime capability admission;
UI configuration does not prove successful activation.
The client pins one reviewed archive and its exact manifest in `admission.py`;
it does not trust a release's `native_patch_runtime_verified` boolean. Modified,
unknown or standalone builds remain blocked for non-native policies. This local
review mechanism is not a signed online update catalog or general fork admission.
The `identity` capability here is the native headless-UA policy, not a complete
device-passport or profile-key/Canvas/GPU privacy admission.

Results and unresolved failures are linked in the
[per-build test matrix](GLINT_TEST_MATRIX.md). Older external-site observations
must not be attributed to the current binary without a new run.

## Page preferences

Glint configuration → **Page preferences** controls the context's CSS media
preferences. Defaults preserve the existing launch options. Explicit values are
validated, stored with browser defaults or profile overrides and passed through
the existing [persistent-context API](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).
No JavaScript APIs are replaced, and these preferences do not simulate an OS,
GPU or a complete device fingerprint.

Example profile overrides:

```json
{"color_scheme":"dark","reduced_motion":"reduce","forced_colors":"none","contrast":"more"}
```

Each field accepts an empty string for default behavior. Other supported values:
`light`/`dark`, `no-preference`/`reduce`, `none`/`active`, and
`no-preference`/`more`, respectively. Invalid values fail rather than falling back.
The health diagnostic checks configured preferences against actual `matchMedia`
results. These are window/frame media queries, not a worker fingerprint control.

## Developer entry points

- [Windows build guide](../native/BUILDING.md)
- [Architecture](../native/ARCHITECTURE.md)
- [Verification requirements](NATIVE_VERIFICATION.md)
- [Prepared branding](../native/branding/README.md)
- [Unapplied development patches](../native/drafts/README.md)

No CAPTCHA score, detector-site result or isolated successful probe proves
undetectability. Current development artifacts are unsigned and require an
upstream security review/rebase before production engine admission.
