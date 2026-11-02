# Checkpoint native fixture corrections

**Unselected test-only source correction. Not compiled or executed in Chromium.
The active R12 source tree and compiled binaries are unchanged.**

These changes address fixture defects found by the
[actual R12 execution](../upstream-156-checkpoint-r12/native-attempt-observations.json),
not a demonstrated fix to production checkpoint logic.

| Observed fixture issue | Prepared correction |
| --- | --- |
| Host-write cookie rejected before reaching the store | Use a valid HTTP Lax cookie, retaining the accepted-write/store-order assertions |
| Trigger fault injection never fires | Use a reversible CHECK constraint; retain failed-checkpoint assertions and verify a later valid cookie really persists after constraint removal |
| Connected Mojo response callback illegally destroyed | Keep the callback pending through timeout, deliver it late, and verify timeout cannot become success; remove the unused unsafe drop helper |

## Verified scope

- Four-file isolated application/reversal restores the exact original bytes.
- All existing test-case declarations remain unchanged; no cases are removed,
  disabled or skipped, and expected failure assertions remain.
- A **host SQLite 3.42.0 probe**, with triggers explicitly disabled, reproduces
  trigger bypass, CHECK rejection and a valid write after dropping the guard.
  **This is not Chromium SQLite execution or checkpoint-error propagation.**
- Source formatted only in changed ranges with the pinned formatter.

Exact hashes: [source-observations.json](source-observations.json).

## Before selection

1. Compose a complete registered candidate without rewriting the recorded R12
   recipe or its failed attempt; preserve all 85 bodies and discovered instances.
2. Rebuild affected native targets and execute the complete checkpoint plan,
   including existing cookie/storage regression and the isolated browser cases.
3. Diagnose any remaining actual failures before runtime or durability admission.
