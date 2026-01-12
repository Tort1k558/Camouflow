# Settings

The **Settings** tab defines global Camoufox defaults applied to all profiles (unless overridden per profile).

## Appearance

Choose the app theme.

Added **CamouFlow Orange** (Light/Dark) themes with orange accents to match the brand/logo.

Default is **CamouFlow Orange (Light)**, and the old Light/Dark themes remain as "Classic" options.

## Camoufox defaults

Settings are split into tabs. The idea:

- **Auto** - use automatic/recommended values.
- **Set** - set a value manually.

Typical options (may vary by version):

- **Headless** - run with window / headless.
- **Humanize** - human-like delays for typing/motion.
- **Locale / Timezone** - locale and timezone.
- **OS / Fonts** - OS emulation and font list.
- **Window** - window/screen metrics (including `screen.*`, `innerWidth/innerHeight`, etc.).
- **Navigator** - overrides for `navigator.*` (e.g., `userAgent`, `platform`, `languages`).
- **Privacy / Network** - WebRTC / images / WebGL blocking, cache, COOP, etc.

Below are the meanings of key parameters (follow the UI labels; some fields may be available only in Settings/profile overrides).

### General

- **headless** - browser mode (with window or headless).
- **persistent_context** - use persistent context (profile is stored on disk in `profiles/`).
- **enable_cache** - enable/disable cache.

### Locale and environment

- **locale** - UI/locale language (e.g. `en-US`, `ru-RU`).
- **timezone** - timezone (e.g. `Europe/Moscow`).
- **os** - OS emulation (Auto or Windows/MacOS/Linux).
- **fonts** - font list (one per line).

### Window / Screen overrides

The **Window** tab allows manual window/screen metrics used in page JS.
Example parameters:

- `screen.width`, `screen.height`, `screen.availWidth`, `screen.availHeight`
- `browser.innerWidth`, `browser.innerHeight`, `browser.outerWidth`, `browser.outerHeight`
- `browser.devicePixelRatio`

If left as Auto, default values are used.

### Navigator overrides

The **Navigator** tab overrides `navigator.*` properties.
Values are usually strings/lists/numbers/bools (UI provides Auto/Set or Auto/True/False).

### Privacy / Network

- **block_webrtc** - block WebRTC.
- **block_images** - block image loading.
- **block_webgl** - block WebGL.
- **disable_coop** - COOP (Cross-Origin-Opener-Policy) tuning for compatibility/isolation.
- **webgl_vendor / webgl_renderer** - manual Vendor/Renderer override (if available in UI).

## Buttons

- **Save** - save settings.
- **Reset to recommended** - reset to recommended values.
