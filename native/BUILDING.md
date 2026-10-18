# Building Glint on Windows

Glint is CamouFlow's own Chromium fork. This guide builds the **registered
development patch chain**, not Camoufox/CloakBrowser and not an admitted release.
Linux/macOS own-fork builds are deferred. The latest verified Windows browser is
**001–061**: all eight runtime gates (160 checks) and compiled Glint branding
passed. Registered source now includes **0062**, the experimental Windows font
rasterization package. Its browser now links and its mode/restart/first-script
compatibility comparison passed. The first full runtime regression hit a font
download `NetworkError`; attributed repeats passed but the cause is unresolved.
A fresh full-suite repeat is in progress;
do not transfer the 001–061 results to it. Exact results and retained failures:
[test matrix](../docs/GLINT_TEST_MATRIX.md).

The five new font-policy fixtures use the existing Chromium `gfx_unittests`
target and the normal isolated verifier:

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_privacy_units.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\font-policy-new.json --vs-installation D:\CamouFlowNative\toolchain\BuildTools --jobs 4 --target font-rasterization
```

Use a fresh report path. Passing these policy units does not prove renderer
startup, actual pixels, worker delivery or fingerprint acceptance.

## Requirements

- Windows 10+, x64, NTFS; upstream recommends more than 16 GiB RAM.
- Git and the application Python 3.12 environment with `requirements.txt` installed.
- At least **180 GiB free** before each heavy helper operation.
- Visual Studio 2026 C++ Desktop workload with MFC/ATL; Windows SDK
  10.0.26100.7705 and SDK Debugging Tools 10.0.26100.3323 or newer.
- A dedicated absolute workspace on **D:**, outside this repository.

Toolchain requirements come from the pinned checkout's
[`docs/windows_build_instructions.md`](https://chromium.googlesource.com/chromium/src/+/8625e066febc721e015ea99842da12901eb7ed73/docs/windows_build_instructions.md).
Do not disable security or modify global Git/PATH to make a build pass.

`build-lock.json` pins Chromium/depot_tools and limits builds to four jobs.
`args.gn` defines the development configuration. Cache, dependencies, temporary
files, source and binaries stay in the workspace; only project source belongs
in public Git. Never include private backend code or credentials.

## 1. Prepare a fresh workspace

Run from the application repository root in PowerShell. Set the toolchain path
to an **installed** Visual Studio instance, not its downloaded bootstrapper.
Stop on any nonzero exit code; PowerShell does not do that automatically for
native commands. Never run two builds or modify source during an active build.

```powershell
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$workspace = 'D:\CamouFlowNative'
$source = Join-Path $workspace 'chromium\src'
$output = Join-Path $source 'out\CamouFlowNative'
$env:vs2026_install = 'D:\CamouFlowNative\toolchain\BuildTools'
$env:GOMEMLIMIT = '3GiB'

