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
| Registered Windows source | 001-048 | Ordered replay passed across 130 paths; 0048 changes only native test fixtures |
| Native navigation/readiness | 001-045 | **42/42** cases passed: missing/conflicting policy, late policy loss, recovery and observer-driven closure |
| Native BrowserContext isolation | 001-045 | **26/26** cases passed |
| Native window/child transport | 001-045 | **13/13** cases passed |
| Native worker surfaces | 001-045 | **55/55** cases passed |
| Current linked Windows candidate | 001-047 | Corrected incremental j4 build succeeded in **12m46s** |
| Complete eight-gate runtime suite | 001-047 | **160 checks passed** on unchanged runtime core |
| Worker startup/restart | 001-047 | Default **40/40**; extended **60/60**, including 20 nested classic/module cases |
| Combined Canvas/OfflineAudio | 001-047 | **Three consecutive 7/7 runs passed** on unchanged core; historical 001-045 profile-B timeout remains unexplained |
| Nested worker Canvas | Prepared | Optional 24-case first-script/repeat/restart probe; no linked-runtime result yet |
| Protected WebGL readback | 001-047 | **Six phases passed**, including clipped CPU/PBO reads, state/errors, exports, restart and profile isolation; wider admission remains blocked |
| Branding | Prepared | Product/logo patch not applied to verified binary |
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
The 31-case native readback gate is still unexecuted:
its first full test-binary build stopped after 302 steps with LLVM out-of-memory
in upstream `style_scope_test.cc`. The retry retains cached objects and `j4`,
without a concurrent candidate C++ checker.
its initial C++ preflight found typed-result errors in pack-copy and region
fixtures. Fixture-only patch 0048 preserves every case and checks `.has_value()`
explicitly. All three fixture translation units now pass actual-target C++
checks (`readback-fixture-cpp-001-048-v2/proof.json` on D); linkage and execution
are still required. Browser checks are not substitutes for native tests.

## Source layout

| Directory/file | Purpose |
| --- | --- |
| `patches/` | Registered, ordered Chromium/V8 patch chain |
| `core/` | Shared C++ policy primitives |
| `windows/` | Windows font-policy source |
| `tests/` | Native policy fixtures and tests |
| `branding/` | Prepared Glint product/logo patch, not applied |
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
