# Glint document and worker delivery candidates

Unregistered, unlinked draft outside the active Chromium checkout. No Canvas
protection or runtime capability is enabled by these files.

The Mojo schema belongs in `third_party/blink/public/mojom/native_privacy/`.
The service belongs in `content/browser/camouflow_native/`. Integration requires
the Blink Mojo GN source registration, content source/dependencies and the
document BrowserInterfaceBroker binder. None are applied during the active build.

The pinned Chromium Mojo parser/type checker and both C++ generator passes
(shared definitions and regular bindings) completed successfully outside the
active checkout. The generated callback signature matches this service and the
fixed-length Mojo byte array maps to `std::vector<uint8_t>` in browser bindings;
the service explicitly copies all 32 bytes. Private evidence:
`D:/CamouFlowNative/document-delivery-bindings-validation-complete/proof.json`.
This does not prove C++ compilation, linkage or renderer delivery.

Subsequent isolated clang-cl syntax checks passed for the service, seven-case
test translation unit and both generated C++ binding translation units, using
the existing browser target's flags and read-only headers/PCH. All temporary
outputs stayed on D outside the active output tree. Evidence:
`D:/CamouFlowNative/document-delivery-cpp-check-test-includes/proof.json`.
No objects were linked and no test cases executed.

The isolated `privacy_document_service_unittest.cc` draft uses Chromium's
RenderViewHostTestHarness, Mojo pipes, queued key loading and mock time. Seven
cases specify missing/ready/loading state, shutdown, deadline, pipe disconnect
and document destruction. They passed syntax checks but are **not registered,
linked or executed**;
they are not included in the existing 20 BrowserContext or 43 key/service cases.

The current document draft has nine test definitions, not seven executed cases.
Two subsequent cases specify retained partition fields when third-party storage
partitioning is disallowed and rejection/disconnection of a duplicate request
while loading. The document receiver now snapshots `SerializeForNativePrivacy()`
and compares that exact encoding both before waiting and before replying.
Ordinary `StorageKey::operator==` intentionally ignores the retained
`*_if_third_party_enabled` fields; using it here could accept a different native
privacy partition despite deriving distinct subkeys. Missing/oversized encodings
reject delivery rather than treating two serialization failures as equal.
This is still a draft fix, not a change to the verified browser binary. The new
primitive test does not simulate mutation of a live RenderFrameHost's private
storage key or prove first-script document/worker bootstrap.
The updated service and nine-case fixture passed isolated Chromium-flag syntax
checks: `D:/CamouFlowNative/document-partition-and-duplicate-cpp-check/proof.json`.
No cases were linked or run; previous seven-case proof hashes remain historical.

The service follows pinned Chromium's `DocumentService`: cross-document navigation,
frame deletion and pipe closure destroy the receiver and invalidate readiness
callbacks. A single request per pipe and a 10-second timer bound pending work;
the existing key service additionally bounds its readiness queue. Partition and
BrowserContext come exclusively from the browser-owned RenderFrameHost. Only
the Canvas subkey crosses IPC; the root key, paths and other surface subkeys do
not. Inactive/BFCache/prerender documents cannot obtain a response seed.

Required before promotion:

- Compile the service and generated bindings, then link their real GN targets.
- Add RenderViewHostTestHarness/Mojo tests for ready/loading/error/timeout,
  duplicate requests, disconnect, navigation, frame/context shutdown, BFCache,
  opaque partitions, same/cross-site frames and independent OTR contexts.
- Verify actual renderer IPC in a linked browser with no JavaScript exposure.
- Provide policy before synchronous pixel readback: no blocking synchronous IPC,
  late unprotected first read or default identity on failure.
- Define worker transport independently from trusted browser worker hosts;
  shared/service worker partition semantics are not solved by this document pipe.
- Finalize version-1 Canvas algorithm before activating this policy. A response
  carrying version 1 here reserves a draft contract, not a released capability.

No command-line seeds, renderer-supplied StorageKeys or JavaScript getters.

## Worker endpoint draft

The separate `NativePrivacyWorker` interface and `PrivacyWorkerService` are
prepared for dedicated/shared/service worker hosts. The service captures a
browser-provided StorageKey and a weak BrowserContext, and must be owned by that
worker host's UniqueReceiverSet. Host destruction or pipe closure must destroy
the service; late loading callbacks cannot retain it. Requests have the same
single-use/10-second bound as document delivery. Only the Canvas subkey is sent.

