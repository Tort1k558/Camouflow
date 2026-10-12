# Unapplied Glint development patches

The remaining context-test candidate is public source, not a registered build
input or passing runtime evidence. Do not apply it during an active build.
Its promoted readiness dependency is described separately below.

## BrowserContext privacy bridge

`browser-context-tests.patch` adds 20 cases to the pinned Chromium
`content_unittests` target, using real TestBrowserContext/BrowserTaskEnvironment
and the production Native bridge. It is not another SupportsUserData-only test.

Coverage:

- persistent loading/readiness and context recreation;
- separate persistent identities;
- independent off-the-record contexts and rejection of persistent OTR roots;
- missing/malformed identities without regeneration;
- early BrowserContext shutdown, stopped service state and late loading replies;
- destruction during loading;
- partition/surface separation, invalid surfaces and null contexts.

Shutdown tests inspect the underlying service state as well as bridge readiness:
checking only ShutdownStarted would conceal a missing service shutdown hook.
Tests use public fixed fixture identities, never real user profile secrets.

The patch passes `git apply --check` against the current source and does not
modify it. It has **not been compiled or run**. Registration in the exact source
replay gate, compilation and execution are pending after the current build.
The planned execution is the standard content unit target filtered to
`NativePrivacyBrowserContextTest.*`, with single-process GoogleTest JSON output.
All 20 named cases must finish successfully; a count alone is insufficient.
Seven cases use the readiness bridge now registered in
`../patches/0016-native-private-key-readiness.patch`. Register this context-test
candidate only after verifying that dependency. They check absent/null contexts, queued
loading, identity failure, real context shutdown/destruction, reentrant shutdown
and off-the-record inline completion without reading the persistent identity.

These tests cover real content-layer BrowserContext behavior, not the actual
Chrome ProfileImpl/incognito bootstrap, renderer/worker IPC, Canvas protection,
operating-system memory sanitization or multi-process profile locking. Those
require separate compilation/runtime evidence.

## Promoted dependency: asynchronous privacy key readiness

`../patches/0016-native-private-key-readiness.patch` adds a UI-sequence `PrivacyKeyService::WhenReady` callback
API and public `WhenNativePrivacyContextReady` bridge, prerequisites to
browser-owned renderer key delivery. It does not expose the
root key or activate fingerprint surfaces. Callers must start initialization
before waiting; an uninitialized service fails immediately, without fallback.

Loading queues at most 256 callbacks. Overflow fails immediately. Readiness,
loading failure and explicit shutdown settle callbacks once; destruction cancels
queued callbacks. Terminal-state callbacks run inline, so callers must tolerate
reentrancy. During completion a callback can shut down or destroy the service:
remaining callbacks must receive failure, never stale success or a freed pointer.

Ten added service tests cover loading/derivation, inline terminal completion,
failure without identity regeneration, shutdown/late replies, destruction,
completion-time shutdown/destruction, nested callbacks and the queue bound.
They extend the existing native unit target, not a separate test framework.

The patch was promoted from this draft directory after the 001–015 build and
verification processes completed. It is registered/applied in the development
checkout; the strict verifier now requires **43** cases, including the ten new
readiness cases. All 43 native cases compiled and passed after correcting test
callbacks to Chromium's `BindLambdaForTesting` helper. The existing linked
001–015 browser does not contain this new implementation.
This is not yet a browser startup gate, document/worker IPC, a timeout policy or
Canvas protection. Those consumers must bind cancellation to their own lifetime
and obtain partitions from trusted browser state, not renderer-provided URLs.
