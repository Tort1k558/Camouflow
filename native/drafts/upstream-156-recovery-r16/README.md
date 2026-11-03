# Glint R16: connected document recovery

**Source preparation. Not a compiled runtime or production admission.**

| Scope | Status |
| --- | --- |
| Complete recipe | 154 unchanged R15 patches + 7 connected follow-up packets |
| Isolated replay / reversal | 161 / 161; 481 final sources, 338 restored originals |
| Native plan | 225 declarations across seven binaries; all 175 R15 bodies retained |
| Cookie owner | Existing connection only; deadline, generation, bounded pending replies |
| Session cookies | Explicit local opt-in; no startup-tab restoration or expiry bypass |
| Document commit | Retained producer cohort, both backends, final lease/topology validation |
| C++ corrections | Out-of-line renderer lifecycle and capturing test callback bindings |
| Composed C++ frontend checks | 13 / 13; style plugin and negative control verified |
| Full native / browser / persistence QA | Pending |

The document-prefix acknowledgment is not a global mutation cut, an atomic snapshot,
or power-loss durability. Worker/HTTP producers, IndexedDB/CacheStorage coordination,
crash-after-ack, real session-cookie restoration and package/update/rollback gates
remain open. No manager feature or fingerprint policy is admitted by this recipe.

The build runner accepts this candidate explicitly; its default remains R12.
C++ frontend checks use composed VFS sources and existing source-set flags; they
do not generate the new build graph, compile objects, link, or execute native tests.
See [cxx-observations.json](cxx-observations.json).
