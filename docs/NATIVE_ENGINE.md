# CamouFlow Native

## Scope and current status

Native is a new public engine project inside CamouFlow, not a renamed Camoufox
or CloakBrowser. The current increment is an independent persistent Chromium
runtime and configuration foundation. It is selectable as **Native (preview)**,
not a fingerprint-patched Chromium fork and not a production-ready anti-detection
release. Existing engines remain available.

All Native source is public. Server source remains private. Windows, Linux and
macOS runtime validation are required before the first working release is complete.
Mobile Web must remain distinct from real Android/iOS browser execution.

## Architecture audit: integration points

- `app/core/browser_interface.py`: shared Playwright page/context API, proxy
  verification, storage restoration, callbacks and startup/teardown. Current
  selection now includes Native through that existing interface, without a
  second scenario executor.
- `app/core/browser_launchers.py`: current engine-specific launch configuration.
  Native configuration/lifecycle lives separately in `app/core/native/`.
- `app/storage/db.py`: checked profile paths, identity-scoped cloud storage,
  per-engine defaults and persisted selection. Native must use a dedicated
  subdirectory and preserve all existing profile data.
- `app/core/browser_proxy_service.py` / `proxy_utils.py`: reusable proxy parsing,
  network/locale checks and authenticated local proxy bridges.
- `app/core/browser_lifecycle.py`: existing callback/watchdog integration;
  process monitoring currently includes Windows-specific paths.
- `app/services/scenario_engine.py`, `scenario_worker.py`, AI agent and recorder:
  consumers of the shared browser interface. Recorder capabilities and worker
  cleanup require actual Native checks, not merely a third dropdown option.
- `app/ui/bridge/browser_settings.py`, profiles/settings bridges and QML pages:
  existing integration points for engine/device configuration and diagnostics.

## Implemented foundation

`NativeConfiguration` validates the explicitly supported viewport, DPR, locale,
timezone and permissions. Its device environments are `desktop` and `mobile_web`.
Mobile Web enables Chromium's viewport/touch emulation, while retaining the native
desktop browser identity. It does not claim an Android Chrome or Safari identity.
Canvas/WebGL/audio/fonts/hardware values remain native; no masking scripts are
injected. Other fingerprint controls require further implementation and evidence.

`NativeRuntime` owns its Playwright driver and persistent Chromium context. It
requires an explicit executable and dedicated profile, rejects unrelated existing
browser data, writes a versioned engine identity, and acquires a per-profile
cross-process lock using the project's existing Qt dependency. Another owner of
the same profile is rejected. Closing the context/driver releases the lock.
Chromium sandboxing is enabled; launch and teardown have explicit time bounds.

This uses the upstream Chromium-compatible distribution selected by the pinned
Playwright version for initial runtime verification. Replacing that executable
with a future own build does not require changing the runtime's public interface.
Publisher-verified binary manifests/update management are not implemented yet.

## Observed Windows evidence — 2026-10-11

Builds/downloads and owned test artifacts use `D:\CamouFlowNative`. Initial binary:
Chrome for Testing `148.0.7778.96`, Playwright revision `1223`, downloaded through
the existing pinned Playwright installer. Its measured local executable SHA256:
`290fa7018fda22c52ada5eddb0113baf3ebc41fd0fde6085eddb19793606c635`.
This is a recorded measurement, not an independently authenticated release manifest.

Actual controlled HTTP tests launched two concurrent Native profiles, rejected
a duplicate owner and verified independent cookies/localStorage/IndexedDB.
All three stores retained the correct independent values after closing and
restarting each profile. Mobile Web observed DPR 3 and touch support; a page
without a viewport meta tag used Chromium's 980px mobile layout viewport, so
viewport-width claims must distinguish configured device and page layout values.

Local regression suite: **620 passed**, including 13 Native configuration and
profile-safety tests. No Native browser processes remained after the controlled
runtime checks. Linux/macOS real-runtime evidence is still required.

