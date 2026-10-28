# Chromium 156 rebase candidate

**Draft source port, not an enabled engine or a compiled browser.** The active
build lock and registered 001-062 chain still target Chromium 148.0.7778.96.

Target: **156.0.8078.36**, Chromium revision
`5a93aa59e3043e747eff68659dcf7d20193d160e`.
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

The helper copies installed VC and the SDK into a **new** owned directory,
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
both system module targets. The public preparer is covered by small real-file
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
