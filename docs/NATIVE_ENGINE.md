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

The updated local full suite passed **658 tests**, including negative proxy-auth
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
Native compatibility checks now perform an asynchronous, real headless startup
and teardown in a disposable profile and display the observed Chromium version.
The QML button reflects single-flight progress. Changed settings or a different
selected engine cannot receive a stale result. The non-daemon probe job completes
its owned-browser cleanup before normal application exit. This is binary health,
not publisher authentication, scenario compatibility or fingerprint-patch proof.
The actual QML button/worker callback/version display/temp-profile cleanup were
verified locally on Windows using the upstream bootstrap executable.
Per-profile JSON overrides use that same validator against merged Native
defaults before local/cloud mutation. Unsupported UA, hardware and GPU controls
(including legacy WebGL key names) fail at save time, not only at launch.

New profile creation has an explicit engine selector. The local Native profile
creation, Mobile Web preset, edited viewport persistence, unsupported-setting
rejection and missing-binary diagnostics were exercised through actual QML
controls. A Windows-platform UI screenshot was reviewed using an owned temporary
workspace; the offscreen plugin alone does not provide reliable Windows fonts.
Native cookie inspection and storage preflight now use the same dedicated
`native/` directory as launch, not another engine's root directory.
Profile backup includes Native defaults when private settings export is enabled;
restore merges them with profile overrides without changing workspace defaults.
Native runtime locks are excluded from new exports and discarded from older
archives after integrity verification. Public metadata-only exports retain the
engine identity but do not include private Native settings. Restored local
profiles discard inherited cloud IDs, storage scopes and lock-owner metadata.
The real runtime gate now includes restoring cookies/localStorage/IndexedDB/
cache/service workers into a new Native profile and checking source isolation.
Unit checks cover the archive changes. The third full Windows run passed all
12 runtime checks, including real backup/restore of all five storage types and
source-profile isolation. Two preceding runs timed out in the pre-existing
first context close before reaching backup/restore. Owned browsers were cleaned
up. Isolated sequential/concurrent storage probes, including process-owner
exclusion, then closed normally in approximately 1–2 seconds. The earlier
shutdown timeouts have not been root-caused or claimed fixed; runtime teardown
policy and timeouts were not weakened to obtain this passing result.
The matching `aad4c7f` desktop CI run `38101918271` also passed all 12 Native
source-runtime checks on Windows x64, Linux x64 and macOS ARM64. Downloaded
reports confirm backup/restore isolation on each platform. All use upstream
bootstrap Chromium 148.0.7778.96 and explicitly report `fingerprint_patched:
false`; this is not proof that the own Chromium fork has compiled or run.

The private backend's existing profile schema already accepts Native; no schema
change was needed. Isolated local API tests verified create, update and list
roundtrips for all three engine identifiers, including Native Mobile Web
configuration and team identity (15 resource-validation tests passed). This is
not production evidence: live cloud creation, locking, storage synchronization
and Native launch still require end-to-end validation against the deployed API.
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
Existing Camoufox/CloakBrowser teardown limits are unchanged. Interrupted driver
stop retains its handles/profile lock; launching another runtime over those
retained handles is rejected. The continuation semantics are detailed below.

This is bounded teardown and committed-storage recovery evidence, not a promise
that in-flight writes survive a crash. It does not prove arbitrary controller
termination/orphan cleanup or long-running resource stability. Fresh Linux/macOS
crash-gate reports are still required. No owned Chromium processes were observed
after the completed Windows gate.

## Actual configuration diagnostics

`app/core/native/diagnostics.py` reads document and dedicated-worker UA, low-entropy
and high-entropy Client Hints, platform, language/languages, timezone, hardware concurrency and
device memory, plus document viewport, screen, DPR, touch and webdriver. It
compares configured and observed values without replacing browser APIs. Worker
probe failures remain explicit; its transient worker/Blob URL are cleaned up.
Native profile health reports include these facts and mismatch warnings.

