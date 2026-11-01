# Scoped index preparation: R8 source pin

**Unselected. The active builder, Chromium sources and build arguments are unchanged.**

This refresh binds the [existing scoped/bulk index packet](../scoped-patch-index/README.md)
to the registered R8 builder. The patch and checker are byte-identical to their
predecessors; only the source/candidate pins and preparation evidence change.

Detached apply/reverse restored the exact current builder bytes and the proposed
Python source parsed successfully. [Preparation](preparation.json) does **not**
claim the checker, full R8 recipe replay or a native build was executed. The old
1171-test/R7-recipe evidence belongs to the predecessor, not this source version.

## Reproduce before integration

Run only after native/browser jobs are idle to avoid contending with Chromium on
the same HDD. Use a fresh canonical D: directory:

```powershell
.venv\Scripts\python.exe -B native/drafts/scoped-patch-index-r8/check.py `
  --work-dir D:\GlintManagerQA\scoped-index-r8-check-new
```

The checker refuses a changed builder, patch or test pin. It prepares only a
detached D: copy and runs the existing real-Git tests. Before adoption, also replay
the complete 131-patch R8 recipe with unrelated-file/index guards and measure the
actual source-operation cost. Preserve the immutable R7 packet and an exact host
source archive when integrating the R8 version.

The change batches index seeding and limits the temporary patch index to owned
paths. It does not remove the full foreign-change check, cache source hashes,
trust timestamps, skip compiler work or lower resource limits. Any benefit is to
source verification/preparation; **C++ compilation speedup is not established**.
