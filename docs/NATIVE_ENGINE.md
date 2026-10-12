# Glint: status and limitations

Glint is the independent Chromium engine developed for CamouFlow. It is
experimental, not a released replacement for Camoufox or CloakBrowser.

| Capability | State |
| --- | --- |
| Independent persistent runtime, profiles and owner exclusion | Implemented; Windows baseline runtime tested |
| Proxy/permissions, Recorder/automation and observed diagnostics | Windows baseline runtime tested |
| Local checksum-verified bundles, activation and rollback | Implemented; development delivery tested |
| Hardware/font/WebRTC/automation/headless policies | 001-027 passed all eight Windows runtime gates / 160 checks; not automatic manager admission |
| Profile keys, partition codec and browser-owned key service | Included in linked 001-027; native key/context tests passed; not protected Canvas admission |
| Readiness callbacks | Included in linked browser; 43 native key/service cases passed |
| Real BrowserContext tests | All 20 cases passed; combined context/delivery run passed 54 cases |
| Document/worker policy endpoints and worker consumer | All 34 native cases passed; document first-script bootstrap still missing |
| Dedicated/shared/service-worker startup gates | Linked 001-027 passed 40 classic/module startup, restart, shared-client and rejection checks under explicit diagnostic flags |
| Blink worker seed ownership | Four C++ handoff cases registered; strict worker-handoff runner prepared, linked execution pending |
| Glint product name and existing CamouFlow logo in Chromium | Branding patch prepared; old binary not rebranded |
| Native Canvas/WebGL/WebGPU/audio protection | Incomplete; not advertised as active |
| Linux/macOS own-fork runtime | Deferred; not released |
| Mobile Web | Desktop viewport/touch emulation, not real Android/iOS |
| Signed online engine updates | Not implemented |

The manager uses the Glint display name while technical engine IDs, profile
schemas, cryptographic domains and historical build paths remain compatible.
Nonempty privacy requests still require verified runtime capability admission;
UI configuration does not prove successful activation.

## Developer entry points

- [Windows build guide](../native/BUILDING.md)
- [Architecture](../native/ARCHITECTURE.md)
- [Verification requirements](NATIVE_VERIFICATION.md)
- [Prepared branding](../native/branding/README.md)
- [Unapplied development patches](../native/drafts/README.md)

No CAPTCHA score, detector-site result or isolated successful probe proves
undetectability. Current development artifacts are unsigned and require an
upstream security review/rebase before production engine admission.