High-entropy observations include the native architecture, bitness, OS version,
full browser-version list, model, WoW64 and form factors returned by Chromium.
Unavailable APIs stay null; denied observations retain an explicit error, not
invented identity values. The Windows SDK control observed matching document and
worker values on the owned secure loopback fixture and null values on about:blank.
The runtime gate requires real high-entropy hints on its loopback fixture.
Profile settings reject the entire case-insensitive `Sec-CH-UA*` header namespace,
including future identity hints, as well as User-Agent and Accept-Language.
Ordinary custom headers remain supported. This prevents HTTP-only overrides
from contradicting the browser identity; it is not UA or platform masking.
See the [UA Client Hints specification](https://wicg.github.io/ua-client-hints/).

The first Windows probe found that context-level locale alone differed from
worker language. Native now supplies Chromium's own `--lang` and `--accept-lang`
flags from the central validated configuration. Their behavior was inspected in
the pinned Chromium switch/preference source and tested in the actual runtime.
The Windows gate passed with both default English/UTC and non-default German/
Europe-Berlin configuration; document/worker values agreed. The latest report
had eleven checks and retained native patch capabilities as empty. This is native
locale configuration and factual diagnostics, **not an own fingerprint-patched
Chromium build**. Matching reports are recorded below.

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
observed progressing after that correction. Dependency sync and hooks subsequently
completed; own-source compilation is now in progress. Customer/global Git
configuration is not changed.

The docs workflow at that revision initially failed inside Retype with negative
capacity errors. An unmodified, debug-enabled retry of the same run/revision
completed build and deployment successfully; it remains an observed transient,
not a diagnosed Retype fix.

The first Native C++ policy implementation is now public in `native/core/`, with
standalone compilation/tests and a three-platform CI job. Its initial Windows
test passed under MSVC with warnings-as-errors. This is a **compiled policy
prototype**, not an exposed runtime capability. Public Chromium C++ bindings now
exist in the pinned checkout, but complete own-browser compilation and actual
patched API checks remain required. See the
Native source-workspace README for its explicit privacy-ceiling semantics and
verification command.

## Latest verified status

Downloaded reports from [run 38105667238](https://github.com/Tort1k558/Camouflow/actions/runs/38105667238)
at `47ea812` passed all thirteen source-runtime checks on Windows x64, Linux x64
and macOS ARM64, including profile backup/restore and disposable headless binary
health. All report Chromium 148.0.7778.96 and `fingerprint_patched: false`.
QML tests now also exercise Native and its explicit/managed binary selection on
all three platforms; both existing packaged engines passed in the same workflow.
These are upstream bootstrap checks, not three-platform own-fork build proof.

The owned Windows Chromium build reached 4,402 completed actions, then failed
its upstream MIDL output comparison because name hashes depended on the Russian
host locale instead of the locale stored in the type library. Exact-version SDK
tools reproduced the failure. The public locale-normalization patch preserves
the full comparison and made the original failed command pass against unchanged
baseline artifacts. Full compilation has resumed; native fingerprint controls
remain disabled until the own binary passes the dedicated hardware binding gate.

## Cancellation-safe driver stop

The pinned Playwright context manager marks its stop callback consumed before
awaiting connection cleanup. Cancelling that await and calling `stop()` again
can therefore return without having waited for the original cleanup operation.
Native now retains one driver-stop task and shields it from caller cancellation
and its eight-second waiting deadline. A later `close()` waits for that same task
instead of invoking the SDK's one-shot callback again. Profile ownership is
released only after successful completion. A terminal stop error remains an
error on subsequent attempts; it is not converted into a successful no-op.

Unit tests exercise the actual pinned SDK context manager's consumed-callback
behavior with controlled cancellation/timeouts and test retained terminal errors.
The Windows upstream runtime gate now passes fourteen checks: it cancels a real
Native close while its driver-stop task is pending, proves another process cannot
acquire that profile, then waits for the same stop operation and verifies owner
release. There is no simulated browser or injected stop delay in this gate.
Downloaded reports from [run 38106687996](https://github.com/Tort1k558/Camouflow/actions/runs/38106687996)
at `e81f269` now confirm all fourteen checks on Windows x64, Linux x64 and macOS
ARM64. Each reports `fingerprint_patched: false`. This remains upstream bootstrap
evidence; later startup/controller checks and resource soaks require their own
matching results.

## Abrupt controller termination gate

The Windows source gate now also passed an actual hard kill of its owned Python
controller, not a graceful `close()` or a browser-only crash. Before killing it,
the helper verifies that its startup PID is the actual interpreter PID. This is
important on Windows: killing a venv launcher can merely close stdin and let the
real interpreter perform graceful cleanup, which is not controller-crash proof.
The gate launches the base interpreter with the current environment's package
directory explicitly supplied, and checks the PID before issuing the kill.

The process-tree snapshot excludes processes that existed before the helper
started. The test observes both the owned Node driver and Chromium, then waits
for all observed process identities to disappear after controller termination.
Identity uses PID and creation time rather than parent PID or mutable thread
names: reparenting/renaming must not count a surviving orphan as exited. Other processes are not
killed and their command lines are not included in snapshots or reports.

After that exit check, the same owned profile restarted and all five committed
stores were verified: cookies, localStorage, IndexedDB, CacheStorage and service
workers. Two complete Windows runs passed fifteen source-runtime checks; the
latest observed eight controller descendants. The same gate is wired into the
Linux/macOS CI jobs, but matching reports for this revision remain pending.
This verifies the pinned upstream bootstrap runtime, not an own-fork binary,
in-flight write durability, a packaged GUI-controller crash or a long resource soak.

## Cancellation-safe driver startup

Native now retains and shields its driver-start task, with a 30-second startup
waiting deadline. Cancelling startup does not discard a driver that is still
being created: cleanup waits for that same operation and then stops its returned
driver. If the cleanup waiting deadline expires, the operation and profile owner
remain retained; a later `close()` can finish cleanup. A terminal SDK startup
error remains an error, not a successful release of unknown resources.

Both Native itself and the browser adapter check all retained resources, including
pending start/stop tasks and the profile lock. The adapter must not replace a
partially started runtime merely because its public Playwright handle has not
been assigned yet. Unit tests cover cancellation, deadlines, ownership exclusion
and adapter preservation for each retained resource type.

The Windows source gate passed sixteen checks: it cancels real driver startup
without an injected delay, verifies the pending operation was not cancelled,
checks no new owned Node/Chromium processes remain after cleanup, and successfully
starts the same profile again. Matching Windows, Linux x64 and macOS ARM64 CI
reports at `110c381` each passed all sixteen checks. These remain upstream
bootstrap-runtime checks; own-fork build
and runtime verification are separate requirements.

### Linux process-observer correction

The first Linux controller-crash CI check failed with "Owned driver was not
observed". A local Ubuntu 22.04 WSL probe using the Node binary from the exact
Playwright 1.60.0 Linux wheel reproduced the cause: `ps comm` reported `MainThread`,
while `/proc/<pid>/exe` identified the actual executable as `node`.

Linux snapshots now read process birth ticks and parent IDs from `/proc/<pid>/stat`
and observe executable identity separately through `/proc/<pid>/exe`. Inaccessible
executables remain explicitly unknown; their thread names are not substituted as
executable identities. Exited zombie/dead states are excluded. A direct Linux
probe of the updated observer identified that owned Node, tracked its descendants
and verified its exit. The matching Linux CI report at `110c381` then passed the
full sixteen-check gate, including controller death and cancelled driver startup.
Neither the observer probe nor that SDK-runtime gate proves a Linux Chromium fork build.

### Permission verification

The source-runtime gate additionally queries real Chromium geolocation and
notification permission states on the owned loopback fixture. It checks configured
grants, simultaneous profile isolation, revocation, origin-scoped regrant and
reapplication of configuration after a persistent-profile restart. It does not
request location, notifications, camera or microphone access from the host.

An empty configured permission list is an explicit Playwright/CDP override:
these permissions are `denied`, not the browser's ordinary `prompt` state.
`clear_permissions()` resets that override, so revocation is checked against
`prompt`; a subsequent restart reapplies the configured list. This is permission
policy verification, not evidence of media-device emulation or WebRTC leak prevention.

Two complete local Windows runs passed all seventeen checks on the pinned
upstream bootstrap binary; the report includes measured permission states.
Matching reports at `8fe6bbb` passed all seventeen checks on Windows x64,
Linux x64 and macOS ARM64, including these exact permission states. These are
still pinned upstream SDK binaries, not independently built Chromium forks.

## Native graphics observations

Diagnostics now observe native WebGL 1/2 in both the document and a disposable
dedicated worker: standard and unmasked vendor/renderer values, API/shader
versions, texture limits and viewport limits. Each probe uses its own small
OffscreenCanvas and releases its graphics context. Unsupported or blocked APIs
remain explicitly unavailable; no synthetic renderer or JavaScript override is
installed. Available document/worker values are compared for consistency.

The Native Engine health action runs these observations on an owned disposable
profile, displays both standard and unmasked renderer values and any configuration
mismatches, then verifies teardown. The diagnostics card grows with the report.
Binary installation health checks retain their existing version-string API and
do not require graphics observations.

Late Native health/release and workspace-read completions now tolerate a deleted
Qt owner without trying to update destroyed UI objects. Other signal-delivery
errors still propagate. This prevents the observed shutdown-time worker exception;
it does not waive owned-browser teardown or recover a failed SDK cleanup.

On Windows, the seventeen-check source-runtime gate observed the same AMD/ANGLE
renderer and limits in both contexts. A real QML health-button run also observed
matching configured locale/timezone and graphics, rendered the green interface
and cleaned its temporary profile. These are upstream-bootstrap observations,
not evidence of graphics masking or an independently built Native fork.

## Local release management in the GUI

Native Engine health provides a local `.tar.gz` picker, trusted SHA-256 input,
install-and-activate and rollback actions. Select Managed release and its store
explicitly in Native configuration; these operations do not silently change engine settings
or migrate profiles. There is no authenticated online release catalog yet.

Archive verification/extraction and real headless health checks run on an owned,
non-daemon worker. Concurrent release actions are disabled. Activation remains
atomic and old immutable versions remain available; failed health checks retain
the existing active pointer. Successful GUI activation invalidates earlier
compatibility results, including a check that was already in flight. If settings
change during an operation, its completion identifies the previously selected
store rather than adopting the new settings.

Two local Windows GUI runs used three complete upstream browser bundles: two
versions installed and passed real headless activation; a third deliberately
declared the wrong Chromium version and failed without changing the exact
active-pointer bytes; rollback selected the first release and retained all
installed versions. Owned health profiles were cleaned up. The second run also
verified compatibility-result invalidation and rendered the green Windows UI.
These are bootstrap-package checks, not own-fork builds or signed publisher releases.

References: [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
and [browser emulation](https://playwright.dev/python/docs/emulation).
