# Local-storage checkpoint owner

**Unselected source draft. No C++ type check, compilation or native test execution
is claimed. The active R12 source tree and build recipe are unchanged.**

| Prepared behavior | Contract |
| --- | --- |
| Existing browser-owned connection | Negotiate LocalStorageControl v1; never start a service |
| Completion | Propagate the backend result; legacy Flush is not an acknowledgment |
| Deadline | 30 seconds, including version negotiation |
| Backpressure | 64 wire slots; timeout alone does not release an outstanding RPC |
| Lifecycle | Rebind/shutdown invalidate callbacks; shutdown dooms UI weak pointers before cross-sequence final release |
| Caller delivery | Always posted; queued success rechecks connection and owner generation |

This is a localStorage backend acknowledgment, **not a whole-profile checkpoint**.
It does not fence producers, freeze subsequent writes, coordinate cookies/IDB/cache,
persist session cookies, prove crash durability or guarantee power-loss recovery.

## Evidence

- Three-file isolated application and reversal passed, with exact byte comparison.
- Prepared source formatted with the pinned Chromium clang-format.
- Seven mock-backend fixture bodies prepared: absent connection, success, backend
  failure, timeout/late reply, disconnect, idempotent shutdown and retained wire bounds.
- Host checks validate the artifact and declared scope, not native behavior.
- No full follow-up recipe composition, type check, linking or native execution yet.

Exact source hashes and limitations: [source-observations.json](source-observations.json).
Requires the [R12 recipe](../upstream-156-checkpoint-r12/README.md).

## Before promotion

1. Type-check and run linked fixtures, including old-version negotiation, rebind,
   queued-success invalidation and cross-sequence final release.
2. Compose with the producer cohort without modifying an active build.
3. Define mutation-cut semantics and coordinate network/backend/manager completion.
4. Repeat actual crash-after-ack, compatibility, resources and package/rollback gates.
