# Chromium 156 rebase candidate

**Development candidate, not a production/default engine.** The default build
lock and reviewed 001-062 chain still target Chromium 148.0.7778.96. The separate
156 / 001–066 browser is linked and all 17 native target groups passed. Baseline
001–065 runtime evidence remains historical; new policy and installed-package
gates remain separate. The manifest is a source
contract, not a mutable binary-readiness flag.

### Selected 0066 fixture correction: native gates passed

The selected manifest now appends `0066-native-gpu-optional-query-fixture.patch`.
It changes only the GPU unit fixture, explicitly requests the native optional
texture-query extension, and adds a negative case for its absence. No production
GPU implementation or feature default changes. The canonical GPU gate requires
all **34 cases**, including that negative control; no skips or exclusions.

The preceding actual [001–065 batch](native-batch65-observations.json) collected
all 17 groups in one Ninja invocation: 16 passed, GPU metadata failed 6 of 33.
Source/core/receipt/SDK postguards passed. These filters overlap; counts are not
independent coverage. Actual sync/hooks, complete source replay and the 001–066
build now completed. Only the fixture changed; 256 byte-identical source files
retained their old timestamps. The browser build took **2m32.62s / one action**,
not a full C++ rebuild. The three browser core hashes stayed unchanged; the new
receipt binds all 66 patches. The [canonical batch](native-batch66-observations.json)
passed **17/17 groups**, including GPU **34/34**, with source/SDK/core postguards.
Its exact manifest is preserved in `checkpoints/001-066.json`. Runtime and
installed-payload checks remain required; neither source nor units admit policies.

Prepared local Windows SDK/MSVC selection is supported explicitly for candidate
`sync`, `hooks`, `patch` and `build`, not only the compiler step. Sync/hooks
recheck the SDK provenance before recording success; changed inputs reject the
stage. No default/internal toolchain download or automatic selection is added.
For explicit local hooks, the downloader is disabled and the VS override points
to the validated owned installation. The separate GN/build stage still uses the
verified `win_toolchain.json` depot layout. This distinction is required because
the upstream update hook forces a download when depot mode is enabled.
For a manifest refresh, preserve the old runtime/receipts and exact source delta,
return only the verified patch-owned source changes to the pinned clean state,
then execute real sync/hooks and reapply the complete selected chain. Never edit
the old stage JSON to make a new manifest appear synchronized. Preserve original
source timestamps only for files whose exact bytes are unchanged after replay;
changed sources and generated/object files must not receive old timestamps.

### Reproducible 001–065 checkpoint

[`checkpoints/001-065.json`](checkpoints/001-065.json) preserves the exact manifest
bytes used by the first compiled 156 baseline. Its hash is bound by
`windows-runtime-observations.json`; all 65 patch files remain in `patches/`.
Historical Audio integration and GPU-fixture observations reference this frozen
manifest rather than silently inheriting future changes to `manifest.json`.
This archive neither selects a new patch nor admits a different binary.

### Batch native units on Windows

`verify_native_privacy_batch.py` validates one source/SDK/core checkpoint, builds
the required unit executables in **one Ninja invocation**, then runs every
selected exact test filter. Case failures are collected instead of hiding later
targets. Shared postguards must pass before `batch.json` can pass. Filters can
overlap; their counts are not disjoint tests. The single-target CLI remains available.

```powershell
.venv\Scripts\python.exe scripts/verify_native_privacy_batch.py `
  --workspace D:\Glint156Candidate --candidate upstream-156 `
  --report-dir D:\Glint156Candidate\native-units-new-run `
  --targets keys contexts delivery worker-handoff document-partition document-navigation `
    surface-navigation window-transport gpu-pack-copy gpu-readback gpu-metadata `
    worker-surfaces font-rasterization identity-keys identity-contexts identity-transport identity-handoff `
  --local-windows-toolchain --git-ssl-backend schannel --jobs 4
```

Use a fresh report directory. This is unit/source verification, not installed
browser or privacy admission. The 001–065 GPU fixture failure remains a failure
until its correction is promoted; batching does not skip or waive it.
Child-process temporary files also stay under that D: report directory.