Shared/service worker requests fail explicitly when third-party storage
partitioning is disabled: the service does not invent one client's top-level
site for a worker that can serve several sites. Dedicated worker identity must
come from its actual host's worker StorageKey, not an ancestor frame lookup.

Fresh Mojo generation and isolated clang syntax checks passed for both services,
the seven document-test definitions and generated binding translation units:
`D:/CamouFlowNative/worker-delivery-cpp-check-message-header/proof.json`.
Worker host ownership/binders are prepared separately in `worker_integration.patch`.
An isolated copy of all three host implementations and BrowserInterfaceBroker
passed clang syntax checks, alongside both services, document test definitions
and generated bindings (nine translation units):
`D:/CamouFlowNative/worker-host-cpp-check/proof.json`.
The patch passed applicability checks after the document integration draft;
the active source tree remained unchanged. At that checkpoint, host-lifetime
tests and Blink consumers were absent; real runtime delivery remains unverified. The document
integration patch below does not register this worker service by itself.

Nine endpoint test definitions in `privacy_worker_service_unittest.cc` passed
clang syntax checks; `worker_integration.patch` adds them to content_unittests.
Coverage specifies readiness/derivation for all three kinds, queued loading,
shutdown, deadline/late callbacks, receiver-owner destruction, pipe disconnect,
expired BrowserContext and explicit rejection of unpartitioned shared/service
workers. Evidence: `D:/CamouFlowNative/worker-endpoint-tests-cpp-check/proof.json`.
They have **not executed**. The owner fixture is a real UniqueReceiverSet, not an
actual DedicatedWorkerHost/SharedWorkerHost/ServiceWorkerHost: process teardown,
worker termination/restart and real host destruction still need separate tests.

## Integration draft

`integration.patch` registers the schema, browser sources, document fixture and
document BrowserInterfaceBroker binder. It is not applied or registered in the
build lock. After the current build finishes, copy the Mojo file to the schema
directory above and the three service C++ files to the content directory above;
then apply this integration patch. It passed applicability checks against the
001-017 source tree with input hashes unchanged. Real GN generation, dependency
checks, compilation, linkage and tests remain mandatory before promotion.

The worker integration draft depends on the document integration patch. Copy
`privacy_worker_service.h`, `.cc` and `_unittest.cc` into `content/browser/camouflow_native/`,
then apply `worker_integration.patch` only in an idle checkout. It adds host-owned
UniqueReceiverSets and broker bindings; dedicated/shared workers use their host's
GetWorkerStorageKey, service workers use the running version's immutable key.
Missing process hosts close the new pipe rather than selecting another context.
No renderer startup caller, Canvas readback hook or advertised capability is enabled.

## Worker startup consumer draft

`PrivacyWorkerBootstrap` is a sequence-bound, single-request client for a
`NativePrivacyWorker` pipe obtained from the worker host's own broker. It accepts
only ready/version-1/32-byte policy replies, returns an owned Canvas surface seed,
and rejects failure replies containing a seed, missing policies or unsupported
versions. Peer disconnect and a ten-second local deadline produce typed errors.
Completion resets the pipe, timer and weak callbacks before invoking the owner;
destruction cancels pending work. It never requests a URL, partition or profile
root key, and never substitutes an unprotected policy on failure.

Ten Mojo/mock-time test definitions cover success/ownership, browser failure and
timeout, malformed replies, disconnect, client timeout/late replies, destruction
and absent pipes. Implementation and fixture passed isolated clang checks with
the pinned renderer target flags:
`D:/CamouFlowNative/worker-bootstrap-cpp-check/proof.json`.
They are **not linked or executed**.

`worker_bootstrap_integration.patch` contains the three files, adds implementation
sources to content/renderer and registers the fixture in content_unittests,
which already depends on renderer's for_content_tests target. It depends on the
document schema registration and worker browser-host binder draft. Patch
applicability and GN formatting-delta checks passed without active input changes:
`D:/CamouFlowNative/worker-bootstrap-registration-format-delta/proof.json`.
The pinned content/test BUILD.gn already has two unsorted 0017 insertions; the
check verified the new insertion introduces no additional formatting drift,
rather than rewriting unrelated live-build inputs or claiming whole-file format
success. The first failed formatting check remains in the separate
`worker-bootstrap-registration-draft/proof.json` evidence directory.

