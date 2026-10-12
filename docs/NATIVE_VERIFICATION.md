# Glint verification

External destinations, run protocol and per-build observations are maintained in
the [Glint test matrix](GLINT_TEST_MATRIX.md). Update it for every linked build.

## Evidence levels

1. Python/source tests prove manager behavior under their fixtures.
2. Standalone C++ tests prove the tested policy primitives.
3. Chromium native units prove the linked native test target, not browser startup.
4. Production object compilation proves those translation units, not chrome.exe.
5. A linked own-fork binary needs actual runtime tests and measured code hashes.
6. Packaged/relocated payloads need independent integrity, lifecycle and rollback checks.

Never treat one level as proof of a broader level. Prepared/unapplied patches,
upstream SDK controls and old reports are not proof of a new own-engine release.

## Public gates

| Tool | Scope |
| --- | --- |
| `scripts/verify_release.py --build --runtime` | Desktop package and packaged legacy-engine checks |
| `scripts/verify_native_cpp.py` | Standalone native policy primitives |
| `scripts/verify_native_privacy_units.py` | Default: 43 exact key/service cases; `--target contexts`: 20 BrowserContext cases; `--target delivery`: 34 document/worker IPC and consumer cases |
| `scripts/verify_native_suite.py` | Runtime, hardware, WebRTC, automation, fonts, identity, CDP and combined gates |
| `scripts/verify_native_storage_paths.py` | Windows path-depth/storage probes |
| `scripts/verify_native_canvas.py` | Canvas verification tooling, not an implemented protection claim |

Run commands as documented in the [build guide](../native/BUILDING.md). Use fresh
report paths outside source/application repositories. Keep raw outputs and
measured executable/core-DLL hashes; a count without exact names and successful
completion is insufficient. Failed or skipped cases are not a passing gate.

The standalone Canvas baseline also measures the executable and Windows core
DLLs before and after observation, and refuses to overwrite an existing report.
For a relocated Windows payload, pass `--windows-library-directory` with its
canonical versioned DLL directory. Canvas consistency is not masking acceptance.
Canvas/combined readback probes cover document, same/cross-origin iframe,
about:blank/srcdoc and dedicated/shared/service workers. Security checks retain
their explicit three document/frame contexts; AudioWorklet and measured OOPIF
process separation are not implied by this coverage.

## Required release checks

- Profile separation and persistence for cookies, localStorage, IndexedDB,
  Cache Storage and service workers across reopen/restart.
- Cross-process owner exclusion, controller death, browser crash and bounded
  cancellation/teardown with no surviving owned browser processes.
- Authenticated proxies and permissions with explicit no-direct-route controls.
- Document/iframe/worker consistency and combined policies, including unsupported
  input rejection with the expected native diagnostic.
- Navigation, forms, extraction, screenshots, Recorder and replay.
- Packaged/relocated resources, full payload integrity, real credits and rollback.
- UI compatibility results invalidated when configuration changes.

Crash persistence covers a gracefully committed checkpoint, not every pending
write. Shared/service worker partitioning, actual Chrome incognito bootstrap and
future renderer key delivery require their own lifecycle evidence.

### Terminal driver-start failure recovery

The manager's failed-start cleanup was checked with both an injected RuntimeError
and a terminally cancelled startup task. In each case the profile lock became
available, the same runtime/profile successfully launched the real Windows browser
on retry, JavaScript evaluation returned the expected value, and closing the
browser released ownership again. This is fault injection followed by real startup,
not proof of recovery from an OS/process crash or a driver subprocess partial start.

Local evidence: `D:/CamouFlowNative/glint-driver-failure-retry-runtime/proof.json`.
The tested browser was Chromium 148.0.7778.96, patches 001–015; unchanged executable
and core-DLL hashes were measured before and after both cases. The executable hash
was `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222`.
The public regressions in `tests/test_native_runtime.py` cover both terminal paths
alongside pending-start cancellation/deadline ownership tests. No active Chromium
build inputs or future Canvas/privacy capabilities were changed by this check.

