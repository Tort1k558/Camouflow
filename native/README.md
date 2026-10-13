# Glint

CamouFlow's independent Chromium-based development engine. It is not a
Camoufox/CloakBrowser rename or a JavaScript fingerprint wrapper.

- [Build on Windows](BUILDING.md)
- [Architecture](ARCHITECTURE.md)
- [Status and limitations](../docs/NATIVE_ENGINE.md)
- [Verification requirements](../docs/NATIVE_VERIFICATION.md)
- [External test sites and per-build results](../docs/GLINT_TEST_MATRIX.md)
- [Development plan and continuation prompt (Russian)](../docs/GLINT_ROADMAP.ru.md)

## Source layout

Current Windows development source is **001-044**. Patches 0031-0034 jointly
promote browser-owned document/worker surface policy, startup/child transport,
Canvas/OfflineAudio candidates and partial native WebGL readback. Exact source
replay passed across 125 paths for 001-038. That Windows browser compiled, but
its full runtime gate failed on missing-policy cancellation. The last fully
verified baseline remains 001-027; no anti-bot result is admitted by this promotion.

Patch 0035 fixes initial-origin calculation; its translation unit compiled.
The full build remains pending. Two j4 attempts and the following j2 attempt
ended with LLVM out-of-memory failures. One failed object subsequently compiled
at j1; available system commit dropped to 0.39 GiB during the measured run.
The following j1 build reached a C++ incomplete-type error in the dedicated
worker host. Repair 0036 adds the complete Mojo surface type to its service
header; the previously failed dedicated worker translation unit compiled with
the exact 001-036 source chain unchanged. The user-requested j4 retry completed
100 tasks before failing on WebGL C++ errors, not LLVM OOM. Patch 0037 checks
the pack-copy `base::expected` through `has_value()` and binds a stateless
cleanup callback with a GC-owned context, restoring both pack parameters and
the pixel-pack buffer. The formerly failed WebGL translation unit compiled
with the exact pinned build flags in an isolated output directory; source,
browser core and GN guards passed (`webgl-readback-compilation-001-037-v2/proof.json`
on D). Ordered next-batch replay passed across 125 paths with this follow-up.
The full incremental retry uses j4; none of these checks is browser/runtime
admission.

The next j4 attempt completed 449 tasks before a renderer C++ error:
`mojo::StructPtr` does not support comparison with `nullptr`. Patch 0038 uses
its actual `is_null()` API when checking the legacy Canvas carrier. The failed
renderer translation unit compiled with the pinned build flags in a separate
owned output; source/core/GN guards passed
(`renderer-pointer-compilation-001-038-v1/proof.json` on D). Full source replay
passed across 125 paths. The 001-038 j4 browser build succeeded in 31m11s.
Its receipt binds all 38 patches and the measured EXE/DLL core.

Actual 001-038 worker startup checks passed **40/40**. Combined Canvas/OfflineAudio
checks passed six baseline/profile/restart phases and cross-profile isolation,
but the missing-policy phase crashed: failure processing attempted an illegal
`READY_TO_COMMIT` state transition. The combined gate remains **failed**, not admitted.
Patch 0039 cancels through the owning RenderFrameHost, records `ERR_ABORTED` and
cleans the speculative host without rewinding state or committing unprotected
content. This repair still requires a new build and runtime rerun.
Private evidence on D: `worker-surfaces-startup-001-038-v1.json` and
`combined-surfaces-001-038-v1.json`. These are owned fixtures, not CAPTCHA results.

The 001-039 browser compiled on j4 in 8m15s. Its revised combined owned gate passed
**7/7**, including exact missing-policy document abort. A browser-level CDP probe
avoids requiring a denied startup about:blank to commit: a control page executes,
the missing-key page is fetched once but never commits or executes, and its
Document request reports `ERR_ABORTED`. Frame/loader/history and live-browser
checks passed (`combined-surfaces-001-039-v2.json` on D). The first persistent-driver
probe timeout remains recorded; it is not a passing startup-recovery check.
Patch 0040 promotes the reviewed observer-lifetime follow-up and eight native
cases. The surface-navigation gate now requires all **42** exact native cases,
including late policy loss, recovery and observer-driven tab destruction.
The latest linked browser is still 001-039; 0040 native execution and browser
verification remain pending. This is not release or external anti-bot admission.

The 001-039 general runtime gate also passed all **18** named checks, including
persistent storage/lock/crash recovery, permissions, owned authenticated HTTP
proxy, scenarios, Recorder and Mobile Web Emulation. It requested only the
runtime gate, not the full eight-gate suite; evidence is
`owned-runtime-suite-001-039-v1/runtime.json` on D. These results do not admit
the later 0040/0041 source or external proxy/anti-bot behavior.

The first 0040 native test build completed 276 steps before a fixture C++ access
error, not OOM: child transport called a private RFH override directly. Patch
0041 dispatches through the public `mojom::FrameHost` interface and uses its
callback alias, without widening the production API. The formerly failed fixture
compiled to an isolated object with pinned target flags; input/core guards passed
(`child-interface-compilation-001-041-v1/proof.json` on D). Source replay passed
across 125 paths. Existing cache is preserved; the 42-case execution remains pending.