## Exact-version stock control and Audio calibration

An official CfT Windows archive for **156.0.8078.36** was downloaded with its
GCS generation pinned and MD5 checked. Runtime `Browser.getVersion` independently
reported revision `5a93aa59e3043e747eff68659dcf7d20193d160e`. The per-version JSON
lookup returned 404, but that did **not** establish absence of the Windows asset.
URLs, archive/core hashes and scope: [`stock-control-observations.json`](stock-control-observations.json).

The Glint-off → CfT → Glint-off Audio matrix produced **135 captures**, all
15 configurations bit-exact across browsers and repeated Glint runs. This is
same-upstream-base calibration on one Windows host, not identical GN/toolchain
settings, math-mode/device-cohort verification or privacy admission.
[Audio evidence](../audio-dsp-math-v2/matched-stock-observations.json).

Glint's current non-official GN defaults deliberately emit a dummy CDP revision;
its source binding is the reviewed receipt plus exact runtime-core hashes, **not**
a real runtime-reported Git stamp. The unapplied [`revision-stamp.args.gn`](revision-stamp.args.gn)
selects the real LASTCHANGE without claiming an official build. Isolated upstream
header generation changed only LAST_CHANGE; GN/binaries remain frozen. Apply only
after current queues finish, rebind inputs and verify the rebuilt runtime.

## Fixture portability batch 0065

`patches/0065-native-fixture-portability.patch` is **selected by the manifest**.
It repairs the three failed fixture translation
units: worker post-evaluation synchronization, the explicit opaque-origin flags
for storage/origin APIs, and typed GPU canary storage with wire/buffer assertions.
All three repaired copies compiled using their original Clang flags and generated
dependencies; source/toolchain/GN postguards and `git apply --check` passed.

The selected 001–065 tree then passed both keep-going compile batches: **85
production object targets and all 38 mapped fixture object targets**, with final
source/toolchain/GN postguards. Dependency inputs were verified unchanged and
sync/hooks records rebound; those stages were not rerun. The browser build has
completed, followed by 62 identity-key, 37 context and 20 transport cases with
postguards. Handoff and the remaining gates are still pending. The interrupted
queue was replaced only after confirming its processes missing and all 201
reviewed inputs/browser cores unchanged; cached objects were retained, j4 unchanged.
Evidence on D: `fixture-activation65-20261029-v2/report.json`; the isolated-copy
proof remains `fixture-portability-20261029-v2/probe-v2/compile-report.json`.

## Selected candidate

The current candidate chain is **001–065**. The 001–062 browser build stopped
on three production objects with Clang unsafe-buffer errors. Append 0063 uses
bounded word spans and typed hardware option ranges; it does not suppress the
diagnostics or change identity-policy admission. See the
[test matrix](../../../docs/GLINT_TEST_MATRIX.md) for measured object/semantic
checks and linked browser baseline; no full 156 policy/runtime admission follows.
The next 001–063 run found the remaining direct Audio `memcpy`; 0064 replaces it
with a bounded domain copy. A keep-going compile batch passed all 85 selected
production object targets covering 83 patched source files. Native fixture
compilation/execution and the full browser are separate gates, not implied PASSes.

