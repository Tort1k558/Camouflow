<p align="center">
  <img src="images/logo.svg" width="84" alt="CamouFlow" />
</p>

<h1 align="center">CamouFlow</h1>

<p align="center"><b>English</b> · <a href="README.ru.md">Русский</a></p>

<p align="center">
  <b>A local-first desktop workspace for browser profiles, proxies and visual automation.</b><br/>
  Different profiles. One workflow. On your computer — under your control.
</p>

<p align="center">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows-202820?labelColor=d1f366" />
  <img alt="stack" src="https://img.shields.io/badge/Python%203.12%20·%20PyQt6%20·%20QML-202820?labelColor=d1f366" />
  <img alt="engines" src="https://img.shields.io/badge/Camoufox%20·%20CloakBrowser-202820?labelColor=d1f366" />
  <img alt="license" src="https://img.shields.io/badge/license-MIT-202820?labelColor=d1f366" />
</p>

---

📚 **Documentation (RU/EN): [camouflow.site/docs](https://camouflow.site/docs)** · API reference: [camouflow.site/api](https://camouflow.site/api)

## What is CamouFlow

CamouFlow is a desktop app for working with isolated browser profiles. Every profile has its own context: cookies, fingerprint, proxy and engine settings. Profiles come together in one workflow: visual automation scenarios, proxy pools with health checks, logging and team collaboration through an optional server.

- 🔒 **Local-first** — profiles, scenarios and data stay on your machine; local mode needs no server login
- 🧬 **Anti-detect engines** — Camoufox (Firefox-based) and CloakBrowser (Chromium-based) with configurable fingerprints
- 🕸 **Visual automation** — scenarios are assembled on a canvas from steps linked by success/error transitions
- 🌐 **Teams and control center** — optional server: roles, shared pools, audit, billing

## Screenshots

| Overview | Profiles |
|:---:|:---:|
| ![Overview](images/dashboard.png) | ![Profiles](images/profiles.png) |

| Proxies | Scenarios |
|:---:|:---:|
| ![Proxies](images/proxies.png) | ![Scenarios](images/scenarios.png) |

| Browser engine | Logs |
|:---:|:---:|
| ![Browser engine](images/browser.png) | ![Logs](images/logs.png) |

## Features

### 🗂 Profiles

- create, edit, duplicate and delete browser profiles
- start and stop profile browser sessions
- bulk import with an account parse template
- tag groups and search by name, tag or proxy
- assign a proxy, edit profile variables and cookies
- per-profile browser overrides: locale, timezone, User-Agent, WebGL/GPU, CPU cores
- batch-run a scenario on profiles with a selected tag

### 🕸 Proxies

- proxy pools/groups: create, rename, delete
- bulk list import: `socks5://host:port:user:pass`, `http://user:pass@host:port`
- health checks: single, per pool or all at once — status, latency, geo
- quarantine and release, unassigning from profiles
- pool statistics: active, checking, failed, locations

### ⚙️ Scenarios

- visual editor: draggable steps on a canvas, pan/zoom
- `success` / `error` links between steps, context menus for nodes and links
- scenario library: create, duplicate, delete
- run a scenario on a selected profile, recent runs panel
- shared variables inside the editor, step editor with raw JSON
- scenario marketplace (with a connected server)

Supported steps: `start`/`end` · open URL · HTTP request · wait for element/load · sleep · click · type text · set/parse variables · shared variables · extract text · write file · `if` condition · tab management · tag · run another scenario · log/message

### 🧬 Browser engine

- switch Camoufox ↔ CloakBrowser with separate per-engine settings
- launch modes: windowed / headless / virtual display
- behavior humanization: cursor, mouse speed, typing delays, presets
- Camoufox OS fingerprint pool and seed, Chromium launch args
- navigator/UA/WebGL/CPU overrides, window/screen sizes
- JSON overrides (navigator, window), addons/fonts, permissions and headers
- engine status strip: compatibility check and updates

### 📋 Logs

- application and automation events in a `level · time · event` table
- filters: all / errors / warnings with live counters
- refresh and clear the log (with confirmation)

## Architecture

```text
┌─────────────────────────────┐        ┌─────────────────────────────┐
│   Desktop app (this repo)   │        │   Server (optional)         │
│   PyQt6/QML + Python core   │◄──────►│   teams · roles · pools     │
│   Camoufox · CloakBrowser   │  API   │   audit · billing · market  │
│   local profiles and data   │        │   owner web console         │
└─────────────────────────────┘        └─────────────────────────────┘
```

Local mode is fully self-sufficient. The server is connected optionally — for team access, shared pools and the scenario marketplace. Project site: **[camouflow.site](https://camouflow.site)** (RU/EN).

```text
app/
  core/         browser engine integration, fingerprints, proxies
  qml/          UI (QML): pages and components
  services/     scenario engine and executable steps
  storage/      local database and storage helpers
  ui/bridge/    Python ↔ QML bridges
images/         screenshots used by the README
```

## Quick start

**Download the ready-to-run Windows build:** [CamouFlow 0.2.0 (zip)](https://github.com/Tort1k558/Camouflow/releases/download/v0.2.0/CamouFlow-0.2.0-win64.zip) — unpack and run `CamouFlow.exe` (browser engines download on first launch). All releases: [Releases](https://github.com/Tort1k558/Camouflow/releases).

Or run from source. Requirements: **Windows**, Python 3.12, Git.

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The first launch may take a while — browser engine dependencies are downloaded.

```bat
python main.py
```

### Build the Windows app

```bat
build.bat
```

Output: `dist\CamouFlow\CamouFlow.exe`.

## Data and privacy

All working data — profiles, scenarios, proxies, settings, logs and browser profile data — is stored locally. The active data root is shown in **Settings → App Settings**.

## License

MIT — see [LICENSE](LICENSE).
