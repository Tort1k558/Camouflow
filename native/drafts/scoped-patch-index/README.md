# Scoped patch preparation

**Unselected builder draft. The running R7 builder is unchanged.**

The candidate applicator currently prepares a full Chromium Git index before
applying each repository's patch chain. This draft seeds only the owned paths,
feeds validated `ls-tree` entries to `update-index --index-info` in one batch,
and restricts the binary delta to those explicit paths.

The existing revision, clean-tree, manifest, complete-chain, concurrent-edit and
rollback guards remain. No source-hash cache, timestamp shortcut, resource-limit
reduction, native compilation skip or dependency-stage bypass is introduced.

| Check | Measured result |
| --- | --- |
| Public detached host checker | 1171 passed, 1 skipped; input postguards passed |
| Synthetic complete R7 recipe | 129 patches; 400 final files matched; 270 restored |
| Real fixture indices / unrelated files | Preserved; 192 unrelated files unchanged |
| Active builder / native speed | Unchanged / not measured |

[Host observations](observations.json) and
[synthetic recipe observations](recipe-observations.json) remain separate evidence.

## Check

From the project root, with the exact source and test pins in [packet.json](packet.json):

```powershell
.\.venv\Scripts\python.exe -B native/drafts/scoped-patch-index/check.py --work-dir D:\GlintManagerQA\scoped-index-public-check
```

Use a fresh directory. The checker patches only a detached D: copy and runs the
existing real-Git net-path and release-tool tests with input postguards. It refuses
changed inputs rather than adapting the patch to an unmeasured builder version.

The full-recipe diagnostic additionally uses independent synthetic Git commits,
the exact 129 public R7 patches and pinned upstream bytes. It compares 400 final
owned files, preserves unrelated files and real indices, and restores 270 upstream
files. This is a source-operation check, not a Chromium build or runtime result.

An observed full Chromium temporary index was 74,190,906 bytes; the scoped R7
fixture's root index was about 41 KB. These are **not elapsed-time benchmarks**.
Native compilation, GN generation and Siso dependency scanning are separate costs.
Do not claim an end-to-end speedup before integrating and measuring the draft.
