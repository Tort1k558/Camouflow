# Native Windows verification backlog

An item is **pending on the own-fork executable** until its matching report
has been inspected. Observed own-fork results are recorded below; SDK successes,
C++ helper tests, saved presets and upstream
marketing tables do not change that status. Keep failed reports, not just passes.
The running source tree must not be changed while compilation is active.

### Windows compile correction, 2026-10-11

The four-job build terminated with exit code 1 after 6h6m23s: 8470 actions
completed, one failed and 21592 remained. The failing translation unit was
`dwrite_font_proxy_impl_win.cc`; Chromium's `-Werror,-Wexit-time-destructors`
rejected the font configuration helper's cached static optional/vector.
After verifying the builder had exited, the public header, patch 0005 and owned
checkout were updated to use Chromium's existing function-local
`base::NoDestructor`. Policy parsing and native-value behavior are unchanged.
Exact pinned-source patch validation passed. All three real affected Chromium
translation units (`dwrite_font_proxy_impl_win`, `font_enumeration_data_source_win`
and `font_data_service_impl`) then compiled successfully with the existing Ninja
flags, including the failing warning-as-error policy: three steps, exit code 0.
The local regression suite passed 980 tests. This is a compile-policy correction,
not a font runtime pass; own-fork gates were still pending at that point.

## First own Windows build and partial runtime results, 2026-10-12

The resumed four-job build completed with terminal exit code 0 after 7h29m53s
(17,486 executed actions; 63,579 skipped cached actions). This was not a new
from-scratch build. The existing post-build gate revalidated pinned sources,
patches 0001–0005 and GN inputs before writing `camouflow-build.json`.
The measured `chrome.exe` checksum matches its receipt:
`61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222`.
The executable and DLL are in
`D:\CamouFlowNative\chromium\src\out\CamouFlowNative`.

The first own-fork suite is retained privately in
`D:\CamouFlowNative\verification-001-005-20261012`:

| Gate | Own-fork result | Scope |
| --- | --- | --- |
| Runtime | PASS, 18 checks | Lifecycle, isolated persistent stores, owned process cleanup, crash recovery checkpoints, proxy, permissions, scenarios and Recorder |
| WebRTC | PASS, 7 checks | Owned STUN positive control, protected document/frames and rejected malformed native policy |
| Automation | PASS, 55 checks | Native webdriver binding, initial scripts, frames/targets/workers and CDP override interactions; not general bot resistance |
| Windows fonts | PASS, 42 checks | Genuine collection/styles, CSS/local(), canvas rendering, downloaded fonts, workers, enumeration and restart |
| Hardware | FAIL / interrupted | The malformed renderer-configuration case stalled during teardown; only its identified test browser/driver were stopped. This run is not admissible as a passing hardware gate. |

The suite returned exit code 1 and `passed: false`; it also has `full_suite: false`
because draft identity/CDP patches 0006/0007 were not compiled. Hardware API reads
and context closing now have explicit deadlines; a timeout remains a failure.
The bounded retry (`D:\CamouFlowNative\hardware-bounded-retry-20261012.json`)
completed without manual termination and retained five passing positive hardware
checks, but failed with `TimeoutError` while reading an invalid configuration.
No matching hardware fixture processes remained afterward. This reproduces the
negative-case problem instead of treating a manually induced crash as a pass.
Browser-side validation before renderer creation and a fresh full hardware gate
are still required; the five positive cases alone do not admit the capability.
The updated patch 0001 now validates both hardware switches in the browser
process before forwarding them to a renderer, using the same bounded parser as
Blink. Empty explicitly supplied values are rejected too. Exact pinned-source
patch comparison and Chromium dependency checks passed; 217 release-tool tests
passed. The negative runtime probe now requires the specific native validation
diagnostic at startup: unrelated launch failures and timeouts cannot count as
successful rejection. The complete local Python/QML suite passed 1,026 tests.
The incremental four-job Windows rebuild is recorded in
`D:\CamouFlowNative\native-build-browser-hardware-validation-j4.log`.
This is a source correction awaiting rebuilt runtime evidence, not a hardware
capability pass. The preceding binary and receipt are retained separately as
core evidence, not as a complete runnable rollback package.
No capability is enabled merely because its setting is saved. The first receipt
still records `fingerprint_patched: false` and
`native_patch_runtime_verified: false`. Packaged-payload verification, combined
policy admission, public-site observations and a shipping release remain pending.

### Browser-side hardware correction: own runtime passed

