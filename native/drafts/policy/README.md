# Surface policy v2 candidate

## Ready-commit cancellation follow-up

`document_ready_commit_observer_guard.patch` follows registered 0039. It saves
the frame-tree node ID and reacquires the node after cancelling the owned request:
a navigation-finish observer may close the tab and destroy the original pointer.
This matches the existing renderer-rejection cleanup pattern. Both cancellation
follow-ups are now promoted together in registered patch **0040**; source is
001-040, while the latest linked browser is 001-039.

`document_ready_commit_observer_tests.patch` adds eight parameterized native
NavigationSimulator cases: Canvas and surface policy loss in the ready callback,
both URL-loader paths, subsequent-navigation recovery and WebContents destruction
from the finish observer. The earlier missing-service throttle tests do not reach
this late cancellation point.

Both patches replayed in an owned overlay against 001-039 without changing active
sources (`document-ready-observer-replay-v1/proof.json` on D). Both actual C++
translation units passed syntax/type checking with their generated browser and
content-unittest target flags; source/compiler/core/GN guards passed
(`document-ready-observer-cpp-v1/proof.json`). They are **not yet optimized,
linked or executed**. The native surface-navigation gate requires all 42 cases
(34 existing plus these eight); neither syntax nor source promotion substitutes
for running that executable.

## Earlier preparation record

Unregistered, uncompiled and not transported into Blink. Existing Canvas v1 IPC
and active 0030 build sources are unchanged.

`CreateSurfacePolicy` prepares one UI-sequence, browser-owned snapshot containing
independently derived Canvas, WebGL, WebGPU and Audio partition seeds. It reuses
the existing BrowserContext key service and derivation domains; no new root key,
page-provided origin, renderer derivation or profile identifier is introduced.
Unready/failed/shutting-down contexts and incomplete snapshots produce no policy.
Typed validation rejects unsupported versions, invalid encoding, any pair of
reused surface seeds and a different final partition, including nonce, retained
top-level site and exact binary encoding. A preflight owns all four seeds only
after checking every payload length; it reuses document StorageKey resolution
and still requires final-partition validation. Ten validator, five preflight
and four producer fixtures plus two wire ownership/validation fixtures are not
compiled or executed yet. Two additional worker codec fixtures preserve exact
opaque and nonce identities without document-origin normalization. Worker decoding
must use the final selected worker StorageKey, not a key reconstructed from IPC.
Two final-origin/wire-key fixtures additionally reject conflicting legacy seeds
and disagreement between the typed browser partition and binary commitment.

`surface_policy_helpers_integration.patch` registers helper/fixture sources in
candidate GN targets only. It replays alongside GPU and Audio drafts without
applying changes to the active checkout; it does not replace any v1 IPC.

`surface_policy_wire_schema.patch` registers a separate, currently unused Mojo
schema. Its four fixed-length seed arrays and binary ByteString encoding passed
the pinned Mojo parser and C++ binding generator in an isolated directory
(`surface-policy-bindings-v2/proof.json` on D). Its typed StorageKey retains
opaque, nonce and upstream retained partition fields; no private key is sent.
`surface_policy_wire.h` prepares
validated owned encoding/decoding without connecting an endpoint. Generated
bindings are not C++ compilation, navigation/worker delivery or admission.

Before installation: compile/test the codec; connect its one owned v2 payload to
document/worker bootstrap coherently; validate all four seed lengths before copying;
retain old v1 behavior only for explicitly Canvas-only development launches.
Validate the final document/worker StorageKey, preserve token-bound rejection,
and make first-script, restart, multi-client worker and failure tests cover every
surface. Do not derive Audio keys from the Canvas seed or expose this snapshot
through JavaScript. v2 versioning must not change the established v1 profile key
derivation domain: transport format and identity derivation are separate contracts.

This snapshot alone enables no protection. Worker Audio API absence remains
explicit; no real-time AudioContext hook or emulated OS/GPU is claimed.

## Reproduce batch composition

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_next_batch.py `
  --workspace D:\CamouFlowNative `
  --report D:\CamouFlowNative\next-batch-new.json
