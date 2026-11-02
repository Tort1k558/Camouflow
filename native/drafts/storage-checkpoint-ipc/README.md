# localStorage checkpoint IPC and pending-write-load fence

**Unselected source extension. No browser or profile checkpoint is admitted.**

Apply the [database completion prerequisite](../storage-commit-barrier/README.md)
first, then [this patch](storage-checkpoint-ipc.patch). Its seven additional
files implement the service-side path:

| Layer | Prepared behaviour |
| --- | --- |
| Storage area | Wait for previously received write-load tasks; owner loss or abandoned completion returns an error |
| Partition controller | Fence every captured area, then request one database commit completion |
| Privileged IPC | Append `FlushForCheckpoint() => (bool success)` at interface version 1; existing methods stay at version 0 |
| Database replacement | Advance generation on opening, recovery and shutdown; a stale reply cannot acknowledge the new connection |
| Missing persistence | Reject memory-only/unavailable databases instead of claiming a successful disk checkpoint |
| Existing Flush | Original fire-and-forget method body and earlier schema prefix retained |

Completions are posted to the owning sequence. Failed or abandoned area/database
operations fail the aggregate; the prior write-error guard remains in force.
The request has no profile-path selector: it operates on its already bound
privileged partition controller. No renderer-brokered flush method, JavaScript
surface or manager capability is added.

## Evidence

[Source observations](source-observations.json) record two-packet forward/reverse
replay: ten resulting files matched and ten pristine files were restored. This
is **not** a complete future candidate replay. The current R11 recipe, checkout
and runtime remain unchanged.

The actual Mojo parser/generator produced fresh version-1 bindings. Eight C++
syntax/type checks pass with real generated target flags: three implementations,
three native fixture units and two generated binding units. These are not linked
tests or an IPC runtime run.

Twelve new parameterized native case bodies are prepared: pending puts, detached
cache/area loss, asynchronous fencing, empty/memory-only partitions, control-pipe
version and reply, owner loss during open, stale generation, write failure and
two storage keys with bindings kept open. Together with the prerequisite there
are 21 prepared bodies, **none executed by this packet's checks**.

## Not yet covered

The fence starts with writes already received by the storage service. Renderer
messages still in transit and newly created actors/partitions require separate
producer and profile-generation fencing. Cookie write-error completion, browser
control, manager lifecycle/cancellation, linked native tests, crash-after-ack and
guarded package delivery remain unfinished. This does not repair the recorded
[no-checkpoint write losses](../upstream-156-image-r11/crash-recovery-observations.json)
or imply power-loss safety. Older runtimes must not receive the new method without
an explicit version/capability check; no fallback is implemented here.
