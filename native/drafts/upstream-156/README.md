# Chromium 156 rebase candidate

**Draft source port, not an enabled engine or a compiled browser.** The active
build lock and registered 001-062 chain still target Chromium 148.0.7778.96.

Target: **156.0.8078.36**, Chromium revision
`5a93aa59e3043e747eff68659dcf7d20193d160e`.
`manifest.json` binds each source input to an immutable Gitiles URL/hash and
each draft patch to its hash and original registered patch hash.

| Draft | Ported scope |
| --- | --- |
| 0001 | CPU/memory ceilings, renderer switches; updated Blink build/DEPS contexts |
| 0002 | Existing locale-correct MIDL helper, adapted to upstream Python indentation |
| 0003 | WebRTC routing policy; source-context replay passed |
| 0004 | Existing webdriver control, updated runtime-feature registration context |
| 0005 | Native font collection/fallback and service manager; new upstream DirectWrite local-font matcher uses the same restricted collection's font set |
| 0006 | Existing native headless-UA control; source-context replay passed |
| 0007 | Inspector Error-description safety, rebased onto the exact V8 dependency while retaining upstream builtin-getter checks |
| 0008 | Existing LevelDB Windows path separator normalization |
| 0009 | Existing extended Windows SQLite path handling and its upstream test cases |
| 0010 | Existing Windows persistent-profile namespace handling |
| 0011 | Versioned StorageKey privacy serialization and partition tests |
| 0012 | Profile-key derivation primitives and native test target; build registration moved to the new upstream file layout |
| 0013 | Existing fail-closed owned-profile key loader and loader tests |
| 0014 | Key service lifetime and ephemeral keys |
| 0015 | BrowserContext/Profile ownership and off-the-record context initialization |
| 0016 | Key-readiness contract and checks |
| 0017 | BrowserContext tests and content-test dependency registration |
| 0018-0020 | Document/worker Mojo services, bindings and renderer bootstrap consumer |
| 0021-0025 | Dedicated/shared/service-worker startup gates and owned seed handoff; dedicated-worker continuations retain the new upstream PolicyContainer |
| 0026-0028 | Worker-thread tests adapted to upstream factory/mock APIs, bootstrap failure and fixture lifetime |
| 0029-0030 | Document partition validation, navigation commit carrier/preflight, throttle registration and loader/context tests |
| 0031-0032 | Worker/document surface transport, initial windows/child frames and readiness; new InitiatorStateToken is retained end-to-end |
| 0033-0034 | Existing experimental Canvas/Audio/WebGL readback and GPU metadata candidates, not admitted profile controls |
| 0035-0045 | Origin, type/ABI, cancellation, observer lifetime and fixture/throttle corrections |
| 0046-0048 | Bounded/clipped WebGL readback and publication fixtures |
| 0049-0054 | Profile-identity derivation/mode, context/transport/handoff tests and launch policy; updated worker fixture calls |
| 0055-0058 | Existing GPU metadata protocol and attachment candidates; command appended at target ID 577 without changing upstream IDs |
| 0059-0062 | Unchanged-snapshot write avoidance, Glint branding/resources and Windows font rasterization |

The font service gained an independent local-font matcher upstream. Merely
repairing rejected patch context would leave that new path unrestricted. The
draft also restricts its DirectWrite font set without changing allowed fonts'
real file paths or disabling all CSS local-font matches. The default path,
including upstream test-font handling, remains unchanged when no policy is set.
The conversion uses the documented
[IDWriteFontCollection1::GetFontSet API](https://learn.microsoft.com/en-us/windows/win32/api/dwrite_3/nf-dwrite_3-idwritefontcollection1-getfontset).

## Reproduce source-context verification

Use an unmodified checkout of the exact target revision, or a directory with
the exact `source_files` listed in the manifest. No dependencies need downloading
for this limited gate. It rejects mismatched/linked source inputs and changed
patches before creating output. It does not modify the supplied source tree.

```powershell
.venv\Scripts\python.exe scripts/verify_native_rebase_draft.py --source D:\Glint156\src --output D:\Glint156\replay-1
```

The manifest pins V8 revision `8ce248ef8f7f71c04f7faaac249a37d340279f52`
from the exact Chromium DEPS file, not from an unrelated Stable rollout.
Patch 0007 runs in the separate `v8` repository directory. The verifier checks
the DEPS binding before creating output and disables Git autocrlf for patch
application, regardless of the user's global configuration. It rejects BOM/CRLF
patches rather than rewriting entire source files as an incidental rebase.

The output must be new, external and outside the input tree. The gate copies
only checksummed inputs into its owned scratch directory, checks/applies all
62 patches in sequence, parses included Python/DEPS files and rechecks inputs.
Real local evidence: `upstream-156-replay-v8/report.json` on D: **62/62 passed**,
165 upstream source inputs, including original binary resource inputs. Earlier
reports cover their smaller patch sets. After an upstream HTTP 429, 24 missing
inputs were recovered from the owned immutable Git baseline and individually
checked against the already recorded upstream hashes; no alternate source or
unchecked content was substituted.
15 resulting GN/GNI files passed syntax parsing with the existing installed
GN tool, without changing bytes: `upstream-156-gn-syntax-v4.json`. This is not
`gn gen`, `gn check`, dependency-graph validation or execution of C++ tests.
`upstream-156-abi-resources-v1.json` separately confirms preservation of all
321 upstream GLES2 command ordinals, append-only command 577, and unchanged
GRIT XML structure/attributes. It does not regenerate GPU code or compile GRIT.
The earlier v2 report covers only the first six drafts. The v3 scratch replay
was superseded after detecting CRLF-only churn in generated V8 patch context;
v4 uses the compact LF patch and explicit autocrlf-disabled application.
The Windows standalone C++ policy suite also passed with added real DirectWrite
font-set conversion and allowed/excluded unique-name positive controls. This
does not compile the new Chromium local-font matcher translation unit.

Readback candidates are retained for research/regression, not silently enabled
for user profiles. Their previously observed explicit-pixel/HDR compatibility
problems on 148 are not fixed by a source rebase. No 156 compatibility result,
production admission or Canvas/Audio/GPU protection claim follows from replay.

## Still required

- Complete full-source/API review and select the candidate explicitly in build
  tooling; the default build lock/registered patch chain still target 148.
- Check all new upstream paths that could bypass old policy boundaries.
- Run GN/checkdeps and compile against the target's actual dependency set.
- Repeat complete runtime, rendering, storage, proxy, restart and crash gates.
- Review upstream security changes and update the reviewed package only after
  packaging and rollback checks. No manifest flag or successful patch replay
  admits production or grants the existing 148 package's capabilities to 156.

The replay gate also checks source invariants automatically: existing GLES2
command names/ordinals must remain unchanged, with exactly one append-only
metadata command; branding may change GRIT text but not its element structure
or attributes. Failure keeps `passed=false` in the report. The complete run
`upstream-156-replay-v9/report.json` passed these checks (321 original commands,
new ordinal 577). These checks do not replace code generation or compilation.
