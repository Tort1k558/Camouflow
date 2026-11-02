# Renderer localStorage aggregation

**Unselected source extension. No browser/profile checkpoint or runtime repair is admitted.**

Apply the [area fence](../renderer-storage-fence/README.md) before
[this patch](storage-aggregate-fence.patch). The cookie and localStorage database
completion packets remain separate parts of the future checkpoint chain.

| Layer | Prepared behaviour |
| --- | --- |
| StorageNamespace | Wait for every captured localStorage area's existing mutation fence |
| Aggregate epoch | Include locally issued mutations, area creation/removal and connection resets; recheck at posted reply delivery |
| Early area completion | A later mutation in an already completed area invalidates the whole aggregate |
| Eviction | Keep unused areas with unacknowledged writes or pending fences; do not silently forget their in-flight work |
| Failed eviction | Retain a namespace failure marker when an unused failed area is removed |
| StorageController | Fence the existing localStorage namespace; recheck controller lifetime, namespace identity and both generations |
| Empty producer set | Complete asynchronously without creating a namespace; this says nothing about disk persistence |
| Bounds | Require a finite caller deadline; each namespace/controller admits at most 64 in-flight requests |
| Unsupported scope | SessionStorage namespaces reject this localStorage-only operation |

Area callbacks remain weak, so snapshots do not pin otherwise unused caches.
Namespace callbacks use Oilpan weak roots; controller callbacks use its weak
lifetime. Neither late success nor an equal area count after remove/recreate can
acknowledge a different cohort. Changes originating outside this renderer still
need their own browser/network coordination; the epoch is not a database revision.

## Evidence

[Source observations](source-observations.json) bind the pristine inputs and shared
area-header/implementation transition. Six isolated packets apply/reverse across
**37** files. This is not replay of the complete future browser candidate.

Seven C++ syntax/type checks pass with actual generated target flags: three
implementations, the extended mock and three native fixture translation units.
Seventeen added native case bodies cover empty scope, two-area ordering, mutations
after early completion, topology changes, pending-write eviction, failure retention,
reset, session rejection, deadline validation, queue limits, controller lifetime,
namespace creation and reset through the real DomStorageClient pipe.

**The fixtures were prepared/type-checked, not linked or executed.** The real-pipe
case is a prepared test, not a measured runtime result. Canonical R11 sources,
compiled browser and recorded no-checkpoint losses remain unchanged.

## Remaining

- Public Blink facade and browser-owned renderer/actor coordination.
- Network producers, session-cookie contract and all owned partition/backends.
- Whole-profile protocol and manager capability/lifecycle/cancellation binding.
- Linked native checks: weak GC roots, timeouts/virtual time, actual pipes, eviction/backpressure and crash-after-ack.
- Complete candidate/build, resource and package admission.

Retaining stalled unused caches needs resource/backpressure validation. Local
deadlines cannot settle a frozen renderer; the browser needs an independent
timeout. These fences neither commit databases nor promise an atomic snapshot,
rollback of partial commits or OS power-loss safety.
