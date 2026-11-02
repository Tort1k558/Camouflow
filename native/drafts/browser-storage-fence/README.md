# Browser-owned localStorage producer fence

**Unselected source preparation. R11 binary and canonical sources are unchanged.**

| Implemented in source | Boundary |
| --- | --- |
| Public Blink facade | Uses the existing storage controller; never creates one to satisfy a fence |
| Dedicated normal Mojo endpoint | Browser-only method at version 1; primordial Renderer protocol unchanged |
| Browser deadline | Independent monotonic timer covers interface negotiation and a hung renderer |
| Lifecycle checks | Captured endpoint generation, weak host lifetime and live process checked before sending and replying |
| Backpressure | At most 64 outstanding wire requests; timeout does not release a still-pending wire slot |
| Failure behavior | Unsupported host, missing endpoint, exit, expired deadline and abandoned callbacks reject without legacy fallback |

This acknowledges renderer producer work only. It does **not** commit databases,
freeze future mutations, enumerate a profile's actors/partitions, fence network
cookie producers, or implement a manager checkpoint.

## Evidence

- Seven isolated packets apply/reverse across **50 files**; both new files are
  removed on reverse. The replay restores captured R11 inputs, not an entirely
  pristine upstream tree.
- Two modified R11 inputs were independently reconstructed by replaying the 99
  root-repository R11 patches filtered to those two paths. This is **not** full
  candidate composition.
- **16 C++ translation units** passed syntax/type checks with fresh bindings.
  The two new generated units use flags from the corresponding existing Renderer
  binding targets; no new Ninja edge or full GN graph is validated by that check.
- Both changed GN files pass formatting. **GN generation, linking and runtime
  execution remain pending.**
- Eight native case bodies are prepared, including four browser tests for live
  producer acknowledgment, expired deadline, renderer exit and a busy renderer.
  **None of these eight tests has been executed.**

Inputs, hashes and exact checked units are recorded in
[source-observations.json](source-observations.json).
Requires the [aggregate fence](../storage-aggregate-fence/README.md) and its
prerequisites. Do not apply this packet to an active build.

## Next gates

1. Stable whole-profile actor/partition cohort and mutation exclusion.
2. Network producer ordering, persistent/session-cookie contract and actual
   backend completion acknowledgments.
3. Manager cancellation, partial-write, shutdown and restart semantics.
4. Complete candidate/GN build, linked native and browser tests, crash-after-ack
   matrix and resource checks before package/update/rollback admission.
