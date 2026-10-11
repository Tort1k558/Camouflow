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
Failures
remain failures; there is no alternate browser/toolchain fallback.

After a successful build, `src/out/CamouFlowNative/camouflow-build.json` records
actual executable and build-input checksums. It is a measured local build
receipt, **not** a publisher-signed release manifest or a complete distribution.
Run the real source-runtime gate with that executable:

```powershell
& $python scripts/verify_native_runtime.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\fork-runtime.json
```

## Current boundary

The first source checkout/build is an upstream baseline for the actual fork.
No native fingerprint patch is claimed by these inputs; receipts explicitly
record `fingerprint_patched: false`. Source acquisition, hooks, compilation and
runtime verification are distinct stages. A running transfer or installer is
not a completed build. Neither CI bootstrap-browser checks nor a local checksum
prove native Chromium modifications or Linux/macOS fork readiness.

Native fingerprint changes must be reviewed against these exact sources,
compiled, and tested in actual document/worker/browser APIs before being exposed
as supported controls. Device identity must remain consistent; random JS
overrides and promises of guaranteed protection bypass are not acceptable.
Upstream Chromium and dependency license/NOTICE obligations apply to distributed
source and binaries. Signing infrastructure has not been configured.
