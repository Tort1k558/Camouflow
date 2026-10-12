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

![CamouFlow profile workspace](images/profiles.png)

## One workspace, three engines

Manage persistent profiles, proxy pools and scenario runs locally. Describe a
task with AI, review the recorded actions, then replay without another model
request. Connect our optional hosted service for team assignments and shared work.

| Engine | Foundation | Role in CamouFlow |
| --- | --- | --- |
| Camoufox | Firefox-based, third-party | Configurable anti-detect profiles through the existing integration |
| CloakBrowser | Chromium-based, third-party | Configurable anti-detect profiles through the existing integration |
| **Glint** | **Our public Chromium/Blink fork** | Windows development runtime; native C++/Mojo policies, not a renamed third-party engine |

Settings and capabilities differ by engine. Glint is **not a production
anti-detect release** and does not silently substitute an unsupported setting.
The desktop download is not proof that it contains the latest Glint development build.

## Glint: what is native, what is still in development

| Surface | Implementation | Current boundary |
| --- | --- | --- |
| Profile identity | Private versioned profile key; browser-owned partition/surface derivation | Key/context tests passed; not a complete generated device passport |
| CPU / memory | Native hardware ceilings | Limits, not arbitrary emulation of another computer |
| Fonts | Native selection from installed Windows fonts | No fabricated font inventory or macOS/Linux font simulation |
| WebRTC | Native routing policy | Controlled checks passed; external leak testing remains separate |
| Automation signals | Source-level policies for selected automation/headless/CDP signals | **Not full CDP invisibility**; manager automation still uses Playwright/CDP |
| Workers | Owned startup/seed transport behind a developer-only gate | Runtime startup checks passed; exact Blink handoff tests pending |
| Document policy | Browser → commit IPC → renderer → Document candidates | Unregistered drafts; runtime and final-partition recovery pending |
| Canvas | Native readback/export candidates | **Protection not activated**; baseline checks are not protection tests |
| WebGL / WebGPU / Audio | Planned native protection | Incomplete; no arbitrary GPU identity or audio emulation |
| TLS / HTTP | Upstream Chromium/BoringSSL network stack | No custom ClientHello spoofing; comparative measurements pending |
| Mobile profiles | Desktop viewport/touch Web Emulation | **Not Android Chrome or iOS Safari**; full mobile identity pending |
| Platforms | Verified Windows development runtime | Own-fork Linux/macOS runtime verification deferred |

[Architecture](native/ARCHITECTURE.md) · [Capabilities](docs/NATIVE_ENGINE.md) ·
[Implementation roadmap (RU)](docs/GLINT_ROADMAP.ru.md) · [Public patches](native/patches)

## Glint verification snapshot

Last verified browser: **Windows · Chromium 148.0.7778.96 · patches 001–027**.
This is a pinned development baseline, not a claim of current Chromium security updates.

| Check | Result | Scope |
| --- | --- | --- |
| Existing runtime policies | **160 checks passed / 8 gates** | Controlled local checks, not external detector scores |
| Worker startup / restart / rejection | **40 checks passed** | Diagnostic opt-in; does not prove Canvas protection |
| Canvas API baseline | **4 phases passed** | Unprotected pixel/export/API behavior |
| CreepJS / Pixelscan / BrowserScan / Sannysoft | **Not run for 001–027** | Earlier builds' observations do not transfer |
| Fingerprint Playground / IPhey / BrowserLeaks | **Not run for 001–027** | Recognition, consistency and leak checks pending |
| TLS / HTTP fingerprint comparison | **Not run for 001–027** | Same-route stock Chromium comparison required |
| reCAPTCHA / real-key Turnstile / hCaptcha | **Not verified for 001–027** | No guaranteed scores or CAPTCHA acceptance claims |

The [living test matrix](docs/GLINT_TEST_MATRIX.md) retains build history, test
destinations, evidence references and limitations. Pass counts describe their
named check sets, not “anti-detect readiness” or guaranteed site access.

