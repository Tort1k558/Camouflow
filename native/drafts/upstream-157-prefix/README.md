# Chromium 157 source-port prefix

**Partial source draft: 001–029 only. Not a build candidate or browser release.**

Pins Chromium `157.0.8103.27` / `f9d7b13a569b352a0267234ea5740fdecc83ffa2`
and its DEPS-selected V8 `a4889e05285021952e2ca9648c805a4c989345ae`.
The manifest records **72 pristine inputs** and 29 selected patches. Only five
ported patches are stored here; the other 24 reference the unchanged
`upstream-156/patches` payloads. No upstream source files are committed.

| Patch | Adaptation |
| --- | --- |
| 0006 | Reanchor the existing UA/metadata tests; added/removed lines preserved |
| 0018 | Preserve upstream's new connection-allowlist include around document-service registration |
| 0022 | Use upstream's three-argument worker creation API; move the seed before moving script-load parameters |
| 0026 | Preserve `RunWorkerToplevelScriptForTesting` after the existing seed bootstrap |
| 0029 | Reanchor validator-header registration to the current service-worker header list |

## Reproduce the bounded source replay

Create the output parent directories first; both outputs must be fresh and
external to the repository. Use the **drafts root** as the patch directory so
manifest-relative references resolve without copying unchanged patches:

```powershell
$manifest = (Resolve-Path native/drafts/upstream-157-prefix/manifest.json).Path
$patches = (Resolve-Path native/drafts).Path
.venv\Scripts\python.exe scripts/fetch_native_rebase_sources.py --manifest $manifest --output D:\GlintSources\157-prefix
.venv\Scripts\python.exe scripts/verify_native_rebase_draft.py --source D:\GlintSources\157-prefix --output D:\GlintEvidence\157-prefix-replay --manifest $manifest --patch-directory $patches
```

The fetcher's optional `--cache` validates existing bytes without changing them.
Its rate, no-retry/redirect rules and manual-cooldown requirements are described
in the [refresh instructions](../upstream-156-refresh/README.md).

## Measured scope and remaining work

October 29: all 29 selected patches applied through the public CLI, with source,
manifest and patch postguards passing. Input preparation used **72 cache hits,
zero network requests**. Evidence on D:
`public-157-prefix-inputs-20261029-v1/source-fetch-report.json` and
`public-157-prefix-replay-20261029-v1/report.json`.

The earlier 157 retrieval resumed after more than 15 minutes, verified the
previous 28 cached files, then reached **72 of 185 inputs** before a read timeout.
That failed report remains `upstream-forward-preflight-20261029-v3/report.json`;
no automatic retry was made. Active 156 build/source hashes and cached inputs
remained unchanged. Failed pre-port replays are retained, not relabeled as passes.

Patch **0030** needs eight unavailable inputs listed in the manifest.
Patches **0030–0063 remain unverified** on 157. The current 156 base includes the
later safe-buffer portability append; this 29-patch prefix does not apply it.
GPU/GRIT invariant inputs are not
in this bounded replay; empty `source_invariants` is not a pass for those gates.
No C++ compilation, native tests, runtime behavior, security review or package
verification has been established for this draft. The active 156 build and
default 148 pin remain unchanged; `native_build.py` does not accept this target.
