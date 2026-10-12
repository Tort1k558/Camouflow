# Glint browser test matrix

Living test register. Update after every linked Glint build; keep previous build
results rather than replacing them. A planned check is not a passing result.

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

The four-case Blink worker-seed handoff gate has not passed. Document
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
The full four-case incremental retry is pending under the new
`worker-handoff-001-028-fixture-lifetime-j4.json` evidence path.

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
