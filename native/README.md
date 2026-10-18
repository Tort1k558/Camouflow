# Glint

CamouFlow's independent Chromium-based development engine. It is not a
Camoufox/CloakBrowser rename or a JavaScript fingerprint wrapper.

- [Build on Windows](BUILDING.md)
- [Architecture](ARCHITECTURE.md)
- [Status and limitations](../docs/NATIVE_ENGINE.md)
- [Verification requirements](../docs/NATIVE_VERIFICATION.md)
- [External test sites and per-build results](../docs/GLINT_TEST_MATRIX.md)
- [Development plan and continuation prompt (Russian)](../docs/GLINT_ROADMAP.ru.md)

## Verified status

**Development engine, not a signed release.** Results belong to the stated
patch chain; they do not transfer automatically to newer binaries.

| Layer | Patch chain | Evidence and boundary |
| --- | --- | --- |
| Registered Windows source | 001-062 | Runtime/branding verified; selected controls enabled experimentally for one reviewed local package. General fork admission remains closed |
| Native identity keys/service | 001-059 | **62/62** passed, repeating the 001-058 result: 19 new derivation/mode cases and 43 legacy checks; unchanged browser core/GN/receipt |
| Native identity contexts/transport | 001-059 | **37/37 + 20/20** passed in the linked Chromium content target; not a linked identity-mode browser or renderer delivery proof |
| Native identity handoff | 001-059 | **15/15** Blink cases passed: 12 document cases across four modes and three worker-thread cases; not a linked identity-mode browser |
| Native navigation/readiness | 001-045 | **42/42** cases passed: missing/conflicting policy, late policy loss, recovery and observer-driven closure |
| Native BrowserContext isolation | 001-045 | **26/26** cases passed |
| Native window/child transport | 001-045 | **13/13** cases passed |
| Native worker surfaces | 001-045 | **55/55** cases passed |
| Native bounded/clipped readback | 001-048 | **31/31** cases passed: pack copy 14, region planner 11, clipped publication 6; browser core 001-047 remained unchanged |
| Identity/GPU package | Registered 0049-0058 | **22 identity + six GPU C++ units** type-checked before integration; native selections and initial combined runtime runs now passed. Product capability admission remains closed |
| GPU metadata codec | Registered 0055 | **14/14** actual codec fixtures executed with standalone MSVC/GoogleTest; not GN decoder/attachment execution or browser admission |
| Native GPU metadata | 001-058 | **33/33** Chromium `gpu_unittests` cases passed: codec 14, passthrough protocol 5, attachment 14. Not validating-decoder, WebGPU or browser readback admission |
| Windows font rendering policy | 001-062 | **5/5** Chromium units and standalone/combined rendering comparisons passed; raw/HDR controls retained. Experimental reviewed-package activation, not five distinct identities |
| Current linked Windows candidate | 001-062 | Incremental j4 build succeeded in **29m02s**, 52 executed steps; separate runnable 001-061 rollback copy retained |
| Windows development package | 001-062 | 261 checksummed files, 220.95 MiB archive; installed-copy **160/160** and same-Chromium rollback passed. Selected controls have experimental local admission; artifact remains unsigned |
| Complete eight-gate runtime suite | 001-062 | **160 checks passed** in continuation v2; first-run font NetworkError remains unexplained and recorded |
| Compiled branding | 001-062 | Main/app-list icons, ProductName and version-page Glint logo/name verified; not cached taskbar/shortcut migration or every UI screen |
| Combined identity and privacy surfaces | 001-059 | Profile-identity and partitioned-privacy each passed **12/12 phases + 24 nested Canvas cases** with concurrent profiles, restart and WebGL readback; not WebGPU protection or third-party anti-bot acceptance |
| Worker startup/restart | 001-047 | Default **40/40**; extended **60/60**, including 20 nested classic/module cases |
| Combined Canvas/OfflineAudio | 001-047 | **Three consecutive 7/7 runs passed** on unchanged core; historical 001-045 profile-B timeout remains unexplained |
| Nested worker Canvas | 001-047 | **24/24** first-script/repeat/restart cases passed alongside all seven combined phases |
| Strict HTTP/JS Client Hints | 001-047 | **18/18** checks passed: eight strict document/frame comparisons, six worker JS checks, four invalid-UA rejections; worker HTTP hints and TLS are not covered |
| Protected WebGL readback | 001-047 | **Six phases passed**, including clipped CPU/PBO reads, state/errors, exports, restart and profile isolation; wider admission remains blocked |
| Linux/macOS | Deferred | No current own-fork runtime admission |
| Mobile Web | Emulation | Desktop viewport/touch mode, not Android/iOS |

The four native groups total **136 passing cases** on the same test binary.
Raw Gtest results and guarded proof reports remain outside public source:
`surface-navigation-001-045-v6`, `contexts-001-045-v1`,
`window-transport-001-045-v1` and `worker-surfaces-001-045-v1` on D:.
These are C++ fixtures, not CAPTCHA or external anti-bot results.

