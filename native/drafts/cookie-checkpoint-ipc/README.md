# Cookie checkpoint forwarding and privileged IPC

**Unselected source extension. No profile checkpoint or runtime repair is admitted.**

Apply the [SQLite cookie completion prerequisite](../cookie-checkpoint/README.md)
before [this patch](cookie-checkpoint-ipc.patch). The storage database and
localStorage packets remain separate prerequisites for the future whole-profile
checkpoint.

| Layer | Prepared behaviour |
| --- | --- |
| CookieStore / PersistentCookieStore | Unsupported implementations explicitly return false asynchronously; never call legacy Flush as a substitute |
| CookieMonster | Wait on the existing global load/task queue, which drains already received per-key mutations before the commit request |
| CookieMonster ownership | Posted reply checks its existing weak lifetime; destruction during loading or a discarded backing callback returns failure |
| Cleanup wrapper | Forward the concrete SQLite result; atomic lifetime marker rejects a reply after wrapper destruction, even if SQLite stays alive |
| CookieManager | Forward completion through an immutable store binding; owner loss or dropped backing completion rejects success |
| Privileged IPC | Append browser-only `FlushCookieStoreForCheckpoint() => (bool success)` at interface version 1 |
| Compatibility | Seventeen old IPC methods remain version 0; existing Flush bodies are unchanged; the existing test stub rejects the unsupported checkpoint |

No renderer-facing cookie API, JavaScript surface, profile-path selector or
checkpoint capability advertisement is added. Clients must check interface
version and the eventual profile capability before calling the new method.

## Evidence

[Source observations](source-observations.json) bind the revision, patch chain,
pristine/composed source hashes and generated binding hashes. Four isolated
packets apply and reverse across **27** files, including the shared SQLite header.
This is not replay of the complete future candidate recipe.

Fourteen C++ translation units pass syntax/type checking with actual generated
target flags: production implementations, existing test-support implementers,
four native fixture units and two fresh generated binding units. Mojo's real
parser/generator produced the version-1 header. **No linked native test or live
IPC request is claimed.**

Fifteen added native case bodies cover:

- memory-only and unsupported backing stores;
- load completion and an earlier host mutation before the commit request;
- success, backing failure and abandoned completion;
- CookieMonster destruction during loading and before a late success;
- cleanup-wrapper disk visibility and destruction with SQLite retained;
- manager lifetime, persistent forwarding, version query and unchanged legacy IPC.

These bodies are prepared and type-checked, **not executed**. The earlier nine
SQLite cases and 21 localStorage/database cases are also still unexecuted by
these source checks. Canonical R11 inputs and the compiled browser remain unchanged.

## Remaining boundary

Only operations already received by the cookie machinery are covered by this
source design. Renderer/network messages still in transit, new actors/partitions,
all other profile stores and the manager lifecycle need a coordinated producer
fence and profile-generation binding. The future protocol must also define which
session cookies are persisted: this method does not silently enable session-cookie
persistence or claim that intentionally memory-only cookies reached disk.

Missing replies after sequence shutdown must fail the manager's request. Partial
commits cannot be treated as atomic whole-profile rollback. Linked tests, real IPC,
SQL/encryption fault injection, crash-after-ack, full candidate/build/resource and
package gates remain required. The recorded no-checkpoint write losses are not
relabelled as fixed, and SQL completion does not promise OS power-loss safety.
