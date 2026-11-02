# Profile producer cohort

**Unselected source draft. No C++ type check, compilation, native execution or
runtime verification is claimed. The live R12 build and recipe are unchanged.**

| Prepared source | Boundary |
| --- | --- |
| BrowserContext scope | Weak owner; rejects shutdown, off-the-record and unready renderers |
| Producer set | Existing R12 per-renderer IPC; no process or partition startup |
| Loaded partitions | Value-only complete configurations, including blob fallback mode |
| Lifecycle | Renderer creation/launch/exit and final cohort changes reject success |
| Completion | Posted callback, independent deadline and asynchronous cancellation |
| Bounds | 512 renderers and 128 loaded partitions |

An acknowledgment covers the captured producers only. It **does not freeze later
writes or establish a global cut**, flush databases/network producers, persist
session cookies or implement a whole-profile checkpoint. Empty producer success
is not evidence that any data reached disk.

## Evidence

- Five-file isolated apply/reverse passed; three new files are removed on reverse.
- Both modified R12 GN inputs were reconstructed by replaying the 106 root patches
  filtered to those two paths. This is not full follow-up candidate composition.
- Both changed GN files parse with the pinned GN executable. **Parsing is not GN
  generation, target/dependency validation, C++ type checking or linking.**
- Twenty fixture bodies are prepared using TestBrowserContext and mock renderer
  hosts. **They have not been compiled or executed; they are not real IPC tests.**
  These include a new loaded partition before posted completion, renderer exit
  followed by a late acknowledgment, and rejection of 513 actors before any RPC.

Exact hashes and remaining gates:
[source-observations.json](source-observations.json).
Requires the complete [R12 recipe](../upstream-156-checkpoint-r12/README.md).
Do not apply this draft during the active build.

## Before promotion

1. C++ checks, linked fixtures, partition topology/bounds/restart cases and actual
   cross-process browser coverage.
2. Explicit global-cut/mutation semantics and network producer ordering.
3. Versioned backend completion, session-cookie contract and manager cancellation/
   partial-write handling.
4. Complete recipe/build, crash-after-ack, resources and package/update/rollback gates.
