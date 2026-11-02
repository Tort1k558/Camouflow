# R12: combined checkpoint prerequisites

**Build candidate only. No compiled R12 browser, native execution or runtime
admission is claimed. R11 remains the measured runtime.**

| Evidence | Result |
| --- | --- |
| Complete recipe | R11's 136 patches plus seven checkpoint prerequisites |
| All repositories | 143 patches applied and reversed in an isolated tree |
| Final source comparison | 454 owned files matched |
| Upstream restoration | 319 original files restored; added files removed |
| Active checkout | Not changed by this preparation |
| Build policy | Windows, maximum j4, existing 180 GiB reserve retained |

This combines the database completion, storage-service IPC, cookie completion
and forwarding, renderer mutation/aggregate fences and browser-owned producer
bridge. See the [bridge packet](../browser-storage-fence/README.md) for its
limitations and prerequisite links.

The completed composition is recorded in [preparation.json](preparation.json).
[manifest.json](manifest.json) binds the complete patch sequence, exact upstream
inputs, dependency revisions and seven source packets.

This candidate **does not implement a whole-profile checkpoint**: actor/partition
cohorts, network producer ordering, session-cookie persistence semantics and
manager completion/cancellation remain open. The reproduced R11 last-write losses
are not fixed merely by registering this candidate.

## Next

1. Verify host regressions and preserve the measured R11 runtime/source state.
2. Perform guarded source transition and full GN generation.
3. Build and execute the prepared database, cookie, storage and real IPC cases.
4. Complete whole-profile coordination and manager integration; then repeat
   crash-after-ack and the existing privacy/compatibility/resource/runtime matrix.

Do not use R11 evidence as R12 runtime proof or advertise a checkpoint capability.
