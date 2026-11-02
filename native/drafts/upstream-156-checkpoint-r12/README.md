# R12: combined checkpoint prerequisites

## Native execution: first attempt failed, browser repeat passed

[Executed observations](native-attempt-observations.json) retain the failed first
attempt. All six test binaries compiled: 6716 steps in 3h 51m 20.16s, maximum j4,
one link slot. The 85 prepared bodies expand to 107 discovered instances.

| Binary | Observed result |
| --- | --- |
| components_unittests | 42/42 passed |
| content_unittests | 2/2 passed |
| services_unittests | 7/7 passed |
| content_browsertests | Original grouped run aborted; all four pass in separate processes with source/binary postguards |
| net_unittests | 17 executed; three fixture failures remain unresolved by a compiled repeat |
| blink_unittests | Aborted on an illegal mock Mojo callback drop; remaining cases not verified |

Browser tests require a fresh process per case. The corrected runner preserves
the shared per-binary deadline, exact result validation and owned-tree cleanup.
The other diagnosed fixture corrections are prepared, **not compiled/executed**.
SQL trigger injection was ineffective because Chromium disables triggers by
default; the prepared replacement uses a reversible CHECK constraint and checks
that a subsequent valid write persists despite the retained earlier error.

The first following regression did not start: post-link free space was below the
unchanged 180 GiB reserve. After lossless debug-symbol compression, the
[29-group repeat](native-all-observations.json) passed all 586 executions / 429
distinct cases and final postguards. This does not repair the checkpoint fixture
failures. Their complete [R13 correction recipe](../upstream-156-checkpoint-r13/README.md)
still requires a selected build and native execution. Runtime/durability gates remain open.

## Windows build passed

[Compilation and postguards](windows-build.json) passed for the complete
143-patch recipe, maximum j4. Ninja completed **2508 steps in 1h 25m 28.03s**;
the official build stage, including dependency/GN/source/SDK/receipt checks,
took 5574.557 seconds. The receipt binds the exact manifest and all three core
binary hashes.

**Full native verification failed; runtime remains unverified.** These are separate
gates. Never launch from the writable compiler output; use an independently
preserved QA copy after the native phases settle.

## Committed host verification

The [complete host suite](host-observations.json) passed **6037 tests, one skipped**
in 612.219 seconds at commit 369d39f. This is not evidence for later source changes
or any linked Chromium test. The [native case plan](native-case-plan.json) accounts
for all **85 added test bodies** across six native binaries; actual parameter
instances are now discovered; the partial execution above is not a full pass.

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
Browser cases use separate processes and result files; host tests of this runner
do not execute native cases.

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
