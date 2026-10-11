# Browser

The **Browser** page configures global browser-engine defaults.

## Engines

CamouFlow supports:

- **Camoufox**
- **CloakBrowser**
- **Native (preview)**

The selected engine is stored globally and can be overridden per profile.

## Native preview

Native has its own persistent Chromium runtime, profile directory and cross-process
owner lock. It does not fall back to Camoufox/CloakBrowser or adopt their profile
directories. Current own-engine development and CI are Windows-only; the patched
Chromium binary is still being compiled, not available as a verified release.

Native configuration supports Desktop and Mobile Web, viewport size, DPR,
locale, timezone and browser permissions. Mobile Web is desktop Chromium with
viewport/touch emulation, **not real Android/iOS**. Unsupported identity/masking
options are rejected; Canvas, audio, GPU and hardware diagnostics report native
values rather than invented fingerprints.

Choose an explicit installed executable or **Managed release** with an absolute
owned binary-store path. Maintenance can install a local `.tar.gz` bundle using
a SHA-256 obtained from a trusted publisher, verify headless startup and select
or roll back compatible releases. There is no signed online update catalog.
Own-fork bundles require checksums for their complete payload, including DLLs
and resources. Verification runs in background workers; changed settings invalidate
earlier compatibility results. Existing sessions must be closed before changing
their executable or configuration.

The Native compatibility action checks startup, observed document/worker values
and teardown. It does not certify CAPTCHA scores, CDP invisibility or third-party
anti-bot acceptance. Current upstream SDK runtime checks are distinct from
verification of our unfinished source patches. See the
[Native implementation and evidence](https://github.com/Tort1k558/Camouflow/blob/main/docs/NATIVE_ENGINE.md)
for that boundary.

## Main groups

- **Execution**: window/headless mode and humanization.
- **Operating Systems**: Camoufox OS fingerprint pool.
- **Cloak Fingerprint**: CloakBrowser platform and fingerprint seed.
- **Locale & Timezone**: browser locale and timezone overrides.
- **Storage / Runtime**: persistent context, cache and Cloak backend.
- **Window Size**: viewport and screen defaults.
- **Runtime Protection**: WebRTC, image, WebGL and COOP restrictions.
- **Window Overrides**: raw Camoufox `window_overrides` JSON.
- **Navigator**: user agent, CPU cores and raw navigator overrides.
- **WebGL / GPU**: vendor and renderer overrides.
- **Addons / Launch**: Camoufox fonts/addons/exclude-addons or CloakBrowser extension paths/launch args.

## Actions

- **Save** persists the active engine settings.
- **Reset** restores recommended defaults for the active engine.

## Applying settings

Saved defaults apply to new browser launches; a profile's explicit overrides take priority. Existing browser sessions must be closed and reopened. For Camoufox and CloakBrowser, context settings (headers, JavaScript, CSP, downloads, permissions and storage-state import) apply in both persistent and ephemeral modes. Native requires persistent profiles and supports only its explicitly validated configuration.

For CloakBrowser, window dimensions control the viewport and screen dimensions control the fingerprint separately. Auto window size uses the wrapper's native default viewport, so humanized typing also works without a manually specified size. Locale and timezone use native launch flags in both context modes, rather than extra Playwright emulation.

Camoufox retains its generated identity and audio noise seed across launches. Changing its OS explicitly regenerates that identity; changing window dimensions does not. GPU overrides must be a supported vendor/renderer pair for that OS. Virtual display is Linux-only. Cursor duration is Camoufox-only; human presets are CloakBrowser-only.

Canvas export changed after restart in the tested Camoufox build; the saved profile identity does not make that surface persistent. Related upstream background is in [`canvas:seed` issue #721](https://github.com/daijro/camoufox/issues/721). The audit records this as a warning, separate from integration checks. CamouFlow does not silently disable Canvas protection or inject a JavaScript spoofing workaround.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\verify_browser_settings.py
.venv\Scripts\python.exe scripts\verify_browser_settings.py --public-sites --headed
```

The verifier uses temporary profiles and a loopback fixture, not personal sessions. It checks language/timezone, dimensions, typing, JavaScript/CSP, persistent versus ephemeral storage and identity stability. The optional public-site check visits Sannysoft, BrowserLeaks and CreepJS and saves screenshots and observations in `.local/browser-audit/`.

A detector's score is not proof of anonymity or universal bot-detection compatibility. Chrome-only checks can report failures on Firefox. Manual locale/timezone do not change the connection's IP. These checks do not certify an external proxy, GeoIP routing, DNS/WebRTC leak protection, CAPTCHA acceptance or paid anti-bot systems. Enable Camoufox's WebRTC blocking when that API is not needed; locale matching alone does not spoof its IP.