This client is **not called by the active runtime's worker startup yet**. Before enabling protection,
the DedicatedWorkerHostFactoryClient path must hold script startup and preserve
owner lifetime until a successful reply; shared/service and nested workers need
their own startup wiring and thread handoff, not a creator-document pipe. The
surface seed must reach the global scope before evaluation. Browser-host StorageKey
and renderer security origin can differ for data-URL dedicated workers in this
pinned revision; that case needs an explicit policy and tests, not silent
origin substitution. Document commit/bootstrap, initial about:blank/srcdoc,
BFCache/prerender and Canvas API wiring also remain unimplemented.

Do not apply this patch, regenerate GN or compile into an active output tree.
Promote exact source checksums into the build lock in an idle checkout, then
generate/link and inspect all ten named `NativePrivacyWorkerBootstrapTest.*`
cases in fresh JSON. That would validate the consumer, not demonstrate first-script
startup ordering or complete worker fingerprint protection.

## Dedicated-worker caller and startup gate draft

`dedicated_worker_startup_gate.patch` connects that consumer to the actual pinned
DedicatedWorkerHostFactoryClient path, behind the explicit developer-only
`--glint-worker-canvas-bootstrap-test` switch. The browser forwards this test
switch to renderer processes; it is not enabled by CamouFlow settings or admitted
as a runtime capability. The key-service opt-in is separately required for a
successful browser reply. Normal launches retain their original startup path.

The caller requests the policy from the newly created worker's own broker before
handing the broker to Blink. It retains the original script-load parameters,
loader factories and reporting pipes until a successful validated reply; either
reply/script-load ordering is handled. Failure drops the pending continuation and
uses the existing script-load-failure path, rather than running without policy.
Weak callbacks and owned pipe parameters follow factory-client lifetime. Pinned
DedicatedWorkerMessagingProxy::HasPendingActivity retains the worker while it has
not been asked to terminate; its existing StartWorkerGlobalScope termination check
still precedes thread creation. These are source-level observations, not runtime
tests of GC, termination or race ordering.

The owned surface seed is copied into WorkerMainScriptLoadParameters. **Global
scope/thread handoff and Canvas use are not implemented by this patch.** Holding
startup and retaining a seed does not itself protect OffscreenCanvas. The data-URL
origin discrepancy above must also be resolved/rejected before admission.
Shared/service worker startup and document bootstrap remain separate work.

The actual renderer factory-client implementation and browser renderer-switch
implementation passed isolated clang syntax checks with their respective pinned
target flags:
`D:/CamouFlowNative/dedicated-worker-startup-gate-cpp-check/proof.json` and
`dedicated-worker-startup-switch-cpp-check/proof.json`. The full four-patch stack
applied successfully to a private copy, with active source inputs unchanged:
`D:/CamouFlowNative/worker-startup-full-stack-applicability/proof.json`.
No active patch application, graph generation, linking or worker runtime execution
has occurred. After promotion in an idle source tree, real tests must exercise
both event orders, absent/failed policy, timeout/disconnect, owner destruction,
termination and nested workers before claiming first-script ordering.

## Worker thread handoff draft

`worker_canvas_thread_handoff.patch` continues the startup-gate stack into Blink.
DedicatedWorker::ContinueStartInternal first creates GlobalScopeCreationParams,
moves the owned optional seed from WorkerMainScriptLoadParameters and then starts
the worker with those parameters. WorkerGlobalScope stores that value as an
immutable member during construction, before script evaluation. Its internal
C++ accessor checks the owning context thread and returns a copy, not a pointer
into another thread or a JavaScript property. No profile root key crosses the
thread boundary. Workers without supplied bootstrap data keep an absent value;
there is no creator-document seed substitution or generated fallback identity.

The pinned DedicatedWorker and WorkerGlobalScope implementation translation units
passed isolated syntax checks with actual Blink core flags:
`D:/CamouFlowNative/worker-canvas-thread-handoff-cpp-check/proof.json`.
These are not object/link/runtime results.

