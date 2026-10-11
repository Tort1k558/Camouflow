# Native Chromium source workspace

This directory tracks the public CamouFlow Native build inputs. Chromium source,
dependencies, tools and output stay **outside this repository**, on the approved
`D:\CamouFlowNative` workspace. Backend source and credentials are not included.

`build-lock.json` pins full upstream Chromium and bootstrap depot_tools commits.
Chromium's pinned `DEPS` defines its own dependency revisions/CIPD instances,
including its vendored depot_tools; the bootstrap tool is pinned separately and
self-updates are disabled. `args.gn` sets an unbranded, local release build with
reduced symbols and no paid remote build service. Compilation uses four jobs to
limit pressure on the inspected 24-GiB machine.

## Windows preparation

The selected upstream revision's [Windows build instructions](https://chromium.googlesource.com/chromium/src/+/8625e066febc721e015ea99842da12901eb7ed73/docs/windows_build_instructions.md)
require an x64 host, at least 8 GiB RAM, NTFS and at least 100 GiB free. The local
script conservatively requires 180 GiB free before each heavy operation. The
approved D: volume was inspected as NTFS with approximately 395 GiB free before
source transfer; host RAM is 24 GiB, CPU has six cores/twelve threads.

Install the native C++ Build Tools and ATL/MFC components according to the pinned
upstream instructions, including the required Windows SDK/debugging tools. Place
the toolchain and download cache on D:; some Windows installer/system components
may still require C:. Verify the Microsoft Authenticode signature before running
the installer. Do not disable system security, reboot, or change global Git/PATH
configuration to make a build pass.

For a D: Visual Studio 2026 installation, set `vs2026_install` explicitly to its
actual installed directory before hooks/build. This is required by the pinned
upstream toolchain detection; a downloaded bootstrapper is not proof of an
installed compiler.

```powershell
$python = '.\.venv\Scripts\python.exe'
& $python scripts/native_build.py preflight --workspace D:\CamouFlowNative
& $python scripts/native_build.py bootstrap --workspace D:\CamouFlowNative
& $python scripts/native_build.py sync --workspace D:\CamouFlowNative
$env:vs2026_install = 'D:\CamouFlowNative\toolchain\BuildTools'
& $python scripts/native_build.py hooks --workspace D:\CamouFlowNative
& $python scripts/native_build.py build --workspace D:\CamouFlowNative
```

Sync uses shallow, exact-commit source/dependency checkouts without hooks. Hooks
are explicit because they require a valid local toolchain and download further
build dependencies. Existing unrelated directories, changed Git origins,
uncommitted source changes and incompatible gclient configurations are rejected,
not overwritten. Tools/cache/temp are scoped to the owned workspace. Windows
build subprocesses use Git's OpenSSL TLS backend without changing global Git
configuration or disabling certificate validation. This transport completed the
pinned source transfer after the system-default Schannel transfer disconnected.
Successful sync and hooks write separate atomic stage records tied to the
pinned source/depot revisions, platform and actual `DEPS`/`.gclient` checksums.
Hooks require a completed sync record; compilation requires both. A new sync
invalidates both records, and rerunning hooks invalidates its previous result
before executing. A partial `.gclient_entries` file is not success evidence:
upstream writes it before its final CIPD installation has finished. Older
workspaces without stage records must successfully rerun the corresponding
commands; records must not be manufactured to skip dependencies or hooks.
Dependency snapshots record actual Git/GCS revisions with `gclient revinfo -a`
and actual installed CIPD instance IDs with `cipd installed`. The first command
explicitly excludes CIPD: otherwise `revinfo -a` re-resolves every pinned package
tag through sequential remote `cipd describe` requests, even after successful
installation. The local installed-package command was exercised against this
workspace and completed immediately. This does not skip CIPD ensure/install or
its integrity checks. Stage records also bind both snapshot checksums.
Failures
remain failures; there is no alternate browser/toolchain fallback.

The Windows gclient command uses the installed, pinned CIPD vpython package
directly. Missing vpython is an explicit bootstrap error, not substitution with
an arbitrary system Python. Windows Git stubs are generated using the pinned
upstream bootstrap implementation. Build subprocesses use an owned
`build.gitconfig`, keeping user-global Git configuration separate. Optional
depot_tools metrics are disabled in those subprocesses: the upstream Google-IP
discovery request has no timeout and blocked even a local help/version probe.
With metrics disabled, that probe completed immediately.

