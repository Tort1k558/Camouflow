# R12: combined checkpoint prerequisites

## Windows build passed

[Compilation and postguards](windows-build.json) passed for the complete
143-patch recipe, maximum j4. Ninja completed **2508 steps in 1h 25m 28.03s**;
the official build stage, including dependency/GN/source/SDK/receipt checks,
took 5574.557 seconds. The receipt binds the exact manifest and all three core
binary hashes.

**Native tests and runtime are not yet verified.** Their builds/runs are separate
gates. Never launch from the writable compiler output; use an independently
preserved QA copy after the native phases settle.

## Committed host verification

The [complete host suite](host-observations.json) passed **6037 tests, one skipped**
in 612.219 seconds at commit 369d39f. This is not evidence for later source changes
or any linked Chromium test. The [native case plan](native-case-plan.json) accounts
for all **85 added test bodies** across six native binaries; actual parameter
instances and execution remain unverified.

## Native runner

After a successful R12 browser build, use the checkpoint runner with a **fresh**
report directory on D:

~~~powershell
.venv\Scripts\python.exe scripts\verify_native_checkpoint_units.py --workspace D:\Glint156Candidate --report-dir D:\GlintManagerQA\checkpoint-r12-native-run-01 --jobs 4
~~~

It builds all six executables in one invocation, discovers actual parameter
instances, rejects missing/disabled/duplicate cases and validates exact successful
results. It refuses an old browser receipt, a live builder or altered source/SDK/
GN/runtime inputs. Test deadlines terminate only that invocation's owned process
tree. Per-binary failures are retained while the other built binaries are checked.
Preparing or testing this Python runner does not execute any native case.

**R12 compiled; native and runtime verification pending. R11 remains the last
measured runtime. No checkpoint, privacy or release admission is claimed.**

| Evidence | Result |
| --- | --- |
| Complete recipe | R11's 136 patches plus seven checkpoint prerequisites |
| All repositories | 143 patches applied and reversed in an isolated tree |
| Final source comparison | 454 owned files matched |
| Upstream restoration | 319 original files restored; added files removed |
| Active checkout | Transitioned to all 143 R12 patches; 454 owned source hashes matched |
| Windows build | Passed compile/link and postguards; native execution/runtime pending |
| Build policy | Windows, maximum j4, existing 180 GiB reserve retained |

This combines the database completion, storage-service IPC, cookie completion
and forwarding, renderer mutation/aggregate fences and browser-owned producer
bridge. See the [bridge packet](../browser-storage-fence/README.md) for its
limitations and prerequisite links.

The [source transition](source-transition-observations.json) completed sync,
hooks and patch stages. All 269 preserved R11 runtime assets were verified.
Fifty source files changed; 381 byte-identical files regained their original
timestamps. That source-only record does not establish compilation; the later
Windows build record above provides its separate evidence.

The completed composition is recorded in [preparation.json](preparation.json).
[manifest.json](manifest.json) binds the complete patch sequence, exact upstream
inputs, dependency revisions and seven source packets.

This candidate **does not implement a whole-profile checkpoint**: actor/partition
cohorts, network producer ordering, session-cookie persistence semantics and
manager completion/cancellation remain open. The reproduced R11 last-write losses
are not fixed merely by registering this candidate.

## Next

1. Host regressions and R11 preservation passed for the recorded inputs.
2. Guarded source transition, GN generation and Windows compilation passed.
3. Build and execute the prepared database, cookie, storage and real IPC cases.
4. Complete whole-profile coordination and manager integration; then repeat
   crash-after-ack and the existing privacy/compatibility/resource/runtime matrix.

Do not use R11 evidence as R12 runtime proof or advertise a checkpoint capability.