`worker_canvas_handoff_tests.patch` adds two cases to the existing WorkerThreadTest
fixture and an optional seed argument to its test-only startup helper. They
specify delivery to the worker thread before evaluation, owned-copy immutability,
and absence when no policy was supplied. Ordered mock expectations require scope
creation before script evaluation and shutdown. The existing core unit-test GN
registration already includes this fixture; no separate runner or dependency is
introduced. The updated fixture passed isolated syntax checks with actual Blink
unit-test flags, omitting its unbuilt PCH:
`D:/CamouFlowNative/worker-canvas-handoff-ordered-tests-cpp-check/proof.json`.
**Neither of the two new cases has been executed.** They use FakeWorkerGlobalScope
and do not prove real broker/GC/nested-worker startup or OffscreenCanvas API use.

The complete six-patch stack, including these ordered tests, applied to a private
copy without changing active inputs:
`D:/CamouFlowNative/worker-handoff-ordered-full-stack-applicability/proof.json`.
It remains unregistered and inactive. Canvas hooks, document bootstrap,
shared/service worker startup, data-URL origin policy and real runtime checks are
still required; this handoff does not admit Canvas protection as a capability.

## Browser-owned worker origin guard

The current PrivacyWorkerService constructor requires the worker origin from the
browser host as well as its StorageKey; it has no inferred/default origin. A
mismatch returns unavailable without deriving or sending a seed. Dedicated
hosts supply their immutable renderer_origin_, shared hosts their instance's
renderer_origin(), and service hosts the origin of the running version's script
URL. No origin supplied by renderer JavaScript or a parent frame is accepted.

Pinned worker_util.cc constructs a fresh opaque renderer origin for data: workers
while retaining the creator StorageKey when kDataUrlWorkerOpaqueOrigin is off.
That feature is disabled by default in this pinned revision. The guard therefore
rejects that legacy discrepancy, rather than reusing the creator's Canvas key or
changing origin/feature defaults. When the Chromium feature is explicitly enabled,
its own opaque worker StorageKey and renderer origin agree; that path can pass
the guard. Full data-worker compatibility is still not a verified capability.

Two additional worker endpoint cases use the real CalculateWorkerStorageKey and
CalculateWorkerRendererOrigin helpers to specify both configurations. The fixture
now contains eleven definitions. The updated service, fixture and all three host
implementations passed isolated clang syntax checks:
`D:/CamouFlowNative/worker-origin-policy-cpp-check/proof.json`.
The updated six-patch stack still applies without active input changes:
`D:/CamouFlowNative/worker-origin-guard-full-stack-applicability/proof.json`.
Earlier worker-host proof hashes are historical. None of these new endpoint cases
has been linked or executed, and actual dedicated/shared/service host lifetimes,
opaque-origin isolation, GC and startup behavior remain mandatory runtime gates.

## Delivery verification target

`scripts/verify_native_privacy_units.py --target delivery` prepares a strict
content_unittests verification for exactly 31 cases: nine document endpoint,
twelve worker endpoint and ten bootstrap consumer cases. It rejects missing,
duplicate, skipped, failed or foreign cases. Before building, the ten source and
schema files must match the public drafts as decoded UTF-8 text; raw source
checksums are recorded and rechecked after execution. Registered native patch
verification, idle-builder enforcement, baseline browser/args/receipt preservation
and fresh report paths remain required. This does not bypass build-lock promotion.
The present active source tree has not been promoted and cannot pass this target.

After promotion in an idle checkout, the intended command is:

```text
.venv/Scripts/python.exe scripts/verify_native_privacy_units.py --workspace D:/CamouFlowNative --report D:/CamouFlowNative/privacy-delivery-new-proof.json --vs-installation D:/CamouFlowNative/toolchain/BuildTools --jobs 1 --target delivery
```

Use an unused report path. A successful result would cover the named Mojo/consumer
units, not real host lifetimes, first-script ordering, the two Blink thread-handoff
cases, Canvas API behavior or privacy admission. Python tests for the verifier use
synthetic GTest JSON and mocked subprocesses; they are not execution evidence for
the 31 C++ cases.

### Duplicate worker request cancellation