The incremental four-job build completed with exit code 0: four executed steps
in 5m49.98s after GN generation. The affected browser translation unit and
`chrome.dll` linked successfully; pinned-source checks refreshed the receipt.
The standalone hardware gate then passed all nine cases on Chromium
148.0.7778.96, recorded in
`D:\CamouFlowNative\hardware-browser-validation-own-20261012.json`.
Five positive cases cover native values, independent overrides and ceilings in
documents, frames and workers. Four malformed values are rejected at browser
startup with the expected native validation diagnostic, not a renderer timeout.
This supersedes the failed hardware result for the preceding build, not the
unfinished full-suite, combined-policy or release-admission work.

The launcher checksum stayed unchanged after relinking, while `chrome.dll` is
now `01c34e325fbc7c8f3ae53a235c4d39e0a8aebbbb75dad21a0ff0190c7f5a0174`.
Runtime reports now measure Windows `chrome.exe`, `chrome.dll` and
`chrome_elf.dll` before and after the checks; changed or missing code fails.
The Windows packager requires the matching three-file measurement and rejects
old launcher-only reports. This closes stale runtime admission after a DLL-only
rebuild; it is not a signature or proof of every resource file's runtime behavior.
The existing archive verifier still measures every packaged file separately.
Regression coverage rejects missing/mismatched core hashes and a changed DLL
even when staging matches it and the launcher is unchanged. The full local suite
passed 1,036 tests after this correction.

## Executable verification queue

### Combined compiled-policy gate, 2026-10-12

The corrected own build passed the repeated five-gate suite: runtime 18,
hardware 9, WebRTC 7, automation 55 and Windows fonts 42 checks. Reports are in
`D:\CamouFlowNative\verification-browser-hardware-validation-20261012`.
The suite is deliberately partial: draft identity/CDP patches remain unapplied.

`scripts/verify_native_combined.py` now runs the compiled hardware, font,
WebRTC and automation policies together. Two distinct persistent profiles are
checked sequentially, then each is reopened. Every phase measures documents,
same/cross-origin frames and dedicated/shared/service workers, compares Canvas
reads/exports/geometry, checks frame security behavior and tests protected WebRTC
against an owned loopback observer. A separate unprotected STUN positive control
must emit packets. Local storage markers must remain profile-specific on restart.
Windows executable/DLL hashes are measured before and after the complete run.

The own build passed all five aggregate checks in
`D:\CamouFlowNative\combined-own-001-005-20261012.json`: all six contexts reported
CPU 1 and memory 0.25; document/frame webdriver was false; Courier New resolved
to the genuine allowed Arial metrics. Protected WebRTC completed without direct
UDP packets, and Canvas compatibility checks stayed intact. The upstream SDK
failed the identical probe with CPU 12, memory 16, webdriver true and distinct
Courier metrics, retained in `D:\CamouFlowNative\combined-sdk-negative-20261012.json`.

The suite includes a `combined` gate and rejects missing/duplicate phases,
altered policy arguments and incomplete runtime code measurements. All 1,054
local regression tests passed. This is compiled-policy combination evidence,
not Canvas protection, profile-key transport, concurrent protected sessions,
identity/CDP patch verification, release capability admission or CAPTCHA proof.
Manager policy activation remains blocked pending the complete release contract.

### First official archive and delivery blockers

The official `mini_installer_archive` target finished with exit code 0 in
1m15.13s (37 executed steps). The tested executable/DLL hashes, build receipt,
GN arguments and pinned patches remained unchanged; no installer was executed.
The first real staging run exposed `chrome.release`'s explicit asset relocation:
root-output `Logo.png` and `SmallLogo.png` become versioned `VisualElements`
files. The packager now maps only those two names and still compares their
hashes against the compiled-output assets. Missing or changed assets fail.

A 261-file development archive was created on D:, checksum
`e2f018adca64dc710b1724e1c50e2d651214f69bfa2f091ee84fcc42a5d45573`, and installed
through the existing immutable store at `D:\CamouFlowNative\owned-release-store-001-005`.
This isolated test store was not activated for the user's application and is
not a customer release. Versioned package DLL measurements now require an
explicit `--windows-library-directory`: canonical package-owned storage and a
directory matching the actual browser version. No library search fallback was
added.

Two real delivery probes failed and their evidence is retained. Embedded
`chrome://credits` was only Chromium's sample page, explicitly requesting
`generate_about_credits=true`. That GN input is now enabled; rebuild, actual
license-page inspection, re-staging and package verification are required.
Do not distribute the preceding archive as a shipping release.

