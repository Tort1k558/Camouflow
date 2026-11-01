# Offline Audio completion ownership

**Unselected R7 patch; no browser build or runtime admission.**

The completion resolver is claimed before callbacks. The captured partition seed
is erased before dispatch, rejection or detachment; late completion cannot publish
an unprotected buffer after teardown. A scoped owner also erases temporary seed
captures when allocation or budget checks fail. Event and promise retain the same
mutable output buffer, including changes made by an event listener.

Four proposed Blink tests cover reject, detach, missing destination and completion
callbacks (normal, teardown and reentrant completion). The existing copy-budget
test additionally checks that no seed or resolver survives rejection.

`next.patch` applies to the exact R7 preimages in `packet.json`. Its three files
are disjoint from [masker cleanup](../audio-masker-cleanup/README.md), which erases
the derived masker state. Apply both packets in the next candidate, not to an
active build tree. Neither changes the sample algorithm or repairs the remaining
Legacy Audio analyser/worklet discrepancy.

Compilation checks are not execution of the proposed native tests. Integrated
native tests and browser lifecycle/readback regression gates remain required.

## Measured preparation

[Bound observations](observations.json): both packets applied and reversed in
disposable copies, restoring all six exact preimages. All four implementation/test
translation units passed Clang syntax checks with their actual generated GN flags,
including Chromium plugins and existing module dependencies. The VFS overlay left
canonical source files unchanged; input postguards passed. No warnings were
disabled. This does not execute native GTests or produce a browser binary.
