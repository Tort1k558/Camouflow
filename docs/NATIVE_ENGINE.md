# Glint: status and limitations

Glint is the independent Chromium engine developed for CamouFlow. It is
experimental, not a released replacement for Camoufox or CloakBrowser.

| Capability | State |
| --- | --- |
| Independent persistent runtime, profiles and owner exclusion | Implemented; Windows baseline runtime tested |
| Proxy/permissions, Recorder/automation and observed diagnostics | Windows baseline runtime tested |
| Local checksum-verified bundles, activation and rollback | Implemented; development delivery tested |
| Current linked Windows browser | 001-062; incremental j4 build, 29m02s. Full continuation v2 passed eight gates / 160 checks; first font NetworkError remains unexplained |
| Hardware/font/WebRTC/automation/headless policies | Explicit diagnostic flags tested; not automatic manager admission |
| Profile keys, partition codec and browser-owned key service | Native identity/context/transport/handoff fixtures passed on stated historical builds; see per-build matrix |
| Document/worker startup and readiness | Dedicated/shared/service, classic/module and nested-worker checks recorded per build; not universal page compatibility |
| Glint product name and existing CamouFlow logo in Chromium | Compiled 001-062 icons, ProductName and version-page branding verified; not all cached shortcuts/taskbar surfaces |
| Windows text rendering | 001-062: five native cases and six-configuration, two-start, eight-scope diagnostic passed. Manager saves drafts; launch admission remains closed |
| Native Canvas/WebGL/audio protection | Experimental combined/readback checks recorded per build; fidelity limitations remain. Not advertised as production-active |
| WebGPU protection | Incomplete; metadata diagnostics do not prove protected rendering/readback |
| Linux/macOS own-fork runtime | Deferred; not released |
| Mobile Web | Desktop viewport/touch emulation, not real Android/iOS |
| Signed online engine updates | Not implemented |

The manager uses the Glint display name while technical engine IDs, profile
schemas, cryptographic domains and historical build paths remain compatible.
Nonempty privacy requests still require verified runtime capability admission;
UI configuration does not prove successful activation.

Results and unresolved failures are linked in the
[per-build test matrix](GLINT_TEST_MATRIX.md). Older external-site observations
must not be attributed to the current binary without a new run.

## Developer entry points

- [Windows build guide](../native/BUILDING.md)
- [Architecture](../native/ARCHITECTURE.md)
- [Verification requirements](NATIVE_VERIFICATION.md)
- [Prepared branding](../native/branding/README.md)
- [Unapplied development patches](../native/drafts/README.md)

No CAPTCHA score, detector-site result or isolated successful probe proves
undetectability. Current development artifacts are unsigned and require an
upstream security review/rebase before production engine admission.
