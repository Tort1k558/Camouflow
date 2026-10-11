# Native Windows verification backlog

Every item below remains **pending on the own-fork executable** until its report
has been inspected. SDK successes, C++ helper tests, saved presets and upstream
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
not a font runtime pass; all own-fork gates above remain pending.

## Executable verification queue

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

The key is not yet connected to Chromium IPC or Canvas/Audio policy. Runtime
capabilities remain unchanged; no fingerprint masking is claimed. Before native
activation, implement versioned domain-separated derivation with explicit
top-level-site/origin/storage partition semantics and test worker inheritance,
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

The [CloakBrowser repository](https://github.com/CloakHQ/CloakBrowser) is a feature
reference, not proof of Native parity. Superiority requires reproducible matched
comparisons, not copied scores or a larger patch count. Linux/macOS remain deferred
at the user's request; their earlier SDK reports are not own-fork verification.
