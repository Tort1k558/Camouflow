# Chromium 157: R8 source-port workbench

**All 131 packets apply and reverse. No compiled 157 runtime or release admission.**

The [complete source replay](full-source-observations.json) preserves all 270
immutable inputs, 321 upstream GPU command ordinals and GRIT structure. Reversing
all 131 packets restores the exact upstream files and removes added files.
The active 156 checkout, runtime selection and default 148 pin are unchanged.

The 15 new adaptations preserve orphaned screenshot-session teardown, Dawn's
new command-signature API and indirect-draw batching. Collection-only preview
does not enqueue GPU draws. Audio ownership claims queued resolvers before
completion, retains the captured key across idle/queued chunks and clears it on
final completion, close, rejection or detach. Four R8 completion tests and three
new finite/indefinite/queued-owner tests are prepared, **not compiled or executed**.
Source application does not prove C++ type correctness or runtime compatibility.

Target: Chromium **157.0.8103.27** / `f9d7b13a569b352a0267234ea5740fdecc83ffa2`,
V8 `a4889e05285021952e2ca9648c805a4c989345ae`,
Dawn `3c24c91e70eaf701ae92ab8cc414669cc4c38892` from that Chromium's DEPS.

| Artifact | Proven scope |
| --- | --- |
| `full-source-manifest.json` | Complete 131-packet applicable source inventory; not a registered build candidate |
| `full-source-observations.json` | Forward/reverse replay, immutable inputs and explicit compilation/runtime limits |
| `manifest.json` | First 75 packets apply; GPU command ordinals and GRIT structure preserved |
| `full-unported-manifest.json` | Complete 131-packet inventory, **not** an applicable full port; stops at 76 |
| `patches/0067-…patch` | AudioMath adapted to 157's finite/indefinite chunk API; 14/16 original file sections retained verbatim |
| `source-observations.json` | Exact replay/input hashes and explicit incomplete/compile/runtime boundaries |
| `upstream-audit.json` | November 1 official metadata: current R8 `.36` remains behind Stable |

The input corpus contains 270 pinned pristine files: 185 validated cached inputs
and 85 new immutable official HTTPS responses, with a two-second request interval
and no retries. No upstream sources, tools or binaries are bundled here.

AudioMath captures its pipeline only once for queued chunks, keeps Math separate
from legacy post-read processing and preserves upstream chunk sizing/queueing.
All upstream 157 OfflineAudioContext test bodies are retained, as are the older budget test and the
12 AudioMath case names after packet 68. These are **source assertions present**,
not compiled or executed tests. The sixteen adapted-packet postimages match the
isolated preparation; only the context and its test file require adaptation.

## Reproduce the complete source application

Use fresh canonical D: directories with existing parents. The patch root must be
`native/drafts` because unchanged packets reference existing public source files.

```powershell
$manifest = (Resolve-Path native/drafts/upstream-157-r8-port/full-source-manifest.json).Path
$patches = (Resolve-Path native/drafts).Path
.venv\Scripts\python.exe -B scripts/fetch_native_rebase_sources.py --manifest $manifest --output D:\GlintSources\157-r8-inputs
.venv\Scripts\python.exe -B scripts/verify_native_rebase_draft.py --source D:\GlintSources\157-r8-inputs --output D:\GlintEvidence\157-r8-prefix --manifest $manifest --patch-directory $patches
```

The older `manifest.json`, `full-unported-manifest.json` and
`source-observations.json` retain the historical 75-prefix / packet-76 failure.
They are not rewritten as successes. The next gate is C++ API/type review and
native execution of the new queue/lifetime tests, followed by the full combined
runtime checks. Do not disable upstream chunking, batching or assertions merely
to make those gates pass.

The workbench is unregistered in `native_build.py`. It cannot change the active
156 checkout, default 148 pin, manager policy admission or current R8 QA.
Source application does not establish C++ API/type correctness, linking, runtime,
security, device cohorts, anti-bot acceptance or production readiness.
