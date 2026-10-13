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

Manager diagnostics now validate emitted WebGL/WebGPU capability structures
before treating equal values as meaningful: context coverage, boolean availability,
unique extension/features lists, integer limits, texture/limit agreement,
viewport dimensions and adapter-info/subgroup fields. Unavailable APIs remain
unavailable; no renderer/adapter or capability is synthesized. Legacy comparisons
remain compatible, and missing GPU sections in older observations do not become
new evidence. This is observation validation, not measured preset admission or
proof that a driver identity is plausible.

## Public gates

Health checks delete disposable profiles only after the runtime releases its
tracked resources. SDK teardown errors or a close that leaves ownership active
retain the owned directory and report its path, rather than returning success
or deleting live profile files. Released-resource errors still propagate; this
cleanup rule does not replace actual orphan-process/crash verification.

| Tool | Scope |
| --- | --- |
| `scripts/verify_release.py --build --runtime` | Desktop package and packaged legacy-engine checks |
| `scripts/verify_native_cpp.py` | Standalone native policy primitives |
| `scripts/verify_native_gpu_metadata_codec.py` | 14 actual candidate codec cases on standalone MSVC/GoogleTest; not a Chromium GN target, decoder/driver test or browser capability |
| `scripts/verify_native_privacy_units.py` | Keys: 43; contexts: 26; surface navigation: 42; window transport: 13; worker surfaces: 55; GPU readback: 31/31 passed on 001-048. Legacy delivery remains a separate 34-case target |
| `scripts/verify_native_privacy_units.py --target identity-*` | Keys **62/62 passed** on 001-058. Contexts 37, transport 20 and handoff 15 remain unverified; full selection includes 50 new cases and 84 legacy cases |
| `scripts/verify_native_suite.py` | Runtime, hardware, WebRTC, automation, fonts, identity, CDP and combined gates |
| `scripts/verify_native_storage_paths.py` | Windows path-depth/storage probes |
| `scripts/verify_native_canvas.py` | Canvas verification tooling, not an implemented protection claim |
| `scripts/verify_native_worker_startup.py` | Default: 40 owned startup/restart/shared-client cases; `--include-nested` adds 20 nested dedicated-worker cases; no Canvas admission |
| `scripts/verify_native_surfaces.py --include-nested-canvas` | Passed on browser 001-047: 7 existing phases and 24 parent/child Canvas cases across baseline/two profiles and restart, including first-script/repeated readback and separate fetch/body counters |
| `scripts/verify_native_surfaces.py --derivation-mode profile-identity --include-nested-canvas` | Prepared: stable cross-origin Canvas/Audio, restart and two-profile isolation using exact compiled patches 0049-0054; existing 001-047 receipt is rejected, not treated as an identity-mode result |
| `scripts/verify_native_surfaces.py --include-concurrent-profiles` | Prepared: five additional phases with two live profiles, symmetric close/restart, unchanged survivor surfaces and exact launch-policy checks; not yet browser-executed |
| `scripts/verify_native_surfaces.py --include-gpu-readback` | Prepared: Canvas/Audio/WebGL measured in the same document/worker contexts and profiles; composes with restart, concurrency and nested Canvas options; not yet browser-executed |
| `scripts/verify_native_gpu_readback.py --derivation-mode profile-identity` | Prepared: six existing phases with cross-origin WebGL1/2/renderbuffer consistency, restart and profile isolation; requires exact identity and complete GPU transport patches, not an old receipt |
| `scripts/verify_native_identity.py --strict-client-hints` | Passed on browser 001-047: 8 strict document/frame HTTP-versus-JS comparisons, 6 worker JS-preservation checks and 4 invalid-UA rejection checks; 18 total |

Run commands as documented in the [build guide](../native/BUILDING.md). Use fresh
report paths outside source/application repositories. Keep raw outputs and
measured executable/core-DLL hashes; a count without exact names and successful
completion is insufficient. Failed or skipped cases are not a passing gate.