Helper calls use an owned `tool-launchers/vpython3.bat` pointing to the same
installed vpython executable. It does not rerun the entire unrelated LUCI CLI
package bootstrap for every gsutil invocation. Its path is prepended only for
build subprocesses; unrelated launcher files are rejected, not overwritten.
Before parallel Windows source sync, the pinned gsutil is initialized once via
its own installer/checksum checks. Cold parallel initialization otherwise held
its exclusive cache lock beyond the upstream 30-second contention budget.
No fake CIPD/gsutil completion markers or disabled integrity checks are used.

After a successful build, `src/out/CamouFlowNative/camouflow-build.json` records
actual executable and build-input checksums. It is a measured local build
receipt, **not** a publisher-signed release manifest or a complete distribution.
Run the real source-runtime gate with that executable:

```powershell
& $python scripts/verify_native_runtime.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\fork-runtime.json
```

## Current boundary

### Native C++ policy prototype

`core/hardware_limits.h` is the first compiled Native C++ policy module. It
validates concurrency limits and supported memory buckets, rejects invalid
configuration atomically, and applies explicit privacy ceilings without
inventing processors or memory above the host's native values. Empty limits
explicitly preserve native behavior. This is reported-value policy, not hardware
virtualization or an arbitrary device identity.

The standalone tests were compiled and run on Windows using MSVC 18.10.3,
C++20 and warnings-as-errors. Reproduce with the installed toolchain:

```powershell
& $python scripts/verify_native_cpp.py --work-dir D:\CamouFlowNative\cpp-check --vs-installation D:\CamouFlowNative\toolchain\BuildTools
```

CI also compiles/runs this policy on Windows, Linux and macOS; fresh results are
required. The verifier uses owned temporary output and no extra test framework.
`patches/0001-native-hardware-privacy-limits.patch` now connects this policy to
Blink's shared Navigator implementations used by documents and workers. Browser
switches are forwarded to renderer processes, rather than injected into page
JavaScript. Explicit limits never report more CPU or memory than the native
value. Absent switches preserve upstream behavior; invalid or empty explicit
limits fail the renderer's configuration check rather than silently pretending
to work. These are reporting ceilings, not resource quotas or a full device
identity. The patch includes the exact policy exercised by standalone tests.

The patch passes `git apply --check` against the pinned Chromium revision. It
has **not yet passed a complete Chromium build or real patched API checks**.
CamouFlow still rejects those fingerprint controls until that integration is
verified; standalone parser tests cannot prove browser behavior.

After source sync finishes successfully, apply it explicitly before building:

```powershell
git -C D:\CamouFlowNative\chromium\src apply --check "$PWD\native\patches\0001-native-hardware-privacy-limits.patch"
git -C D:\CamouFlowNative\chromium\src apply "$PWD\native\patches\0001-native-hardware-privacy-limits.patch"
```

The build accepts either a clean upstream baseline or exactly this checked
patch; unrelated source modifications are rejected. Build receipts record the
applied patch checksum and explicitly leave runtime verification false. The
source-sync command requires clean source, so do not rerun it over an applied
patch. Preserve local changes rather than resetting the checkout to retry sync.

Run the hardware binding gate separately against the built executable:

```powershell
& $python scripts/verify_native_hardware.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\fork-hardware.json
```

It observes the actual Navigator APIs in a main document, same-origin and
cross-origin frames, dedicated workers, shared workers and service workers.
It checks both limits together, independently, upper limits that must not invent
host hardware, unchanged UA/platform/language and invalid configuration failures.
All pages and profiles are owned temporary fixtures; the probe never replaces
Navigator APIs. Success does not prove unrelated Canvas/WebGL/Audio protections.

The local Windows upstream bootstrap negative control observed coherent values
in all six contexts (`12` logical processors, `16` GiB reported memory), then
correctly failed: requested limits `1`/`0.25` were ignored. Desktop CI repeats this
negative control on all three platforms; a success requires the specific
ignored-switch failure after a successful baseline, not any nonzero exit code.
This validates the gate, **not** the unbuilt patch's browser behavior.

The first source checkout/build is an upstream baseline for the actual fork.
No verified native fingerprint capability is claimed by these inputs; receipts
explicitly record `fingerprint_patched: false`. Source acquisition, hooks, compilation and
runtime verification are distinct stages. A running transfer or installer is
not a completed build. Neither CI bootstrap-browser checks nor a local checksum
prove native Chromium modifications or Linux/macOS fork readiness.

Native fingerprint changes must be reviewed against these exact sources,
compiled, and tested in actual document/worker/browser APIs before being exposed
as supported controls. Device identity must remain consistent; random JS
overrides and promises of guaranteed protection bypass are not acceptable.
Upstream Chromium and dependency license/NOTICE obligations apply to distributed
source and binaries. Signing infrastructure has not been configured.
