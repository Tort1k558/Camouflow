# Building Glint on Windows

Glint is CamouFlow's own Chromium fork. This guide builds the **registered
development patch chain**, not Camoufox/CloakBrowser and not an admitted release.
Linux/macOS own-fork builds are deferred. The branding candidate in `branding/`
is not a registered build input. Context tests are registered in patch 0017;
document/worker IPC unit infrastructure is registered in patches 0018-0020.
Worker startup gates and thread handoff are registered in patches 0021-0026,
including four unexecuted Blink handoff cases. They do not enable Canvas privacy.

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
Do not add draft/branding patches to this loop; they must first be registered
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
is not a manager privacy capability. Canvas helpers/readback hooks, document
bootstrap and branding are still outside the registered chain. Registration
alone is not successful compilation or execution. The four `WorkerThreadTest`
handoff cases belong to `blink_unittests`, not this 34-case content gate.
The scripts do not admit capabilities automatically or prove CAPTCHA success.
Do not substitute a passing old report, SDK binary or Python tests for new
own-fork runtime evidence. Canvas/GPU/audio protection is not complete.

### Worker startup development probe

After a successful 001-026 browser build, run the separate owned fixture probe:

```powershell
& $python scripts/verify_native_worker_startup.py --executable "$output\chrome.exe" --work-dir "$workspace\worker-startup-probe" --report "$workspace\worker-startup-new.json"
if ($LASTEXITCODE -ne 0) { throw 'Glint worker startup probe failed' }
```

The probe requires the exact registered 0015-0025 patch hashes in the local build
receipt and measures the executable/core DLLs before and after. It covers thirty
classic/module dedicated/shared/service-worker cases: baseline and key-enabled
startup/restart, plus unavailable-policy rejection. Ready service-worker restart
uses the retained registration without re-registering and requires a new body
execution beacon with no main-script HTTP fetch. Explicit third-party partitioning
is enabled in this controlled probe; this does not prove every default setting.
Worker profiles are isolated outside the public checkout using NativeRuntime's
existing identity/lock/lifecycle path. A timeout is inconclusive, not a rejection
pass. This probe does not verify Canvas keys/readback, nested workers, early
termination, network outages or capability admission. The four Blink handoff
unit cases still require their own linked execution.

## 5. Package and deliver separately

`scripts/package_native_windows.py` requires the official mini-installer staged
**Chrome-bin** tree, a matching build receipt and passing `runtime.json` for the
same binary/core DLLs. Do not ZIP arbitrary build output or ship only chrome.exe.
The public build command currently builds `chrome`, **not the installer staging
pipeline**; end-to-end fresh-machine packaging remains a separate work item.

For an already prepared official staging tree:

```powershell
& $python scripts/package_native_windows.py --build-output $output --staged "$workspace\staging\Chrome-bin" --runtime-report "$workspace\verification-new\runtime.json" --archive "$workspace\glint-dev-new.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Glint packaging failed' }
```

Archives/reports must use new paths. The packager checks payload against compiled
output and retains licenses/credits. Installation/activation/rollback use
`scripts/native_release.py`; activation requires health checks and must not
replace a working runtime based only on successful compilation. Windows
development archives are unsigned. No production release is implied here.

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
- On `LLVM ERROR: out of memory`, retain the output and retry the build command
  with `--jobs 2` (or `--jobs 1` for a single large object). Four jobs are a
  concurrency maximum, not a total-memory cap. Do not rerun sync or erase cached
  objects to recover from an OOM.

Individual preparation, build and runtime stages have been exercised in the
development workspace. This consolidated fresh-machine sequence has **not yet
been replayed end to end on a new machine**. Existing runtime proof covers the
001–010 baseline; newer key/context code and prepared branding/readiness must
be compiled and verified before claiming them in a released browser.
