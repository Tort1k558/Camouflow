# Cookie commit completion

**Unselected source prerequisite. Not a browser/profile checkpoint or a runtime fix.**

[Patch](cookie-checkpoint.patch) adds a concrete SQLite cookie-store completion
method without changing the existing void `Flush` method or its base interface.

| Boundary | Prepared behaviour |
| --- | --- |
| Commit | Run the existing before-commit hook and transaction before posting the result |
| Errors | Remember SQL preparation, transaction, add/update/delete, partition serialization and encryption failures |
| Earlier losses | A later empty or successful commit cannot clear the failure |
| Cleanup | Include failed session, partition, noncanonical and administrative deletes |
| Missing persistence | Reject unopened, closed or empty-path stores |
| Ownership | Check a reference-counted atomic closed flag at reply delivery; do not retain the frontend or impose a new destruction sequence |
| Abandoned work | A discarded background task posts failure, not success |
| Compatibility | Legacy Flush body and existing load/backend lifetime remain unchanged |

Replies require a live calling task sequence. Its shutdown may discard delivery;
the future manager must treat missing/expired replies as failure, not successful
checkpoints. The sticky error is conservative for the lifetime of this backend:
there is no automatic retry, error reset or claim that skipped writes were saved.

## Checked

[Source observations](source-observations.json) bind the pristine Chromium 156
revision, source/patch hashes and actual generated-target C++ flags. Both the
implementation and native fixture translation units pass syntax/type checking.
The earlier atomic-construction failure is retained in the evidence.

Forward/reverse replay composes this patch with the
[database prerequisite](../storage-commit-barrier/README.md) and
[localStorage service extension](../storage-checkpoint-ipc/README.md): thirteen
files match after application and return to their exact pristine bytes. Replay
explicitly disables Git's automatic CRLF conversion; it is not a full candidate
replay or a change to global Git configuration.

Nine native case bodies cover asynchronous empty completion, plaintext/encrypted
disk visibility before acknowledgment, frontend loss, unopened persistence,
prior/new SQL errors, encryption failure and abandoned background work.
**They are prepared and type-checked, not linked or executed.**

## Still required

- Validate the [prepared forwarding/IPC extension](../cookie-checkpoint-ipc/README.md)
  through PersistentCookieStore, CookieMonster, cleanup wrappers and CookieManager.
- Establish whole-profile ownership/generation and capability admission beyond that source extension.
- Fence renderer/network producers and capture all owned partitions/actors.
- Bind the manager's lifecycle, cancellation and partial-write semantics.
- Run linked native tests, real error injection and browser crash immediately after acknowledgment.
- Compose/build the complete candidate and pass resource/package gates.

No JavaScript surface, capability advertisement, fallback to void Flush or change
to the registered R11 source/runtime is introduced. The recorded no-checkpoint
cookie/localStorage losses remain unresolved in that runtime. SQL completion is
not a guarantee against OS power loss or faulty storage hardware.