Target: **156.0.8078.36**, Chromium revision
`5a93aa59e3043e747eff68659dcf7d20193d160e`.
The October 29 official Windows Stable audit places this target behind observed
156.0.8078.75 and 157.0.8103.27. The active build remains a frozen development
checkpoint; do not change pins/patches in a live checkout. An upstream refresh,
security review and fresh runtime gates are required before production delivery.
Run `scripts/audit_native_upstream.py --candidate upstream-156 --output <fresh-D-report.json>`
to compare this manifest-selected target without changing the default 148 pin.
An isolated October 29 forward check retrieved the 185 required inputs at
156.0.8078.75 and replayed all 62 unchanged patches, preserving the checked GPU
command IDs and GRIT structure. This is source-context evidence only: the .75
target is not selected/registered for building, and no .75 binary exists from
that check. A 157 source fetch stopped after 28 inputs on HTTP 503. See the
[retained reports and limits](../../../docs/GLINT_TEST_MATRIX.md#rate-limited-cache-resume).
`manifest.json` binds each source input to an immutable Gitiles URL/hash and
each draft patch to its hash and original registered patch hash.

## Isolated Windows SDK

The target requires SDK **10.0.28000.2270**, not the default 148 SDK. Keep the
installed SDK and old workspace intact. `native/toolchain/windows-sdk-28000.json`
pins four official Microsoft NuGet packages by URL, size and SHA-256: common
headers/tools plus x64, x86 and ARM64 libraries. Download these exact archives
to an external D: directory; the helper does not download alternative versions.
It requires an installed .NET SDK for real NuGet signature verification and
compatible, Authenticode-signed x64/x86 Debugging Tools 10.0.26100.3323 or newer.

```powershell
.venv\Scripts\python.exe scripts/native_windows_sdk.py --packages D:\Glint156Packages --output D:\Glint156Sdk --debuggers "C:\Program Files (x86)\Windows Kits\10\Debuggers"
```

The output must be new. Input hashes and NuGet repository signatures are checked
before tool extraction; package libraries are mapped to the SDK's expected
`Lib/10.0.28000.0/` layout without changing bytes or relabeling versions. No
registry, global PATH, security or installed-SDK settings are changed. Failed
assemblies retain an explicit failed provenance report, not a ready SDK receipt.
The helper verifies layout, **not Chromium compilation or runtime readiness**.
Assembly alone does not select this SDK for Chromium: setting `WINDOWSSDKDIR`
was insufficient for the installed MSVC discovery path. Use the explicit owned
[local toolchain preparation](#explicit-local-windows-toolchain-selection)
below, rather than changing registry or installed SDK contents.

| Draft | Ported scope |
| --- | --- |
| 0001 | CPU/memory ceilings, renderer switches; updated Blink build/DEPS contexts |
| 0002 | Existing locale-correct MIDL helper, adapted to upstream Python indentation |
| 0003 | WebRTC routing policy; source-context replay passed |
| 0004 | Existing webdriver control, updated runtime-feature registration context |
| 0005 | Native font collection/fallback and service manager; new upstream DirectWrite local-font matcher uses the same restricted collection's font set |
| 0006 | Existing native headless-UA control; source-context replay passed |
| 0007 | Inspector Error-description safety, rebased onto the exact V8 dependency while retaining upstream builtin-getter checks |
| 0008 | Existing LevelDB Windows path separator normalization |
| 0009 | Existing extended Windows SQLite path handling and its upstream test cases |
| 0010 | Existing Windows persistent-profile namespace handling |
| 0011 | Versioned StorageKey privacy serialization and partition tests |
| 0012 | Profile-key derivation primitives and native test target; build registration moved to the new upstream file layout |
| 0013 | Existing fail-closed owned-profile key loader and loader tests |
| 0014 | Key service lifetime and ephemeral keys |
| 0015 | BrowserContext/Profile ownership and off-the-record context initialization |
| 0016 | Key-readiness contract and checks |
| 0017 | BrowserContext tests and content-test dependency registration |
| 0018-0020 | Document/worker Mojo services, bindings and renderer bootstrap consumer |
| 0021-0025 | Dedicated/shared/service-worker startup gates and owned seed handoff; dedicated-worker continuations retain the new upstream PolicyContainer |
| 0026-0028 | Worker-thread tests adapted to upstream factory/mock APIs, bootstrap failure and fixture lifetime |
| 0029-0030 | Document partition validation, navigation commit carrier/preflight, throttle registration and loader/context tests |
| 0031-0032 | Worker/document surface transport, initial windows/child frames and readiness; new InitiatorStateToken is retained end-to-end |
| 0033-0034 | Existing experimental Canvas/Audio/WebGL readback and GPU metadata candidates, not admitted profile controls |
| 0035-0045 | Origin, type/ABI, cancellation, observer lifetime and fixture/throttle corrections |
| 0046-0048 | Bounded/clipped WebGL readback and publication fixtures |
| 0049-0054 | Profile-identity derivation/mode, context/transport/handoff tests and launch policy; updated worker fixture calls |
| 0055-0058 | Existing GPU metadata protocol and attachment candidates; command appended at target ID 577 without changing upstream IDs |
| 0059-0062 | Unchanged-snapshot write avoidance, Glint branding/resources and Windows font rasterization |
| 0063 | Clang-safe hardware parsing and fixed-size Canvas word spans; no warning suppression or policy expansion |
| 0064 | Bounded Audio domain copy with unchanged message bytes; no HMAC, sample-policy or GN flag change |
| 0065 | Test-only worker synchronization/API and typed GPU canary repairs; all 38 mapped fixture objects compile |

The font service gained an independent local-font matcher upstream. Merely
repairing rejected patch context would leave that new path unrestricted. The
draft also restricts its DirectWrite font set without changing allowed fonts'
real file paths or disabling all CSS local-font matches. The default path,
including upstream test-font handling, remains unchanged when no policy is set.
The conversion uses the documented
[IDWriteFontCollection1::GetFontSet API](https://learn.microsoft.com/en-us/windows/win32/api/dwrite_3/nf-dwrite_3-idwritefontcollection1-getfontset).

## Linked native unit targets

After building the candidate, run the existing unit verifier with explicit
`--candidate upstream-156`. It checks the candidate workspace, source revision,
complete Chromium/V8 patch chain and manifest-bound sync/hooks records. It holds
the same exclusive workspace lock as sync/build/patch operations. Preserve the
baseline browser core, GN arguments and build receipt; their postguards run
even when compilation or a test fails. This is unit evidence, not proof that the
baseline browser implements the selected sources or that a policy is admitted.

```powershell
$evidence = 'D:\Glint156IdentityEvidence-1'
New-Item -ItemType Directory -Path $evidence -ErrorAction Stop
foreach ($target in 'identity-keys', 'identity-contexts', 'identity-transport', 'identity-handoff') {
    .venv\Scripts\python.exe scripts/verify_native_privacy_units.py --workspace D:\Glint156Candidate --candidate upstream-156 --target $target --report "$evidence\$target.json" --local-windows-toolchain --git-ssl-backend schannel --jobs 4
    if ($LASTEXITCODE -ne 0) { throw "Glint unit target failed: $target" }
}
```

The local selection derives the compiler/SDK environment from the prepared
layout; do not supply a different `--vs-installation`. `--git-ssl-backend` has the
same explicit Windows selection as the build helper. Missing/skipped/failed test
cases are rejected; source and core changes invalidate the report. The four
filters contain 62/37/20/15 cases, not a claim that those cases ran on 156.

## Reproduce source-context verification

Use an unmodified checkout of the exact target revision, or a directory with
the exact `source_files` listed in the manifest. No dependencies need downloading
for this limited gate. It rejects mismatched/linked source inputs and changed
patches before creating output. It does not modify the supplied source tree.

```powershell
.venv\Scripts\python.exe scripts/verify_native_rebase_draft.py --source D:\Glint156\src --output D:\Glint156\replay-1
```

The manifest pins V8 revision `8ce248ef8f7f71c04f7faaac249a37d340279f52`
from the exact Chromium DEPS file, not from an unrelated Stable rollout.
Patch 0007 runs in the separate `v8` repository directory. The verifier checks
the DEPS binding before creating output and disables Git autocrlf for patch
application, regardless of the user's global configuration. It rejects BOM/CRLF
patches rather than rewriting entire source files as an incidental rebase.

The output must be new, external and outside the input tree. The gate copies
only checksummed inputs into its owned scratch directory, checks/applies all
62 patches in sequence, parses included Python/DEPS files and rechecks inputs.
Real local evidence: `upstream-156-replay-v8/report.json` on D: **62/62 passed**,
165 upstream source inputs, including original binary resource inputs. Earlier
reports cover their smaller patch sets. After an upstream HTTP 429, 24 missing
inputs were recovered from the owned immutable Git baseline and individually
checked against the already recorded upstream hashes; no alternate source or
unchecked content was substituted.
15 resulting GN/GNI files passed syntax parsing with the existing installed
GN tool, without changing bytes: `upstream-156-gn-syntax-v4.json`. This is not
`gn gen`, `gn check`, dependency-graph validation or execution of C++ tests.
`upstream-156-abi-resources-v1.json` separately confirms preservation of all
321 upstream GLES2 command ordinals, append-only command 577, and unchanged
GRIT XML structure/attributes. It does not regenerate GPU code or compile GRIT.
The earlier v2 report covers only the first six drafts. The v3 scratch replay
was superseded after detecting CRLF-only churn in generated V8 patch context;
v4 uses the compact LF patch and explicit autocrlf-disabled application.
The Windows standalone C++ policy suite also passed with added real DirectWrite
font-set conversion and allowed/excluded unique-name positive controls. This
does not compile the new Chromium local-font matcher translation unit.

Readback candidates are retained for research/regression, not silently enabled
for user profiles. Their previously observed explicit-pixel/HDR compatibility
problems on 148 are not fixed by a source rebase. No 156 compatibility result,
production admission or Canvas/Audio/GPU protection claim follows from replay.

## Still required

- Complete full-source/API review and select the candidate explicitly in build
  tooling against the full checkout; the default build lock/registered patch chain still target 148.
- Check all new upstream paths that could bypass old policy boundaries.
- Run GN/checkdeps and compile against the target's actual dependency set.
- Repeat complete runtime, rendering, storage, proxy, restart and crash gates.
- Review upstream security changes and update the reviewed package only after
  packaging and rollback checks. No manifest flag or successful patch replay
  admits production or grants the existing 148 package's capabilities to 156.

The replay gate also checks source invariants automatically: existing GLES2
command names/ordinals must remain unchanged, with exactly one append-only
metadata command; branding may change GRIT text but not its element structure
or attributes. Failure keeps `passed=false` in the report. The complete run
`upstream-156-replay-v9/report.json` passed these checks (321 original commands,
new ordinal 577). These checks do not replace code generation or compilation.

## Optional GPU source regeneration

The manifest now includes **185 inputs**: the earlier 165 plus the exact target
generator library, `.clang-format` and the remaining generated GPU sources.
With all inputs present, source regeneration is explicit:

```powershell
python scripts/verify_native_rebase_draft.py --source D:/path/to/verified-inputs --output D:/path/to/new-report --formatter D:/path/to/clang-format.exe
```

`--formatter` runs the actual target generator in the new owned replay tree,
formats with the checksummed target style and requires the complete generated
file set to remain byte-identical. Missing, changed or unexpected generated
files fail the gate. The formatter executable is measured before/after, not
automatically trusted as the target's pinned toolchain.

Local evidence `upstream-156-replay-v10/report.json`: **62/62 patches, 30/30
generated files unchanged**, source invariants and input guards passed. This
used the existing clang-format 21 binary; its target dependency provenance is
**not verified**. Target-toolchain reproduction, C++ compilation, GRIT build
and runtime gates remain outstanding. No browser compilation was started.

## Explicit candidate build selection

`scripts/native_build.py --candidate upstream-156` selects this manifest's
Chromium/V8 revisions and draft patches without modifying the default 148
lock. Start with a **new empty** workspace on D:, never the existing reviewed
checkout or the sparse replay input tree:

```powershell
python scripts/native_build.py preflight --workspace D:/Glint156Candidate --candidate upstream-156 --jobs 4
```

Preflight is read-only. When builds are explicitly resumed, the same selection
must accompany `bootstrap`, `sync`, `hooks`, `patch` and `build`. The first mutating step
claims the workspace with a revision marker. Default or other-revision commands
cannot reuse it; candidate selection cannot claim an existing nonempty checkout.
The build requires the **complete draft chain already applied** to the full
Chromium/V8 checkouts, rejects unrelated/partial source changes, and revalidates
patches after compilation. Apply the chain explicitly after successful hooks,
before building (never while another process is using/building that checkout):

```powershell
python scripts/native_build.py patch --workspace D:/Glint156Candidate --candidate upstream-156
```

The patch action prepares both repositories in temporary Git indexes and checks
both complete deltas before touching source files. The real indexes stay intact.
Already fully applied chains are validated without reapplying. Partial or
unrelated edits are rejected. On an application/verification error, only an exact
owned patch state can be reversed; concurrent user edits prevent automatic
rollback and are retained for inspection. Private deltas and a JSON report remain
under `chromium/glint-candidate-patches-*`. This is not a power-loss-atomic
transaction across two repositories. Tiny real Git fixtures cover binary edits,
new files, preflight failures, second-repository failure, rollback and concurrent
edit preservation. On 2026-10-28 the complete chain was also applied to the full
owned Chromium 156/V8 checkout and passed the source-chain guards.
All mutating `native_build.py` stages also hold an OS-backed workspace lock.
A concurrent script invocation fails before tool/source changes; read-only
preflight remains available. The OS releases the lock after a process exits,
so a retained `glint-build.lock` file is not a stale-PID recovery problem.
This coordinates cooperating script invocations only: manually launched tools
and orphaned child processes still require an actual process check before
changing source. Windows lock contention and owner termination are covered by
real subprocess tests; Linux/macOS behavior is not runtime-verified.
Stage records and build receipts bind the candidate manifest hash; a default
148 stage record cannot satisfy the 156 gate. Runtime verification remains false.

The candidate explicitly reuses depot_tools revision
`a03dfbf7f2d1cefa2795d81d59ca4f16c8616a8f`. Dependency sync and hooks completed
on 2026-10-28. GN generation passed; the first compilation failed in unified
system modules before linking. This is **not** a verified 156 runtime.

### Explicit local Windows toolchain selection

For a deliberately prepared owned `build/win_toolchain.json`, the candidate
build accepts `--local-windows-toolchain`. It validates the exact VS 2026 local
layout without VC junctions, pinned official SDK provenance and every recorded SDK file, and binds
environment scripts/compiler executables to a before/after digest. The flag is
Windows-only and build-only; it is rejected for default 148 and for sync/hooks.
There is no automatic SDK fallback or global environment change.

```powershell
python scripts/native_build.py build --workspace D:/Glint156Candidate --candidate upstream-156 --jobs 4 --git-ssl-backend schannel --local-windows-toolchain
python scripts/verify_native_privacy_units.py --help
```

The unit verifier accepts the same explicit local toolchain flag with a
candidate selection, holds the workspace lock and checks toolchain drift even
when compilation/testing fails. Do not run it alongside a browser build.
For a fresh, explicitly claimed candidate workspace with hooks complete and
**no existing** `chromium/src/build/win_toolchain.json`, prepare the layout with
the public helper. Supply the original signature-verified SDK assembly from
`scripts/native_windows_sdk.py`, not a previously prepared composite layout:

```powershell
python scripts/native_windows_toolchain.py --workspace D:/Glint156Fresh --candidate upstream-156 --vs-installation D:/CamouFlowNative/toolchain/BuildTools --sdk D:/Glint156Fresh/toolchain/windows-sdk-28000 --output D:/Glint156Fresh/toolchain/local-msvc-sdk
```

The helper copies installed VC, **DIA SDK** and the Windows SDK into a **new** owned directory,
checks source/destination hashes, generates x86/x64 SetEnv files in the same
canonical namespace and writes Chromium's ignored toolchain metadata only
after copying. It requires 20 GiB free and rejects links, input drift, excessive
size/file counts, unsafe batch paths, existing output/configuration and a held
workspace lock. A failed preparation retains provenance without admitting the
layout; concurrent configuration edits are preserved. It does not install,
download, redistribute or modify the original compiler/SDK. No Google toolchain
is impersonated. Original installations and global settings remain untouched.

Do not run this command against the currently active prepared workspace. Its
existing config is deliberately not replaced. The initial VC junction layout
failed Siso dependency resolution; materialized copies subsequently compiled
both system module targets. A subsequent full build stopped on 19 Dawn DXIL
actions because the original composite omitted `DIA SDK/include/dia2.h`.
The local selection now requires and hashes DIA headers, x86/x64 GUID libraries
and runtime DLLs; the preparer copies the installed DIA tree without COM
registration or global include-path changes. Missing DIA fails before copying.
After materializing the installed DIA files, the actual Dawn `lib_dxildia.lib`
target compiled successfully with unchanged source/toolchain postguards
(`dia-sdk-compile-20261029-v1/report.json`). The full j4 build resumed with
existing objects; this library probe is not a linked browser or WebGPU admission.
The public preparer is covered by small real-file
fixtures; running it through a fresh complete 156 build remains a separate gate.

### Rendering checks after linking

The existing rendering verifier supports independent gamma/contrast checks:

```powershell
python scripts/verify_native_font_rendering.py --series text-tuning --candidate upstream-156 --executable D:/Glint156Candidate/chromium/src/out/CamouFlowNative/chrome.exe --output D:/Glint156Candidate/text-tuning-156-v1
```

This requires a complete matching candidate receipt and unchanged runtime,
resources, source inputs and screenshots. The nine-case series checks separate
gamma-only and contrast-only effects in all eight scopes, fidelity and restart
stability. Its completed 148 run does not count as a 156 result or enable
manager admission. See the [test matrix](../../../docs/GLINT_TEST_MATRIX.md).

To include controlled editing/web-font/export workloads, add an explicit real
font with widths distinguishable from the native monospace control. The
candidate checkout supplies the WPT Ahem test font:

```powershell
python scripts/verify_native_font_rendering.py --series text-tuning --candidate upstream-156 --executable D:/Glint156Candidate/chromium/src/out/CamouFlowNative/chrome.exe --output D:/Glint156Candidate/text-tuning-156-workloads-v1 --workload-font D:/Glint156Candidate/chromium/src/third_party/blink/web_tests/external/wpt/fonts/Ahem.ttf
```

The helper checks Unicode input, native selection/undo/redo, checksummed font
loading, DOM/SVG/Canvas metrics, PNG round trips, UTF-8 download and bounded PDF
output. Artifacts remain in the new private evidence directory. Semantic
changes across modes/restarts or changed artifacts fail the gate. IME, PDF
content equivalence and third-party application compatibility are not implied.
Run the public verifier only after the builder exits; matched research on
isolated 148 binaries is recorded separately from candidate verification.

Add `--profile-concurrency 2` to keep pairs of differently configured private
profiles live during measurement. The sequential default stays unchanged.
The runner checks five-store separation/persistence and rendering against the
same controls, closes every owner even if its peer fails and stops on retained
resources. The final odd case runs alone. These bounded runner batches are not
a two-profile application limit. Missing peers, storage leaks, timeouts or
changed evidence do not silently downgrade to a sequential pass.

### Full runtime suite after linking and identity units

The existing eight-gate runner now accepts an explicit candidate selection:

```powershell
.venv\Scripts\python.exe scripts/verify_native_suite.py --candidate upstream-156 --executable D:/Glint156Candidate/chromium/src/out/CamouFlowNative/chrome.exe --report-dir D:/Glint156Candidate/runtime-156-new
```

Wait for browser and native-unit builders to exit first. The candidate path
rejects active builders, requires the matching adjacent build receipt/GN
arguments, and binds every selected gate to the manifest, full ordered
Chromium/V8 chain, executable/DLL core and exact observed browser version.
Installed-copy verification instead validates the immutable package's embedded
receipt and candidate metadata; use the existing explicit store/checksum/DLL
directory options. No receipt search or automatic version fallback is used.
Omitting `--candidate` retains the previous control/default verification path.

Receipt/argument changes during initial measurement reject before creating
evidence. Manifest/patch/receipt/argument or core drift between gates stops the
remaining run and retains partial reports. Individual gate failures are kept
without being converted into successful evidence. Only all eight selected gates
can set `full_suite: true`; candidate reports keep `privacy_admitted: false`.
`full_suite` records requested coverage, not success: `passed` must also be true.
This binds local unsigned provenance, not a trusted publisher signature.

The new paths passed synthetic flat/installed and failure fixtures. They have
**not run on a linked 156 browser** yet and cannot establish new policy admission.

### Development staging and packaging after linking

The Windows staging/packaging helpers now accept an explicit
`--candidate upstream-156`. Omitting it still selects the original 148 lock;
there is no receipt-driven version fallback. Staging holds the same OS workspace
lock as compilation, validates candidate sync/hooks/source/receipt and local
toolchain, and rechecks all inputs afterward. A marked candidate workspace
cannot be staged through the default path.

**Do not run these commands beside the active browser/unit build.** After the
156 browser links and the selected native tests finish, use new evidence paths:

```powershell
$workspace = 'D:/Glint156Candidate'
$output = "$workspace/chromium/src/out/CamouFlowNative"
$evidence = "$workspace/package-156-new"
New-Item -ItemType Directory -Path $evidence -ErrorAction Stop
.venv\Scripts\python.exe scripts/verify_native_runtime.py --executable "$output/chrome.exe" --work-dir $evidence --report "$evidence/runtime.json"
if ($LASTEXITCODE -ne 0) { throw 'Candidate runtime checks failed' }
.venv\Scripts\python.exe scripts/stage_native_windows.py --workspace $workspace --candidate upstream-156 --git-ssl-backend schannel --local-windows-toolchain --jobs 4 --report "$evidence/staging.json"
if ($LASTEXITCODE -ne 0) { throw 'Candidate staging failed' }
.venv\Scripts\python.exe scripts/package_native_windows.py --candidate upstream-156 --build-output $output --staged "$output/gen/chrome/installer/mini_installer/mini_installer/temp_installer_archive/Chrome-bin" --runtime-report "$evidence/runtime.json" --archive "$evidence/glint-156-dev.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Candidate packaging failed' }
```

Packaging requires the complete ordered Chromium/V8 receipt chain and current
manifest/patch hashes, the exact executable/DLL core, all required lifecycle
checks and matching official staged files. Manifest/patch changes during
archiving fail before publication. The archive retains candidate provenance,
uses `0.2.0-dev`, and keeps `native_patch_runtime_verified: false`.

### Verify the installed development payload

After successful packaging, install into a **new isolated store**, without
activation. Do not point this check at the manager's working binary store:

```powershell
$archive = "$evidence/glint-156-dev.tar.gz"
$store = "$evidence/isolated-store"
if (Test-Path -LiteralPath $store) { throw 'Use a new isolated binary store' }
$digest = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
$installedJson = .venv\Scripts\python.exe scripts/native_release.py --store $store install --archive $archive --sha256 $digest
if ($LASTEXITCODE -ne 0) { throw 'Candidate installation failed' }
$installed = $installedJson | ConvertFrom-Json
$libraries = Join-Path (Split-Path -Parent $installed.executable_path) $installed.chromium_version
.venv\Scripts\python.exe scripts/verify_native_suite.py --candidate upstream-156 --executable $installed.executable_path --windows-library-directory $libraries --release-store $store --release-sha256 $digest --report-dir "$evidence/installed-suite"
if ($LASTEXITCODE -ne 0) { throw 'Installed candidate runtime checks failed' }
```

The store verifies every payload file; the suite binds the installed candidate,
embedded receipt, versioned DLL layout and runtime core to all eight gates.
Do not add `--activate` or replace a user profile for this check. Installation
and successful relocated tests do not grant production or experimental policy
admission. Compatible rollback needs its own measured previous release; the
store intentionally blocks an older Chromium version, including 156 → 148.

The first actual 001–066 development payload completed official staging
(39 build actions, 6m29.21s), archive creation and isolated installation without
activation. All eight raw and installed browser gates passed, **160 checks per
layout**. This precedes the Python integration batch; canonical post-integration
checks remain separate. Audio-v1 fidelity still fails and no new policy or
production admission follows. Compatible cross-version rollback is not verified.
