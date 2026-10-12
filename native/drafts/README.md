# Unapplied Native verification patches

These candidates are public source, not registered build inputs or passing
runtime evidence. They must not be applied during an active Chromium build.

## BrowserContext privacy bridge

`browser-context-tests.patch` adds 13 cases to the pinned Chromium
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
All 13 named cases must finish successfully; a count alone is insufficient.

These tests cover real content-layer BrowserContext behavior, not the actual
Chrome ProfileImpl/incognito bootstrap, renderer/worker IPC, Canvas protection,
operating-system memory sanitization or multi-process profile locking. Those
require separate compilation/runtime evidence.
