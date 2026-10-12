<p align="center">
  <img src="images/logo.svg" width="84" alt="CamouFlow" />
</p>

<h1 align="center">CamouFlow</h1>

<p align="center"><b>English</b> · <a href="README.ru.md">Русский</a></p>

<p align="center">
  <b>Browser profiles. Visual automation. Your own workspace.</b><br/>
  Local-first desktop manager for Camoufox, CloakBrowser and the Glint engine preview.
</p>

<p align="center">
  <a href="https://github.com/Tort1k558/Camouflow/releases/latest"><img alt="Latest desktop release" src="https://img.shields.io/github/v/release/Tort1k558/Camouflow?label=desktop&color=202820&labelColor=d1f366" /></a>
  <img alt="Windows desktop" src="https://img.shields.io/badge/platform-Windows-202820?labelColor=d1f366" />
  <img alt="Glint development preview" src="https://img.shields.io/badge/Glint-development%20preview-202820?labelColor=d1f366" />
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-202820?labelColor=d1f366" /></a>
</p>

<p align="center">
  <a href="https://github.com/Tort1k558/Camouflow/releases/latest">Download</a> ·
  <a href="https://camouflow.site/docs">Documentation</a> ·
  <a href="docs/GLINT_TEST_MATRIX.md">Glint test results</a> ·
  <a href="native/BUILDING.md">Build Glint</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

## Your browser workflow, in one place

| Work with profiles | Build visual scenarios |
| :---: | :---: |
| ![Persistent profiles, tags and per-profile settings](images/profiles.png) | ![Visual scenario editor](images/scenarios.png) |
| Separate sessions, engine settings and proxy assignments. | Connect actions with success/error paths. |

| Capability | Example workflow |
| --- | --- |
| **Persistent profiles** | Organize profiles by tags; select a group for a scenario run. |
| **Proxy pools** | Import connections, check health and assign a pool; unavailable assignments fail without a direct fallback. |
| **Visual automation** | Open a catalog → extract rows → branch on a condition → export results. |
| **AI → review → replay** | Describe an extraction task; inspect the actions and replay without another model request. |
| **Run queue & debugging** | Schedule profile runs; step through a failure and inspect screenshots/traces. |
| **Backup & restore** | Export a checksummed profile archive; restore under a new identity. |
| **Optional team workspace** | Assign work, review linked runs and request browser assistance through the private server. |

## Describe. Review. Replay.

![AI catalog extraction and verified replay](images/ai-workflow-demo.png)

**Example:** extract a synthetic catalog → inspect the table → export JSON/CSV →
save a parameterized scenario → verify read-only replay.

[Watch the UI demo](images/ai-workflow-demo.gif) · [AI quickstart](docs/AI_WORKFLOWS.md) ·
[CLI / MCP / n8n](docs/AI_WORKFLOWS.md#local-cli)

> Model-reported success is not verified replay. Page content goes to your chosen
> AI provider; editable-field exclusion does not remove every possible secret.

## Choose your engine

| Engine | Foundation | Status |
| --- | --- | --- |
| **Camoufox** | Third-party Firefox-based engine | Integrated configurable anti-detect profiles |
| **CloakBrowser** | Third-party Chromium-based engine | Integrated configurable anti-detect profiles |
| **Glint** | **Our public Chromium/Blink fork** | **Windows development preview**, native C++/Mojo policies |

Settings differ by engine. Glint is not a renamed third-party browser and does
not silently substitute unsupported settings. The desktop release does not
necessarily contain the latest Glint development build.

### Glint: implementation at a glance

| Area | What exists | What remains |
| --- | --- | --- |
| Identity & contexts | Private profile keys; browser-owned partition/surface derivation | Complete coherent device-passport generator |
| Hardware & fonts | Native CPU/memory ceilings and installed Windows-font selection | Cross-platform device emulation |
| WebRTC & automation | Native routing and selected automation/headless/CDP signal policies | External leak checks; **no full CDP invisibility** |
| Worker/document delivery | Worker opt-in transport; four Blink handoff tests passed; document drafts | Document runtime/recovery gates and production admission |
| Canvas / GPU / Audio | Canvas candidates; upstream GPU/audio behavior | **Protection incomplete and not activated** |
| TLS / HTTP | Upstream Chromium/BoringSSL | Same-route measurements; no custom ClientHello spoofing |
| Mobile & platforms | Viewport/touch Web Emulation; verified Windows development runtime | Not real Android/iOS; Linux/macOS runtime checks deferred |

[Public patches](native/patches) · [Architecture](native/ARCHITECTURE.md) ·
[Capabilities](docs/NATIVE_ENGINE.md) · [Roadmap (RU)](docs/GLINT_ROADMAP.ru.md)

### Glint: verified, not advertised

**Windows · Chromium 148.0.7778.96 · patches 001–027** — pinned development
baseline, not a production release or a claim of current security updates.

| Check | Recorded result |
| --- | --- |
| Existing runtime policies | **160 checks passed across 8 local gates** |
| Worker startup / restart / rejection | **40 checks passed**, diagnostic opt-in |
| Blink seed ownership / thread handoff | **4 cases passed**, with test-only fixture correction 0028 |
| Document partition validator | **9 cases passed**, registered unit target 0029; not navigation recovery |
| Unprotected Canvas API baseline | **4 phases passed** — not protection evidence |
| External fingerprint/bot services | **Not run for 001–027** |
| reCAPTCHA / real-key Turnstile / hCaptcha | **Not verified for 001–027** |

[Full test matrix & build history](docs/GLINT_TEST_MATRIX.md): CreepJS, Pixelscan,
BrowserScan, Sannysoft, BrowserLeaks, Fingerprint Playground, TLS/HTTP and more.
Earlier builds' observations do not transfer. No guaranteed CAPTCHA scores or site access.

## Get started

**[Download the Windows desktop app](https://github.com/Tort1k558/Camouflow/releases/latest)** →
unpack → run `CamouFlow.exe`. Browser engines download on first launch.
Local mode requires no server login.

<details>
<summary>Run from source · Windows, Python 3.12</summary>

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Build the desktop app with `build.bat`.
Output: `dist\<build-id>\CamouFlow\CamouFlow.exe`.
Glint has a separate [Chromium build guide](native/BUILDING.md).

</details>

## Explore

[Desktop reference](docs/DESKTOP_REFERENCE.md) ·
[Hosted tasks](docs-site/docs/hosted-tasks.md) ·
[Team center](docs-site/docs/team-center.md) ·
[Python scenarios](docs-site/docs/python-scripting.md) ·
[API](https://camouflow.site/api) · [Changelog](CHANGELOG.md)

<details>
<summary>Proxy management & workspace overview</summary>

| Proxy pools | Overview |
| :---: | :---: |
| ![Proxy pools and health checks](images/proxies.png) | ![Workspace overview](images/dashboard.png) |

</details>

**Local-first, not a sandbox:** profiles and data are stored locally; optional
cloud work and configured AI providers have separate data flows. Keep archives,
traces and session files private. The optional server is not in this repository.

[Contribute](CONTRIBUTING.md) · [Report a bug](https://github.com/Tort1k558/Camouflow/issues/new/choose) ·
[Code of conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md) · [MIT license](LICENSE)
