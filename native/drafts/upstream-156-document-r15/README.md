# Glint R15: document producer batch

**Registered source preparation, not a compiled or admitted runtime.**

| Scope | Evidence |
| --- | --- |
| Complete recipe | 152 unchanged R14 patches plus 2 follow-up packets |
| Isolated replay / reversal | 154 / 154; 471 final sources, 332 restored originals |
| Native plan | 175 prepared bodies: all 163 from R14 plus 12 additional cases |
| Document producer scope | LocalStorage, cookies or both; one deadline, reject either producer failure |
| Include correction | Corrected CookieJar translation unit compiled separately with the failed R14 CXX flags |
| Full C++ / native / runtime | Pending; no production admission |

R14 stopped after 851 completed actions because CookieJar accessed the forward-declared
MainThread type without including its definition. R15 adds the missing header;
it does not remove the thread checks or erase the failed build result.

The combined producer acknowledgment is **not an atomic whole-profile snapshot**.
Global mutation coordination, worker/HTTP producers, backend and session-cookie
persistence, crash-after-ack, resource and package/update/rollback gates remain open.
Existing localStorage-only callers retain their explicit legacy behavior; a
requested cookie fence never falls back to a localStorage-only acknowledgment.

See [preparation.json](preparation.json), [native-case-plan.json](native-case-plan.json)
and [manifest.json](manifest.json). Compile and execute the complete candidate
before claiming browser behavior or enabling checkpoint support.