A second request on the same pipe cancels the pending reply, deadline timer and
readiness weak callbacks before reporting a bad message. Late key readiness must
not deliver a seed after a protocol violation. The new mock-time fixture checks
both pipe disconnection and absence of replies after readiness and the deadline.
The service and twelve-case fixture passed isolated Clang syntax checks using
the pinned build flags; these fixtures have not been linked or executed.

### Initial-document delivery constraints

The pinned renderer creates a local child immediately after the asynchronous
`CreateChildFrame` call. A document-service response alone therefore cannot
guarantee policy delivery before initial about:blank script execution.
Navigation storage keys are also provisional: `DocumentLoader` adjusts the key
to the final security origin before installing it on the window. A future
document bootstrap must validate the final full privacy partition encoding and
cover initial documents; commit-time delivery alone is insufficient. No document
Canvas protection or first-script readiness guarantee is implemented here.

### Shared-worker thread handoff

`worker_canvas_thread_handoff.patch` also moves an optional owned surface seed
from WorkerMainScriptLoadParameters to WebSharedWorkerImpl's creation parameters
before WorkerThread::Start. Both classic and module script paths subsequently
move the load parameters, so this transfer precedes either script evaluation.
The existing immutable WorkerGlobalScope field receives the value on its own
thread. No creator-document seed, JavaScript property or inferred partition is
introduced; an absent value remains absent.

At this handoff-only checkpoint, EmbeddedSharedWorkerStub did not wait for the
browser-owned policy; ordinary shared workers still receive no seed. Startup
failure, host disconnect, pending Connect/Freeze/Resume requests,
partitioned reuse and service-worker startup remain separate gates. Do not enable
the experimental capability from this handoff alone.

The updated nine-patch stack applies to an isolated copy with active inputs
unchanged: `D:/CamouFlowNative/shared-worker-canvas-full-stack-applicability/proof.json`.
WebSharedWorkerImpl passed isolated syntax checking with the pinned Blink core
flags: `D:/CamouFlowNative/shared-worker-canvas-handoff-cpp-check/proof.json`.
These checks are not GN generation, linking or shared-worker runtime evidence.

### Shared-worker startup gate draft

`shared_worker_startup_gate.patch` reuses PrivacyWorkerBootstrap under the same
developer-only `--glint-worker-canvas-bootstrap-test` switch. It requests the
worker host's own endpoint through the supplied broker; no URL or client partition
is supplied by the renderer. The command receiver remains active during startup:
Terminate and disconnect can destroy the unstarted stub without waiting for policy.
Owned loading parameters, policy container, broker and host pipes are
bound to one startup continuation; no references to constructor arguments escape.
The normal path invokes the same continuation immediately without a seed.

Only a validated ready policy starts WebSharedWorkerImpl. The seed is installed
before the existing classic/module thread handoff. Connect, Freeze and Resume
received before readiness are stored as owned weak-bound callbacks and replayed
in arrival order after the implementation exists. Unavailable policy, disconnect, malformed response or the
consumer's ten-second deadline terminate the unstarted stub instead of starting
without protection. Network-factory disconnection also handles the not-yet-started
state. Weak callbacks are invalidated on destruction, dropping queued ports and
startup parameters. Replaying a control that destroys the stub cannot invoke
later controls through a dangling owner. Receiver pausing was removed because it
could defer a queued Terminate until after worker creation. Dispatch timing and
worker-thread ordering still require runtime verification.

Chromium's callback implementation rejects capturing lambdas: this draft uses
stateless lambdas and explicitly owned bound arguments. The earlier rejected
syntax check is not a passing result. Final syntax verification passed with the
pinned renderer flags:
`D:/CamouFlowNative/shared-worker-immediate-teardown-gate-cpp-check/proof.json`.
The complete ten-patch draft stack applies in an isolated copy with active inputs
unchanged: `shared-worker-immediate-teardown-full-stack-applicability/proof.json`.

The gate remains unregistered and inactive in every linked browser. No shared
startup/lifecycle test has executed against it. Required next tests include early
host/network disconnection, timeout, ordered Connect/Freeze/Resume and early Terminate,
classic/module scripts, partitioned reuse across clients, nested workers and
Canvas readback/export agreement. Service-worker and document startup are still
unfinished; no Canvas capability or production admission is enabled.