foreach ($stage in @('preflight', 'bootstrap', 'sync', 'hooks')) {
    & $python scripts/native_build.py $stage --workspace $workspace --jobs 4
    if ($LASTEXITCODE -ne 0) { throw "Glint preparation failed: $stage" }
}
```

`GOMEMLIMIT` is a soft Go heap limit, not a cap on total compiler memory.
Successful sync/hooks write stage records binding revisions and dependency
snapshots. Do not manufacture those records. Sync rejects modified source:
**do not rerun the fresh-workspace sequence over an already patched checkout**.

## 2. Apply the registered patches

`native_build.py build` checks applied patches but **does not apply them**.
For a fresh checkout after successful hooks, apply numbered production patches
in order. Patch 0007 belongs to the separate V8 repository, not Chromium root.
Do not add unregistered draft patches to this loop; they must first be registered
in the exact source replay gate and have their verification updated.

```powershell
foreach ($patch in (Get-ChildItem 'native\patches\*.patch' | Sort-Object Name)) {
    $target = $source
    if ($patch.Name -eq '0007-native-inspector-error-accessors.patch') {
        $target = Join-Path $source 'v8'
    }
    git -C $target apply --check $patch.FullName
    if ($LASTEXITCODE -ne 0) { throw "Patch check failed: $($patch.Name)" }
    git -C $target apply $patch.FullName
    if ($LASTEXITCODE -ne 0) { throw "Patch application failed: $($patch.Name)" }
}
```

This loop is not transactional: if it stops, earlier patches remain applied.
Inspect the failed checkout; do not rerun the whole loop or reset/delete it
blindly. Build rejects changes that cannot be replayed exactly from registered
patches, including partial overlapping chains and unrelated edits.

## 3. Compile

```powershell
& $python scripts/native_build.py build --workspace $workspace --jobs 4
if ($LASTEXITCODE -ne 0) { throw 'Glint build failed' }
```

Output: `$output\chrome.exe` and required resources/DLLs. A successful build
writes `$output\camouflow-build.json` with the measured executable, arguments
and patch hashes. A receipt is not privacy/runtime proof. An object-only build
does not produce a new browser. Keep a verified baseline outside the mutable
output before rebuilding; failed/interrupted builds may leave mixed artifacts.

For incremental rebuilds, retain source/dependencies and `out\CamouFlowNative`,
then rerun **build**, not sync. Shared header or GN changes can rebuild many
dependent objects; incremental does not mean instant.

## 4. Verify the exact binary

Use fresh report paths outside source/application repositories:

```powershell
& $python scripts/verify_native_suite.py --executable "$output\chrome.exe" --report-dir "$workspace\verification-new"
if ($LASTEXITCODE -ne 0) { throw 'Glint runtime suite failed' }
& $python scripts/verify_native_privacy_units.py --workspace $workspace --report "$workspace\privacy-units-new.json" --vs-installation $env:vs2026_install --jobs 4
if ($LASTEXITCODE -ne 0) { throw 'Glint privacy units failed' }
& $python scripts/verify_native_privacy_units.py --workspace $workspace --report "$workspace\privacy-contexts-new.json" --vs-installation $env:vs2026_install --jobs 4 --target contexts
if ($LASTEXITCODE -ne 0) { throw 'Glint BrowserContext units failed' }
```

The runtime suite covers runtime, hardware, WebRTC, automation, fonts, identity,
CDP and combined policies. Private-key units currently require 43 named cases
for chain 001–016, including readiness; older 001–015 reports covered 33.
Patch 0017 adds 20 required real content-layer BrowserContext cases to
`content_unittests`, executed separately with `--target contexts`. This target
may require substantial additional compilation; do not run concurrent builds.
Patches 0018-0020 register the document/worker endpoints, worker consumer and
34 required native cases. To verify this separate gate after context units:

```powershell
& $python scripts/verify_native_privacy_units.py --workspace $workspace --report "$workspace\privacy-delivery-new.json" --vs-installation $env:vs2026_install --jobs 4 --target delivery
if ($LASTEXITCODE -ne 0) { throw 'Glint delivery units failed' }
```

Patches 0018-0020 alone do not connect the consumer to worker startup. The separate
0021-0026 stack wires dedicated/shared/service workers and owned Blink seed
transport behind `--glint-worker-canvas-bootstrap-test`; it additionally needs
the existing browser-owned key-service opt-in for a successful response. The flag
is not a manager privacy capability. Later numbered patches register Canvas
helpers/readback hooks, document bootstrap and branding. Registration
alone is not successful compilation or execution. The four `WorkerThreadTest`
handoff cases belong to `blink_unittests`, not this 34-case content gate.
The scripts do not admit capabilities automatically or prove CAPTCHA success.
Do not substitute a passing old report, SDK binary or Python tests for new
own-fork runtime evidence. Canvas/GPU/audio protection is not complete.

### Worker startup development probe

After a successful 001-027 browser build, run the separate owned fixture probe:

```powershell
& $python scripts/verify_native_worker_startup.py --executable "$output\chrome.exe" --work-dir "$workspace\worker-startup-probe" --report "$workspace\worker-startup-new.json"
if ($LASTEXITCODE -ne 0) { throw 'Glint worker startup probe failed' }
```

The probe requires the exact registered 0015-0027 patch hashes in the local build
receipt and measures the executable/core DLLs before and after. It covers forty
classic/module dedicated/shared/service-worker cases: baseline and key-enabled
startup/restart, plus unavailable-policy rejection. Ready service-worker restart
uses the retained registration without re-registering and requires a new body
execution beacon with no main-script HTTP fetch. Explicit third-party partitioning
is enabled in this controlled probe; this does not prove every default setting.
Worker profiles are isolated outside the public checkout using NativeRuntime's
existing identity/lock/lifecycle path. A timeout is inconclusive, not a rejection
pass. Shared-client cases require one worker body/script fetch across two pages,
continued replies after the first page closes and rejection of both clients when
policy is unavailable. The probe measures the driver's default disabled-feature
argument and replaces only its partitioning exclusion, preserving other features.
Diagnostic `--enable-automation` permits effective command-line inspection;
these are not anti-bot score runs or proof of the manager's default launch flags.
This probe does not verify Canvas keys/readback, nested workers, early startup
termination, network outages or capability admission. The four Blink handoff
unit cases still require their own linked execution.

The four Blink worker-scope ownership cases have a separate strict target:

```powershell
& $python scripts/verify_native_privacy_units.py --workspace $workspace --vs-installation "$workspace\toolchain\BuildTools" --jobs 4 --target worker-handoff --report "$workspace\worker-handoff-new.json"
if ($LASTEXITCODE -ne 0) { throw 'Glint worker handoff units failed' }
```

This builds `blink_unittests` and selects exactly the four Glint `WorkerThreadTest`
cases, not the whole upstream suite. It still compiles the target's dependencies;
do not assume four selected tests make its initial build small. Run only after
other builders and mutable-output browser probes finish. The report checks exact
completed case coverage, test executable hash and unchanged browser/GN/receipt
and registered source inputs. Success proves Blink scope ownership, not that a
real browser host delivered the correct partition key or that Canvas is protected.

## 5. Package and deliver separately

`scripts/package_native_windows.py` requires the official mini-installer staged
**Chrome-bin** tree, a matching build receipt and passing `runtime.json` for the
same binary/core DLLs. Do not ZIP arbitrary build output or ship only chrome.exe.
The ordinary build command builds `chrome`, **not the installer staging
pipeline**. Run the separate official archive target only after browser probes
finish and no other builder owns this output:

```powershell
& $python scripts/stage_native_windows.py --workspace $workspace --vs-installation "$workspace\toolchain\BuildTools" --jobs 4 --report "$workspace\official-staging-new.json"
if ($LASTEXITCODE -ne 0) { throw 'Glint official staging failed' }
```

This uses Chromium's `mini_installer_archive` target, not a hand-picked file
copy. It checks the pinned source, build receipt, core DLLs, GN and patch chain
before/after the action without rewriting GN or the browser receipt. The target
may rebuild installer dependencies; its duration is not just archive time.
The proof records the resulting `Chrome-bin` path under the build's `gen` tree.
That generated staging directory is mutable: package it before starting another
build. Do not treat a staging success as relocated runtime or privacy admission.

For the official staging tree reported by this command:

```powershell
& $python scripts/package_native_windows.py --build-output $output --staged "$output\gen\chrome\installer\mini_installer\mini_installer\temp_installer_archive\Chrome-bin" --runtime-report "$workspace\verification-new\runtime.json" --archive "$workspace\glint-dev-new.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Glint packaging failed' }
```

Archives/reports must use new paths. The packager checks payload against compiled
output and retains licenses/credits. It requires the receipt's complete browser
core to match the report and guards receipt, GN, report, licenses and every
compiled payload source until the archive is published. Installation/activation/rollback use
`scripts/native_release.py`; activation requires health checks and must not
replace a working runtime based only on successful compilation. Windows
development archives are unsigned. No production release is implied here.

After installing the archive into a separate owned store with
`native_release.py install`, verify the **installed** executable, not the original
build output. Use the returned `executable_path`, release checksum and exact
`chromium_version` directory; do not copy DLLs beside the launcher:

```powershell
& $python scripts/verify_native_suite.py --executable $installedExe --windows-library-directory $installedLibraries --release-store $store --release-sha256 $releaseSha256 --report-dir "$workspace\relocated-suite-new"
if ($LASTEXITCODE -ne 0) { throw 'Glint relocated package verification failed' }
```

`$installedLibraries` is the installed EXE's parent joined with its declared
Chromium version. The suite verifies the store's complete checksummed payload
around each gate, binds lifecycle observations to that release, and stops on
payload drift. Evidence/profiles must stay outside the binary store. Identity,
runtime and combined gates receive the explicit versioned DLL directory.
Success does not enable experimental policies or prove publisher signatures.
Activate only after successful verification; test rollback in this owned store,
not the user's configured installation or profiles.

## Verification boundary

See the [clean-workspace audit](../docs/GLINT_WINDOWS_BUILD_AUDIT.md) for observed
steps and the unresolved first-download transport limitation.

### Troubleshooting

- Bootstrap requires HTTPS access to `chrome-infra-packages.appspot.com` and its
  download redirects. A successful Git clone is not sufficient. The pinned
  upstream PowerShell downloader has no explicit request timeout; if it stalls,
  inspect the owned process tree and test that endpoint with a bounded request.
  Do not disable TLS/security, run overlapping bootstrap processes or replace a
  failed fresh download with cached files and call it a clean build.
- depot_tools global-Git recommendations are warnings. Keep the project's
  workspace-local configuration instead of applying suggested global changes.
- On `LLVM ERROR: out of memory`, retain the failed report/log/reproducer and
  inspect physical memory and Windows commit headroom. `-j4` limits concurrent
  local work, not total memory: see the [official Siso concurrency documentation](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/siso_tips.md).
  Known heavy object targets can be compiled separately with the same `-j4`,
  production flags and diagnostics, then reused by the cached full build.
  This worked for generated navigation, instrumentation and CSS shorthand
  objects on 001-058. Do not silently lower an explicitly requested job count,
  suppress diagnostics, rerun sync or erase cached objects to recover from OOM.
- Do not launch a manual browser from an output directory that is being built.
  Use a separate complete runtime package instead. On Windows, a running
  browser can retain mapped runtime files, including the V8 context snapshot,
  and prevent build actions from replacing them. Preserve the failed log and
  cached objects; let the user finish their session before replacing runtime
  files. A successful snapshot generated elsewhere does not complete the
  original build action or prove the test binary passed.
  Patch 0059 avoids rewriting an already byte-identical snapshot, with a
  size-bounded read and exact byte comparison. A changed snapshot still requires
  a writable destination; write errors are not suppressed. This resolved the
  identical-snapshot action while a manual browser remained open, but is not
  permission to replace its DLLs or other mapped runtime files.
  An unpacked Windows runtime also needs its versioned assembly `.manifest`,
  resources and locale files, not just `chrome.exe` and DLLs. Verify a copied
  rollback runtime actually launches before starting a build that overwrites
  the original output. The checked 001-047 copy on D contains 509 hashed files
  and passed an isolated headless launch before the 001-059 browser build.

Individual preparation, build and runtime stages have been exercised in the
development workspace. This consolidated fresh-machine sequence has **not yet
been replayed end to end on a new machine**. Current per-build runtime, branding,
experimental rendering and unresolved failure evidence is maintained in the
[test matrix](../docs/GLINT_TEST_MATRIX.md). Older successful checks do not
automatically admit a new binary, relocated package or fingerprint capability.