The first relocated runtime probe stopped at a duplicate QA account. The new
hash helper had imported the distribution utility, which eagerly imported the
application database before the verifier established its temporary data root.
The helper now hashes with the existing standard-library pattern without that
early import. A subprocess regression proves verifier import leaves the database
uncached; an explicit workspace guard precedes any QA account creation. The
identified QA account was removed without altering other account records or
removing profile directories. The earlier runtime report with this import
regression does not establish owned-workspace isolation. A fresh isolated
relocated runtime run is required, not reuse of its partial failure or older
18-check result as full delivery admission.
The local suite passed 1,064 tests with the visual-asset mapping, explicit
versioned DLL layout, deferred database import, workspace guard and real-credit
GN setting. The credits rebuild and isolated packaged-runtime retry remain live
checks, not results inferred from those unit tests.

### Relocated baseline passed; real credits rebuilt

After the import correction, the fresh isolated relocated runtime passed all
18 checks, including scenarios/Recorder, storage checkpoints, permissions,
proxy routing and three-profile crash/restart rounds with zero owned survivors.
Its report is `D:\CamouFlowNative\runtime-own-packaged-isolated-001-005-20261012.json`.
This proves the relocated development baseline works; its sample credits still
prevent shipping that archive.

Real credits generation and resource packing completed with exit code 0:
three executed steps in 4m12.89s. The explicitly selected own source executable
then rendered actual `chrome://credits` with 19,465,020 HTML bytes and third-party
entries, recorded in `D:\CamouFlowNative\own-source-real-credits.json` and HTML.
The three Windows code hashes stayed unchanged; the generated resource payload
and GN receipt changed. This is rendered-license evidence, not a complete legal
compliance review. Official staging is being regenerated before creating a new
archive; previous immutable packages are not overwritten.

The runtime verifier additionally accepts paired `--release-store` and
`--release-sha256` arguments. It verifies every file through the existing immutable
store before/after the runtime, requires matching own-fork executable/versioned
DLL identity and records the archive checksum plus all payload hashes. This
closes the resource-file gap left by measuring only executable code. It does not
authenticate a release catalog or admit privacy capabilities. The complete local
suite passed 1,070 tests. The first full-payload run then passed all 18 runtime
checks, recorded in `D:\CamouFlowNative\runtime-own-packaged-full-payload-001-005-20261012.json`.
Its archive checksum and all 261 payload hashes match the installed development
release exactly. The new real-credit package still requires its own relocated
checks; the earlier sample-credit archive is not promoted by this result.

### Real-credit baseline verified; identity/inspector compilation started

Official re-staging finished in 24.75s (one executed action). The new 261-file
development archive has checksum
`cd5f2bbd8ebf3e440bd1647ab2574c315f68154a8e860c8241b1c6d0aed0a167`.
It was installed alongside the preceding release in the isolated store, without
activating either release for the user's application. Its own full-payload
runtime passed all 18 checks and every file measurement:
`D:\CamouFlowNative\runtime-own-packaged-real-credits-full-payload-001-005-20261012.json`.
The packaged credits page rendered the same actual license HTML as the source
build, retained in `D:\CamouFlowNative\own-packaged-real-credits-001-005.json`.
This is the immutable Windows development baseline for subsequent engine work,
not publication, authenticated update metadata or complete product readiness.

After confirming all preceding builders had terminated, patches 0006 and 0007
were applied to Chromium and its pinned V8 repository respectively. Strict
source comparison and dependency checks passed. Both affected translation units
(`user_agent_utils` and `value-mirror`) compiled successfully under the existing
warning/error settings. The four-job incremental build is still running in
`D:\CamouFlowNative\native-build-identity-inspector-j4.log`; its V8 snapshot/cache
generators and browser link must finish before runtime verification. No own
identity/CDP runtime pass is claimed from translation-unit compilation.

The combined gate now also requests native UA and compares actual browser major,
JavaScript UA and HTTP UA in all six contexts. Genuine Client Hints remain the
separate identity gate's responsibility. The preceding immutable own baseline
correctly failed the new combined probe specifically on headless UA, after its
STUN control and four earlier policies succeeded; evidence is in
`D:\CamouFlowNative\combined-baseline-missing-identity-owned-negative-20261012.json`.
An initial invocation without the required versioned DLL path failed before
browser testing and is not an admissible negative control. The explicit package
DLL option is now supported, without automatic search. The local regression
suite passed 1,073 tests. Rebuilt identity/CDP gates and the five-policy combined
run are pending; profile-key transport and native Canvas protection remain
unimplemented, and manager capability admission remains blocked.

