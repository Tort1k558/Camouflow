# CamouFlow

CamouFlow is a local desktop workspace for browser profiles, proxies and visual automation scenarios.

The app is built with **Python + PyQt6/QML** and runs automation through **Camoufox / CloakBrowser** with local storage for profiles, settings, scenarios, proxy pools and logs.

## Screenshots

| Dashboard | Profiles |
|---|---|
| ![Dashboard](images/dashboard.png) | ![Profiles](images/profiles.png) |

| Browser settings | Proxies |
|---|---|
| ![Browser settings](images/browser.png) | ![Proxies](images/proxies.png) |

| Scenarios | Logs |
|---|---|
| ![Scenarios](images/scenarios.png) | ![Logs](images/logs.png) |

## Current features

### Dashboard

- profile, browser, scenario and proxy counters
- running session list
- recent activity feed
- quick navigation actions

### Profiles

- create, edit and delete browser profiles
- bulk import profiles with an account parse template
- start and stop profile browser sessions
- assign proxy data to a profile
- manage profile tags
- edit profile variables and cookies
- run a scenario for profiles matching a tag
- per-profile browser overrides:
  - locale
  - timezone
  - user agent
  - WebGL/GPU vendor
  - CPU cores

### Browser engine settings

- switch and configure Camoufox / CloakBrowser behavior
- headless/windowed execution settings
- humanization options
- OS fingerprint pool for Camoufox
- CloakBrowser fingerprint seed and Chromium launch options
- locale and timezone overrides
- persistent profile storage
- viewport and screen size defaults
- navigator, user agent, CPU and WebGL/GPU overrides
- Camoufox addons/fonts/exclude-addons settings

### Proxies

- proxy pools/groups
- bulk import proxy list
- supported input formats:
  - `socks5://host:port:user:password`
  - `http://user:pass@host:port`
- rename/delete pools
- edit/delete individual proxies
- select multiple proxies
- release or remove selected proxies
- health checks per proxy or group
- pool statistics: active, checking, failed, locations

### Scenarios

- visual node-based scenario editor
- draggable steps on a canvas
- pan/zoom canvas navigation
- success/error links between steps
- right-click context actions for nodes and links
- scenario library: create, duplicate, delete, save
- run selected scenario on a selected profile
- shared variables modal inside the scenario editor
- step editor with raw JSON preview

Supported step types:

- start / end
- open URL
- HTTP request
- wait for element
- wait for page load
- sleep
- click
- type text
- set variable
- parse variable
- pop from shared variables
- extract text
- write file
- compare / if
- open, switch and close browser tabs
- set tag
- run another scenario
- log/message

### Logs

- application and automation event log
- refresh logs
- clear logs

### Settings

- application data root display

## Project structure

```text
app/
  core/              browser integration, fingerprints, proxies
  qml/               current PyQt6/QML interface
  services/          scenario engine and executable steps
  storage/           local database/storage helpers
  ui/bridge/         Python <-> QML bridge objects
images/              current screenshots used by README
```

`newdesign/` is a separate React/Vite design prototype and is not the active desktop UI.

## Requirements

- Windows
- Python 3.12 recommended
- Git

Python dependencies are listed in `requirements.txt`:

- PyQt6
- Camoufox
- CloakBrowser
- PySocks
- PyInstaller

## Install

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

First launch can take longer while browser dependencies are prepared.

## Run

```bat
python main.py
```

## Build Windows app

```bat
build.bat
```

Output:

```text
dist\CamouFlow\CamouFlow.exe
```

## Tests

There is no full automated test suite yet. For a quick static check:

```bat
python -m compileall app
```

## Data and storage

CamouFlow stores working data locally:

- profiles
- scenarios
- proxies
- settings
- logs
- browser profile data

The active data root is shown in **Settings → App Settings**.

## License

MIT
