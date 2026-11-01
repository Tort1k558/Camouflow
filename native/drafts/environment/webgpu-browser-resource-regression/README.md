# WebGPU browser resource regressions — unselected diagnostic packet

| Preserved 118-patch R2 fixture | Result |
| --- | --- |
| 1,921 / 2,048 RGBA/BGRA baseline textures | 4 exact baseline cases |
| Same large protected textures | Failed: native capture OOM and device loss |
| Document, same-/cross-origin frames, dedicated/cross-origin/nested workers | 12/12 observations passed |
| Render/copy/storage writes and retained CPU capture | 10/10 cases passed |

The three collector patches are **alternatives**, not a stack. Each extends the
same pinned canonical `scripts/verify_native_webgpu_consistency.py` in a disposable
source tree. Include this packet's fixtures at their declared repository paths;
then run the helper with an explicit candidate, independent receipt-bound runtime,
pinned driver and fresh owned D: work directory. Never patch an active source,
build or previously measured collector. No new Git clone is required.

The portable source differs from the actually measured collector only in its
root/probe path bindings. Exact round-trip reconstruction and isolated Git
apply/reverse passed; the newly rebound source paths have **not** been executed.
Raw results remain hash-bound, without publishing private profile keys or paths.

Cross-context checks validate each realm's own direct/shader/PNG agreement, not
equality between different sites. Worker replies bind nonce, origin, URL and realm;
the cross-origin frame proves denied parent access. This is not a hostile-worker
protocol audit or a proof of cross-site key separation. Mutation checks preserve
the old CPU snapshot, but do not cover every retained GPU consumer or resource
exhaustion. No CAPTCHA, privacy, newest-R3 or production admission is claimed.

## Subsequent portable-source execution

After the preparation snapshot above, all three patches were actually executed
from an exact public Git archive on D:, without another clone. Contexts passed
12 observations and mutation passed 10 cases. Large protected capture reproduced
the same native OOM/device-loss failure on preserved R2; this is an expected
failure control, **not** an all-green browser result. Independent source/runtime
postguards passed at each measurement boundary, patches were reversed afterward,
and no owned runtime/driver processes remained. The earlier preparation JSON is
retained unchanged; `portable-execution-observations.json` binds this later run.
No R3, privacy or production admission follows from these outcomes.
