# Restricted-cookie producer drain

**Unselected internal C++ source draft. Not type-checked, compiled or executed.
No Mojo method, Blink integration or working profile-checkpoint capability is
provided by this packet. The active R12 sources and build are unchanged.**

`document.cookie` sends SetCookieFromString without a response. Receiving that
message is not the same as completing CookieStore's asynchronous mutation.
This packet prepares tracking at the actual SetCanonicalCookieAsync dispatch,
shared by accepted string and canonical writes, and completes tracking from the
existing result callback without changing the caller's result.

| Prepared behavior | Boundary |
| --- | --- |
| Per-manager drain | Wait for all recorded CookieStore write callbacks |
| Ordering | Out-of-order completions cannot hide an earlier pending write |
| Posted delivery | New writes or owner destruction invalidate queued success |
| Deadline | 30 seconds; timeout does not forget unfinished mutations |
| Bounds | 64 waiting drains, 4096 tracked writes, checked serial overflow |
| Tracking failure | Fail checkpoint requests closed; preserve ordinary cookie writes |

The drain is **not a database commit**. Policy/parser rejection remains normal
cookie behavior; a drained operation does not mean its cookie was accepted.
It covers one live manager, not other pipes, workers, HTTP response producers,
network requests, session-cookie persistence or a global mutation cut.

## Evidence

- Three prepared packets compose across 11 final files in isolation; reversal
  restores eight exact R12 originals and removes three new files.
- Canonical prerequisite bytes match before and after that check.
- Pinned clang-format applied; no full candidate/GN/type/link checks yet.
- Twelve parameterized fixture bodies prepared, **not executed**. Ten exercise
  bookkeeping through fixture helpers; two also prepare real in-memory
  CookieMonster dispatch/readback checks. None is a real cross-process IPC test.

Exact hashes and prepared cases: [source-observations.json](source-observations.json).
Companion drafts: [producer cohort](../profile-producer-cohort/README.md),
[localStorage owner](../local-storage-checkpoint-owner/README.md).

## Remaining integration

1. Type-check and execute all fixture instances and existing cookie regressions.
2. Add a bounded, versioned producer endpoint and update all implementations;
   capture document/worker manager identity without creating new connections.
3. Define cross-pipe and HTTP producer ordering before backend commit completion.
4. Coordinate the complete profile operation with the manager, then verify actual
   crash-after-ack, resources, compatibility and package/update/rollback behavior.
