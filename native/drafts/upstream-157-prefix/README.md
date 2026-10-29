# Chromium 157 source-port prefix

**Source-only workbench: all 65 patch applications verified. No compiled 157 browser.**

Pins Chromium `157.0.8103.27` / `f9d7b13a569b352a0267234ea5740fdecc83ffa2`
and its DEPS-selected V8 `a4889e05285021952e2ca9648c805a4c989345ae`.
Eleven selected ported patches are stored here; unchanged payloads reference
`upstream-156/patches`. No upstream source files are committed.

| Manifest | Pristine inputs | Patch selection | Measured result |
| --- | --- | --- | --- |
| `manifest.json` | 88 | 001–032 | Source application passed |
| `full-inputs-manifest.json` | 185 | 001–065 | Source application, GPU numbering and GRIT structure passed; compilation/runtime pending |

| Patch | Adaptation |
| --- | --- |
| 0006 | Reanchor the existing UA/metadata tests; added/removed lines preserved |
| 0018 | Preserve upstream's new connection-allowlist include around document-service registration |
| 0022 | Use upstream's three-argument worker creation API; move the seed before moving script-load parameters |
| 0026 | Preserve `RunWorkerToplevelScriptForTesting` after the existing seed bootstrap |
| 0029 | Reanchor validator-header registration to the current service-worker header list |
| 0030 | Retain that upstream header-list context for navigation commit declarations; added/removed code preserved |
| 0033 | Prototype for chunked Audio: retain upstream queues and final-event ordering, check actual chunk size, capture policy once, reject/close on failed copy |
| 0055 | Reanchor the feature declaration around upstream's new GPU initialization feature |
| 0056 | Retain upstream idle-trim tests and existing includes while adding the metadata protocol fixtures |
| 0061 | Apply branding to the same message IDs without removing new upstream messages; retain binary logo payloads |
| 0065 | Reanchor the test-only fixture repair's include context; same added/removed code as the compiler-checked 156 repair |

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
and new output paths. It records all 185 known hashes and the complete 65-patch
source application. Do not label source application or an input download as
runtime readiness.

## Measured scope and remaining work

October 29: the public CLI passed the 32-patch prefix with input/patch postguards.
Cache preparation measured **88 hits / zero HTTP requests**. Separately, all
**185 inputs** were cache-validated and the full public 64-patch attempt retained
its earlier 0033 failure with unchanged inputs/patches. Evidence on D under
`Glint157ObjectCache`: `public-prefix32-{inputs,replay}`,
`public-full185-inputs` and `public-full64-attempt`.

The subsequent full replay applied **001–065** over all 185 inputs.
GPU command numbering retained 321 entries and appended command 577; GRIT
structure was preserved. The public full manifest reproduces this source check.
Evidence: `D:\Glint157ObjectCache\public-full65-replay-v2\report.json`.
Earlier failures remain historical evidence, not passing compilation results.

Earlier HTTP timeouts, the interrupted Git operation and partial replays remain
failed historical evidence. Verified cached objects supplied the complete corpus;
this was not a successful full checkout or a claim that Git transport never fails.

### Next validation: chunked OfflineAudioContext

`0066-native-chunked-audio-tests.patch` is a **pending, unselected** fixture
extension outside `patches/`. `chunked-audio-tests.json` binds its exact bytes to
the full 001–065 manifest and test-source input. It does not change either
selected manifest or the live 156 build.

Eleven test bodies are prepared; **none has been compiled or executed on 157**:

| Fixture scope | Intended assertion |
| --- | --- |
| Missing required policy | Explicit chunk call rejects before resolver/thread creation |
| Zero and overflowing chunks | Upstream exception types/messages precede missing-policy errors |
| Rounded allocation budget | A three-channel request fits before rounding but exceeds 64 MiB after rounding; rejection allows a small retry |
| Large finite render length | A small requested chunk is not rejected using the entire context length |
| Three queued chunks | 128/128/44 frames; one final event; the event and final Promise share a mutable buffer |
| Separate policy vectors | Real constant-source samples match independent seed-4/seed-5 HMAC vectors, not merely silence |
| Flag-off indefinite rendering | Raw samples remain unchanged; closing settles without a completion event |
| Protected queue suspend/resume | Both chunks remain pending at the pause; resume returns protected samples and one final event |
| Close while the protected queue is paused | Both render Promises and a future suspend reject; closing produces no completion event or late success |
| Closed context with missing policy | The upstream InvalidState error precedes policy lookup and resolver creation |

The patch preserves all 12 existing test cases. Source application and five API
header blobs were verified against pinned 157 Git objects. Header validation,
formatting, HMAC-vector calculations and Python assertions are **not C++ or native
test results**. Evidence: `D:\Glint157ObjectCache\chunked-audio-fixtures-20261029-v5`.
Apply it only to a separate 157 tree after the selected 001–065 replay, never to
the active 156 checkout. A 157 build/test run is still required before selection.
Injected copy-failure cleanup and policy lifetime under teardown still lack
fixtures. Suspend/resume and paused-close now have fixture code but remain
unverified until a real 157 native test run.

#### Compatibility control, not just distinct hashes

The v1 HMAC vectors verify the experimental transform's mechanics, **not ordinary
browser fidelity**. For a constant input `0.25`, seed 5 predicts `3e800001` rather
than `3e800000`. The [Web Audio constant-source model](https://www.w3.org/TR/2026/WD-webaudio-1.1-20260922/#ConstantSourceNode)
describes the output through its offset parameter. Chromium's constant-source
handler fills the output with that value. This exposes a plausible calibration
conflict, not evidence that a changed hash is a successful fingerprint policy.

The public `audio-constant-control.js` probe was actually run in **stock
148.0.7778.96** using a new isolated profile: `0`, `0.25`, `-0.25`, `0.5` each
returned 256 exact samples, shared event/Promise buffers and closed contexts.
Executable/core hashes were unchanged. This is **not a matched-version A/B run
of 156 or 157**, nor a measured native-candidate failure. Evidence:
`D:\Glint157ObjectCache\stock-audio-dc-control-20261029-v4\report.json`.
The descriptor explicitly keeps the compatibility/production gate false.

Before admission, run matched stock/candidate controls for constants, identity
gain/buffer graphs and segmentation. Do not "fix" this by skipping flat buffers:
that can change the same signal depending on chunk boundaries. Resolve the
algorithm/identity model and preserve whole-render/chunk consistency first.

157 makes total render length optional and supports finite/indefinite chunks;
the old 0033 hunks no longer apply. The prototype preserves upstream chunking,
captures a stable policy before rendering, checks the actual chunk's allocation
budget before resolver/buffer/thread creation, and transforms each chunk before
its Promise. The final completion event shares that final chunk's mutable
result; intermediate chunks do not gain completion events. Missing policy, retries,
cancellation, pause/resume and feature-off calibration need native/runtime tests.
Do not force `.value()` on an indefinite length or disable chunking to make a patch apply.

The prefix preserves all earlier 72 inputs and adds prerequisites for 0030–0032.
GPU/GRIT invariant inputs are outside that selected prefix; empty
`source_invariants` is not a pass for those gates. Use the full manifest for them.
**Source application is complete, but the Audio API adaptation still needs
native queued-chunk, error-cleanup, budget/retry, policy-lifetime and runtime
compatibility tests.** `complete_forward_port` remains false for that reason.
No C++ compilation, native tests, runtime behavior, security review or package
verification has been established for this draft. The active 156 build and
default 148 pin remain separate; `native_build.py` does not accept this target.
