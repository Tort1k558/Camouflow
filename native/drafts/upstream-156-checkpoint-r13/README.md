# R13: fixture-corrected checkpoint candidate

**Registered source recipe; not selected, built or executed.** This preserves the
failed [R12 attempt](../upstream-156-checkpoint-r12/native-attempt-observations.json)
instead of rewriting its recipe or relabelling its results.

| Scope | Prepared result |
| --- | --- |
| Complete recipe | All 143 R12 patches plus one test-only correction packet |
| Isolated replay/reversal | 144 patches, 454 final owned files, 319 restored originals |
| Production source changes from R12 | None |
| Test-only changes | Four files: valid cookie, effective SQL fault injection, legal unanswered Mojo response |
| Native plan | All original 85 bodies retained; actual native discovery/execution pending |
| Build constraints | Windows, maximum j4, unchanged 180 GiB reserve |

The [fixture correction](../checkpoint-native-fixture-fixes/README.md) does not
weaken failure assertions: it also checks later cookie persistence and rejection
of a late Mojo success after timeout. Host SQLite evidence is not a Chromium pass.

Exact recipe: [manifest.json](manifest.json).
Replay evidence: [preparation.json](preparation.json).
Execution contract: [native-case-plan.json](native-case-plan.json).

## Verification sequence

1. Verify/back up the current selected R12 and completed native regression; reject
   live processes and foreign source changes before any transition.
2. Use official candidate stages with fresh manifest-bound receipts and preserve
   mtimes only for byte-identical sources. Do not delete the existing object cache.
3. Build the selected R13 browser and execute the complete native plan:

~~~powershell
.venv\Scripts\python.exe scripts\verify_native_checkpoint_units.py --workspace D:\Glint156Candidate --candidate upstream-156-checkpoint-r13 --report-dir D:\GlintManagerQA\checkpoint-r13-native-run-01 --jobs 4
~~~

4. Repeat all 29 regression groups, then preserve an independent QA runtime and
   run source-runtime, compatibility, resources and crash-after-ack checks.

This candidate does not include the unselected producer-cohort, localStorage-owner
or document-cookie follow-up drafts. Those remain required development work, not
completed checkpoint functionality. No whole-profile durability, privacy, package
or production admission follows from this test-only recipe.