### Canvas baseline rendering anchors

The Canvas probe now also measures a partially clipped rectangle's transparent
padding, a literal opaque RGBA corner and a literal semitransparent RGBA sample.
An implementation returning empty/constant images can no longer pass merely
because repeated and exported hashes agree. These baseline invariants passed
in six contexts and after restart on the immutable own real-credit package;
the four aggregate reports are retained in
`D:\CamouFlowNative\canvas-rendering-anchor-owned-baseline-20261012.json`.
No source inputs of the active identity/inspector build were modified.
These are still unprotected drawing expectations: protected-policy acceptance
needs a separate justified transformation contract, not weaker baseline checks.

### First complete 0001-0007 run: inspector failure retained

The build finished with exit code 0 in 13m32.12s (56 executed steps). The full
eight-gate run returned exit code 1 and `passed: false`, retained in
`D:\CamouFlowNative\verification-001-007-full-20261012` with its original receipt.
Identity passed 18 checks, combined policies 5, runtime 18, hardware 9,
WebRTC 7, automation 55 and fonts 42. Inspector/CDP failed: Error name/message
accessors and `Error.prepareStackTrace` were still executed during console
serialization. Ordinary seven-type native previews and explicit access controls
passed; that is not a passing no-side-effect gate.

An owned diagnostic recorded actual getter call stacks in
`D:\CamouFlowNative\owned-error-preview-call-traces.json`. The uncovered paths
were console text coercion through `Error.toString` and native accessor reads
during property preview. Patch 0007 now reuses its safe descriptor-based Error
description for console text without stack formatting, and routes native Error
property-preview reads through the same guarded helper. Other console values
retain their existing conversion path; explicit page reads are not replaced.
The criteria and failed reports were not weakened or overwritten.

The corrected three-file V8 patch exactly matches the pinned checkout and its
whitespace check passed. Its incremental four-job build is running in
`D:\CamouFlowNative\native-build-inspector-console-correction-j4.log`.
Recompiled inspector/console units, the native side-effect gate, explicit lazy
stack controls and the complete suite still require fresh runtime evidence.
This correction is not yet a verified CDP capability or general invisibility.
All 1,077 local regression tests passed; the added regression requires coverage
of both newly identified preview paths in the public patch.
The first correction build stopped with exit code 1 after 22.67s: the property
iterator supplies `v8::Name` (string or symbol), while the guarded helper accepted
only `v8::String`. The helper now accepts native property keys without string
coercion and applies stack-specific checks only to string keys. Exact pinned V8
comparison and whitespace checks passed; 268 release-tool tests passed. The
new four-job retry is in
`D:\CamouFlowNative\native-build-inspector-console-name-fixed-j4.log`.
Neither compilation retry substitutes for the unchanged runtime acceptance gate.
Both corrected inspector translation units subsequently compiled successfully
in the retry; snapshot-generator and browser linking remain in progress.

### Suite-wide executable-code binding

The suite now snapshots all three Windows executable-code files before any
child gate, rechecks them before/after each child and records their hashes in
the suite report. It stops subsequent gates on code drift even if `chrome.exe`
is unchanged. Child reports that contain a code measurement must match that
same suite snapshot. This prevents a full-suite PASS assembled across DLL-only
rebuilds; it does not replace complete packaged-resource verification.

`--windows-library-directory` also enables an explicit versioned `Chrome-bin`
suite. The suite measures that directory and forwards the argument only to
runtime/combined validators, the two children that need it; other gates retain
their existing browser launch contracts. Regressions cover unchanged-launcher
DLL drift, mismatched child DLL evidence and supported-only argument propagation.
There is no automatic library search or silent legacy-code measurement fallback.
The complete local regression suite passed 1,080 tests after this change.

### Corrected native Error serialization gate passed

The retry finished with exit code 0 in 6m25.39s (55 executed steps), refreshed
the exact-source receipt and measured `chrome.dll` as
`d375da9b9bd93064334d4a3a1c768906b22e3b17bfe322fc0386cfccff490e56`.
The new full eight-gate run is retained in
`D:\CamouFlowNative\verification-inspector-console-corrected-full-20261012`.
Its first inspector/CDP gate passed all six aggregate checks: own/inherited
stack/name/message getter counters stayed zero during serialization, custom
`Error.prepareStackTrace` stayed zero during preview, and explicit reads invoked
the formatter once for the same Error and twice including a fresh Error.
All seven ordinary native Error descriptions/stacks and explicit accessor
controls were preserved. This proves the measured Error-preview contract, not
general CDP invisibility, public-site classifications or CAPTCHA acceptance.
The other seven groups are still running; a complete suite PASS is not inferred
from the first passing gate. Shipping/capability admission remains pending.

