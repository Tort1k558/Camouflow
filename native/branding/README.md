# Glint branding

Glint is the product name of CamouFlow's own Native browser. Technical engine
identifiers (`native`, `camouflow-native`), profile schemas, executable paths and
Chrome-compatible UA policy remain unchanged. Upstream copyright/credits remain
intact. Camoufox and CloakBrowser are not renamed.

`glint.patch` is a prepared, unapplied branding patch for the pinned Chromium
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

Do not apply it during an active build. After the current build terminates,
register this patch in the strict source replay gate before applying/building.
The current browser binary is not yet Glint-branded. Actual window/taskbar icons,
shortcut migration and product/about strings require a new build and runtime
verification. Preparation and a successful apply check are not runtime proof.

Earlier numbered patches retain their historical diagnostic text for exact
source replay and the current development binary. The branding patch replaces
those strings after that chain; do not rewrite applied patches during a build.
Existing verification scripts still target that unbranded baseline and must be
updated together with admission of the branded binary.