Source integration 0049–0058 is recorded privately in
`D:\CamouFlowNative\identity-gpu-source-integration-0049-0058-v1\proof.json`.
All 58 patches replayed and source matched the reviewed composition; browser
001-047 core, GN and receipt stayed unchanged. Native test filters enumerate
exact suite/case names, including all four DocumentLoader parameter variants.
Registration does not admit identity mode. The public Identity/GPU replay gates
now accept registered 001-058 by verifying promoted/canonical hashes and
reversing exact promotions only inside their owned temporary copy. The combined
source/fresh-generation gate passed after promotion:
`D:\CamouFlowNative\identity-readback-post-promotion-001-058-v1.json`.
Manual candidate application to the integrated checkout remains incorrect.

The strict identity extension preserves the existing gate by default:

```powershell
.venv\Scripts\python.exe scripts/verify_native_identity.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative --report D:\CamouFlowNative\identity-strict-new.json --strict-client-hints
```

It compares every advertised brand/version, including escaped GREASE values,
without assuming brand order or discarding duplicates. Missing or malformed
observations reject rather than invent values. The bounded parser handles the
Chromium brand/version field, not arbitrary HTTP Structured Fields. High-entropy
HTTP hints need server opt-in: see the [UA-CH specification](https://wicg.github.io/ua-client-hints/).
Worker request hints are not inferred from document headers; this strict HTTP
extension covers documents/frames only. EXE/DLL hashes must remain unchanged
and existing reports cannot be overwritten. The actual strict run is recorded in
`D:\CamouFlowNative\identity-strict-001-047-v2.json`: all 18 checks passed with
unchanged browser core hashes. This is not TLS or cross-platform identity proof.
The initial strict run failed cross-origin HTTP hint comparisons because the
owned fixture omitted Permissions-Policy delegation. Strict mode now delegates
only the exact owned localhost origin and iframe features; legacy mode is
unchanged. The failed report is retained, not reclassified as passing.

The combined surface gate has an optional nested Canvas extension:

```powershell
.venv\Scripts\python.exe scripts/verify_native_surfaces.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative --report D:\CamouFlowNative\surfaces-nested-new.json --include-nested-canvas
```

It starts the existing OffscreenCanvas read in both parent and child script
bodies, before awaiting a message/network event, then repeats after messaging.
All four classic/module combinations must match the validated same-partition
dedicated worker, including PNG/pixel agreement, geometry and API errors. Each
body and main script fetch must occur once. Across baseline and two independent
profiles before/after restart this adds 24 cases to the existing seven phases;
raw failed observations are retained and missing coverage rejects the gate.
Independent child-policy denial, nested Audio and early termination are not
covered. Actual browser evidence is
`D:\CamouFlowNative\combined-surfaces-nested-001-047-v4.json`: all seven phases
and 24 nested cases passed, with unchanged browser core hashes and no cleanup
error. This establishes that scoped execution, not future identity-mode behavior.
Run heavy C++ candidate checks separately from native builds after the observed
out-of-memory failure; do not silently lower the requested four build jobs.

Profile-identity execution is opt-in through `--derivation-mode profile-identity`.
It preserves the baseline and existing partitioned-privacy default, requires
every exact identity patch in a core-bound receipt, and verifies the measured
launch mode. Protected document/frame/worker Canvas and document OfflineAudio
must now agree across origins as well as across same-partition contexts; restart
and independent-profile isolation remain mandatory. Optional nested Canvas
retains its 24-case contract. The missing-policy denial phase still uses the
compatibility mode and is labelled separately; it is not identity-specific
failure-path coverage. This is an owned diagnostic gate, not manager admission.
The old browser was actually rejected before any fixture/profile launch:
`D:\CamouFlowNative\profile-identity-old-core-rejection-001-047-v1.json`.
No successful identity-mode browser execution is claimed from that negative check.
The WebGL readback gate has the same opt-in and mode-propagation checks. It
retains CPU/PBO/packing/clipping/export/error checks, but requires protected
pixels to agree across all document and worker origins in profile-identity
mode. Its receipt additionally binds 0046/0047 and 0055–0058. The existing
001-047 browser was rejected before any fixture launch:
`D:\CamouFlowNative\profile-identity-gpu-old-core-rejection-001-047-v1.json`.
This is not WebGPU, validating-decoder coverage or a passing new-mode result.

`--include-concurrent-profiles` adds five phases after the sequential baseline:
both profiles live, A closed, A restarted while B stays live, B closed, then B
restarted while A stays live. Every observed survivor must match its earlier
Canvas/Audio snapshot; both-live phases also require cross-profile isolation.
Each phase checks actual launch arguments, including the selected mode and
storage-partitioning exclusions. Teardown attempts both owners even when one
fails. The original seven-phase default and optional 24 nested Canvas cases
remain unchanged. These are prepared lifecycle/consistency checks, not memory/
CPU benchmarks, concurrent nested-worker coverage or passing browser evidence.

`--include-gpu-readback` selects the existing native readback configuration and
its exact receipt gate. Each settled document/frame/worker measurement includes
Canvas, Audio and WebGL in one collector; both component validators must pass.
GPU normalization, cross-profile isolation and restart checks are reused from
the standalone readback gate. With concurrent profiles enabled, the same GPU
snapshots are also checked through all five close/restart phases. Worker scripts
use the composite collector; missing GPU contexts reject rather than skip.
The first-parser-script and optional nested-worker extensions still cover only
Canvas/Audio and Canvas respectively, not first-script/nested GPU protection.
WebGPU protection, TLS and external detector acceptance are not covered.

Nested worker coverage is opt-in and preserves the existing 40-case contract:

```powershell
.venv\Scripts\python.exe scripts/verify_native_worker_startup.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative --report D:\CamouFlowNative\worker-nested-new.json --bootstrap-policy surfaces --include-nested
```

This requires all four classic/module parent/child combinations in baseline,
ready and unavailable-parent modes, including restart for baseline and ready.
Independent fetch and body-execution counters bind the reply to the child.
Timeouts, duplicate/missing executions and unexpected child fetches reject.
Unavailable-parent coverage does not prove independently denying an already
running parent's child. Early termination and protected pixel output are
separate gates. HTTP fixtures and Node syntax checks alone are not browser
execution; retain the measured-core runtime report before claiming these cases.

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
At preparation time, the four C++ handoff cases had not been linked or executed.
The full Python suite after this target extension passed 1245 cases in 61.38s.
After all mutable-output runtime probes exited, a dry run of `blink_unittests`
completed successfully and enumerated 1423 remaining CXX commands. D had 301.2 GiB
free and available commit headroom exceeded 10 GiB. The separate four-case
handoff gate was built on four jobs under `worker-handoff-001-027-j4.json`;
the build log is `worker-handoff-001-027-j4-build.log`. That build succeeded in
2h24m55.18s but the test process aborted after two passing cases: the sequential
fixture created an extra worker after its last iteration and destroyed it without
startup/shutdown. Its complete four-case gate failed, not passed.

Test-only patch 0028 creates a successor only at the next iteration, retaining
all seed comparisons, graceful shutdown waits, mock checks and upstream DCHECKs.
The incremental retry `worker-handoff-001-028-fixture-lifetime-j4.json` passed
all four required cases without skipped cases. Build: 12m19.98s, two steps;
test execution: 149 ms. Test executable SHA-256:
`c12081c58b2370f43f4f2e7ce27f9465f58205c45c298c1e71c442bb2ea273af`.
The required case set, executable hash, baseline browser core, receipt and GN
arguments were independently rechecked. The full Python suite passed 1265 tests.
This is Blink fixture ownership/timing evidence, not a new browser release,
real browser-partition seed equality or Canvas protection/admission.
Future Canvas drafts remain outside the active checkout until their own gates.

The nine final-partition validator cases also passed in an isolated standalone
native executable, using the generated native-unit flags and existing linked
dependencies on registered 001-028 inputs. Raw evidence lives under
`document-partition-validator-001-028-linked-v4/`; source/fixture hashes, exact
JSON cases, executable hash and unchanged browser core were independently
rechecked. This is not the actual DocumentLoader/navigation target. It proves
binary partition comparison and rejection semantics, not recovery after frame
teardown or browser-to-renderer delivery. Failed staging/launcher attempts remain
separate; they were not converted into passing reports.

Patch 0029 now registers that exact public validator and nine-case fixture in
the existing native unit executable. The public command
`verify_native_privacy_units.py --target document-partition` requires patch 0029,
selects the nine exact names and retains strict no-skips/results/source/GN/core
checks. The registered run passed all nine cases, with a 1m22.26s two-step
incremental build: `document-partition-001-029-registered-j4.json`.
Test executable SHA-256:
`104e1e37dcc52460246a50df5ab43039e9e37372e7162e56c043935113e04ae8`.
Actual executable, case set and unchanged browser core/receipt/GN hashes were
independently rechecked. This supersedes the private standalone command for
reproduction, not its historical results. Document transport now reuses the
registered helper; all five remaining candidates replayed over 27 composed and
canonical paths in `document-delivery-public-replay-001-029-v1.json`.
The Python regression suite passed 1283 tests. No new lint findings were added;
existing unrelated findings remain. Navigation recovery and first-script delivery
remain distinct unexecuted runtime gates.

An independent unregistered `document_canvas_seed_handoff.patch` now prepares
the immutable Blink document-side carrier. A native-only initializer owns one
surface-seed snapshot, construction copies it into a const Document field and
getter snapshots cannot mutate that field. Three DocumentTest definitions cover
absence/copy ownership/independent supplied seeds; they have not executed.
Applicability and isolated syntax verification of initializer, Document and
fixture passed, and the five active source hashes remained unchanged:
`document-canvas-seed-handoff-overlay/proof.json` and
`document-canvas-seed-handoff-cpp-check/proof.json`. This is not browser delivery
or first-script readiness: the trusted committed-partition producer is still
missing. No Canvas hook or policy capability was enabled by this draft.

The independent `privacy_navigation_throttle` candidate now implements a bounded
readiness barrier before normal response/no-URL-loader commits, behind an explicit
developer switch. Registration is posted after DEFER to handle inline terminal
readiness safely. Failure/shutdown/deadline cancel only the deferred navigation;
resume/cancel may delete the owner. Eleven fixture definitions cover these
lifecycles. Production source and fixture syntax passed separately with their
actual pinned browser/content-unit flags; no native case executed and neither
registry/GN registration nor policy derivation is present. The earlier fixture
syntax failure with production flags is retained, not represented as a pass.
The current Chromium commit StorageKey is provisional and DocumentLoader can
adjust it: first-script delivery therefore also needs an exact trusted-partition
commitment check against final document state, not just a ready profile root.

## Current full-build repair

The 001–034 full Chrome build terminated after 1,406 completed tasks with a
`document_loader.cc` compilation error: initial policy adoption assigned to the
immutable `origin_to_commit_` member. Registered repair 0035 instead uses a local
effective origin inside the existing origin calculation. The commit member and
header ABI remain unchanged; sandbox, same-origin and local-access checks remain.
Source integrity replay of the complete repaired chain passed. The repaired
`document_loader.obj` compiled successfully in a bounded one-object build; full
001–035 Chrome compilation has resumed with existing objects retained. No new
browser or protected fingerprint capability is verified by that object result.

## Stable profile-identity derivation candidate

The separate [identity candidate](../native/drafts/profile-identity/README.md)
provides browser-owned profile/service/context derivation with a distinct HMAC
purpose, retaining partition validation and the unchanged partitioned privacy API.
Source replay and four independent Python/native-fixture vector comparisons passed.
Its eleven native fixtures remain uncompiled. Mode selection, policy/IPC mode
delivery, UI admission and cross-API identity behaviour are not implemented by it.

## GPU attachment metadata transport candidate

The separate [GPU transport draft](../native/drafts/gpu-transport/README.md)
extends the pending readback batch with a private command, both native decoder
implementations and the Blink consumer. It queries the actual selected attachment,
including supported texture levels, instead of deriving dimensions from a viewport.
The new feature defaults off and adds no WebGL JavaScript API.

Source replay of all five candidate patches passed with canonical helper matching,
324 legacy command IDs preserved and new command ID 580. An isolated rerun of the
pinned upstream command generator reproduced all 59 copied generated headers.
Neither check compiled C++, executed the command or admitted protected readback.
The 12 codec fixtures and 10 decoder command fixtures remain uncompiled. The
decoder fixtures cover unavailable responses, invalid shared memory, overflow,
truncated buffers and initialized results on both backends; they are not proof
of those invariants until executed. Real texture/error/binding checks remain pending.
Three additional feature-on validating-decoder fixtures execute the command
against actual renderbuffer metadata: RGBA8 extents, integer format classification
and storage redefinition. These are also uncompiled; passthrough attachment
fixtures and protected texture runtime coverage remain pending.
The active 001–034 Chromium build was not changed by these checks.

## Manager identity coherence diagnostics

The manager's profile inspection compares the measured Chromium runtime version
with the reduced UA major, low-entropy Chromium brand version and genuine
high-entropy full version in document and dedicated worker. Missing observations
cannot pass merely because both contexts omit the same fields. Primary language
must agree with `languages[0]`; Intl locale is observed and compared across contexts.

The owned feature-off 001–027 runtime passed real inspection with `en-US` and
`de-DE`; measured runtime core and diagnostic source hashes remained unchanged.
This does not generate cross-OS/GPU presets, verify HTTP headers on arbitrary
sites or admit new native capabilities. The separate native identity gate remains
responsible for controlled HTTP/Client Hints/frame/worker checks.

The manager health path no longer inspects `about:blank`, where the actual
browser cannot expose secure-context Client Hints. Its disposable context loads
an owned loopback document through an intercepted response; every other request
is aborted, with no external server/network fallback. CSP permits the diagnostic
blob worker, not external resources. A real 001–027 health-path run observed a
secure context, genuine Client Hints and no mismatches; navigation/inspection
failure still requires runtime teardown. This is not HTTP or TLS evidence.

The controlled health document includes a responsive viewport declaration.
Without it, genuine mobile layout uses a 980 CSS-pixel viewport, which is not a
configured-screen failure. An owned Mobile Web run with 390×844, DPR 3, touch,
`de-DE` and `Europe/Berlin` passed the manager diagnostic after that fixture fix.
It still reports genuine Windows Client Hints with `mobile=false`: Web Emulation,
not an Android identity. The earlier layout mismatch is retained as failed evidence.

## Texture lifecycle baseline

`scripts/verify_native_gpu_textures.py` verifies actual texture uploads/readback,
2D resize, non-base mip attachment, cube faces and WebGL2 array/3D layers on
selected color attachment 1 with a deliberately different viewport. Read repeats,
binding preservation and exact errors are checked in all eight contexts before
and after restart. The owned feature-off 001–027 runtime passed 208 case
observations; its measured runtime core matched the prior baseline.

The initial diagnostic failed because its non-base texture mip chain was
incomplete under ANGLE's ES3 completeness rules. The fixture now explicitly
sets `TEXTURE_MAX_LEVEL=1`; that failure is retained separately. This is baseline
compatibility evidence, **not execution of the new native GPU metadata command**
and not a privacy capability. Protected texture results remain pending.

## Current WebGL clipping compatibility gate

The first 001–034 browser build failed; repair 0035 is registered. A complete
rebuilt browser and its protected readback checks remain pending. The following
independent checks do not change that boundary:

- An owned feature-off 001–027 browser confirmed native CPU/PBO reads preserve
  destination bytes outside a framebuffer, including negative/partially clipped,
  entirely outside and zero-sized requests, in eight contexts across restart.
- The registered 0034 source currently republishes the entire zero-initialized
  private rectangle. This is a known source-level clipping compatibility issue;
  a successful build cannot override the required destination-preservation gate.
- The separate [next-readback batch](../native/drafts/next-readback/README.md)
  prepares bounded halo allocation plus clipped CPU/PBO publication. Source
  replay passed against an owned copy of 001–034 across 11 paths. Its 17 native
  fixtures have not been compiled or executed; protected browser results remain
  pending. The independent 58,860-comparison model is not native GPU proof.

`verify_native_gpu_readback.py` now requires the boundary cases in both original
and resized attachment extents. Tight and padded CPU/PBO destinations must agree
with full-frame protected pixels inside bounds; outside pixels, offset bytes,
skipped rows/pixels and padding must remain unchanged. Exact errors and native
buffer binding are checked, not inferred from a digest or a case count.

Current development is Windows-only. Linux/macOS own-fork runtime verification,
Canvas/GPU/audio protection and security rebasing remain required. External
anti-bot scores may be observations, never guaranteed release capabilities.