| Area | Prepared artifact | Required own-fork evidence |
| --- | --- | --- |
| Lifecycle and storage | `verify_native_runtime.py` | All 18 checks; five stores survive committed checkpoints; independent profiles; lock exclusion; cancellation; zero owned survivors after controller death and three-profile restart rounds |
| Hardware ceilings, patch 0001 | `verify_native_hardware.py` | Native document/frame/worker observations; actual ceilings, not invented hardware; ignored-switch negative control; invalid settings fail explicitly |
| Windows MIDL compatibility, patch 0002 | Build receipt and generated TLB comparison | Pinned source/toolchain, successful own build, unchanged expected generated interfaces; no system locale change |
| WebRTC routing, patch 0003 | `verify_native_webrtc.py` | Baseline actually sends owned STUN UDP; protected document/same-origin/cross-origin contexts do not; invalid policy rejected; do not infer TURN/media connectivity |
| webdriver, patch 0004 | `verify_native_automation.py` | First script, native descriptors, frames, new targets, workers and CDP override; explicit native getter reads still work |
| Windows fonts, patch 0005 | `verify_native_fonts.py` | Real installed styles and glyph fallback; CSS local fonts, canvas metrics/pixels, frames/workers, downloaded font, local enumeration and restart; no fabricated fonts |
| UA coherence, draft 0006 | `verify_native_identity.py` | Apply only after current build stops; compile; actual version/platform retained; HTTP UA/Client Hints match document/worker values; invalid values fail |
| Inspector side effects, V8 draft 0007 | `verify_native_cdp.py` | Apply inside pinned V8 checkout after current build; compile; own/inherited Error accessors not executed by serialization; seven native Error stacks preserved; lazy custom formatter works on explicit reads without poisoning cached stacks |
| Manager policy activation | `NativePrivacyPolicy`, Native Fingerprint tab | Saved policy mapped to verified binary capabilities; unsupported binary rejected before driver/profile creation; requested switches observed in every relevant context; defaults remain usable |
| Shipping | `package_native_windows.py`, managed store | Official installer staging; complete DLL/resource checksums; relocated packaged runtime; licenses/credits; real install/activation/rollback; failed health retains active pointer |

## Sequential post-build runner

