# Document cookie producer endpoint

**Unselected source preparation. Windows import checks and binding generation
passed; C++ type checks, linking and native execution remain unverified. This is
not a working whole-profile checkpoint. The active
R12 source tree and build recipe are unchanged.**

Requires the [restricted-cookie drain](../restricted-cookie-producer-drain/README.md).

| Prepared source | Boundary |
| --- | --- |
| RestrictedCookieManager v1 | Drain accepted write dispatches on the existing bound manager; no cookie data returned |
| HeapMojoRemote version query | Public forwarding API, without reaching into private binding internals |
| CookieJar drain | Query the existing endpoint before sending; no implicit bind, legacy fallback or JavaScript API |
| Caller completion | Always asynchronous; deadline state survives dropped Mojo replies and Oilpan owner collection |
| Owner identity | Check document activity, connection generation and write epoch through posted delivery |
| Bounds | 64 outstanding wire requests; timeout does not release an in-flight wire slot |
| Connection replacement | Reject unknown earlier write completion; old callbacks cannot decrement new-generation counters |

An unbound jar with no issued writes can report an empty producer prefix without
creating a connection. This says nothing about other cookie producers or disk.
The render-thread timer is not a substitute for the independent browser deadline
when a renderer is frozen or busy.

## Verified scope

- Four follow-up source packets compose across 19 final files in isolation.
  Reversal restores 16 exact canonical prerequisites and removes three new files.
- Official Windows parser/import checks and normal/Blink/shared generators pass:
  18 generated artifacts, 16 transitive modules and 32 measured inputs unchanged
  through completion. Existing six method wire shapes/ordinals remain unchanged;
  the new bool-response method is ordinal 6 at minimum version 1.
- **Binding generation is not C++ type checking, linking, IPC execution or full
  GN/dependency-graph validation.** See [binding-observations.json](binding-observations.json).
- Prepared C++ formatted with the pinned formatter.
- Eight additional native fixture bodies prepared, **not executed**: two network
  pipe cases, two HeapMojoRemote query/reset cases and four document lifecycle/
  deadline cases. Unsupported peers, actual CookieJar IPC/GC, all interface
  implementations and the existing regressions still require native verification.

Exact hashes: [source-observations.json](source-observations.json).
The shared HeapMojoRemote header may invalidate many objects when this packet is
eventually selected. Batch it with the complete follow-up recipe, not a running build.

## Still required

1. C++ type checks, all implementers, linked/native and GC/lifecycle tests.
2. Enumerate document producer cohorts without creating documents or connections;
   integrate the browser-owned aggregate and reject topology changes.
3. Fence worker/CookieStore and HTTP/network producers; define cross-pipe ordering.
4. Coordinate backend commit/session-cookie semantics and manager cancellation.
5. Full candidate build, crash-after-ack, compatibility, resources and package/
   update/rollback verification before admission.