```

Use a new absolute report outside the application and Chromium repositories.
The public checker passed across 26 composed paths on registered 001-030 source:
`gpu-audio-policy-public-replay-v3.json` on D. It verifies registered source
replay, exact canonical copies, active source/core/receipt/GN invariants and
records input hashes. No compiler, linker, browser or capability admission runs
inside this composition checker.

## Worker endpoint follow-up (unregistered)

`surface_worker_endpoint.patch` adds a separate GetSurfacePolicy method to the
existing worker-host endpoint, sharing its one-request rule, readiness timer,
BrowserContext lifetime and partition/origin checks with Canvas-only delivery.
It does not create a second key service or reuse a creator document's identity.
Ready replies use the four-domain producer and owned binary codec. Existing
Canvas-only callers retain their method; requesting both methods on one pipe is
a bad message, not an automatic fallback. The legacy consumer fixture explicitly
fails if it unexpectedly requests a surface bundle.

Eight new native fixture definitions cover ready/missing/loading/shutdown,
origin mismatch, both cross-method duplicate orders and unpartitioned
shared/service-worker rejection. They are not compiled or executed. Renderer
surface bootstrap, final Blink worker installation and first-script tests are
still required before this endpoint can enable a protection.

Mojo endpoint parsing/binding generation passed in
`surface-worker-endpoint-bindings-v1/proof.json` on D. The expanded five-patch
public replay passed across 31 paths with unchanged active source/core/GN/receipt:
`gpu-audio-policy-worker-public-replay-v1.json`. These are source/type proofs only.

## Worker consumer and Blink follow-up (unregistered)

`surface_worker_bootstrap.patch` adds an explicit v2 request to the existing
consumer, reusing its timer/disconnect/cancellation ownership. It accepts a known
worker partition or the browser-provided worker origin. The origin-only form is
needed because dedicated-worker creation does not give its renderer factory the
authoritative StorageKey. The reply carries a typed browser partition plus an
exact binary commitment; the consumer never derives a key from the creator URL.
Its seventeen consumer and five explicit-mode fixtures are not compiled or executed.

`worker_surface_handoff.patch` prepares owned creation parameters and immutable
WorkerGlobalScope state. Blink selects its actual security origin independently,
then rejects mismatches, reused seed domains and simultaneous v1/v2 bootstrap.
Required missing/malformed data prevents top-level script execution and uses
normal failure/close notifications, not a renderer CHECK. Four thread fixtures
cover owned seeds before evaluation and rejected first-script paths; none ran.

The scope patches do not enable Canvas/GPU/Audio hooks. Endpoint binding generation v2 and the
expanded seven-patch replay passed: `surface-worker-endpoint-bindings-v2/proof.json`
and `gpu-audio-policy-worker-handoff-public-replay-v1.json` on D (40 paths).
Active source, baseline browser core, receipt and GN arguments stayed unchanged.

## Three launcher paths (unregistered)

`worker_surface_launchers.patch` connects the explicit v2 request and owns its
result through dedicated/shared/service startup and Blink creation parameters.
The shared-worker constructor receives the **creator** key, so it does not treat
that as the worker's partition. Shared and dedicated requests compare the
browser-provided worker origin; their authenticated endpoint supplies the actual
key. Service startup also checks its existing browser-provided StorageKey.

One mode selector keeps off, Canvas-only, v2 and conflicting flags distinct.
Off does not acquire a policy; conflicting flags reject startup. Required v2
never substitutes a Canvas seed. Dedicated startup ignores late load messages
after failure. Service startup copies its key before moving parameters into
the continuation. Both installed-script and network service startup carry the
required flag and owned bundle. No active build files are modified.

The eight-patch public replay passed across 50 paths:
`gpu-audio-policy-worker-launchers-public-replay-v1.json` on D. This proves source
composition, not C++ compilation, successful browser startup or protection.

`verify_native_worker_startup.py --bootstrap-policy surfaces` prepares the same
classic/module, restart, shared multi-client and missing-policy execution-beacon
checks as Canvas-only diagnostics. It requires the exact registered/receipted
worker surface patch before launching anything; current 001-027 binaries cannot
pass by ignoring an unknown flag. The actual old-binary denial report is
`worker-surface-001-027-rejected-before-launch-v1.json`. Reports retain
`privacy_admitted: false`. The default Canvas-only command remains compatible.
Its full 001-027 regression rerun passed all forty actual startup/denial checks:
`worker-startup-001-027-canvas-regression-v2-probe-v1.json` on D. This validates
the existing Canvas bootstrap path, not the uncompiled v2 candidates.

## Document v2 ownership and final-partition gate (unregistered)

`document_surface_policy.h` owns the authenticated browser partition together
with all four independent surface seeds. Its preflight reuses the existing
provisional-origin resolver and validates the typed wire key against the binary
commitment before copying. A Canvas-only payload cannot substitute for v2 or
coexist with it. Off, Canvas-only, surfaces and conflicting modes are explicit;
unknown modes reject every payload combination.

`ValidateDocumentSurfacePolicy` checks both the owned browser partition and
Blink's final StorageKey. Missing required data fails, and payload presence
cannot bypass validation by clearing a required flag. The retained top-level
site remains significant even where upstream StorageKey equality ignores it
because third-party partitioning is disabled. Opaque identities, nonces and
embedded NUL bytes are preserved.

`document_surface_commit_producer.{h,cc}` resolves the selected navigation key
with the same document resolver, derives through the existing BrowserContext
service and encodes the owned typed envelope. Absent/loading/failed/shut-down
identities cannot produce a commit; no root key is recreated or sent. Eight
producer fixtures cover readiness, inherited origin, nonce preservation,
independent domains, ownership, shutdown and malformed identity retention.

`document_surface_validation.patch` adds these helpers, producer and **30 native
fixture definitions** (22 ownership/mode + 8 producer) to the existing content
unit target. They have **not compiled or executed**. The nine-patch public replay
passed across 55 paths:
`gpu-audio-policy-document-producer-public-replay-v1.json` on D. Active source,
browser core, GN arguments and receipt stayed unchanged. No v2 document startup
switch, DocumentLoader installation or Canvas/Audio/GPU hook is enabled here.

Next integration must carry this owned snapshot through browser commit and
renderer preflight, then establish a safe final-origin decision before any
unprotected document can execute. Do not call `DocumentLoader::CalculateOrigin`
as an early read-only probe: it mutates origin privileges and can consume a
sandbox token. Do not move the existing late CHECK to claim rollback: upstream
constructs the new DocumentLoader only **after** unloading/detaching the old
document. Early malformed-payload rejection, final-partition rejection, old-page
usability and synchronous blank/srcdoc/JavaScript/XSLT inheritance need separate
integration evidence before admission.

## Document/worker delivery batch (unregistered, source-only)

The next five patches extend the helper stage above:

| Candidate | Implementation | Current evidence |
| --- | --- | --- |
| `surface_bootstrap_switches.patch` | Forward both document and worker v2 switches to renderer processes; preserve v1 flags | Ordered source replay only |
| `document_surface_transport.patch` | Shared readiness/mode selection, browser producer, typed commit payload with an explicit required bit, early renderer validation and selected-token rejection | Source replay; pinned C++ and Blink Mojo binding generation |
| `document_surface_handoff.patch` | Owned DocumentLoader/DocumentInit handoff; immutable document state validated against the final window key; script gate; exact-partition synchronous inheritance and clone ownership | Source replay only; no C++ or execution |
| `document_surface_handoff_tests.patch` | Fifteen first-script, invalid-data, blank/srcdoc/sandbox and clone fixture definitions in four existing storage/link modes | Sixty expected cases; **not executed** |
| `document_surface_navigation_tests.patch` | Six readiness/deadline/shutdown fixtures and eight navigation fixtures in two URL-loader modes | Twenty-two expected cases; **not executed** |

`worker_surface_scope_state.patch` adds matching thread-checked readiness and
ownership accessors to the existing worker scope. Shared readback consumers must
distinguish an upstream flag-off context from a required policy that is missing
or invalid. Treating both as an absent optional seed would expose unprotected
output. These accessors do not activate any API hook.

The renderer rejects malformed/missing required envelopes before lifecycle
callbacks, body decoding or old-page teardown. The browser rejection remains
bound to its exact pending navigation token, selected RFH and browser-owned
privacy requirement; no caller-selected partition or root key is accepted.
Cleanup re-resolves the cached frame-tree node ID after cancellation rather than
dereferencing a raw node pointer: a finish observer may destroy the tab/RFH/node
inside cancellation. A new two-mode fixture covers that reentrant destruction;
it has not executed.

Final Blink validation is distinct. A late mismatch produces an **inert
replacement document**, not a new renderer CHECK and **not restoration of the
old page**. The fixture explicitly describes this limitation. Missing required
browser data cannot borrow an owner's seed. Synchronous inheritance may copy an
owner's already validated policy only when its full binary partition matches
the final key, including retained site/nonce/opaque identity. Clones preserve
all four domains and the required state, including required-but-missing state;
they cannot downgrade to Canvas-only data.

Root initial empty documents and different-partition sandboxed children still
need their own authenticated browser delivery path. They cannot borrow a parent
identity or silently run unprotected. Safe navigation recovery, XSLT/discard
replacement, all first-script paths and real browser compatibility are not
verified. Do not activate v2 or promote readiness from this source batch.

The fifteen-patch public replay passed across **75 paths**:
`gpu-audio-policy-document-scope-public-replay-v2.json` on D. Native sources,
baseline browser core, receipt and GN arguments stayed unchanged. Binding proof:
`document-surface-transport-bindings-v1/proof.json` and
`document-surface-blink-bindings-v1/proof.json`. Binding generation is not
translation-unit compilation, linking or browser execution. The document
stage has 112 planned native cases (30 helpers/producer + 60 handoff + 22
readiness/navigation); none of these new cases has run. The active 0030 build
still uses its unchanged, older twelve-case navigation gate.

## Initial main-frame and popup delivery candidate

`initial_main_surface_transport.patch` prepares authenticated policy delivery
for initial main documents and `window.open()` replies. The selected browser
RFH supplies its own BrowserContext, StorageKey and origin. Popup data is
captured before `ShowCreatedWindow`, which can destroy the RFH. No root key is
sent to a renderer.

The renderer decodes an owned snapshot before `WebLocalFrame::CreateMainFrame`.
A native client callback consumes it exactly once inside `FrameLoader::Init`'s
script-forbidden scope, before constructing the initial DocumentLoader.
Missing, mixed-mode or invalid required data remains required-and-inert; it
cannot borrow an opener policy. Flag-off initial documents retain upstream
behavior.

Before `CalculateOrigin`, the loader verifies the actual creator origin and
sandbox flags. An origin-sandboxed window requires an opaque browser origin;
an ordinary local creator must match exactly. Valid data supplies the browser
origin and key through existing loader fields while preserving upstream origin
aliasing, trust/local-resource inheritance and the final partition check.
Invalid or provisional state drops the snapshot without adding a renderer
CHECK or making the required document executable.

Fourteen native helper fixtures are prepared, **not compiled or executed**.
The 23-patch/102-path public replay passed with active inputs unchanged:
`initial-main-surfaces-public-replay-v3.json` on D. Initial-main/popup Mojo
parsing and C++ binding generation passed:
`initial-main-surface-bindings-v2/proof.json`. Neither proves runtime operation.

**Still incomplete:** a cold/loading key service needs a browser readiness
barrier before initial-frame creation. This candidate alone deliberately leaves
missing policy inert; it does not make cold startup ready. Authenticated child
sandbox delivery, first-script/browser-context tests, popup/creator lifecycle
regressions and XSLT/discard behavior also remain unverified. The earlier
four-patch promotion snapshot predates this new source and must be regenerated
before any promotion. Nothing here is registered or active in the current build.

## Bounded popup readiness candidate

`window_privacy_readiness.patch` holds a validated `CreateNewWindow` request
while its BrowserContext loads the existing identity. It waits asynchronously,
for at most ten seconds, without blocking the browser UI or returning raw
policy. Each requesting RFH admits at most one pending request. Missing service,
read failure, shutdown and timeout return the existing blocked-window result.

Completion stops the timer and invalidates late replies before invoking the
one-shot callback, which may destroy the waiter. RFH destruction cancels it.
Before retrying the original creation path, the callback verifies the original
render-frame generation, document token and live renderer. The original path
rechecks sandbox restrictions, URL and current activation; the wait does not
extend or fabricate a user gesture. Eight native fixtures are prepared, not
executed, including inline destruction and late-reply cancellation.

This is **popup readiness, not a solution for cold initial main-view creation**.
Simply deferring `CreateView` while marking its associated frame live is unsafe:
Mojo's endpoint client CHECKs calls before interface association. A main-view
barrier must precede that creation/lifecycle boundary; it cannot be implemented
as a postponed send or a sleep. That integration, true timeout execution and
full RFH/popup lifecycle regressions remain mandatory before activation.

## Startup identity preload candidate

`startup_privacy_preload.patch` closes the source-level cold-main readiness gap
before profile publication and associated frame endpoint creation. Only the
surface-policy diagnostic mode uses this path; feature-off and legacy Canvas
initialization keep the existing asynchronous implementation.

It reads the existing validated identity file inside the established profile
startup blocking exemption. The service is Ready or Failed before returning.
Missing or malformed identity is never regenerated, duplicate installation
cannot replace a Ready/Loading owner, and off-the-record contexts use their own
ephemeral key without reading the persistent root. An accepted installation is
not a readiness guarantee: callers must still query the service.

The identity reader bounds file **size** (256 bytes), not I/O duration. Slow storage can
delay synchronous profile startup; no timeout or nonblocking guarantee is
claimed. Real startup latency, first-script policy delivery, failure behavior
and synchronous/asynchronous profile creation must pass before activation.
There is no nested event loop, deferred `CreateView` or second identity format.
The existing browser trace category measures this scoped startup read as
`Glint.ReadOnlyStartupIdentityPreload`, without recording paths or key bytes.

Six BrowserContext fixtures are prepared, **not compiled or executed**. They
cover readiness before pumping tasks, missing/malformed identity, refusal to
replace an existing owner, ephemeral isolation and invalid-root rejection.
This is the 25th unregistered patch; it does not modify the active build.
Ordered replay of all 25 public patches across 112 paths passed with the active
sources, GN inputs, build receipt and linked runtime core unchanged:
`startup-preload-public-replay-v2.json` on D. This is source evidence only.
Before promotion, the context unit verifier must require the existing 20 cases
plus all six named startup cases. Its active-build definition is deliberately
unchanged while the current unit target compiles.

## Authenticated initial-child transport candidate

`child_surface_transport.patch` adds a separate synchronous FrameHost method
only for surface diagnostic mode. The existing asynchronous child API and its
method ordering remain unchanged. The browser reuses its original routing-token
authentication, sandbox restrictions and child-creation path; only afterward
does it return the actual child's StorageKey/origin-derived policy.

The reply requires the same live requesting-frame generation and document token,
the expected parent, the same BrowserContext and an initial-empty child. Missing
or mixed-mode policy does not authorize a raw initial document. The renderer
owns and validates the reply before `CreateLocalChild`, then uses the existing
single-consumption, script-forbidden initial-document handoff. No parent seed,
renderer-derived opaque identity or root key is substituted. The loader retains
its creator/sandbox checks and final StorageKey validation.

Five native fixtures are prepared, **not compiled or executed**: feature-off
rejection without token consumption, no policy disclosure despite a Ready key,
callback-time owner destruction and actual child/parent derivation checks. They
do not prove authenticated routing-token processing or the full Mojo round trip.
Pinned Mojo parsing and all four C++ binding generation modes passed in
`child-surface-bindings-v1/proof.json` on D; that is not C++ compilation.
The generated binding contract check also passed: all pre-existing method
ordinals in that configuration remain unchanged, and the new synchronous reply
uses a bool plus an owned typed policy with a one-shot callback
(`child-binding-contract-v1.json`). Ordered replay of 26 public patches across
113 paths passed with active source/GN/receipt/runtime unchanged:
`child-surfaces-public-replay-v2.json`. Four aggregate patches on D independently
reproduce that exact source (`surface-promotion-v5/proof.json`); they remain
unregistered and unapplied.
That historical promotion snapshot predates the renderer mock adapter and GPU
shader follow-up; the updated 27-candidate aggregate is
`surface-promotion-v6/proof.json` on D. Promotion still requires the current
registered navigation-unit build to finish and pass first.

This synchronous opt-in protocol is not a production performance admission.
Nested creation, iframe removal/reparenting, parent navigation/process exit,
prerender, credentialless/fenced partitions, opaque sandbox origins with the
sandbox-token feature both on and off, invalid tokens and associated endpoint
ordering need actual browser tests. No active build source has changed.

The renderer-only `MockFrameHost` adapter explicitly reports unavailable for
both signatures of the new child protocol. It has no browser-owned key service
and cannot fabricate an authenticated policy or call the legacy asynchronous
creation path as a fallback. These mock responses are not real IPC/key tests.
