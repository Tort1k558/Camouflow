# Storage commit-completion prerequisite

**Source prepared and type-checked. Not a working profile checkpoint.**

The separate [service IPC extension](../storage-checkpoint-ipc/README.md) now
prepares pending-write-load fences and versioned privileged completion. It remains
unselected; producer, cookie, browser/manager and runtime admission work is open.

The [three-file patch](storage-commit-barrier.patch) adds
`AsyncDomStorageDatabase::CommitPendingMaps(callback)` without changing the
existing `InitiateCommit()` interface. It collects available map batches, waits
for their database task and notifies existing committers before posting the
completion result to the caller's sequence.

| Invariant | Implementation |
| --- | --- |
| No false success after owner loss | Weak ownership checked when delivering the posted result |
| Abandoned/migration-queued operation | Dropped completion produces an error, not success |
| Earlier failed write | Sticky error; a later successful or empty batch cannot erase it |
| Memory-only/unopened database | Explicit rejection, no persistence fallback |
| Existing callers | Same interface and per-batch committer statuses retained |

## Evidence

[Source observations](source-observations.json) bind the exact R11 base, three
pristine upstream inputs, patch and resulting source hashes. Forward/reverse
application passes in isolated copies. Two translation units, implementation
and native fixtures, pass syntax/type checks using the actual generated Windows
target flags and an overlay. Canonical sources and runtime remain unchanged.
The initial nodiscard compile failure is retained; warnings-as-errors were not
relaxed.

Nine new parameterized native cases are **prepared, not linked or executed**:
loaded-map completion ordering, asynchronous empty batches, memory/unopened
rejection, owner destruction, destruction from a committer callback, prior/new
write errors and neighbour-database isolation. Fault controls use the existing
fake database; the packet does not claim execution against either real backend.

## Required remainder

This fence covers currently collectable database batches. It does **not** fence
renderer IPC, pending map loads, other storage partitions or future concurrent
writes. It is not an fsync/power-loss guarantee and does not repair the measured
[uncheckpointed browser losses](../upstream-156-image-r11/crash-recovery-observations.json).

Next connected work must include:

1. Producer and pending-load fences before collecting partition commits.
2. Acknowledged privileged IPC with profile/partition ownership and teardown errors.
3. Cookie commit status: the existing void flush completion alone cannot report
   a failed write as an error.
4. Browser-level checkpoint, partial-result/cancellation semantics and manager
   capability binding; no web-visible JavaScript API or older-runtime fallback.
5. Linked native tests, crash-after-ack and cross-profile runtime checks, complete
   candidate composition/build and package acceptance.

No new candidate is registered or admitted by this packet.