Additional manager regressions cover delayed driver failure during cleanup of a
cancelled start: both RuntimeError and driver-task cancellation must preserve the
caller's CancelledError, release profile ownership and permit idempotent close.
Existing timeout/caller-cancellation cases still require ownership while startup
is pending. These delayed-failure cases are synthetic task/lock tests, not an
additional browser subprocess fault-injection result.

## BrowserContext destruction fixture correction

The context test target linked successfully after resuming with four compile
jobs. Its first run passed ten cases, then timed out in
`DestructionDuringLoadDoesNotUseDestroyedContext`. `TestBrowserContext` directory
cleanup calls `RunAllTasksUntilIdle`, whose asynchronous ThreadPool flush cannot
finish while this fixture intentionally keeps loader tasks queued. The failing
run was stopped; `privacy-contexts-001-017-resume-j4.json` records failure, not a
passing context gate.

Both destruction cases now transfer directory ownership using `TakePath` into a
local `ScopedTempDir` before destroying the context. BrowserContext shutdown and
owner destruction still happen before queued loader tasks run; directory cleanup
happens afterwards. No production lifecycle code or timeout was weakened.
Patch 0017 and the pinned checkout contain the same corrected fixture. The new
verification run is `privacy-contexts-001-017-teardown-fixed-j4.json`. All twenty
exact cases passed, including both destruction cases, and the strict result
validator was run independently against the saved GTest output. The test binary
SHA-256 was independently remeasured:
`b8314bcf6fb56575650cc647c4791ca17b2d44237aaa1d3a0590ae8b805f5b75`.
The baseline browser executable/core-DLL hashes also matched the report after
execution. This proves the content-layer bridge fixtures, not renderer delivery,
actual Chrome profile startup or Canvas protection. The incremental rebuild had
three steps and reached completed linkage at 14m07.89s; the twenty tests ran in
103 ms. The old failed run remains retained separately.

## Current boundary

The 001-010 Windows development baseline has completed runtime gates and
packaged-payload checks. Key/codec/owner native units are separate evidence.
The newer 001–015 production context integration has linked a Windows browser;
its eight runtime gates (160 checks) passed with independently rechecked report
and core-code hashes. All 33 named native-unit cases also passed and were
independently revalidated. Limited external observations are in the test matrix;
this is not release admission or full key-service behavior proof.
An opt-in actual Chrome profile/OTR startup smoke completed initial/restart
storage-separation checks; it does not observe key-service readiness or derivation.
Readiness patch 0016 is now registered/applied; its ten additional cases extend
the current verifier to 43; all 43 cases compiled and passed. The linked browser
above still contains only 001–015. The twenty real-context cases registered in
patch 0017 have now compiled, linked and passed, with independently checked
result names and binary/core hashes. Neither change has browser release admission.

The base delivery infrastructure is registered/applied as self-contained patches
0018-0020. It includes the Mojo schema, document-scoped endpoint, worker endpoints
bound to browser-owned partition/origin state, and the separately bounded worker
consumer. The first four-job attempt, `privacy-delivery-001-020-first-j4.json`,
failed before test execution: LLVM reported out-of-memory during concurrent V8
snapshot-generator linkage and `dedicated_worker_hosts_for_document` compilation.
This is not a passing IPC gate or evidence of a failed policy assertion. Cached
objects are preserved. Those two targets are retried serially under
`privacy-delivery-heavy-step-retry.json`, then the full four-job unit gate resumes
with a fresh `privacy-delivery-001-020-resume-j4.json`. All 34 required cases must
pass before this unit gate is claimed; serial object/link completion alone is
not sufficient.
Startup gates, Canvas seed thread handoff, Canvas readback hooks and branding
remain unregistered; no protected first-script execution or Canvas capability is
implied by these endpoint registrations.

Current development is Windows-only. Linux/macOS own-fork runtime verification,
Canvas/GPU/audio protection and security rebasing remain required. External
anti-bot scores may be observations, never guaranteed release capabilities.
