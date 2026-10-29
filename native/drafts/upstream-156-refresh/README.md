# Chromium 156.0.8078.75 source replay

**Prepared input manifest, not a build candidate or released browser.**

This snapshot pins Chromium `861389936bf33ea77529ee5dcc0605e68f6bb620`
and its DEPS-selected V8 `235050a0df6db2c9d92a419af2b72fbf3b2dd73b`.
All 185 pristine input files and all 65 patch hashes are recorded in
`manifest.json`. Patch bytes are reused from `../upstream-156/patches`, not
duplicated here. `base_manifest_sha256` binds the selected .36 candidate snapshot.

## Reproduce

Fetch the 185 pristine files into a fresh directory outside the repository:

```powershell
$manifest = (Resolve-Path native/drafts/upstream-156-refresh/manifest.json).Path
.venv\Scripts\python.exe scripts/fetch_native_rebase_sources.py --manifest $manifest --output D:\GlintSources\156.0.8078.75
```

The output's parent must already exist. Optional `--cache <existing-directory>`
reuses only size/hash-validated files without modifying the cache. Present but
invalid cache entries abort before any HTTP request; they are not redownloaded.
Requests use exact official immutable URLs, reject redirects and start at least
two seconds apart. There are no retries or mirrors. A failed fetch leaves its
owned output and `source-fetch-report.json`, including HTTP status/Retry-After.
Honor the server's cooldown before manually resuming into a **new** output with
the previous output as `--cache`; the tool does not schedule or enforce cooldown.

Alternatively, provide the files at their manifest-relative paths. Their immutable
Gitiles URLs, decoded byte lengths and SHA-256 values are in the manifest;
source files are not bundled. The replay verifier does not download anything.
Use fresh evidence outside the repository, source tree and shared patch folder:

```powershell
$null = New-Item -ItemType Directory -Path D:\GlintEvidence -Force
$manifest = (Resolve-Path native/drafts/upstream-156-refresh/manifest.json).Path
$patches = (Resolve-Path native/drafts/upstream-156/patches).Path
.venv\Scripts\python.exe scripts/verify_native_rebase_draft.py --source D:\GlintSources\156.0.8078.75 --output D:\GlintEvidence\refresh-replay --manifest $manifest --patch-directory $patches
```

The explicit manifest and patch directory must be supplied together. There is
no implicit fallback to the default candidate. Input hashes, patch hashes,
Chromium/V8 dependency binding, GPU command ordinals, GRIT structure and final
postguards remain required. Optional `--formatter` retains the existing GPU
generated-output comparison; it is not compiler/toolchain admission.

## Evidence and limits

The current 65-patch chain passed source replay on .36 and .75 with unchanged
inputs and preserved GPU/GRIT invariants:
`audio-safe-copy-20261029-v1/{default-64-replay,refresh-64-replay}/report.json` on D.
This is not compilation of the .75 target or a repeated codegen gate.

After the append-only safe-buffer port, the final 63-patch manifest passed
source replay on both .36 and .75 with GPU ordinals/GRIT postguards preserved.
Evidence: `safe-buffer-minimal-style-20261029-v1/refresh-63-final-replay/report.json`
on D. This does not rerun the older codegen gate or compile the .75 target.

The public fetcher was exercised with all **185 cached files / zero HTTP
requests**, followed by all **62 patch applications**. A separate cold fetch of
one pinned `chrome/VERSION` file passed against Google HTTPS. This is not an
end-to-end cold download of all 185 files. Evidence on D:
`public-source-fetch-proof-20261029-v1/report.json`.
Manifest files use checkout-independent LF bytes via `.gitattributes`.
Retrieval itself does not change a build. The later append-only 0063 C++
portability fix has a separate manifest/proof in the test matrix; it does not
retroactively change the earlier 62-patch reports below.

October 29: the public CLI replay passed all 62 patches with unchanged inputs,
321 preserved GPU command IDs plus command 577, and preserved GRIT structure.
Private evidence on D: `public-refresh-replay-20261029-v1/report.json`.
The optional codegen run also reproduced all **30 generated GPU files**:
`public-refresh-codegen-20261029-v1/report.json`. The measured formatter was not
verified as this target's pinned dependency, so that gate is not toolchain admission.
This checks source contexts and selected invariants, not C++ types, linking,
native execution, runtime behavior or a CVE/security review.

The active build remains **156.0.8078.36**. This refresh is intentionally not
accepted by `native_build.py --candidate`; it cannot change the default 148
pin, restart a build or expand manager capability admission. The latest observed
Windows Stable milestone is 157, so successful replay of this patch-line update
does not by itself make it a production target. See the
[test matrix](../../../docs/GLINT_TEST_MATRIX.md).