The 001-047 runtime gate covers persistent storage, concurrent-profile locks,
crash/restart recovery, permissions, an owned authenticated HTTP proxy,
scenarios, Recorder and Mobile Web Emulation. All eight suite gates passed.
The combined surface gate covers consistency
after restart, cross-profile isolation and exact missing-policy document
abort without commit or script execution.

Evidence on D: `browser-verification-001-045-v1/suite/suite.json`,
`browser-verification-001-045-v1/worker-startup.json` and
`combined-surfaces-001-045-v2.json` and `combined-surfaces-001-045-v3.json`.
Protected GPU failure: `gpu-readback-001-045-v1.json`. The initial combined timeout remains
recorded in `browser-verification-001-045-v1/surfaces.json`; a passing retry
does not prove the intermittent failure is fixed.

All four owned 001-047 browser gates passed on one measured EXE/DLL core:
`browser-verification-001-047-v1/verification.json`. The extended worker run
also passed all 60 cases: `worker-nested-001-047-v1.json`. The older failed
runs remain recorded. Combined surface repeats also passed:
`combined-surfaces-001-047-v2.json` and `combined-surfaces-001-047-v3.json`.
Both completed cleanup; passing repeats do not establish the old timeout's cause.
The nested Canvas extension also passed: all seven phases and 24 parent/child
cases in `combined-surfaces-nested-001-047-v4.json`, with unchanged core and no
cleanup error. Strict Client Hints passed all 18 checks in
`identity-strict-001-047-v2.json`; cross-origin delegation is explicit and limited
to the owned fixture. Neither result admits the future profile-identity mode.
The 31-case native readback gate passed on 001-048 with zero failed, disabled or
error cases: `gpu-readback-units-001-048-v2.json` and its raw `-tests.json` on D.
The j4 retry retained cached objects and completed the test-target build in **1h30m44.64s**, 654 executed
steps; selected tests ran in 176 ms. Source, GN, receipt and all browser core
hashes remained unchanged. Test EXE SHA-256:
`44ac3b7c8e178db08130c62762e323e73077af6f4b9b7e30f5c47bebfb0c90c0`.
The first build's LLVM OOM and initial typed-result preflight failures remain
recorded. These native byte-copy/planning cases do not prove GPU-driver,
WebGPU, future identity mode or third-party acceptance.

## Source layout

| Directory/file | Purpose |
| --- | --- |
| `patches/` | Registered, ordered Chromium/V8 patch chain |
| `core/` | Shared C++ policy primitives |
| `windows/` | Windows font-policy source |
| `tests/` | Native policy fixtures and tests |
| `branding/` | Source assets/replay instructions for registered product/logo and scaled UI patches 0060–0061 |
| `drafts/` | Canonical candidates, unregistered integration patches and explicit proof boundaries |
| `build/`, `toolchain/` | Build/toolchain support source |
| `build-lock.json` | Pinned upstream revisions and build limits |
| `args.gn` | Development Chromium build configuration |

Chromium, tool downloads, cache and binaries belong in an external workspace
on D:, not this Git repository. The historical `D:\CamouFlowNative` and
`out/CamouFlowNative` names remain technical paths, not product branding.
Private backend source is excluded from public Git.

## Development boundary

Registered patches 0031-0034 introduce browser-owned document/worker surface
policy, startup/child transport, Canvas/OfflineAudio modules and partial
native WebGL readback. Follow-ups 0035-0045 repair compilation, cancellation,
throttle registration and fixture lifetimes. Native tests are passing;
the current browser chain passes its ordinary runtime suite, but combined
surface repeatability and remaining GPU gates are required before enabling
capabilities or publishing a release.

Patches 0046/0047 promote the bounded-halo and clipped-publication pair together.
Their exact source replay passed without changing the 001-045 runtime core.
The `gpu-readback` native gate requires all 31 pack-copy, region and clipped-copy
fixtures; execution is pending. Source registration alone does not repair the
already linked browser or enable a verified capability.

Next coherent candidates: [profile policy](drafts/policy/README.md),
[GPU metadata](drafts/gpu/README.md), [offline Audio](drafts/audio/README.md)
and [bounded WebGL readback](drafts/next-readback/README.md).
Draft replay, generated bindings and translation-unit checks do not prove
linked execution or GPU-driver correctness.

Manager diagnostics observe HTTP/JavaScript identity consistency, WebGPU
adapter availability/features/limits and screen geometry in owned pages.
Observation is not spoofing, TLS validation or WebGPU readback protection.
Only capabilities verified against the actual binary may be enabled.

No guaranteed CAPTCHA acceptance, CDP invisibility or third-party PASS is
advertised. External observations belong in the
[per-build test matrix](../docs/GLINT_TEST_MATRIX.md). Durable contracts live
in architecture docs; released changes belong in the [changelog](../CHANGELOG.md).
