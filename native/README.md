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

Current Windows development source is **001-035**. Patches 0031-0034 jointly
promote browser-owned document/worker surface policy, startup/child transport,
Canvas/OfflineAudio candidates and partial native WebGL readback. Exact source
replay passed across 125 paths; this batch is **not yet compiled or runtime
verified**. The preceding document-commit binary passed all 12 NavigationSimulator
cases. The last verified browser remains 001-027; no new privacy capability or
anti-bot result is admitted by this promotion.

Patch 0035 fixes initial-origin calculation; its translation unit compiled.
The full build remains pending. Two j4 attempts and the following j2 attempt
ended with LLVM out-of-memory failures. One failed object subsequently compiled
at j1; available system commit dropped to 0.39 GiB during the measured run.
The full incremental retry now uses j1, preserving the existing outputs.
Compilation is not runtime admission.

The identity verifier now compares document HTTP User-Agent, primary
Accept-Language and platform/mobile Client Hints against JavaScript, not just
against another HTTP baseline. The exact old 001-027 runtime passed 18 checks
with unchanged core hashes. Worker requests retain their separate baseline
contract: their missing Client Hints must not be fabricated to match documents.
This is not TLS proof, full Client Hints parsing or verification of 001-035.

Manager diagnostics also observe WebGPU adapter information, sorted features
and six native limits in the document and dedicated worker. Adapter requests
are bounded; unavailable adapters remain explicitly unavailable. This creates
no GPU device and does not spoof adapter data or provide WebGPU readback protection.
The feature-off 001-027 runtime passed this manager probe in en-US and de-DE:
document/worker WebGPU observations matched, with unchanged runtime core and
diagnostic inputs. This is evidence for observation, not for a protected GPU.

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
