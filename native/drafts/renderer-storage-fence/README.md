# Renderer localStorage mutation fence

**Unselected source packet. Not a database commit, browser checkpoint or runtime fix.**

[Patch](renderer-storage-fence.patch) tracks the existing `Put`, `Delete` and
`DeleteAll` replies in Blink's `CachedStorageArea`. It adds no Mojo method or
JavaScript API and does not replace a storage operation with a test-only flush.

| Boundary | Prepared behaviour |
| --- | --- |
| Outstanding writes | Track issued serials and a contiguous acknowledged prefix; out-of-order replies cannot hide a missing earlier reply |
| Rejected Put | Remember failure for the cache lifetime; a later empty fence cannot acknowledge the rejected write |
| Concurrent mutation | A new write before reply delivery invalidates the captured fence |
| Connection | A new generation on reset/rebind rejects old replies; losing unacknowledged writes retains failure |
| Owner loss | Posted replies check the existing cache lifetime without retaining it |
| Missing reply | Require an explicit finite monotonic deadline; a local timer expires pending fences |
| Bounded waiters | At most 256 pending fence requests; overflow fails without discarding existing requests |
| Unsupported scope | Reject unbound areas, sessionStorage and prerender-only storage; no silent binding or fallback |

Existing virtual-time pausers and observer/cache-update semantics are preserved.
`Delete` and `DeleteAll` have void responses: these indicate processing, not SQL
write success. Database errors still require the separate privileged commit path.
The caller must coordinate all producers; a quiet interval in one area is not a
stable snapshot of the entire browser.

## Evidence

[Source observations](source-observations.json) bind pristine Chromium revision,
patch and source hashes. Five isolated packets compose/reverse across **32**
files. The new implementation, native fixture and extended existing mock pass
three C++ syntax/type checks with actual generated target flags.

Fifteen new native case bodies are prepared: empty asynchronous completion,
out-of-order writes, concurrent mutation, rejected Put, unanswered-request expiry,
Delete/DeleteAll, reset/rebind, owner loss, disconnection, queue overflow,
sessionStorage, expired deadline, unbound storage and neighbour-area isolation.
One body is parameterized over the existing local/session fixtures.
**None of these cases was linked or executed by the type checks.**

An earlier draft incorrectly assumed dropping a server responder would settle
the client callback on a live pipe. Source review corrected the contract before
selection: callers now supply deadlines, and the fixture exercises expiration.
The previous preparation/type-check hashes are retained; this was not a measured
runtime failure or a passing linked timeout test.

## Remaining

- Aggregate localStorage namespaces/controller with actor/topology generations.
- Coordinate browser-owned renderer and network producer fences.
- Define session-cookie persistence and capture every owned partition/backend.
- Bind manager capability, cancellation, lifecycle and partial-write semantics.
- Execute linked tests and real IPC, error, timeout/virtual-time and crash-after-ack checks.
- Replay/build the complete candidate and pass resource/package gates.

Local timeouts require a runnable renderer sequence. A frozen renderer or paused
virtual-time scheduler still needs an independent browser/manager deadline.
Timeout alone does not prove a write failed or cancel a remote write; it rejects
the fence request. Late acknowledgments may resolve a later explicit request,
but no automatic retry or failure reset is implemented here.

Canonical R11 sources/runtime, capability admission and recorded no-checkpoint
write-loss results remain unchanged. No whole-profile atomicity or OS power-loss
guarantee is claimed.
