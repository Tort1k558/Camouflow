# Glint branding

Glint is the product name of CamouFlow's own Native browser. Technical engine
identifiers (`native`, `camouflow-native`), profile schemas, executable paths and
Chrome-compatible UA policy remain unchanged. Upstream copyright/credits remain
intact. Camoufox and CloakBrowser are not renamed.

`../patches/0060-native-glint-branding.patch` is the registered branding patch for the pinned Chromium
revision. It changes product/installer names, legacy product names in hardware,
font and identity diagnostics, the Windows main/app-list icons, the shared
product SVG and six PNG sizes, and increments the Windows profile
shortcut icon version. The ICO is copied exactly from the existing `logo.ico`;
PNGs are rasterizations of `app/qml/theme/brand.svg`, not generated artwork.
Special incognito/document/PDF icons and other platform packaging are unchanged.

The generator is public and does not modify the Chromium checkout:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_glint_branding.py --source D:\CamouFlowNative\chromium\src --output D:\CamouFlowNative\glint-branding.patch --report D:\CamouFlowNative\glint-branding.json
git -C D:\CamouFlowNative\chromium\src apply --check D:\CamouFlowNative\glint-branding.patch
```

Verify the public candidate without changing the source checkout:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_glint_branding --source D:\CamouFlowNative\chromium\src --patch C:\Users\lolod\Desktop\camouflow-app\camouflow\native\patches\0060-native-glint-branding.patch --output D:\CamouFlowNative\branding-replay-new
```

The output directory must not exist. The gate regenerates the expected assets,
applies the public patch in a disposable source copy, checks every resulting
asset hash, reverses it and checks original-copy and real-source hashes. A
different product/logo, extra source path or changed source rejects the gate.
This replay passed against actual source 001–059 on 14 October 2026; private
proof is `branding-replay-001-059-v5/report.json` on D. Run this gate against
the pre-branding source state: regeneration deliberately rejects already branded
sources. Replay does not compile the patch or prove window/taskbar UI.

Patch 0060 is registered in the strict source replay gate and applied to the
idle Windows source checkout. A checksum-bound, separately launched 001–059
runtime copy was preserved before application; proof on D:
`standalone-runtime-backup-001-059-before-060-v1/proof.json`. The 001–060 browser
linked at j4; actual main/app-list icon payloads and executable/library
ProductName passed. Its version page still displayed Chromium, so full branding
verification **failed**, not passed.

Registered patch 0061 repairs UI message bodies and the actual 1x/2x scaled
light/dark logos and favicons. `glint-wordmark.svg` stores vector outlines beside
the existing project mark; rasterization does not require substituting a system
font. Message IDs, authors/credits, ChromiumOS names and image dimensions remain
intact. The 001–061 continuation is building at j4, with a separately launched
001–060 rollback copy preserved. Do not edit active sources/GN/registered patches.

After successful linking, verify compiled metadata, icons, version-page product,
unchanged resource/locale packs and ownership cleanup:

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_branding.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --output D:\CamouFlowNative\branding-runtime-new
```

This gate does not prove cached Windows taskbar/shortcut migration or all UI
surfaces. Native lifecycle failure under concurrent profile I/O remains a
separate blocker; see the current test matrix. No production admission yet.

Earlier numbered patches retain their historical diagnostic text for exact
source replay and the current development binary. The branding patch replaces
those strings after that chain; do not rewrite applied patches during a build.
Hardware/identity rejection verifiers now accept the exact native CHECK text
from either historical or Glint-branded binaries, without accepting generic
launch failures. Hardware and identity checks passed on the copied 001–060 binary.
