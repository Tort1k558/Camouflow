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
| `scripts/verify_native_worker_startup.py` | Thirty owned classic/module startup/restart and unavailable-policy cases; no Canvas admission |

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
The serial retry was subsequently interrupted at the user's request to return
to four concurrent tasks after freeing memory. Its partial log is retained, not
a passing serial proof. The active replacement uses a new report path,
`privacy-delivery-001-020-user-resume-j4.json`, and preserves completed objects.
That replacement linked successfully and passed twenty cases before a Mojo
DCHECK terminated `DuplicateRequestCancelsPendingDelivery`. The worker endpoint
discarded a pending reply while its receiver was still connected. Global
`mojo::ReportBadMessage` is not the receiver-owning close operation needed here.
The service now references its owning `UniqueReceiverSet` and invokes that set's
`ReportBadMessage`, which removes the receiver and destroys the service with its
timer, weak callbacks and pending reply. All three worker hosts and the fixture
pass the same owning set explicitly; the duplicate test additionally requires
that the set is empty. No DCHECK, bad-message observation or zero-reply assertion
was disabled. Patch 0019 and canonical snapshots were updated together after the
failed runner terminated. The new full gate uses
`privacy-delivery-001-020-duplicate-pipe-fixed-j4.json` failed compilation because
Chromium's raw-reference checker requires `raw_ref` for the stored receiver-set
reference. The member now uses `const raw_ref`, without suppressing the checker.
The corrected full gate is `privacy-delivery-001-020-raw-ref-fixed-j4.json`; its
result passed all 34 exact cases. Saved GTest output, canonical source hashes,
test binary and baseline browser core hashes were independently revalidated.
The linked test binary SHA-256 is
`c5d7b6b8e41abc035dbfd6eb26d274eb80d3d0c59e7d427980fde675a6305a19`.
Incremental linkage completed at 8m35.30s; the full delivery run took 5253 ms.

A subsequent same-process combined run also passed all 54 exact BrowserContext
and delivery cases: `privacy-context-delivery-combined-001-020-tests.json`.
Its four suites, global totals, exact per-target names and successful statuses
were independently checked, and the test/browser code hashes remained unchanged.
This is combined native-unit evidence, not a real worker-host startup,
document-first-script, protected Canvas or browser capability admission result.
The next source batch registers worker startup and seed thread handoff as
0021-0026. All six patches applied in an idle checkout while preserving baseline
browser code hashes: `worker-startup-001-026-promotion.json`. They include four
unexecuted Blink WorkerThread handoff cases; they are not part of the 54-case
content result above. The Windows `chrome` target completed on four jobs under
`worker-startup-runtime-001-026-build.json`. A copy of the previous 001-015 core
code, GN arguments and receipt is retained outside the mutable output; this core
backup is not a separately verified packaged runtime. Compilation/linkage succeeded
in 29m17.54s. The new `chrome.dll` SHA-256 is
`a055fecb73db29c0ababa0cb3da2f4d7d3942253d82453ce6b58e24f938927e2`.
The executable stub hash alone did not change; it cannot identify the new code.
Canvas readback hooks, document bootstrap and branding remain
unregistered; no protected first-script or Canvas capability is admitted.

The worker startup probe is prepared while this browser build runs. Its fixture
checks first-script body execution through an owned HTTP beacon and an owned
message response, not script download alone. It distinguishes observable failure
from timeout and reuses retained service-worker registrations after restart,
requiring no main-script refetch. The Python validator/receipt/flag regressions
passed; the owned HTTP fixture and JavaScript parser checks passed under
`worker-startup-fixture-syntax-check/proof.json`. Those are not browser results.
The previous 001-015 core backup was actually rejected by the CLI before launch
because its receipt lacks the required chain:
`worker-startup-old-baseline-rejection.json`. No new browser startup pass is
claimed until the compiled runtime completes this probe.

The first compiled-browser run passed twelve ordinary baseline cases and two
ready dedicated-worker cases, then timed out on the ready shared worker with
zero execution beacons (`worker-startup-001-026-runtime-first.json`). Measured
launch logging exposed Playwright's default `--disable-features` entry for
`ThirdPartyStoragePartitioning`, conflicting with the requested enable switch.
The probe now measures that exact default argument through CDP, ignores only that
argument and supplies a replacement preserving every unrelated exclusion. It
checks the effective browser arguments after each launch. `--enable-automation`
is explicit only in this diagnostic probe to permit command-line inspection;
these runs are not anti-bot score or ordinary manager-launch evidence.

With the conflict removed, all 24 baseline/ready cases passed, including retained
classic/module service-worker restart without main-script refetch. Both dedicated
unavailable-policy cases passed. The unavailable shared-worker case timed out
with zero beacons (`worker-startup-001-026-runtime-partition-fixed-v3.json`):
the full 30-case gate is still failed, not admitted. The shared startup rejection
deletes the unstarted stub without calling the existing host script-load-failure
notification, leaving its JavaScript client without an error event.