From the public repository, using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_suite.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --report-dir D:\CamouFlowNative\verification-001-005 --gates runtime hardware webrtc automation fonts
```

After 0006/0007 are applied and rebuilt, run the default full suite into a **new**
directory by omitting `--gates`. The runner executes gates sequentially, retains
each JSON report and process log, binds passing reports to the measured executable
SHA-256, continues after an ordinary gate failure, and stops on executable drift.
`suite.json` is updated after every gate. A selected subset is explicitly marked
`full_suite: false`; never use that result as full-release admission.

This runner does not automatically launch after compilation, download a browser,
approve capabilities or replace source provenance. Executable hashing alone does
not authenticate DLLs/resources: shipping must also pass complete payload checks.
Each existing gate owns its temporary profiles; the runner does not kill unrelated
processes or delete work directories on interruption. Inspect interrupted cleanup
before another run. No public accounts or paid APIs are used by these fixtures.

On 2026-10-11 the orchestrator was exercised against the pinned upstream Windows
SDK executable (`290fa7018fda22c52ada5eddb0113baf3ebc41fd0fde6085eddb19793606c635`)
with hardware and WebRTC selected. Both real gates correctly failed: native
hardware switches were ignored (12/16 instead of 1/0.25) and direct owned STUN
UDP was observed. The runner retained both reports/logs, continued to the second
gate and returned exit code 1 with `full_suite: false`. This proves orchestration
and negative-control handling, not own-fork policy effectiveness.

## Next implementation and regression requirements

### Local profile privacy identity

Native startup now creates or validates a 256-bit random profile key under its
exclusive runtime lock, before starting the Playwright driver. The key is stored
in `native/camouflow-native-privacy.json` inside that profile's browser storage.
Writes use Qt atomic save with direct-write fallback disabled. Invalid existing
keys fail closed rather than silently rotating. The key is excluded from object
representations and is not passed through settings, browser arguments or page JS.

Profile exports never include this key, including exports with secrets enabled.
Restore already creates a new local identity; it discards imported privacy-key
files and the next Native start generates a new key. The original is unchanged.
This is local key persistence, **not encrypted storage** or a Windows ACL vault;
the local OS user can read the file. Browser storage itself may contain other
secrets when sessions are exported. Raw directory copying is not a supported
profile clone API and can still copy the key.

`NativePrivacyIdentity.derive` now computes HMAC-SHA256 with separate labels for
Canvas, WebGL, WebGPU and Audio and a bounded opaque browser partition key.
The versioned message is the ASCII prefix `CamouFlowNative/privacy/v1`, a NUL,
then a four-byte big-endian surface length, the ASCII surface label, a four-byte
big-endian partition length and the exact partition bytes. It does not parse
URLs or guess registrable domains. The native C++ message encoder in
`native/core/privacy_partition.h` implements the same contract; the future
browser-side signer must use pinned Chromium `crypto::hmac::SignSha256`, not
custom cryptography. The synthetic fixed-key Python vector was independently
matched with Windows .NET HMACSHA256. Native C++ encoding tests compile and run
through the existing Windows policy verifier; Chromium signer/IPC integration
is still pending.

The key is not yet connected to Chromium IPC or Canvas/Audio policy. Runtime
capabilities remain unchanged; no fingerprint masking is claimed. Before native
activation, connect derivation to trusted browser-owned top-level-site/origin/
storage partition semantics and test worker inheritance,
restart, restore and cross-profile separation against the own-fork executable.
The updated runtime passed all 18 existing owned Windows SDK runtime checks;
the report is retained privately at
`D:\CamouFlowNative\runtime-profile-keys-20261012.json`. This includes restart,
backup/restore, process ownership, crash recovery and three-profile isolation;
it is compatibility evidence for key persistence, not native masking evidence.

### Canvas baseline before native protection

`scripts/verify_native_canvas.py` measures an unmodified browser without injecting
API replacements. It renders an owned opaque text/gradient fixture and checks
repeated pixel reads against PNG-decoded `OffscreenCanvas.convertToBlob`, HTML
`toBlob` and `toDataURL`. Documents, same/cross-origin frames and dedicated/shared/
service workers are measured, then the same persistent profile is reopened.
The three document/frame contexts also check origin-tainted HTML and Offscreen
pixel/export failures (`SecurityError`), zero-width reads (`IndexSizeError`) and
empty HTML exports (`data:,` and null Blob). Their expected native behavior must
remain intact under future protection. No page API is replaced by this fixture.

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_canvas.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative --report D:\CamouFlowNative\canvas-native-baseline.json
```

The pinned upstream Windows SDK passed both phases on 2026-10-11; evidence is
retained privately in `D:\CamouFlowNative\canvas-baseline-20261011.json` with the
measured executable checksum. This proves baseline readback consistency, not
Canvas protection, own-fork readiness, cross-profile unlinkability or anti-bot
acceptance. The probe is deliberately outside release capability admission.
The expanded four-check baseline also passed the SDK on 2026-10-12, recorded in
`D:\CamouFlowNative\canvas-security-baseline-20261012.json`. It does not yet cover
worker-origin taint, transparent/color-managed images, partial readbacks, WebGL
exports or protected-policy expectations. Future origin-scoped
protection requires a separate validator: equal cross-origin output is an
unmodified baseline invariant, not necessarily a protected-policy invariant.

The later geometry baseline adds five checks in every document/frame/worker
context and repeats them after restart: subrectangle bytes agree with the full
read, negative dimensions select the same rectangle, fully out-of-bounds reads
remain transparent, semitransparent reads repeat and their decoded PNG exports
agree. All observations and the existing security checks passed on the pinned
upstream Windows SDK, retained in
`D:\CamouFlowNative\canvas-geometry-sdk-baseline-20261012.json`.
This is not own-fork or protected-policy evidence. Color-managed/float images,
partially clipped rectangles, worker taint, WebGL exports and editor round trips
remain uncovered. Validator regressions reject missing, false, numeric and extra
geometry results instead of accepting truthy or incomplete observations.
The complete local regression suite passed 1,030 tests after this increment.
The rebuilt own-fork Chromium 148.0.7778.96 subsequently passed all four baseline
checks too, including all geometry observations in six contexts across restart,
at `D:\CamouFlowNative\canvas-geometry-own-baseline-20261012.json`.
This establishes an own-fork compatibility baseline before protection, not a
native Canvas mask or partition-key transport implementation.

