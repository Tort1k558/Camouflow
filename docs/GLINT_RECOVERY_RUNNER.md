# Glint: staged Windows installation and recovery helpers

Draft source only. These files are not registered, committed, released or admitted
as a verified Chromium runtime. Keep the protected runtime and profiles unchanged.

| Module | Responsibility | Remaining gate |
| --- | --- | --- |
| `app/core/native/windows_sandbox.py` | Grant Chromium's two installation capabilities read/execute access on an owned verified package stage | Fresh verified R11 copy starts; managed R16 package still needs testing |
| `app/core/native/distribution.py` | Apply the stage-only Windows ACL step after package verification, before publication | Integrate with unchanged update/rollback contracts |
| `scripts/native_checkpoint_process.py` | Atomic job launch, handle-bound membership sampling and shared termination | Current native binary compatibility |
| `scripts/native_checkpoint_contract.py` | Bind the full fixture declarations to the explicit versioned source/case plan | Compiled binary provenance and complete native discovery |
| `scripts/native_checkpoint_crash.py` | Qualify acknowledgement before terminating only the owned job | Real native acknowledged-prefix fixture |
| `scripts/native_checkpoint_recovery.py` | Reopen the same profile in a separate process; verify the exact completed recovery case | Real persistence/crash execution |
| `scripts/native_checkpoint_browser.py` | Run ordinary cases and complete PRE chains with owned-process cleanup | Real native execution of every discovered instance |
| `scripts/native_checkpoint_dispatch.py` | Route the complete browser selection without counting an intentional crash as a gtest PASS | Compiled candidate and source-chain verification by the caller |
| `scripts/verify_native_checkpoint_units.py` | Connect R17 dispatch to existing receipt/SDK/source/binary guards | Publish/register the draft, compile and run the complete candidate |

The recovery API takes the canonical Chromium `source` directory and an explicit
`plan_path`. It does not consume machine-private packet reports. Callers must
separately prove candidate/binary provenance and complete native discovery.
The forced PRE phase is not a completed gtest PASS. The post phase must produce
the exact successful recovery result within the original shared time budget.

Recovery descendants are created inside a kill-on-close job. Before termination,
the runner retains handles to the job's processes and waits for those handles to
signal. It never terminates a PID supplied by the acknowledgement. Cleanup errors
are failures; cancellation propagates after cleanup.

Job membership sampling does not follow global parent-PID links: an unrelated
orphan may retain a parent PID that Windows subsequently reuses. The runner
instead holds handles to exact job members, verifies creation times and requires
the same membership after measurement. Existing resource-tree validation remains
unchanged. There is no post-start assignment or `taskkill` fallback in this protocol.

The publication test overlay contains 94 checks, including actual owned Windows
process/ACL tests and explicit mocked guard checks. Synthetic host child programs
live under `tests/fixtures/glint_checkpoint_host`; they are not browser binaries.

Installation changes only the owned `native-install-*/payload` directory. It uses
the Windows system ACL utility and Chromium's specific installation capabilities,
not broad application-package access, sandbox-disable switches or global policy.
Existing releases, profile permissions and the protected runtime are untouched.

Host protocol tests use Python child processes, not Chromium. Their success does
not establish cookie durability, a whole-profile atomic checkpoint, fingerprint
consistency, CAPTCHA results or production readiness.

Separate real-browser evidence is limited to a fresh R11 installation copy:
269 assets match preserved provenance, startup and exact-job cleanup pass,
the original stays unchanged and the throwaway copy is removed. The R16 browser
has also compiled/linked, but its native/runtime gates have not completed.

R12-R16 execution remains on its existing path; R17 is explicit opt-in only.
R17 is registered only as an explicit build/test candidate, not a selected or
verified manager runtime. Its full
source-derived plan contains 300 declarations across seven test binaries. The
19 browser declarations consist of 18 completed gtests and one separately
qualified forced-termination phase. A successful host simulation is not an
executed Chromium declaration.