`native/drafts/document_delivery/shared_worker_bootstrap_failure.patch` prepares
that notification before teardown while retaining the original host remote in
the startup continuation. It passed source applicability and isolated Chromium
renderer syntax checks (`shared-worker-bootstrap-failure-cpp-check/proof.json`).
It is now registered as 0027 and applied after all runtime probes terminated.
The replacement browser compiled/linked successfully on four jobs in 15m28.62s:
`shared-worker-bootstrap-failure-001-027-build.json`. The previous core/receipt are retained under
`baselines/001-026-before-shared-bootstrap-failure-core` (not a packaged runtime).
The probe requires the exact 0015-0027 chain for subsequent reports.
The probe regressions passed 34 cases before this registration and the
full Python suite passed 1222 cases; neither substitutes for the failed browser
gate. The normal manager launch still uses its current Playwright defaults;
partitioning-dependent privacy capability remains developer-only.

A reordered owned probe checked the remaining service-worker rejection paths:
`worker-startup-001-026-runtime-service-first.json` passed all 24 baseline/ready
cases and both classic/module dedicated and service unavailable cases. It failed
on module shared-worker rejection, again with timeout and zero body beacons.
Together the two orders isolate the failed branch to both shared-worker variants;
neither report is a passing complete worker gate.

The unchanged 001-026 browser separately passed all eight normal runtime gates,
160 checks, under `runtime-001-026-regression-suite/suite.json`. Child-report
checksums, required checks, complete gate coverage and all three core hashes were
independently revalidated after the runner exited successfully. This confirms
existing lifecycle/storage/proxy/automation/policy behavior on owned fixtures,
not the rejected worker gate, protected Canvas or external anti-bot performance.

While 0027 links, the probe is extended with ten owned shared-worker client checks
for the next run (40 total): two pages must reuse one classic/module worker and
one script fetch; after the first page closes, the remaining page must still
receive its owned response without executing the worker body again. Unavailable
policy must reject both pages without body beacons. Seven Python regressions
exercise the validator and page cleanup, including duplicate execution, refetch
and timeout rejection. Those are tool tests, not passing multi-client runtime
evidence. The new JavaScript fixture passed Node syntax checking.
After the extension, the full Python suite passed 1231 cases in 63.99 seconds.

The linked 001-027 browser subsequently passed all **40 exact worker checks**:
`worker-startup-001-027-runtime-40-first.json`. All eight unavailable-policy
checks returned explicit worker/registration errors with zero execution beacons;
both shared clients received their error. Positive multi-page cases used one
worker body and one main-script request, and the surviving page still received
replies after the other closed. Both installed service-worker restart variants
executed from retained registrations without a main-script refetch.

Exact check coverage, passing statuses, cleanup success, receipt checksum and
unchanged runtime core were independently revalidated after the runner exited.
The new `chrome.dll` SHA-256 is
`ec1e8ad8a87bea6e448d0c5f117a561c7f1bf3b6a9db330626dc4e538124d350`.
The executable stub and chrome_elf hashes remain unchanged. This proves the
owned startup/rejection behavior, not actual seed-byte equality, Canvas readback,
early startup termination or protection admission. The normal eight-gate suite
also passed all 160 checks under `runtime-001-027-regression-suite/suite.json`.
All child-report checksums, required cases, complete gate coverage and unchanged
core hashes were independently revalidated after the runner exited. This is a
fresh run on 001-027, not substitution of the previous 001-026 suite.

The same 001-027 runtime also passed the unprotected Canvas baseline:
`canvas-001-027-baseline.json`. Both initial/restart eight-context readback phases
and both origin-security/empty-image phases completed; the four phase statuses
and unchanged core hashes were revalidated. This checks upstream pixel/export/
crop/error behavior, not the inactive Canvas candidate or protected readback.

`verify_native_privacy_units.py --target worker-handoff` now provides the strict
four-case Blink ownership gate. It selects exact case names rather than the
entire `WorkerThreadTest` suite and preserves the existing keys/contexts/delivery
targets. Sixty focused verifier regressions passed, including rejection of
missing/duplicate/skipped/foreign/failed cases and build/source/browser changes.
The four C++ handoff cases have not yet been linked or executed by this target.
The full Python suite after this target extension passed 1245 cases in 61.38s.
After all mutable-output runtime probes exited, a dry run of `blink_unittests`
completed successfully and enumerated 1423 remaining CXX commands. D had 301.2 GiB
free and available commit headroom exceeded 10 GiB. The separate four-case
handoff gate is now building on four jobs under `worker-handoff-001-027-j4.json`;
the build log is `worker-handoff-001-027-j4-build.log`. No passing native handoff
result is claimed until its exact four cases execute. Active source/GN inputs
remain unchanged; future Canvas drafts must stay outside that checkout.

Current development is Windows-only. Linux/macOS own-fork runtime verification,
Canvas/GPU/audio protection and security rebasing remain required. External
anti-bot scores may be observations, never guaranteed release capabilities.
