# Surface policy v2 candidate

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