- **Capability admission:** bind reviewed gate reports to exact source patches,
  own build receipt and complete packaged payload; never accept an arbitrary
  `fingerprint_patched` settings bit. Activate only requested verified policies.
- **Per-profile identity policy:** isolate overrides and validate coherent locale,
  timezone, viewport, hardware/font constraints; preserve settings through backup,
  clone and restore without sharing browser storage.
- **Graphics/privacy design:** specify persistent profile policy before adding
  native Canvas/WebGL/audio protections. Test document, frames, dedicated/shared/
  service workers, OffscreenCanvas, API errors, unchanged explicit reads, restart
  stability and cross-profile separation. Current observations are not masking.
- **Network privacy:** add owned HTTPS/proxy fixtures for WebSocket, service-worker
  traffic, DNS failure, reconnect and redirects. Measure TLS/HTTP2 on the same
  browser version and route; do not equate a proxy's fingerprint with Chromium's.
- **Usability:** headed launch, downloads/uploads, dialogs, PDF/plugins, video,
  clipboard and permission revocation; privacy must not silently break workflows.
- **Automation:** actual scenario/Recorder/AI replay under the activated policy;
  cancellation, deterministic ownership and timeout cleanup remain mandatory.
- **Public benchmark observations:** BrowserScan, bot.incolumitas.com,
  deviceandbrowserinfo.com and public Fingerprint demos, within site limits.
  Save version, mode, route, timestamp, raw observations and repeat rounds.
  CAPTCHA outcomes require a permitted test integration and server-side evidence;
  do not promise scores or infer them from a screenshot.
- **Release maintenance:** security-update/rebase procedure, reviewed patch drift,
  authenticated release metadata, rollback and explicit platform support status.

## Windows storage path regression (2026-10-12)

