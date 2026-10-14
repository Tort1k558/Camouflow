# Glint browser test matrix

Living test register. Update after every linked Glint build; keep previous build
results rather than replacing them. A planned check is not a passing result.

## Latest linked build: 001-059 — 2026-10-14

Chromium 148.0.7778.96 linked at `j4` in **16m35.44s**, 244 executed steps,
reusing the prior source/test builds. The initial planned graph shrank as cached
dependencies were skipped; its 3016 estimate is not a fresh compilation count.
Receipt binds all 59 patches, GN arguments and the complete runtime core:

| File | SHA-256 |
| --- | --- |
| chrome.exe | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` |
| chrome.dll | `b78314a9b158d60729b85a30a0dbbf449d6391c3352b1f8fa7b4da463adbe384` |
| chrome_elf.dll | `3468b145cea9de7df386ad58c0daedba0d39c71bac58b0136486a36a2037b74d` |

| Gate | Result | Boundary |
| --- | --- | --- |
| Eight-gate runtime suite | **160 passed** | Runtime 18, hardware 9, WebRTC 7, automation 55, fonts 42, identity 18, CDP 6, combined 5; owned fixtures, not universal CDP invisibility |
| Combined profile-identity | **12/12 phases + 24 nested Canvas cases** | Canvas/Audio/WebGL in the same profiles and contexts; stable identity across tested origins, separate profiles, restart and simultaneous ownership |
| Combined partitioned-privacy | **12/12 phases + 24 nested Canvas cases** | Original partitioned derivation retained, with the same combined lifecycle/API checks |
| External fingerprint sites | **Mixed observations; see below** | Four public sites tested under proxy in headless/CDP mode; not CAPTCHA or human acceptance |
| CAPTCHA sites | **Not verified for this build** | No challenge completion or human-score claim |

Private proof: `browser-build-001-059-v1.json`,
`browser-verification-001-059-v1/suite.json`,
`combined-identity-surfaces-001-059-v2.json` and
`combined-partitioned-surfaces-001-059-v1.json` on D. Combined reports bind the
runtime core, receipt and probe source hashes; cleanup reported no error.

The first combined identity attempt is retained as failed evidence in
`combined-identity-surfaces-001-059-v1.json`: protected framebuffer reads returned
zeros/GL_INVALID_OPERATION because the harness enabled readback without enabling
its new GPU metadata transport dependency. The corrected harness requests both
features only in ready profiles; the same unchanged binary then passed both
combined modes. No native patch, fabricated metadata or weakened pixel validator
was used to obtain that result. First-script coverage is Canvas/Audio; nested
coverage is Canvas, not nested Audio/GPU. WebGPU is observed but not protected.
Product capability admission, branding, broader compatibility and external-site
verification remain separate outstanding gates.

### Repeatability and external observations

Profile-identity extended runs v2, v3 and v4 each passed **12/12 phases + 24
nested Canvas cases**. Runtime, receipt and probe-source hashes agree across
all three; no cleanup error was reported. Proofs on D:
`combined-identity-surfaces-001-059-v2.json`, `-v3.json` and `-v4.json`.

Four public sites returned HTTP 200 through authenticated SOCKS egress verified
inside the browser. Test profile: native Windows/GPU, de-DE, Europe/Berlin,
headless Chromium 148 with CDP attached and profile-identity surface candidates.
Two runs used the same persistent profile and unchanged core. The first omitted
the existing native UA flag; the second enabled `--camouflow-native-user-agent`.
No JavaScript API overrides or engine rebuild were used for this comparison.

| Service | First run, native UA flag off | Same-profile run, native UA flag on | Boundary |
| --- | --- | --- | --- |
| BrowserScan bot detection | **Robot**, UA highlighted | **Normal**; webdriver/UA/CDP/navigator sections not flagged | One observed visit per configuration, not universal CDP invisibility |
| Sannysoft | `HEADCHR_UA` failed on HeadlessChrome | `HEADCHR_UA` ok, webdriver advanced passed, Chrome object present, five plugins; no FAIL row found in captured scanner text | Some deliberately invalid API calls produced page errors; not a CAPTCHA test |
| Device and Browser Info | `isBot: true`; bot UA and timing resolution flagged | **Still `isBot: true`**; only timing resolution flagged in captured details | Worker/document CDP, Client Hints, WebGL and GPU consistency flags were false in this observation |
| CreepJS | 67% headless; 44% like-headless; reported 14% RGBA noise | 0% headless; **44% like-headless and reported 13% RGBA noise remain** | Its own diagnostic metrics, not a human score or a pass/fail certification |

Private bodies, screenshots and core/cleanup evidence:
`external-identity-probes-001-059-v2/` and `-v3/` on D. Initial discovery failure
is retained in `-v1/`: Browser.getBrowserCommandLine requires the diagnostic
automation flag. All test-owned browser resources were released. No proxy
credentials or raw profiles are published.

### Matching-version stock control

Unmodified Playwright Chromium **148.0.7778.96** was tested on the same machine
and authenticated proxy route, with de-DE/Europe/Berlin, a fresh persistent
profile, headless mode and CDP attached. Its three core hashes matched the
previous stock calibration and remained unchanged after the run. Four page
observations completed with HTTP 200; test-owned resources were released.

| Observation | Glint 001-059, native UA enabled | Matching stock Chromium | Interpretation |
| --- | --- | --- | --- |
| Device and Browser Info timing flag | `hasInconsistentTimingResolution: true` in the recorded visit | **True on all three visits** | Not isolated to Glint patches; no timer root cause established |
| Overall bot verdict | `isBot: true`, timing flag only in captured details | `isBot: true`, also expected UA/WebDriver/CDP flags | Different launch features; do not compare overall verdicts as an equivalent clean-browser control |

Private proof: `stock-site-control-148-001-059-v1/report.json`, screenshots and
captured same-origin diagnostic scripts on D. This control is automated and
headless, **not a manual human-browser baseline**. The captured same-origin
scripts did not expose the named timing check; an external fingerprint script
was listed but not captured. Do not infer the detector's implementation from
its flag name or change browser timer semantics on this evidence alone.

Next: isolate launch/instrumentation factors before changing timer semantics;
investigate detectable Canvas perturbation and ordinary graphics compatibility.
A green BrowserScan observation does not close these gaps or imply
Turnstile/reCAPTCHA success.

## Test destinations

Priority: **Core** for each build; **Extended** before release; **Reference** for
research. Availability and detector behavior must be rechecked at test time.

| Service | What to inspect | Priority | Evidence to retain |
| --- | --- | --- | --- |
| [CreepJS](https://abrahamjuliot.github.io/creepjs/) | JS API inconsistencies, Canvas, Audio, fonts, workers | Core | Report, reported lies and context differences |
| [Pixelscan](https://pixelscan.net/) | Fingerprint/environment consistency and network observations | Core | Exact findings, configuration and screenshot |
| [BrowserScan](https://www.browserscan.net/bot-detection) | Automation signals; use other sections for IP, WebRTC and fingerprint | Core | Bot verdict and individual signals |
| [Sannysoft](https://bot.sannysoft.com/) | WebDriver, headless and automation indicators | Core | Every individual check, not only green tiles |
| [BrowserLeaks](https://browserleaks.com/) | Canvas, WebGL, WebRTC, fonts and Client Hints | Core | Surface values and repeat/context comparisons |
| [IPhey](https://iphey.com/) | Browser and network consistency | Core | Individual findings and route label |
| [Fingerprint Playground](https://demo.fingerprint.com/playground) | Visitor recognition and available bot/tampering signals | Core | Same-profile revisit and different-profile observations |
| [Rebrowser Bot Detector](https://bot-detector.rebrowser.net/) | Automation/CDP-related behavior | Core | Individual tests; manual-only checks remain unverified |
| [Incolumitas](https://bot.incolumitas.com/) | Headless, API and behavioral bot checks | Core | Individual findings and observation duration |
| [Device and Browser Info](https://deviceandbrowserinfo.com/are_you_a_bot) | Browser automation indicators | Core | Individual flags, browser mode and CDP connection state |
| [TLS Peet](https://tls.peet.ws/) | TLS/HTTP fingerprints, including available JA3/JA4 data | Core | Browser-originated request; compare same-route stock Chrome |
| [IPify](https://api.ipify.org/?format=json) | Actual browser request egress | Core | Private expected-egress comparison; redact public IPs |
| [BrowserLeaks WebRTC](https://browserleaks.com/webrtc) | ICE candidates and address exposure | Core | Compare with expected proxy route; redact addresses |
| [DNS leak test](https://www.dnsleaktest.com/) | Resolver exposure during browser requests | Extended | Resolver observations; distinguish proxy and OS behavior |
| [Cover Your Tracks](https://coveryourtracks.eff.org/) | Tracking protection and fingerprint uniqueness in its sample | Extended | Sample size/date; uniqueness is not a bot verdict |
| [AmIUnique](https://amiunique.org/) | Fingerprint uniqueness in its participating population | Extended | Sample/date; results are population-dependent |
| [Fingerprint Demo](https://fingerprint.com/demo/) | Vendor demo entry point and visitor recognition | Extended | Record actual redirected destination and enabled product |
| [PrivacyTests](https://privacytests.org/) | Published browser privacy comparisons and test methodology | Reference | Not an interactive Glint certification; run applicable source tests separately |

## CAPTCHA destinations

| Service | Test | Priority | Acceptance boundary |
| --- | --- | --- | --- |
| [Google reCAPTCHA demos](https://recaptcha-demo.appspot.com/) | Available v2 checkbox/invisible examples | Extended | Record challenge outcome and actual backend response separately |
| [Google reCAPTCHA v3 scores](https://recaptcha-demo.appspot.com/recaptcha-v3-request-scores.php) | Official sample score request | Core | Backend success, score, action and hostname; sample score is not production quality |
| [Google reCAPTCHA v2](https://www.google.com/recaptcha/api2/demo) | Manual checkbox/challenge flow | Extended | Widget completion alone is not server verification |
| [Cloudflare Turnstile demo](https://demo.turnstile.workers.dev/) | Widget and integration smoke check | Core | Check current key/source: dummy keys cannot demonstrate real anti-bot acceptance |
| [Turnstile testing documentation](https://developers.cloudflare.com/turnstile/troubleshooting/testing/) | Controlled pass/fail integration fixtures | Reference | Separate guaranteed dummy outcomes from real production keys |
| [hCaptcha developer guide](https://docs.hcaptcha.com/) | Authorized controlled widget and backend verification | Extended | Requires a controlled deployment; test keys prove integration only |

Real Turnstile managed/non-interactive, hCaptcha and reCAPTCHA acceptance tests
require an authorized deployment with real keys and backend verification. Until
available, mark them **Not verified**, not PASS. Do not use paid solvers, token
substitution or unrelated account workflows. Do not publish CAPTCHA tokens,
secret keys, proxy credentials or identifying fingerprint payloads.

## Repeatable run protocol

First calibrate the existing local probes against stock Chrome. Distinguish
value changes, API behavior regressions and expected context-specific absences.
Add repeatability/isolation comparisons and record CDP attach vs Runtime.enable
separately. The [implementation roadmap](GLINT_ROADMAP.ru.md) defines these gates;
external green tiles do not replace them.

1. Record build ID, Chromium version, applied patch range, executable/core-DLL
   hashes, date, Windows version and policy configuration.
2. Run headed manual, headed automation and headless automation separately.
   Record CDP connected/disconnected state and effective launch arguments.
   Do not use JS API overrides or framework stealth flags as engine evidence.
3. Test the direct route and each configured proxy separately, using disposable
   profiles. Direct means no configured browser proxy, not necessarily no VPN.
   Verify HTTPS egress and DNS/WebRTC expectations without a direct fallback.
4. Compare with unmodified Chrome under the same route and mode. Repeat at least
   three times; compare same-profile restart and separate-profile observations.
5. Save raw reports/screenshots privately, then add a redacted results section
   below. Keep screenshot failures separate from detector observations.
6. Use **Observed**, **Failed**, **Unavailable**, **Not run**, or **Not verified**.
   Never convert a timeout, missing field or test-key CAPTCHA into PASS.

## Build history

### Native identity keys/service 001-058 — 2026-10-14

**62/62 cases passed**: 19 new identity derivation/immutable-mode cases and
43 legacy key/loading/readiness cases. Zero failed, disabled or error cases;
318 ms execution. The cached j4 build completed in **11m15.62s**, 201 executed
steps. Test EXE SHA-256:
`f9a9f48fab2224cf760ed1c24ff5d1186392431369c96da1670954fd2c479eaf`.
Source, browser 001-047 core, GN and receipt remained unchanged after execution.
Private proof/raw results/log: `identity-keys-001-058-v1.json`, `-tests.json`
and `-build.log` on D. This is key/service proof, not BrowserContext, IPC,
first-script delivery, GPU-driver coverage or linked identity-mode admission.

### BrowserContext build recovery 001-058 — 2026-10-14

The first `identity-contexts` build stopped after **5m49.15s**, 152 completed
steps, with `LLVM ERROR: out of memory` while compiling generated
`navigation_params.mojom-blink.cc`. **The 37 cases did not execute.** Failed
report/log remain in `identity-contexts-001-058-v1.*` on D.

The exact failed object subsequently compiled alone under the unchanged
production flags, diagnostics and `j4` setting: **2m21.31s**, one executed step.
Source, browser core, GN and receipt remained unchanged; object SHA-256:
`5cbdc33f47b63a38fe0ead6d581e3955aa029fbfc8137d73e6e642d1e7f3624b`.
Private proof, log and saved Clang reproducer:
`navigation-object-001-058-isolated-v1/` on D. The full cached j4 retry uses
`identity-contexts-001-058-v2.json`; object compilation is not a passing
BrowserContext gate or linked browser result.

The full v2 retry also stopped on memory exhaustion after **56.39s**, five
completed steps. This time `core_probes_impl.cc` failed with LLVM OOM; another
compiler reported Windows **0x5AF** (insufficient paging capacity). The 37
BrowserContext cases still did not execute. Failed v2 evidence is retained.
Known heavy `core_probes_impl` and generated `shorthands` objects then compiled
successfully as separate single-object targets with the original `j4` option and
unchanged flags: **50.43s** and **26.92s**, one executed step each. Proof on D:
`heavy-objects-001-058-isolated-v1/proof.json`. Source, browser core, GN, receipt
and toolchain remained unchanged; no diagnostic was suppressed or paging
configuration changed. The full cached retry now uses
`identity-contexts-001-058-v3.json`. This proves two objects, not the 37 cases or
that every remaining parallel compile will fit memory.

The v3 retry stopped after **4h23m01.48s**, with 3169 completed steps and
477 remaining, at the V8 context snapshot action: `WriteFile of 3918880
snapshot has failed`. The same generator successfully wrote a separate
3918880-byte probe file. A manually opened browser was still using this build
directory, so a mapped-file conflict is suspected; no browser was forcibly
closed and no snapshot was replaced. Failed proof remains in
`identity-contexts-001-058-v3.*` on D. **The 37 cases still did not execute.**

To make progress without touching the live browser's snapshot, all **631
content unittest object targets** were successfully checked/built in bounded
command batches with `j4`. Cached objects were reused; 631 is the target count,
not the number of freshly compiled objects or executed tests. Source, browser
core, GN, receipt, toolchain and existing snapshot hashes remained unchanged.
Private proof: `context-objects-001-058-v2/proof.json` and `build.log` on D.
This is object compilation only: full linking, snapshot generation and the
context/transport test executions remain pending.

The additional **418 object targets** recorded as unfinished in the v3 failure
log then completed in guarded `j4` batches: 34, 0, 30, 100 and 18 executed
steps, with earlier cached objects reused. These overlap the 631 targets above
and must not be added together as distinct compilations. Source, browser core,
GN, receipt, toolchain and existing snapshot hashes remained unchanged. Proof:
`remaining-context-objects-001-058-v2/proof.json` and `build.log` on D.
The browser session is still open; the original snapshot action, final linking
and all 37 context tests remain unverified.

### Identity contexts/transport and snapshot recovery 001-059 — 2026-10-14

Patch **0059** makes the actual V8 snapshot generator avoid writing only when
the existing file matches every generated byte, using a size-bounded read.
The old and freshly generated snapshots both hashed to
`790ea6e0d2b5b1f91cf3e922b0347c7372151c5e728467b95323466755c15905`.
The blocked action then succeeded without closing the manual browser or
rewriting its snapshot. The content target linked at `j4` in **7m36.91s**,
24 executed steps, retaining earlier compiled objects.

**37/37 BrowserContext cases passed** in 153 ms, followed by **20/20 transport
cases passed** in 3.524 seconds, with no skipped, disabled or failed cases.
Source, browser core, GN and receipt guards passed. Content test binary SHA-256:
`a27bca9c279bff13fc7316f8443f7c56553f02f6b813b2e0cfd744b4d375b7bc`.
Proof/raw results/logs: `identity-contexts-001-059-v1.*` and
`identity-transport-001-059-v1.*` on D. These are content-layer fixtures, not a
new Chrome binary, actual renderer IPC or profile-identity capability admission.

Five actual generator controls passed: missing file creation; identical readonly
file accepted without changing bytes or timestamp; different readonly bytes
rejected; an extra-byte readonly file rejected; different writable file replaced
with the generated bytes. Failed writes retained their input bytes and returned
exit code 1. Proof: `snapshot-idempotence-001-059-v1/proof.json` on D, with
source/core/GN/receipt/snapshot/generator hashes unchanged during those controls.
The two Blink identity-handoff fixture objects also compiled in **42.15s**,
but their 15 cases have not executed: `identity-handoff-objects-001-058-v1/`.

### Blink identity handoff 001-059 — 2026-10-14

The actual `blink_unittests` target compiled and linked at `j4` in
**2h1m54.83s**, 948 executed steps. **15/15 cases passed** in 520 ms with no
skipped, disabled or failed cases: three DocumentLoader fixture definitions
each ran in four parameter modes (12 cases), plus three worker-thread fixtures.
The final source/core/GN/receipt guards passed. Test binary SHA-256:
`a358e707622e2c5cff70a4eb331dd5cfb30938e20878c8d83596f387284f5dd6`.
Proof/raw results/log: `identity-handoff-001-059-v1.*` on D.

The selected cases cover policy ownership before inline document execution and
worker evaluation, clone isolation, rejection of unknown modes and retention
of the authenticated final origin. They do not prove Chrome ProfileImpl startup,
complete renderer-to-browser IPC or the new profile-identity browser runtime.
The current browser core remains 001-047; capability admission remains closed.

The key/service gate was subsequently repeated on 001-059 and passed **62/62**:
`identity-keys-001-059-v1.*` on D. All four identity selections now have executed
proof on the same registered source chain: **134/134** cases (50 new, 84 legacy).
This does not promote source-only results into a browser runtime admission.

Before rebuilding Chrome, an isolated 001-047 rollback copy was created on D:
`standalone-runtime-backup-001-047-before-059-v2/`. Its **509 files**, totaling
690878774 bytes, match recorded hashes; the copied runtime launched headlessly
as Chromium 148.0.7778.96 and released runtime ownership. The first attempt is
retained as failed evidence: it omitted the versioned assembly manifest and
Windows reported SideBySide error 14001. The v2 copy includes that manifest.
This is a local rollback copy and launch check, not a new published package or
a repeat of the full browser verification suite. Chrome 001-059 is now building
at `j4`; there is no verified new browser binary yet.

### Native GPU metadata 001-058 — 2026-10-14

The actual Chromium `gpu_unittests` target compiled and linked at `j4` in
**6m42.46s**, 120 executed steps. **33/33 cases passed**, without skipped or
disabled cases: codec 14, passthrough protocol 5 and attachment 14. Execution
took **937 ms** in the first run. The public verifier repeated the same exact
selection successfully using the cached target. Source, browser core, GN and
receipt remained unchanged; the first guarded run also bound the toolchain and
existing snapshot hashes. Test binary SHA-256:
`78119b90a44733b5ded4b0f9937f14c7b78a36b362d03d2d78e3bbf47986330d`.

Proof/raw results/logs on D: `gpu-metadata-units-001-058-v1/` and
`gpu-metadata-001-058-v2.*`. Reproduce the exact registered target with:

```powershell
.venv\Scripts\python.exe scripts/verify_native_privacy_units.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\gpu-metadata-new.json --vs-installation D:\CamouFlowNative\toolchain\BuildTools --jobs 4 --target gpu-metadata
```

This proves the selected codec and passthrough command/attachment fixtures,
including buffer bounds, feature-off behavior, selected attachment dimensions,
formats, mip/face/layer selection, bindings and pending client errors. It does
not prove the excluded validating decoder, renderer-to-GPU IPC, protected
browser readback, WebGPU, profile-identity mode or capability admission.

A broader exact-suite regression run then passed **74/74 cases** in 272 ms:
the 33 selected metadata cases plus 41 existing GLES2/GLES3 passthrough cases.
No skipped, disabled or failed case was accepted; source/core/GN/receipt,
toolchain and snapshot hashes remained unchanged. Private proof/raw results:
`gpu-passthrough-regression-001-058-v1/` on D. The filter covered
`GLES2DecoderPassthroughTest.*`, `GLES3DecoderPassthroughTest.*`,
`GlintReadbackMetadataTest.*` and `GlintPassthroughAttachmentTest.*`; it does
not cover every typed/parameterized GPU suite. These 74 include the earlier
33 and must not be added as disjoint tests. The full Python suite after adding
the public metadata verifier passed **2292 tests** in 82.72 seconds.

### Additional owned browser gates 001-047 — 2026-10-14

| Gate | Result | Scope and limits |
| --- | --- | --- |
| Nested Canvas | **24/24 + 7/7 phases passed** | Four classic/module parent-child combinations across baseline/two profiles and restart; first-script and repeated pixel/PNG reads, exact fetch/body counts. No nested Audio, independent child denial or early-termination claim |
| Strict Client Hints | **18/18 passed** | Eight document/frame HTTP-versus-JS comparisons, six worker JS checks, four invalid-UA rejections. Worker HTTP hints, TLS and cross-platform identity are not covered |
| Combined future Identity/GPU C++ preflight | **22 + 6 units passed** | One composed tree with fresh Mojo/GPU generation and no omitted units; parsing/type checks only, not fixture execution or a linked identity-mode browser |

Private reports on D: `combined-surfaces-nested-001-047-v4.json`,
`identity-strict-001-047-v2.json` and
`identity-readback-combined-cpp-001-048-v3.json`. Browser EXE/DLL core hashes
remained unchanged; candidate preflight also preserved active source and GN.
Strict v1 failed cross-origin HTTP hints because the owned fixture lacked
Permissions-Policy delegation. The fixture now grants only its exact localhost
origin and iframe features in strict mode; the failed evidence remains retained.
These are controlled gates, not external detector or CAPTCHA acceptance.

### Unregistered GPU codec execution — 2026-10-14

**14/14 actual `GlintReadbackMetadataTest` cases passed**, zero failures,
disabled cases or errors. The standalone executable uses real GoogleTest and
GL types from the pinned Chromium source, compiled with MSVC C++20 `/O2 /W4 /WX`.
It checks schema/status, exact wire length, dimensions, format/sample validity,
byte-colour eligibility and producer rejection. It is not the Chromium GN test
target, GPU protocol/attachment execution, a driver test or a new browser build.

Proof and raw logs/results remain on D:
`gpu-metadata-codec-001-048-v3.json` and its `-artifacts` directory.
Browser core, GN and receipt remained unchanged. The original `/WX` failure on
signed/unsigned fixture expectations remains recorded; expected GL enums were
typed explicitly, without suppressing a warning or removing a test. Full draft
composition and fresh Mojo/GPU generation passed after that fixture-only repair:
`identity-readback-codec-fixture-001-048-v1.json`.

### Windows native readback units 001-048 — 2026-10-14

The cached j4 retry linked `blink_unittests.exe` in **1h30m44.64s**, 654 executed
steps, then passed **31/31 cases** across pack copy (14), region planning (11)
and clipped publication (6). Zero failures, disabled cases or errors; 176 ms
test execution. Source, GN, receipt and the 001-047 browser EXE/DLL core stayed
unchanged. Test binary SHA-256:
`44ac3b7c8e178db08130c62762e323e73077af6f4b9b7e30f5c47bebfb0c90c0`.

Private proof/raw tests/log: `gpu-readback-units-001-048-v2.json`,
`gpu-readback-units-001-048-v2-tests.json` and `-build.log` on D.
The first build failed with LLVM OOM after 302 steps; its evidence remains.
This proves the selected native copy/planner fixtures, not a new browser build,
GPU-driver execution, WebGPU, identity mode or external detector acceptance.

### Windows development candidate 001-047 — 2026-10-13

Corrected j4 incremental build succeeded in **12m46.29s**, 76 executed steps.
The first attempt failed on a typed `base::expected` call, not OOM; its log
remains retained. The corrected caller also passed isolated optimized object
compilation before retrying the whole browser.

Measured `chrome.dll` SHA-256:
`f70a287dc74fbb8788c0b94ac55f48169de7fc79a7c500d463cb1d47f1bd59d7`.
The receipt binds all 47 exact patch hashes, EXE/DLL core and GN configuration.

| Owned check | Result | Boundary |
| --- | --- | --- |
| Protected WebGL readback | **Passed: six phases** | Baseline and two independent profiles before/after restart in eight document/worker contexts; CPU/PBO clipping, untouched padding, renderbuffer resize, exports, errors and profile isolation |
| Eight-gate suite | **Passed: 160 checks** | All eight gates completed on the unchanged 001-047 EXE/DLL core |
| Combined Canvas/OfflineAudio | **Passed: three consecutive 7/7 runs** | Same measured EXE/DLL core, restart/profile/context consistency, exact missing-policy abort and completed cleanup; older intermittent timeout remains unexplained |
| Worker startup/restart/shared clients | **Passed: 40/40** | Default contract, surfaces bootstrap |
| Extended nested dedicated workers | **Passed: 60/60** | Includes default 40 and 20 additional classic/module parent/child combinations across modes and restart; not independent child-policy denial or protected child pixels |
| Native readback fixtures | Not executed; C++ preflight failed | Pack-copy and region fixtures misuse typed results; clipped-publication fixture parsed successfully. Exact 31-case execution remains required |
| External detectors and CAPTCHA | Not rerun | No third-party acceptance claim |

Private evidence: `browser-verification-001-047-v1/gpu-readback.json`,
`combined-surfaces-001-047-v2.json`, `combined-surfaces-001-047-v3.json`,
`halo-expected-compilation-001-047-v2/proof.json` and
`nested-fixture-validation-001-047-v1/proof.json` on D:. Source replay is
`clipped-readback-replay-001-047-v2.json`; the earlier failed build is
`clipped-readback-001-047-chrome-j4-v12.log`. No release or broad GPU capability
is admitted by this single owned readback run.

Completed browser evidence: `browser-verification-001-047-v1/verification.json`,
`suite/suite.json`, `surfaces.json`, `worker-startup.json`, and
`worker-nested-001-047-v1.json` on D:. The nested run binds the same core and
probe hash, with independent parent/child fetch and execution counters.
Native fixture preflight failure is retained separately as
`readback-fixture-cpp-001-047-v1/proof.json`; no test was skipped or declared passed.

### Windows development candidate 001-045 — 2026-10-13

j4 incremental build succeeded in **5m29.58s**, four executed build steps.
The receipt now directly binds EXE and both core DLLs. Measured `chrome.dll`
SHA-256: `0e2e217ebcfe59adf15da09ec6d95ac7c65e9258d77bca523c96036f7340e894`.
EXE and `chrome_elf.dll` hashes are unchanged from 001-039; the engine code
changed in `chrome.dll`.

| Owned check | Result | Boundary |
| --- | --- | --- |
| Eight-gate ordinary runtime suite | **Passed: 160 checks** | Runtime, hardware, WebRTC, automation, fonts, HTTP/JS identity, CDP and combined existing policies; unchanged EXE/DLL core |
| Classic/module worker startup/restart | **Passed: 40/40** | Surface bootstrap, shared clients and unavailable-policy rejection; not nested-worker or early-termination admission |
| Combined Canvas/OfflineAudio, initial run | **Failed: timeout** | Four phases passed; profile-B initial frame evaluation timed out; cleanup completed |
| Combined Canvas/OfflineAudio, v2 retry | **Passed: 7/7** | Includes cross-profile/restart checks and exact missing-policy abort; does not resolve initial intermittent timeout |
| Combined Canvas/OfflineAudio, v3 retry | **Passed: 7/7** | Second consecutive passing retry on unchanged core; first failure remains open |
| Protected WebGL readback | **Failed** | Baseline initial/restart passed; profile-A initial failed boundary semantics: out-of-bounds CPU bytes changed from sentinel 165 to zero across all eight contexts, before/after attachment resize |
| Native fixtures | **Passed: 136/136** | Navigation 42, contexts 26, window/child 13, worker surfaces 55 on one test binary; distinct from browser runtime |
| External detectors, proxy routes and CAPTCHA | Not rerun | No third-party result or acceptance claim for this build |
| Next identity/readback batch | Source checks passed | Twelve unregistered patches, 113 paths, isolated Mojo/GPU generation; not compiled or enabled |

Private evidence on D: `browser-verification-001-045-v1/suite/suite.json`,
`browser-verification-001-045-v1/worker-startup.json`,
`browser-verification-001-045-v1/surfaces.json` (failed run),
`combined-surfaces-001-045-v2.json` (passing retry) and
`combined-surfaces-001-045-v3.json` (second passing retry),
`gpu-readback-001-045-v1.json` (protected readback failure) and
`identity-readback-001-045-batch-v1.json`. All failures remain recorded.
The overall first browser-verification run remains failed; no release or
surface capability is admitted from a passing retry alone.

### Windows development candidate 001-039 — 2026-10-13

j4 incremental build succeeded in **8m15.04s**, five executed build steps.
Measured `chrome.dll` SHA-256:
`3c9b71a91ccba24b97e151ed9d63a053b41eb61a0852aa13c6393f9237479c06`.
The EXE and `chrome_elf.dll` hashes remain the same as 001-038.

| Owned runtime check | Result | Boundary |
| --- | --- | --- |
| Combined baseline/profile/restart phases | Passed: 6/6 | Repeated on the linked 001-039 engine |
| Missing required document policy | **Failed: persistent-context launch timeout** | No earlier fatal transition in the saved log; denying initial about:blank prevents the driver's startup wait from completing |
| Revised combined gate v2 | **Passed: 7/7** | Same 001-039 core; controlled document execution plus denied-profile CDP observation independent of startup-page commit |
| Missing-policy browser-level CDP check v2 | Passed | Control: one request/one script execution; denied: one request/zero execution, exact Document request correlated to `ERR_ABORTED`, unchanged frame/loader/history and no commit event; browser remains responsive |
| General manager/runtime gate | **Passed: 18 named checks** | Persistent five-store isolation/restart, owner locks, crash/controller/teardown recovery, permissions, authenticated loopback HTTP proxy, scenarios, Recorder and Mobile Web Emulation |
| Worker checks and external detectors | Not rerun for this build | Do not transfer 001-038 results |

Private evidence: `combined-surfaces-001-039-v1.json` (failed persistent-driver
probe), `no-policy-cdp-v1/proof.json` (prototype), and
`combined-surfaces-001-039-v2.json` (revised full gate passed; cleanup passed).
This is not persistent-driver startup recovery or anti-bot admission. The reviewed
finish-observer lifetime guard and its eight native cases still require promotion
and execution before release.

General runtime evidence: `owned-runtime-suite-001-039-v1/runtime.json` and
`suite.json` on D, bound to the same measured three-file runtime core. This run
requested only `runtime` (`full_suite=false`), not all eight standard gates.
The proxy is an owned local fixture, not proof for the user's external proxies;
Mobile Web Emulation is not an Android/iOS runtime. It does not admit 0040/0041.

### Windows development candidate 001-038 — 2026-10-13

Chromium **148.0.7778.96**; j4 incremental build succeeded in **31m11s**.
Receipt includes all 38 exact patches. Windows browser behavior changed in
`chrome.dll`; an unchanged launcher EXE hash does not imply an unchanged engine.

| Core file | Measured SHA-256 |
| --- | --- |
| `chrome.exe` | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` |
| `chrome.dll` | `68e539371a0b0064f455ca7277b66be9cabbd408f79fcf656702e8c59b970211` |
| `chrome_elf.dll` | `3468b145cea9de7df386ad58c0daedba0d39c71bac58b0136486a36a2037b74d` |

