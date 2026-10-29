# Chromium 156.0.8078.75 source replay

**Prepared input manifest, not a build candidate or released browser.**

This snapshot pins Chromium `861389936bf33ea77529ee5dcc0605e68f6bb620`
and its DEPS-selected V8 `235050a0df6db2c9d92a419af2b72fbf3b2dd73b`.
All 185 pristine input files and all 62 patch hashes are recorded in
`manifest.json`. Patch bytes are reused from `../upstream-156/patches`, not
duplicated here. `base_manifest_sha256` binds that original snapshot.

## Reproduce

Provide the 185 pristine files at their manifest-relative paths. Their immutable
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
