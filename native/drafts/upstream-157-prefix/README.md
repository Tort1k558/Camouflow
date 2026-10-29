# Chromium 157 source-port prefix

**Source-only workbench: 001–032 verified, 0033–0064 still pending. Not a browser release.**

Pins Chromium `157.0.8103.27` / `f9d7b13a569b352a0267234ea5740fdecc83ffa2`
and its DEPS-selected V8 `a4889e05285021952e2ca9648c805a4c989345ae`.
Only six ported patches are stored here; unchanged payloads reference
`upstream-156/patches`. No upstream source files are committed.

| Manifest | Pristine inputs | Patch selection | Measured result |
| --- | --- | --- | --- |
| `manifest.json` | 88 | 001–032 | Source application passed |
| `full-inputs-manifest.json` | 185 | 001–064 | Stops at 0033 Audio integration; not a completed port |

| Patch | Adaptation |
| --- | --- |
| 0006 | Reanchor the existing UA/metadata tests; added/removed lines preserved |
| 0018 | Preserve upstream's new connection-allowlist include around document-service registration |
| 0022 | Use upstream's three-argument worker creation API; move the seed before moving script-load parameters |
| 0026 | Preserve `RunWorkerToplevelScriptForTesting` after the existing seed bootstrap |
| 0029 | Reanchor validator-header registration to the current service-worker header list |
| 0030 | Retain that upstream header-list context for navigation commit declarations; added/removed code preserved |

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

For the complete input corpus, explicitly select `full-inputs-manifest.json`
and new output paths. It records all 185 known hashes, not a fully applicable
patch chain. The same replay command currently **must fail at 0033 after 32
applications**. Do not label that failure or an input download as runtime readiness.

## Measured scope and remaining work

October 29: the public CLI passed the 32-patch prefix with input/patch postguards.
Cache preparation measured **88 hits / zero HTTP requests**. Separately, all
**185 inputs** were cache-validated and the full public 64-patch attempt retained
its expected 0033 failure with unchanged inputs/patches. Evidence on D under
`Glint157ObjectCache`: `public-prefix32-{inputs,replay}`,
`public-full185-inputs` and `public-full64-attempt`.

Earlier HTTP timeouts, the interrupted Git operation and partial replays remain
failed historical evidence. Verified cached objects supplied the complete corpus;
this was not a successful full checkout or a claim that Git transport never fails.

### Next port: chunked OfflineAudioContext

157 makes total render length optional and supports finite/indefinite chunks;
the old 0033 hunks no longer apply. The port must preserve upstream chunking,
capture a stable policy before rendering, check the actual chunk's allocation
budget before resolver/buffer/thread creation, and transform each chunk before
its Promise. The final completion event must share that final chunk's mutable
result; intermediate chunks must not gain invented completion events. Missing policy, retries,
cancellation, pause/resume and feature-off calibration need native/runtime tests.
Do not force `.value()` on an indefinite length or disable chunking to make a patch apply.

The prefix preserves all earlier 72 inputs and adds prerequisites for 0030–0032.
GPU/GRIT invariant inputs are outside that selected scope; empty
`source_invariants` is not a pass for those gates. Patches **0033–0064 remain
unported/unverified** on 157.
No C++ compilation, native tests, runtime behavior, security review or package
verification has been established for this draft. The active 156 build and
default 148 pin remain separate; `native_build.py` does not accept this target.