| Owned runtime check | Result | Boundary |
| --- | --- | --- |
| Surface-policy worker startup | Passed: 40/40 | Classic/module dedicated, shared and service workers; ready, absent-policy and restart phases |
| Combined Canvas/OfflineAudio | Passed: 6 baseline/profile/restart phases | Two protected profiles plus baseline; document/frame/worker observations where APIs apply |
| Cross-profile isolation | Passed | The owned fixture's observations only; not general anti-bot acceptance |
| Missing required document policy | **Failed: browser crash** | Illegal `READY_TO_COMMIT` failure transition; full combined gate failed |
| External detector/CAPTCHA destinations | Not run for this build | Earlier build observations cannot be transferred |

Private evidence on D: `worker-surfaces-startup-001-038-v1.json` and
`combined-surfaces-001-038-v1.json`. Registered repair 0039 and the subsequent
observer-lifetime drafts are not validated by these results. This candidate is
**not release-admitted**; retain failed evidence and rerun after repairs.

### Windows development baseline 001–010 — 2026-10-12

Chromium **148.0.7778.96**; executable SHA-256:
`61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222`.
Headless automation, no JS API overrides; CLI automation masking suppressed.
One observational round, not the complete repeatable protocol above.

| Check | Direct | SOCKS5 route 1 | SOCKS5 route 2 | SOCKS5 route 3 | Limits |
| --- | --- | --- | --- | --- | --- |
| BrowserScan bot detection | Observed: Normal | Observed: Normal | Observed: Normal | Observed: Normal | Route 2 screenshot failed; DOM observation available |
| Fingerprint Playground | Observed: bot/tampering/devtools not detected | Same observation | Same observation | Same observation | Not a complete tracking/isolation test |
| Official reCAPTCHA v3 sample | Observed: backend success, score 0.9 | Not verified | Not verified | Not verified | Proxy backend responses absent within observation window; sample only |
| Real Turnstile / hCaptcha | Not verified | Not verified | Not verified | Not verified | No real-key authorized backend verification |
| Other destinations above | Not run | Not run | Not run | Not run | Pending expanded matrix |