## Automate, review, replay

![AI catalog extraction and verified replay](images/ai-workflow-demo.png)

[AI quickstart](docs/AI_WORKFLOWS.md) ·
[Recorded UI demo](images/ai-workflow-demo.gif) ·
[CLI / MCP / n8n](docs/AI_WORKFLOWS.md#local-cli) ·
[Hosted tasks](docs-site/docs/hosted-tasks.md) ·
[Team center](docs-site/docs/team-center.md)

The demo uses a synthetic catalog and a configured model, not a personal account.
Model-reported success is not verified replay. Page content goes to your chosen
provider; excluding editable field contents does not remove every possible secret.
Local mode requires no server login. The optional backend remains private.

## Screenshots

<details>
<summary>More screenshots</summary>


| Overview | Profiles |
|:---:|:---:|
| ![Overview](images/dashboard.png) | ![Profiles](images/profiles.png) |

| Proxies | Scenarios |
|:---:|:---:|
| ![Proxies](images/proxies.png) | ![Scenarios](images/scenarios.png) |

| Browser engine | Logs |
|:---:|:---:|
| ![Browser engine](images/browser.png) | ![Logs](images/logs.png) |

</details>

## Features

### 🗂 Profiles

- create, edit, duplicate and delete browser profiles
- start and stop profile browser sessions
- bulk import with an account parse template
- tag groups and search by name, tag or proxy
- assign a proxy, edit profile variables and cookies
- engine-dependent per-profile settings: locale, timezone, User-Agent, WebGL/GPU, CPU cores; Glint restrictions are listed above
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
│   Camoufox · CloakBrowser   │  API   │   audit · market            │
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

**Download the ready-to-run Windows build:** [latest release (zip)](https://github.com/Tort1k558/Camouflow/releases/latest) — unpack and run `CamouFlow.exe` (browser engines download on first launch). All releases and per-version changes: [Releases](https://github.com/Tort1k558/Camouflow/releases) · [CHANGELOG.md](CHANGELOG.md).

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

Output: `dist\<build-id>\CamouFlow\CamouFlow.exe` (a new timestamped directory for each build).

## Data and privacy

All working data — profiles, scenarios, proxies, settings, logs and browser profile data — is stored locally. The active data root is shown in **Settings → App Settings**.

## License

MIT — see [LICENSE](LICENSE).

## Repository and safe releases

The desktop lives in `app/` and its CI runs from this repository. The optional backend, web console, migrations and server tests are maintained privately in the sibling `../server/` directory, outside this Git repository. The old local server path and `.github/workflows/server.yml` remain ignored. Back up the backend separately; cloning this repository does not restore it.

`build.bat` writes a separate timestamped release under `dist/` and never deletes previous builds or stops running browsers. Portable data lives beside the executable; upgrading the executable does not migrate it automatically. Stop the application and back up `settings/`, `profiles/`, `scenaries/` and `outputs/` before transferring a portable workspace.

Local synchronization binds that data directory to one server/team. Switching the active team still permits direct cloud work, but does not authorize transferring local resources to a different team. Manual synchronization confirms the destination; cookie upload requires separate confirmation. Deletions require an explicit conflict resolution and browser directories are retained.

## Desktop operations

Python blocks are available under **Scenarios > Scripting > Python script**.
Use **Edit Python script** for code, inputs and the result variable; test through
the existing run debugger. Native Python requires local approval and executes in
a supervised process, not a security sandbox. See the [Python scripting guide](docs-site/docs/python-scripting.md).

Select profiles with their checkboxes, then use **Selected actions** to schedule a scenario, bulk edit/export, or create a full archive. Restore archives through **Profiles > Import > Restore archive**. The queue and results live under **Scenarios > Runs**, beside the editor. Run/Batch run actions use this same queue; switching pages does not stop jobs.

- **Queue & results:** one job per profile, optional local date/time (`YYYY-MM-DD HH:MM`), 1–8 simultaneous browsers, pause new starts, cancel running/queued jobs. The application must remain open. After restart the queue is paused, unfinished executions are marked interrupted, and pending jobs are retained. Resume explicitly; no automatic retries of interrupted work. Scenario definitions (including nested scenarios) are saved locally with the job. Keep the data directory private.
- **Results:** inspect status, failure reason, step metadata, screenshots and Playwright traces. Retry starts the entire scenario and requires confirmation because previous submissions may repeat. Artifacts can contain sensitive account data. Trace viewer uses the local Playwright runtime and requires its Chromium browser; failures are reported with a local diagnostic log.
- **Bulk changes:** preview and apply tag/proxy/engine-setting changes to stopped local profiles. If profiles changed since preview, the operation is rejected. Local metadata export omits credentials and browser sessions. Cloud bulk editing is not enabled by this screen.
- **Backup & restore:** export a local profile to a checksummed ZIP; choose browser session files and sensitive metadata separately. Archives are unencrypted. Session directories can contain secrets even when the metadata-secrets option is off. Restore only trusted archives, always under a new name. Optional scenarios are imported as new copies, engine defaults are applied only to the restored profile, and existing global settings remain unchanged. Browser-encrypted credentials may not transfer between OS users or machines.
- **Proxy policy:** keep the current assignment, check it and stop on failure, or explicitly allow replacement from one named pool before launch. Occupied/quarantined proxies are excluded from replacement; healthy replacements remain assigned. No automatic IP changes are made after launch. Cloud replacement requires manager privileges; queued cloud execution acquires and renews the profile lock.

Queue capacity is limited to 500 unfinished jobs and 32 MiB of metadata. Archive verification is limited to 2 GiB and 50,000 files. These are protective limits, not commercial quotas. Clearing finished jobs preserves artifact files; manage those separately in the data directory.


## Record a scenario (desktop)

### Saved tasks: record once, run with a form

Open **Tasks → Record a task**, record your actions and stop. Review the action list and warnings, select the URL/text/selection values that change between runs, give them readable labels, then **Save task**. Equal recorded values become one shared input; recognized secrets remain profile variables. The technical JSON and variable names are optional advanced details.

In **Tasks**, choose a saved scenario, select a profile, fill all required inputs and **Queue task**. This uses the existing queue, profile locks and Python approval; no model request is needed. Resume the queue explicitly in **Runs** and keep the application open. The task definition is snapshotted with the job. Run inputs are stored locally in the queue, not as profile defaults; never enter credentials here. A changed task must be selected and reviewed again. **Run details** opens the existing result/error/artifact controls. Recording warnings are retained with the saved task.

Open **Scenarios > Record**, select a stopped local or cloud Camoufox profile and enter an HTTP(S) start URL. Click **Start recording**, perform actions in the browser, then **Stop** and **Save & edit**. Stop closes the recording browser. Saving requires a new scenario name and never replaces existing scenarios. Recording reserves the profile against simultaneous launches and workspace operations. Cloud recording also acquires and renews the server profile lock, then releases it after the browser closes. Cloud recording requires operator access; saving a new scenario requires manager access. Save in the same workspace where recording started; switching teams does not transfer the draft.

The first version records the initial tab and main frame: navigation, clicks, text input, single-value HTML selects, checkboxes/radio buttons and Enter. Selectors prefer unique test IDs, IDs, names and accessible attributes; ambiguous targets are reported rather than guessed. Sequential typing is combined into one step. The select_option, set_checked and press actions are available in the editor and executor.

Password inputs use the profile variable {{password}}; other recognized sensitive inputs use {{recorded_secret_N}}. Their literal values are removed before crossing from the page into Python. Missing required variables stop replay. Other text and URLs are recorded as entered and must be reviewed before sharing.

Limitations: Camoufox only, no iframe/popup recording, file uploads, rich-text editors or multiple selects. The installed CloakBrowser runtime does not support the required exposed binding. Unsupported actions generate review warnings. Browser-initiated navigation immediately after an action is represented by a load wait; unusual delayed or multi-stage navigation may need manual editing. Recording is capped at 1,000 steps. Unsaved drafts exist only in memory until the application exits. Automation executes real actions: inspect the draft before replaying submissions.

### Profile editing and step debugging

- Profile settings accept one proxy connection string, an existing pool proxy, or any available proxy from a selected pool. Empty manual input removes the proxy. An exhausted pool is an error, not a direct-connection fallback.
- Workspace list refreshes run in background workers. Profile tabs retain their drafts while switching; cookies load asynchronously.
- In **Scenarios > Runs**, enable **Debug in separate window** before adding a job, then resume the queue. The debugger pauses before the first step. **Next step** executes one step; **Resume** continues; **Run selected** jumps to a step. Closing the debugger stops its run.
- Queue debugging uses the saved run snapshot, not hot reload. After completion, enqueue another run to execute edited steps.

### Local storage recovery

Account/settings mutations refuse to overwrite malformed, wrongly shaped or unreadable JSON. Restore `settings/accounts.json` or `settings/settings.json` from a verified backup before retrying; do not delete these files as a reset. Missing files can initialize a new workspace. UTF-8 BOM documents are accepted; updates use UTF-8 without BOM. These guards are not a recovery tool or cross-process lock.

### Profile-list import and explicit proxy pools

Selecting a proxy pool requires an available unassigned, non-quarantined connection for each imported profile. Exhausted pools and failed cloud reads stop affected imports; they never silently create a direct-connection profile. Malformed or timezone-naive quarantine timestamps remain blocked until explicitly released. Choose **All pools** only when no pool assignment is intended. Partial failures keep the dialog open with only failed lines, so successful rows are not resubmitted. Failed local account writes attempt to restore the pool assignment; multiple-file writes are not a crash-safe transaction. Import error logs identify line numbers, not the credential-bearing input lines.

### Dedicated browser storage

New/renamed profile names must map to a valid, distinct browser directory.
Reserved Windows names, workspace-root identities and names that sanitize to
another profile's directory are rejected. Browser launch, cookie reads/resets,
profile-directory deletion and restore targets validate their storage boundary.
Profile-root links and linked engine directories are not accepted.

Existing ambiguous/unsafe names are not automatically migrated or deleted.
Preserve the workspace and review a verified backup before recovering those
records; do not reset or remove shared browser files. Renames refuse an existing
unmanaged target directory. A failed metadata save attempts to move a renamed
directory back. These guards do not provide crash-safe multi-file transactions,
protect against arbitrary local Python.

Cloud browser directories are keyed by the canonical server origin, team UUID,
and profile UUID, not the display name. The full SHA-256 identity key uses one
bounded directory component below `profiles/.cloud`, avoiding deep Windows
Chromium paths. Renaming a cloud profile keeps its browser session; changing
server, team, or profile identity uses separate cookies, fingerprints, and
scenario variables. Both browser engines, recorder, AI replay, queue workers,
and profile health checks use the captured identity, not the current UI session.
Cloud storage-state files must remain inside that identity's directory.

Existing name-based folders are preserved but never automatically adopted by a
cloud profile: ownership cannot be inferred safely. Sign in again in the new
cloud directory. Review a verified backup before any manual session recovery.
Local profiles keep their existing name-based directories; local cleanup does
not delete the reserved cloud namespace.

Google sign-in opens the configured server's `/api/v1/auth/google/start` in the
system browser so the callback can validate its HttpOnly state cookie. Updated
servers reject callbacks from another browser or an expired flow. After this
OAuth hardening, use the updated desktop build and restart any in-flight login.