The own-fork 0001-0007 full suite passed seven of eight gates; runtime failed
while opening CacheStorage in a nested manager profile. A proposed launch-only
Windows extended path prefix (`\\?\`) passed cache creation, replacement,
restart and deletion, but the full runtime gate then failed on IndexedDB.
An independent eight-case desktop/mobile matrix confirmed IndexedDB failure
even at a 90-character profile path with that prefix. The launch change was
rejected and removed; it is not a released fix.

The public `scripts/verify_native_storage_paths.py` now tests exact profile path
lengths 90, 130, 150 and 170 in both desktop and Mobile Web Emulation modes.
Each case checks cookies, localStorage, IndexedDB, CacheStorage and service
worker registration through creation, replacement and browser restart, then
checks cache entry and cache deletion. It uses only owned disposable profiles
and loopback fixtures, continues after individual failures and binds reports to
all three Windows runtime code files. Existing reports are never overwritten.

Run against the explicit own-fork output, using an existing short work root:

```powershell
.\.venv\Scripts\python.exe scripts\verify_native_storage_paths.py `
  --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe `
  --work-dir D:\CamouFlowNative `
  --report D:\CamouFlowNative\storage-path-matrix-own-normal-20261012.json
```

The recorded normal-path matrix passed the two 90-character cases and failed
the six longer cases: at 130 characters cache writes reported `Entry already
exists`; at 150/170 characters CacheStorage opening failed. This is a storage
compatibility blocker, not a successful release gate. Source-level filesystem
and storage-service handling needs correction and revalidation of the same
matrix, full runtime suite and relocated package. Shortening the fixture path,
skipping IndexedDB or disabling sandboxing does not resolve this requirement.
Private negative-control reports are retained on D under
`owned-all-store-extended-path-results.json` and
`verification-long-path-runtime-corrected-full-20261012/`.

Native logging narrowed the rejected prefix regression to LevelDB `LockFile`:
its generated `...database/LOCK` path contains a forward slash after the Windows
extended prefix. An owned direct `CreateFileW` control reproduced error 123
(`ERROR_INVALID_NAME`) for that mixed-separator path; replacing the separator
with a backslash opened the same owned lock file successfully. Evidence is in
`owned-prefixed-indexeddb-native-log.json` and
`owned-extended-lock-win32-path-results.json`. This identifies a concrete native
path-normalization issue; it does not prove that normalization alone resolves
all longer-path operations. Chromium also contains explicit `MAX_PATH` limits
for deletion, moves and component-length checks, which need separate review.
After rejecting the launch change and adding the regression matrix, the local
project suite passed 1,092 tests. Passing unit tests do not override the failing
real storage matrix.

The subsequent own-fork rebuild with `0008` succeeded (10m05.72s, 51 executed
steps, exit zero); the measured `chrome.dll` was
`e4aaaaf2f779989d11ee80a0acb963f601e631b1e7261914e0bbab18dca5dd73`.
The extended-path eight-case proof in
`D:\CamouFlowNative\owned-normalized-extended-store-proof.json` measured all three
runtime code files before and after execution and confirmed they were unchanged.
IndexedDB, localStorage, CacheStorage and service-worker registrations retained
the expected values after restart; cache entry/cache deletion also succeeded in
every case. Cookies alone were empty after restart in every case, so the matrix
correctly remained failed rather than promoting a cache-only fix.

A separate ordinary-versus-extended control in
`D:\CamouFlowNative\owned-extended-cookie-persistence.json` confirmed cookie
retention on the ordinary path and loss on the extended path. The extended
profile did not contain a persistent Cookies database. Inspection of the pinned
exclusive SQLite open found that its query-injection guard rejects the `?` in
the Windows namespace marker before opening the database. Patch `0009` exempts
only that initial marker, preserves URI escaping and rejects any later query
delimiter. Native SQL tests cover reopen/exclusive locking and appended query
rejection; their execution and the new runtime proof remain pending. A new
four-job source rebuild has been started. The manager still uses ordinary
canonical paths; no launch retry, profile relocation, encryption downgrade or
sandbox bypass was introduced. The local project suite passed 1,094 tests after
this increment; this is not a passing own-fork storage/runtime release gate.

The `0009` own-fork build subsequently finished successfully (5m02.51s, 54
executed steps, exit zero). The new direct extended-path proof passed all eight
desktop/mobile cases at profile lengths 90/130/150/170, including cookies after
restart and cache entry/cache deletion. It required exact `0008` and `0009`
patch identities in the own-build receipt and unchanged measurements of all
three runtime code files. Report:
`D:\CamouFlowNative\owned-sql-namespace-extended-store-proof.json`.
This establishes direct-launch storage compatibility for those cases, not
manager integration, arbitrary Windows path lengths, UNC availability, native
SQL unit test completion or full runtime/anti-bot release acceptance. The native
SQL test target is currently building; its query-rejection and exclusive-lock
cases must pass independently. Browser-internal namespace integration remains
an isolated D draft until that build is terminal; app lifecycle/ownership paths
have not been modified or silently retried.

The Windows `sql_unittests` target subsequently built and ran all 54 selected
native tests successfully (18 each: ordinary special-character open,
extended-namespace write/reopen with exclusive locking, and appended-query
rejection). Proof `D:\CamouFlowNative\native-sql-namespace-unit-proof.json` binds
the run to exact applied patches and unchanged browser code, receipt and GN
arguments; raw native results are in `native-sql-namespace-unit-results.json`.
Only after that process was terminal was `0010` applied. It converts Windows
user-data path syntax inside Chromium without changing the app's canonical
profile ownership/lock paths or introducing a second launch attempt. Its new
four-job build and ordinary-launch storage/full runtime gates remain pending.
The successful eight-case direct proof on `0009` must not be reused as evidence
that `0010` manager integration works.

The `0010` four-job own-fork build completed successfully in 1m26.85s, with five
executed build steps and terminal exit zero. Its measured `chrome.dll` is
`b52b8c7cb66aa83f97d1cb46179a8033c7bfcf48cbfa4260a1f410ee803aa334`.
The public **ordinary-launch** eight-case storage matrix passed through the
unchanged app `NativeRuntime` at profile path lengths 90/130/150/170:
`D:\CamouFlowNative\storage-path-matrix-browser-owned-namespace-20261012.json`.
This closes the reproduced app storage path regression without a launch-prefix
workaround in Python. The full lifecycle/runtime gate also passed all 18 checks,
including existing Recorder capture/replay and profile backup/restore, under
the original nested report/workspace structure. Three concurrent profiles
completed three restart/crash rounds, with zero surviving owned processes in
each round. Report:
`D:\CamouFlowNative\verification-browser-owned-profile-namespace-full-20261012/runtime.json`.
The remaining eight-gate suite execution, new shipping archive and relocated
package verification remain pending; this is not full release admission.

The [CloakBrowser repository](https://github.com/CloakHQ/CloakBrowser) is a feature
reference, not proof of Native parity. Superiority requires reproducible matched
comparisons, not copied scores or a larger patch count. Linux/macOS remain deferred
at the user's request; their earlier SDK reports are not own-fork verification.