A separate headful owned profile loaded
[BrowserLeaks JavaScript diagnostics](https://browserleaks.com/javascript) with
HTTP 200. Observed: Chromium 148 desktop UA, Win32, en-US, UTC, 1366×768 viewport,
DPR 1 and **webdriver=true**. This confirms native values and automation visibility,
not anti-bot bypass. No real customer profile, account or session was used.

## Required next stages

1. Versioned/checksummed binary distribution and update manager, diagnostics and
   launch-failure/crash/cancellation/ownership tests.
2. Integrate Native into the existing storage, browser interface and UI; verify
   proxy support, permissions and lifecycle without changing old engine contracts.
3. Verify existing scenarios, tabs/extraction/screenshots, Recorder and AI workflows.
4. Add consistent UA/Client Hints/device configuration and factual diagnostics;
   unsupported rendering/hardware changes must stay explicitly unsupported.
5. Run real Native runtime/automation gates on Windows, Linux and macOS, including
   cache/service workers, multiple processes, resource use and crash recovery.
6. Prepare pinned Chromium/depot_tools/build configuration, licensing, checksums,
   release compatibility and reproducible fork builds on the approved D: workspace.

No unsupported masking, guaranteed stealth, real-Android identity or production
readiness is claimed. The full Native goal remains active.

## Reproducible source-runtime gate

`scripts/verify_native_runtime.py` now verifies actual Native Chromium, rather
than a mocked browser, against owned HTTP fixtures. Example on the approved D:
workspace (the existing SDK installer downloads the matching full browser):

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = 'D:\CamouFlowNative\browsers'
$env:TEMP = 'D:\CamouFlowNative\tmp'
$env:TMP = $env:TEMP
python -m playwright install chromium --no-shell
python scripts/verify_native_runtime.py --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\native-source-gate.json
```

Run with the project's virtual-environment Python. Create the D: temporary
directory first. `--executable` explicitly selects an own compatible build;
without it the verifier resolves the installed matching binary through the
public Playwright API. It does not substitute a different installed browser.

Verified Windows checks:

- Two concurrent isolated profiles and rejection from a separate owner process.
- Independent persistent cookies, localStorage, IndexedDB, CacheStorage and
  service-worker registrations after each profile is restarted.
- Real navigation, tab open/close, fill/click/extraction and screenshot capture.
- Mobile Web 390×844 layout on a responsive fixture, DPR 3 and touch input.
- HTTP proxy authentication: actual 407 challenge, credentialed proxy traffic
  and successful navigation to a fixture hostname with no direct DNS route.

The updated local full suite passed **657 tests**, including negative proxy-auth
fixture checks and explicit missing-binary failure/reporting without fallback.

The core adapter now dispatches `native` profiles into their own `native/`
storage directory with independent defaults. Worker, scenario and profile
settings use the active engine's settings key; old engine defaults are unchanged.
The Windows gate also executes an existing `ScenarioExecutor` sequence through
`BrowserInterface`: navigation, type, click, wait and extraction passed on the
actual browser. Unsupported identity/header overrides fail explicitly rather
than falling back to a different engine or applying JavaScript patches.

This is not yet evidence for external HTTPS/SOCKS proxies, crash recovery or
AI/Recorder integration. `webdriver` stays visible.
Temporary test profiles are owned and removed after teardown; no customer
profiles or external accounts are used. A JSON report includes actual version,
measured executable checksum, check names and pass/fail state.

Native package CI now installs the matching upstream bootstrap Chromium and
runs this source gate on Windows/Linux/macOS before packaging existing engines;
the report is retained even when a later step fails. This checks source runtime,
**not yet packaged/selectable Native functionality**. Fresh CI evidence is
required; a workflow edit alone does not establish platform readiness.

CI at `41517e1` passed the source-runtime and package checks on Windows and
macOS. Linux navigation timed out on the owned HTTP fixture. The fixture now
handles concurrent connections, including idle Chromium preconnects, with a
regression test; the corrected Linux runtime still needs fresh CI evidence.
The verifier closes only its own workspace log handlers before deleting its
temporary workspace, preserving unrelated application/customer log handlers.

## Native configuration UI

Source-runtime reports from [CI run 38096559489](https://github.com/Tort1k558/Camouflow/actions/runs/38096559489)
at `4b3b3db` were downloaded and inspected for Windows x64, Linux x64 and macOS
ARM64. All seven runtime checks passed on each host, including the existing
scenario executor, cross-process exclusion, persistent storage and authenticated
local HTTP proxy. All reports explicitly retain `fingerprint_patched: false`.
This proves that runtime scope on those platforms, not an own fork build or the
new UI increment's packaging/production readiness.

The existing Browser engine page now includes Native-specific controls for an
explicit Chromium executable, Desktop/Mobile Web, viewport, DPR, locale,
timezone, headless execution and supported permissions. Camoufox/CloakBrowser
masking presets and raw launch arguments are not shown as Native capabilities.
Saving validates Native configuration; unsupported fingerprint requests fail
without silently persisting them. Configuration health checks distinguish file
presence from verified runtime/version readiness.

New profile creation has an explicit engine selector. The local Native profile
creation, Mobile Web preset, edited viewport persistence, unsupported-setting
rejection and missing-binary diagnostics were exercised through actual QML
controls. A Windows-platform UI screenshot was reviewed using an owned temporary
workspace; the offscreen plugin alone does not provide reliable Windows fonts.
Native cookie inspection and storage preflight now use the same dedicated
`native/` directory as launch, not another engine's root directory.

Cloud Native profile creation still requires private backend schema/runtime
support and production validation; UI availability is not proof of those steps.
AI, binary updates, controller-crash/orphan recovery and resource checks remain
incomplete.

Pinned Chromium/depot_tools source acquisition and local build inputs are tracked
in [`native/`](../native/README.md). The D: source transfer and compiler installer
are separate from a successfully built/patched browser. The initial Git transfer
failed with a TLS disconnect; the explicit OpenSSL transport retry successfully
fetched the same pinned commit. Source checkout has completed and its HEAD is
`8625e066febc721e015ea99842da12901eb7ed73`; bootstrap tool/dependency acquisition
must finish before hooks/build can proceed.
Visual Studio Build Tools 2026 18.10.3 installation has completed on D: with
MSVC 14.51.36231 and ATL/MFC; installer signature was verified as Microsoft and
the registered instance reports complete/launchable, with no reboot required.
Required SDK debugging tools and actual compilation remain separate checks.

SDK Debugging Tools installation has since completed from a signature-verified
Microsoft SDK 26100.7705 layout downloaded onto D:. The installed x64 `cdb.exe`
reports 10.0.26100.7705. Source dependency sync has been launched using the pinned
gclient/vpython, owned Git configuration and process-scoped telemetry opt-out;
sync completion, hooks and compilation remain unproven.

## Recorder integration

Recorder capability checks now allow Camoufox and Native; CloakBrowser and unknown
engines remain explicitly unsupported. Profile start permissions, reservations,
cloud locks, sensitive-field handling and draft review are unchanged.

The real Windows Native source gate captured navigation, text and clicks in an
owned page and its stable-ID iframe, closed that browser, then replayed the saved
steps through the existing scenario executor in a newly started Native session.
Both main-document and iframe output were checked. The report contains
`existing-recorder-capture-and-replay` in addition to the previous seven checks.
Recorder event instrumentation is not a JavaScript fingerprint mask.

This does not yet prove Native recording on Linux/macOS, all nested-frame/site
patterns, popups or production cloud profiles. Those require fresh matching CI
reports and further runtime coverage. One local iframe-gate attempt hit a timeout
under concurrent source/tool download; the next run passed. Failure reports now
retain a traceback so future timeouts can be localized instead of losing the
failed call's context. This is not a resolved stability claim.

## Browser crash and ownership recovery

The Windows source gate now deliberately crashes **only its owned browser** via
CDP `Browser.crash`, waits for its disconnect, closes the driver and restarts the
same profile. Previously committed cookies, localStorage, IndexedDB, CacheStorage
and service-worker registration were all verified after restart. A separate
short-lived child leaves an owned test-profile QLockFile without running a
browser; Native then acquires that dead-owner lock. The helper refuses customer
directories. These add two checks to the report, for ten passed Windows checks.

The traceback from the earlier local timeout identified persistent-context close
being cancelled at eight seconds. Native now permits 30 seconds for that close
plus eight seconds for driver stop, inside its own 40-second adapter bound.
Existing Camoufox/CloakBrowser teardown limits are unchanged. Failed driver stop
retains its handles/profile lock and can be retried; launching another runtime
over those retained handles is rejected. Unit tests cover that ownership case.

This is bounded teardown and committed-storage recovery evidence, not a promise
that in-flight writes survive a crash. It does not prove arbitrary controller
termination/orphan cleanup or long-running resource stability. Fresh Linux/macOS
crash-gate reports are still required. No owned Chromium processes were observed
after the completed Windows gate.

## Actual configuration diagnostics

`app/core/native/diagnostics.py` reads document and dedicated-worker UA, low-entropy
Client Hints, platform, language/languages, timezone, hardware concurrency and
device memory, plus document viewport, screen, DPR, touch and webdriver. It
compares configured and observed values without replacing browser APIs. Worker
probe failures remain explicit; its transient worker/Blob URL are cleaned up.
Native profile health reports include these facts and mismatch warnings.

The first Windows probe found that context-level locale alone differed from
worker language. Native now supplies Chromium's own `--lang` and `--accept-lang`
flags from the central validated configuration. Their behavior was inspected in
the pinned Chromium switch/preference source and tested in the actual runtime.
The Windows gate passed with both default English/UTC and non-default German/
Europe-Berlin configuration; document/worker values agreed. The latest report
has eleven checks and retains native patch capabilities as empty. This is native
locale configuration and factual diagnostics, **not an own fingerprint-patched
Chromium build**, and needs fresh matching Linux/macOS reports.

Matching reports from [run 38098705799](https://github.com/Tort1k558/Camouflow/actions/runs/38098705799)
at `a1506fd` have now been downloaded and inspected: all eleven checks passed on
Windows x64, Linux x64 and macOS ARM64, with German/Berlin configuration and no
document/worker mismatches. The entire desktop workflow completed successfully,
including both existing packaged engines. This verifies the tested upstream
bootstrap runtime, **not an own Chromium fork build**.

Windows source sync initially failed during cold parallel gsutil initialization:
one downloader held its cache lock beyond the other jobs' 30-second wait budget.
The build helper now prepares the pinned gsutil once before parallel work and
uses the already installed pinned vpython for helper commands, rather than
rebootstrapping all LUCI CLI packages per invocation. Trace-data downloads were
observed progressing after that correction. Full dependency sync and actual
compilation remain incomplete. Customer/global Git configuration is not changed.

The docs workflow at that revision initially failed inside Retype with negative
capacity errors. An unmodified, debug-enabled retry of the same run/revision
completed build and deployment successfully; it remains an observed transient,
not a diagnosed Retype fix.

References: [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
and [browser emulation](https://playwright.dev/python/docs/emulation).