The repaired test binary linked successfully in 31m17s, but crashed during URL
scheme registration before running tests. Its initial-policy fixture constructed
a namespace-scope `GURL`/origin too early. Patch 0042 creates that origin only
when a test calls its factory; it does not suppress the registry assertion or
change production code. The repaired fixture compiled to an isolated object
(`initial-origin-fixture-compilation-001-042-v1/proof.json` on D). The j4 test
retry retains the completed objects; native test results remain pending.

That incremental test build completed in 49s and reached real native checks.
They exposed a production wiring gap: both throttle registries checked only the
Canvas switch, skipping the full surface mode. Patch 0043 registers the existing
readiness throttle for every explicit non-off document mode in both navigation
paths. Its translation unit compiled to an owned object with pinned flags;
source/core guards passed (`surface-throttle-compilation-001-043-v1/proof.json`).
Source replay passed across 126 paths. The 42-case gate still requires a full
passing rerun; a partially executed/crashed run is not admission.

After 0043, missing-policy checks progressed; the next failure was the simulator's
assumption that inline about:blank conflict cancellation leaves a pending entry.
Fixture-only patch 0044 exercises that case through the real NavigationController,
retaining exact abort, no-commit and original-document assertions. Network-path
simulation and production cancellation behavior are unchanged. The repaired
fixture compiled to an owned object and 126-path replay passed
(`inline-rejection-compilation-001-044-v1/proof.json` on D). Full execution is pending.

The identity verifier now compares document HTTP User-Agent, primary
Accept-Language and platform/mobile Client Hints against JavaScript, not just
against another HTTP baseline. The exact old 001-027 runtime passed 18 checks
with unchanged core hashes. Worker requests retain their separate baseline
contract: their missing Client Hints must not be fabricated to match documents.
This is not TLS proof, full Client Hints parsing or verification of 001-036.

Manager diagnostics also observe WebGPU adapter information, sorted features
and six native limits in the document and dedicated worker. Adapter requests
are bounded; unavailable adapters remain explicitly unavailable. This creates
no GPU device and does not spoof adapter data or provide WebGPU readback protection.
The feature-off 001-027 runtime passed this manager probe in en-US and de-DE:
document/worker WebGPU observations matched, with unchanged runtime core and
diagnostic inputs. This is evidence for observation, not for a protected GPU.
Profile health checks use a separate owned loopback page with page-scoped routing
and guaranteed close. The original profile page and its network requests remain
untouched; this was verified on the same old runtime in both locales.
The owned page enables its own CDP Network session and bypasses service workers
before navigation. A real registered-worker control on 001-027 intercepted normal
page routing but not the diagnostic page; the original page remained controlled
by that worker afterwards. No profile-wide service-worker setting is changed.
Screen diagnostics observe available dimensions, pixel depth and orientation,
and check configured screen geometry and available-area bounds. The same old
runtime passed two desktop locales and a 390x844/DPR3 Mobile Web case with
unchanged inputs/core. This verifies SDK geometry, not a physical monitor identity
or an Android browser.

Prepared native gates additionally require 26 BrowserContext cases, 34 surface
navigation/readiness cases, 13 window/child cases and 14 RGBA8 pack-copy cases.
These new native case sets have not run yet.

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

## Release boundary

Current own-fork work is Windows-only. Linux/macOS support is deferred, not
released. The manager's Mobile Web mode is desktop Chromium viewport/touch
emulation, not Android/iOS. Only verified capabilities may be enabled.

The linked 001-026 Windows browser passed all eight runtime gates (160 checks).
The latest 001-027 browser adds a verified shared-worker rejection notification;
all 40 owned startup/restart/shared-client/rejection checks passed. Its ordinary
runtime regression suite also passed all eight gates / 160 checks. Readiness patch 0016
passed 43 native key/service cases. Context-test patch 0017
passed all twenty native cases. Patches 0018-0020 register document/worker policy
endpoints and the worker consumer; all 34 native cases passed, followed by a
combined 54-case BrowserContext/IPC run. Worker startup/handoff patches 0021-0026
are linked behind a developer-only switch; four Blink seed ownership unit cases
passed on retry after test-only patch 0028 corrected a fixture lifetime abort.
The browser core, receipt and GN arguments were verified unchanged.
Patch 0029 registers the document partition validator and its nine exact cases;
the public `--target document-partition` native-unit gate passed. It does not
activate document delivery or Canvas protection; the verified browser is still
001-027.
The unprotected Canvas baseline passed on 001-027 before
and after restart. Canvas protection remains a candidate; branding
still needs application and verification. No signed own-engine release or guaranteed
anti-bot/CAPTCHA acceptance is advertised.

Development diaries and machine-specific evidence stay outside public source.

The next cohesive development batch is documented in
[GPU metadata](drafts/gpu/README.md), [offline Audio](drafts/audio/README.md) and
[surface policy v2](drafts/policy/README.md). Their source is now registered in
0031–0034, but these are not verified or enabled protections. The following
[bounded WebGL halo batch](drafts/next-readback/README.md) remains unregistered.
Their local diagnostic runners test real GPU operations
and AudioBuffer semantics independently of fingerprint-masking claims.

Durable contracts live in architecture docs; released changes belong in the
[changelog](../CHANGELOG.md).
