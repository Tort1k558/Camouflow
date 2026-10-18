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
ten patches in sequence, parses included Python/DEPS files and rechecks inputs.
Real local evidence: `upstream-156-replay-v4/report.json` on D: **10/10 passed**.
The earlier v2 report covers only the first six drafts. The v3 scratch replay
was superseded after detecting CRLF-only churn in generated V8 patch context;
v4 uses the compact LF patch and explicit autocrlf-disabled application.
The Windows standalone C++ policy suite also passed with added real DirectWrite
font-set conversion and allowed/excluded unique-name positive controls. This
does not compile the new Chromium local-font matcher translation unit.

## Still required

- Port and review patches 0011-0062 and any additional dependency/API changes.
- Check all new upstream paths that could bypass old policy boundaries.
- Run GN/checkdeps and compile against the target's actual dependency set.
- Repeat complete runtime, rendering, storage, proxy, restart and crash gates.
- Review upstream security changes and update the reviewed package only after
  packaging and rollback checks. No manifest flag or successful patch replay
  admits production or grants the existing 148 package's capabilities to 156.
