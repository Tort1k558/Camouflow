# Glint: status and limitations

Glint is the independent Chromium engine developed for CamouFlow. It is
experimental, not a released replacement for Camoufox or CloakBrowser.

| Capability | State |
| --- | --- |
| Independent persistent runtime, profiles and owner exclusion | Implemented; Windows baseline runtime tested |
| Proxy/permissions, Recorder/automation and observed diagnostics | Windows baseline runtime tested |
| Local checksum-verified bundles, activation and rollback | Implemented; development delivery tested |
| Hardware/font/WebRTC/automation/headless policies | 001-010 development baseline tested; not automatic manager admission |
| Profile keys, partition codec and browser-owned key service | 001–015 Windows browser linked; runtime verification in progress, not admitted |
| Real BrowserContext and readiness tests | Prepared, unapplied; not compiled/run |
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