Private evidence: `external-probes-strict-baseline-001-010/external-proxy-matrix.json`
in the external build workspace. Earlier framework-masked observations must not
be substituted for this strict round.

### Windows development candidate 001–015

Windows link completed on **2026-10-12**, build process exit code 0, jobs 4;
the build log records **1h51m49.40s** for this incremental compiler/linker run,
not the entire development history or a clean build. Receipt includes 15 patches.
The eight runtime gates, 33 named native-unit cases, external observation round
and eight-context Canvas baseline completed. Baseline
observations above must not be transferred to this candidate.

| Measured code | SHA-256 |
| --- | --- |
| `chrome.exe` | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` |
| `chrome.dll` | `2bf8b1504afec16c841b761432fd914e20fe358fc284bde4955b515774e4ad77` |
| `chrome_elf.dll` | `3468b145cea9de7df386ad58c0daedba0d39c71bac58b0136486a36a2037b74d` |

The launcher hash is unchanged from 001–010; the changed implementation is in
`chrome.dll`. An executable-only hash cannot distinguish these two builds.

An additional actual Chrome startup smoke with
`--camouflow-native-privacy-key-service=1` passed initial/restart phases:
persistent localStorage survived, two separate OTR contexts did not inherit it,
and the owned identity file remained unchanged. Private report:
`key-bootstrap-001-015/report.json`. This is limited startup/storage evidence,
**not** observation of key loading/readiness/derivation, OTR key separation or
fingerprint protection. The real context/readiness drafts still need execution.

| Candidate 001–015 runtime gate | Completed checks | Result |
| --- | --- | --- |
| Runtime/lifecycle/storage | 18 | Passed |
| Hardware | 9 | Passed |
| WebRTC | 7 | Passed |
| Automation | 55 | Passed |
| Windows fonts | 42 | Passed |
| Identity consistency | 18 | Passed |
| CDP Error-serialization scope | 6 | Passed |
| Combined policies | 5 | Passed |
| **Total** | **160** | **8 gates passed** |

Private report set: `verification-context-chrome-001-015-user-j4/runtime/`.
An independent recheck validated all child report hashes, gate coverage/counts
and the current three runtime code hashes. This is owned-fixture evidence, not
real CAPTCHA acceptance, prepared-draft coverage or production release admission.

The public `verify_native_privacy_units.py` also rebuilt/executed the native target
and passed all **33 exact required cases**, independently revalidated from its
GoogleTest JSON. Browser code remained unchanged. Private evidence:
`verification-context-chrome-001-015-user-j4/privacy-units.json` and
`privacy-units-tests.json`. This covers key primitives/loading/service ownership,
not the unapplied real-BrowserContext/readiness drafts or renderer IPC.

| External check, 001–015 headless observation round | Direct | SOCKS5 route 1 | SOCKS5 route 2 | SOCKS5 route 3 |
| --- | --- | --- | --- | --- |
| BrowserScan bot detection | Observed: Normal | Observed: Normal | Observed: Normal | Observed: Normal |
| Fingerprint Playground bot/tampering/devtools/incognito labels | Observed: Not detected | Observed: Not detected | Observed: Not detected | Observed: Not detected |
| Official reCAPTCHA v3 sample backend | Not verified: navigation failed | Observed: success, score 0.9 | Not verified: no response within 60 seconds | Not verified: no response within 60 seconds |
| BrowserScan screenshot artifact | Saved | Failed | Failed | Saved |
| Real Turnstile/hCaptcha verification | Not verified | Not verified | Not verified | Not verified |

Private report: `verification-context-chrome-001-015-user-j4/external/external-proxy-matrix.json`.
All four browser sessions were closed after observation. The CLI automation
masking flag was suppressed; native policy flags remained explicitly configured.
One round and the public sample score do not establish production CAPTCHA
reliability. Failed screenshots do not erase available DOM observations.

The candidate's separate Canvas run completed all four groups across eight
readback contexts and the original three security contexts. Code hashes match
the candidate table. Report: `verification-context-chrome-001-015-user-j4/canvas.json`.
This remains a compatibility baseline, not an implemented Canvas privacy policy.

### Local Canvas calibration — baseline 001–010, 2026-10-12

An additional run of `scripts/verify_native_canvas.py` against the preserved
001–010 executable above completed all four checks. This tests **unmodified
Canvas consistency**, not fingerprint masking or anti-bot acceptance.

| Check | Observed scope | Result |
| --- | --- | --- |
| Initial readback | Document, same/cross-origin iframe, dedicated/shared/service workers; repeated reads, PNG export and crop geometry | Passed |
| Initial security/empty images | Document and same/cross-origin iframe; expected security exceptions and empty-image behavior | Passed |
| Persistent-profile restart | Same six contexts and readback observations compared with initial run | Passed |
| Restart security/empty images | Same three document/frame contexts | Passed |

Private report: `canvas-calibration-001-010-round2.json` in the external build
workspace. Executable hash and browser version match the baseline header.
This is not a same-version stock Chrome comparison, an AudioWorklet/srcdoc
check, a transformed-Canvas acceptance gate or evidence for candidate 001–015.

### Code-bound Canvas control comparison — 2026-10-12

A subsequent run used the strengthened verifier measuring `chrome.exe`,
`chrome.dll` and `chrome_elf.dll` before/after capture. Both the preserved
001–010 runtime and unpatched Playwright SDK Chromium reported version
**148.0.7778.96**; each completed the four Canvas checks above successfully.
Their captured Canvas/security observations were equal, as expected for this
unmodified-Canvas baseline. This does **not** demonstrate profile unlinkability.

| Runtime | Executable SHA-256 | Private report |
| --- | --- | --- |
| Glint 001–010 baseline | `61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222` | `canvas-core-calibration-001-010.json` |
| Unpatched SDK control | `290fa7018fda22c52ada5eddb0113baf3ebc41fd0fde6085eddb19793606c635` | `canvas-stock-calibration-20261012.json` |

Reports retain all three measured code hashes. The control is SDK Chromium,
not a branded consumer Chrome installation or a commercial-engine benchmark.
Coverage remains limited to the tested Canvas paths and contexts; it does not
validate other surfaces or certify the new 001–015 build.

### Eight-context calibration and combined-policy run — 2026-10-12

The probes now include `about:blank` and `srcdoc` frames in addition to the
previous six readback contexts. Security/WebRTC frame observations are resolved
by owned frame IDs rather than relying on frame enumeration order.

| Run | Coverage | Result | Private report |
| --- | --- | --- | --- |
| Unpatched SDK Chromium 148.0.7778.96 | Four Canvas baseline groups; eight readback contexts; original three security contexts | Passed | `canvas-stock-eight-contexts.json` |
| Glint 001–015, all existing policy arguments combined | STUN positive control plus two profiles before/after restart; eight readback/identity contexts per profile phase | Five named checks passed | `combined-eight-contexts-001-015.json` |

The Glint run's code hashes match the linked candidate above. Native Canvas
protection is still absent. This does not test AudioWorklet, prove renderer
process separation for the cross-origin frame, or validate future key IPC.
The original 160-check suite was captured before this extension; these are
additional results, not retroactively expanded coverage of older reports.

### Source-only readiness progression, chain 001–016

Patch 0016 was registered/applied after the 001–015 verification pipeline ended.
Its first native compilation rejected capturing lambdas in `BindOnce`; test
callbacks were corrected to the upstream `BindLambdaForTesting` helper.
The retry completed all **43 exact native cases**, including ten readiness cases,
with browser code/receipt unchanged. Private report:
`privacy-readiness-001-016-bindings-fixed.json`. The linked browser remains
001–015; these service tests do not establish readiness bridge runtime, renderer
IPC or Canvas protection. Real-context tests were subsequently promoted to
registered/applied patch 0017; their execution remains pending.

The production readiness bridge translation unit also compiled successfully
without changing the linked browser or receipt; private object proof:
`readiness-bridge-object-001-016.json`. Object compilation is not browser linkage
or execution of the real-context tests.

### Source-only real-context progression, chain 001–017

The public native verifier now supports a separate `--target contexts` mode,
building `content_unittests` and requiring exactly 20 named
`NativePrivacyBrowserContextTest` cases. Key/service mode still requires its
original 43 cases; neither mode accepts the other mode's results as coverage.
Patch 0017 is registered/applied and the target is building. No passing context
execution or newly linked 001–017 browser is claimed. The preserved 001–015
runtime remains the last linked/verified browser.

The first context-target build stopped at 380/2361 with LLVM `out of memory`
and Windows error `0x5AF` (insufficient paging file). No context cases executed.
Its log is retained as `privacy-contexts-001-017-build.log`; the interrupted
verifier did not produce a terminal JSON proof. An incremental retry uses one
job and a new evidence path `privacy-contexts-001-017-retry-j1.json`, preserving
completed objects, GN arguments and source inputs. Retry success remains pending;
do not interpret the original four-job invocation as a passing result.

### Linked worker-startup builds, 001-026 and 001-027 (2026-10-12)

Both Windows builds pinned Chromium 148.0.7778.96. The 001-026 build completed
in 29m17.54s; the incremental 001-027 shared-worker rejection fix completed in
15m28.62s, each with four jobs. No external result from 001-015 is carried forward.

| Build | Measured chrome.dll SHA-256 | Local evidence |
| --- | --- | --- |
| 001-026 | `a055fecb73db29c0ababa0cb3da2f4d7d3942253d82453ce6b58e24f938927e2` | Eight runtime gates / 160 checks passed; full worker gate failed on unavailable shared-worker timeout |
| 001-027 | `ec1e8ad8a87bea6e448d0c5f117a561c7f1bf3b6a9db330626dc4e538124d350` | All eight normal runtime gates / 160 checks, 40 worker startup/restart/shared-client/rejection checks and four unprotected Canvas baseline phases passed |

Both executable stub hashes remain
`61e97ba3335f64836b3abcf93d67af0d6ddd0d06c291b4592b1448643b35e222`;
matching only chrome.exe would incorrectly identify these builds as the same code.
Private evidence: `worker-startup-runtime-001-026-build.json`,
`runtime-001-026-regression-suite/suite.json`,
`worker-startup-001-026-runtime-partition-fixed-v3.json`,
`worker-startup-001-026-runtime-service-first.json`,
`shared-worker-bootstrap-failure-001-027-build.json` and
`worker-startup-001-027-runtime-40-first.json`.
The exact worker check set, receipt checksum and core hashes were revalidated.
These controlled runs use explicitly enabled partitioning and diagnostic
`--enable-automation`; they are not external anti-bot score observations.

| Core destination | 001-026 | 001-027 |
| --- | --- | --- |
| CreepJS | Not run | Not run |
| Pixelscan | Not run | Not run |
| BrowserScan | Not run | Not run |
| Sannysoft | Not run | Not run |
| BrowserLeaks fingerprint surfaces | Not run | Not run |
| IPhey | Not run | Not run |
| Fingerprint Playground | Not run | Not run |
| Rebrowser Bot Detector | Not run | Not run |
| Incolumitas | Not run | Not run |
| Device and Browser Info | Not run | Not run |
| TLS Peet | Not run | Not run |
| IPify browser egress | Not run externally; owned proxy fixture passed | Not run externally; owned proxy fixture passed |
| BrowserLeaks WebRTC | Not run externally; owned WebRTC fixture passed | Not run externally; owned WebRTC fixture passed |
| Google reCAPTCHA v3 | Not run | Not run |
| Cloudflare Turnstile | Not run | Not run |

The four-case Blink worker-seed handoff gate subsequently passed with test-only
fixture correction 0028, as recorded below. Document
first-script bootstrap, protected Canvas/WebGL/WebGPU/audio and privacy
admission remain incomplete. Neither build is a new verified production release.

### Blink worker-handoff test target, 001-027 / fixture correction 0028

The 001-027 `blink_unittests` build succeeded in **2h24m55.18s**, jobs 4.
This builds a test executable, not a newly verified browser release.

| Case | First execution |
| --- | --- |
| Seed arrives before evaluation | Passed |
| Seed absent without bootstrap | Passed |
| Sequential scopes do not reuse seed | Aborted during fixture destruction |
| Immediate termination retains owned seed | Not executed after process abort |

The sequential fixture created a never-started worker after its last iteration;
the upstream destructor correctly rejected its `kNotTerminated` exit state.
Patch 0028 moves recreation to the next iteration, preserving seed comparisons,
shutdown waits, mock expectations and the destructor DCHECK. It changes only the
test fixture; the last verified browser remains 001-027. The failed report is
retained as `worker-handoff-001-027-j4.json` in the private build workspace.
The full four-case incremental retry **passed** under the new
`worker-handoff-001-028-fixture-lifetime-j4.json` evidence path. All four exact
cases completed, with no skipped cases. Incremental build: **12m19.98s**, two
steps; test execution: 149 ms. Test executable SHA-256:
`c12081c58b2370f43f4f2e7ce27f9465f58205c45c298c1e71c442bb2ea273af`.
The exact case set, test executable checksum and unchanged browser core,
receipt and GN arguments were independently verified. This is fixture-level
seed ownership/timing evidence, not real browser-partition derivation,
Canvas protection, external anti-bot acceptance or a new browser release.

### Registered document partition validator, source patch 0029

The exact nine `GlintDocumentCanvasPolicyTest` cases passed via the public
`verify_native_privacy_units.py --target document-partition` command.
Build: **1m22.26s**, two incremental steps; no new browser release.
The exact completed case set, actual unit executable checksum and unchanged
browser core/receipt/GN hashes were independently rechecked.
Private evidence: `document-partition-001-029-registered-j4.json`.
The original **43 key/service cases also passed** through the same registered
native unit target, separately: `privacy-keys-001-029-regression-j4.json`.

This covers partition equality/rejection and owned seed return, including
opaque identity, retained partition fields, nonce and binary commitment data.
It does not prove pre-teardown cancellation, actual first-script delivery or
Canvas protection. Those document runtime gates remain incomplete.

## Sources and maintenance

- [GitHub detector directory](https://github.com/TheGP/untidetect-tools): discovery only, not proof of Glint results.
- [Rebrowser detector source](https://github.com/rebrowser/rebrowser-bot-detector): automation checks and their prerequisites.
- [Google sample source](https://github.com/google/recaptcha/tree/master/examples): client and backend verification examples.
- [Cloudflare Turnstile demo source](https://github.com/cloudflare/turnstile-demo-workers): inspect current keys and backend behavior.
- [Cloudflare dummy-key rules](https://developers.cloudflare.com/turnstile/troubleshooting/testing/): fixture outcomes are not real challenge acceptance.

For every linked build, add a new build-history section with all Core checks,
including unavailable/not-run entries. Extended checks are required before a
release claim. This document is maintained alongside saved evidence; it is not
an automatic certification or an unattended scheduler.
