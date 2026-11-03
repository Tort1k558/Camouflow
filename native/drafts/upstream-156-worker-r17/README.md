# Glint R17: connected worker-cookie recovery

**Explicit build/test candidate only. Not selected, compiled or admitted.**

| Component | Evidence / limit |
| --- | --- |
| Recipe | 161 unchanged R16 patches + 15 connected source packets |
| Git-index replay / reversal | 176 / 176; 506 final sources, 351 restored originals |
| Native plan | 300 declarations; all 225 R16 declarations retained |
| CookieStore | Existing document/worker owners, bounded requests and deadlines |
| Worker coordinator | Captured run identity, retained cohort and keepalive cleanup |
| Profile commit | Explicit document + worker-cookie prefix, no narrower fallback |
| Browser checks | Clean restart, explicit acknowledged crash, lifecycle negatives |
| Complete C++ / native / browser checks | Pending |

The exact expected-crash pair must use the explicit source-bound owned-process
controller; its forced phase is not a completed gtest PASS. Ordinary PRE/post
chains need a separate fresh shared profile per chain. The native runner requires receipt-verified discovery and dispatch before this
plan can execute. Its portable host checks are not Chromium execution.

No global mutation cut, HTTP producer fence, IndexedDB/CacheStorage coordination,
whole-profile atomicity, power-loss durability or fingerprint/release admission
is implied. Existing R16 selection and measured R11 remain unchanged.

## Runner and supporting evidence

The registered draft keeps all 300 source declarations. Its explicit browser
dispatcher separates 18 completed gtests from one qualified forced-termination
phase; ordinary PRE chains use their own fresh shared profiles. Existing R12-R16
paths and the default are unchanged. Registration does not apply the recipe to
the canonical checkout or enable it in the desktop manager.

[Scoped observations](runner-observations.json) distinguish host checks, a real
fresh R11 installation probe and the separately successful R16 Windows build.
No R17 C++/native/runtime or whole-profile recovery admission follows from them.
