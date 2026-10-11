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
The pinned upstream dependency-layer checker is also enforced before compiling
a patched tree. Its initial check found that the Native configuration header
needed scoped permission to read `base/command_line.h`. The patch now follows the
existing `navigator_language.cc` pattern in the frame's `DEPS`, granting that
single header permission rather than relaxing Blink's general dependency rules.
The frame dependency check then passed against the actual patched checkout.

After source sync finishes successfully, apply it explicitly before building:

```powershell
git -C D:\CamouFlowNative\chromium\src apply --check "$PWD\native\patches\0001-native-hardware-privacy-limits.patch"
git -C D:\CamouFlowNative\chromium\src apply "$PWD\native\patches\0001-native-hardware-privacy-limits.patch"
git -C D:\CamouFlowNative\chromium\src apply --check "$PWD\native\patches\0002-midl-locale-name-hashes.patch"
git -C D:\CamouFlowNative\chromium\src apply "$PWD\native\patches\0002-midl-locale-name-hashes.patch"
```

The build accepts a clean upstream baseline or exact combinations of these
checked patches. A disposable Git index contains only their original files and
the expected patched versions; actual files must match it completely. Extra edits
inside a recognized file are also rejected, not merely edits to unknown files.
The real checkout index is not modified. Build receipts record all applied
patch checksums and explicitly leave runtime verification false. The
source-sync command requires clean source, so do not rerun it over an applied
patch. Preserve local changes rather than resetting the checkout to retry sync.

### Windows MIDL locale reproducibility

The initial full Windows build stopped after 4,402 completed actions because the
generated tracing-service type library differed from its pinned baseline by ten
bytes. Its declared locale was 1033, but the library-name hash used the host's
Russian locale (1049); the associated hash-chain entries also differed. Using the
exact 26100.7705 MIDL tools reproduced the mismatch, so changing the SDK alone
was not a fix. No Windows locale or global system configuration was changed.

`0002-midl-locale-name-hashes.patch` computes name hashes with the type library's
stored locale and target system using Microsoft's
[`LHashValOfNameSys`](https://learn.microsoft.com/en-us/windows/win32/api/oleauto/nf-oleauto-lhashvalofnamesys),
then rebuilds its name-hash chains before the existing upstream comparison.
It does not replace GUIDs, methods, interface definitions or baseline artifacts,
and does not bypass comparison failures. The helper validates bounds and counts;
unsupported layouts/non-ASCII names fail explicitly. Its tested source is
`native/toolchain/midl_locale.py`; the Chromium patch embeds the identical module.

The actual failed command passed after applying this patch, and its complete
generated TLB matched the upstream baseline. Normalizing the baseline itself
was idempotent. The full own-fork compilation was then resumed; that resumed
process is not yet proof of a complete Chromium build or patched runtime.

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

## Local Linux source workspace

An isolated WSL 2 distribution, `CamouFlowNativeBuilder`, was imported under
`D:\CamouFlowNative\linux-builder`. Its Ubuntu 22.04 root filesystem came from
the [official Jammy WSL image directory](https://cloud-images.ubuntu.com/wsl/jammy/current/).
Both the archive SHA-256 and the detached signature of its checksum file were
verified before import, using the [publisher fingerprint documented by Ubuntu](https://ubuntu.com/docs/public-images/public-images-how-to/verify-image-checksum/):
`D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`. The checked archive SHA-256 was
`1483cc5c1dce13064f774834cbffdff226559fd522a67a381a8ea77d63fb4109`.
The GPG keyring/downloads stayed in the owned D: toolchain directory.

The builder has its own unprivileged `nativebuilder` account. Git, Python/venv,
certificates and basic download tools were installed from Ubuntu's signed package
repositories. Pinned depot_tools bootstrap completed under that user. An independent
clean Chromium checkout in `/home/nativebuilder/CamouFlowNative/chromium/src` was
verified at revision `8625e066febc721e015ea99842da12901eb7ed73`, with the official
origin and no Git alternates. Git connectivity verification passed. Dependency
sync has now started; this is not completed source sync, hooks or a Linux build.

The initial network fetch failed with Git exit 128 (`curl 56`, GnuTLS packet decode
error and early EOF). A bounded HTTP/1.1 retry also failed after 300 seconds without
data (`curl 28`). Instead of repeatedly downloading the same objects, the existing
verified Windows Git object cache was copied through local Git transport into the
separate D:-hosted ext4 checkout. No Windows worktree changes or Native patches
were copied; its active build was not modified. Repository ownership exceptions
were scoped to the exact trusted cache paths in an owned, process-selected config,
not the user's global Git configuration. Failed fetch data was preserved.

```powershell
wsl.exe -d CamouFlowNativeBuilder -u nativebuilder --exec python3 /mnt/c/Users/lolod/Desktop/camouflow-app/camouflow/scripts/native_build.py sync --workspace /home/nativebuilder/CamouFlowNative
```

Existing Docker WSL data, its default-distribution setting and stopped state were
preserved. No global `.wslconfig`, host security/VPN settings or production server
configuration was changed. Linux compilation has not been started alongside the
active Windows build: host available RAM was approximately 6-8 GiB. Recheck memory
and the real D: drive's free space before further work; free space reported inside
the virtual ext4 disk reflects its logical maximum, not actual host disk headroom.

## Binary installation foundation

`app/core/native/distribution.py` installs explicitly checksummed `.tar.gz`
bundles into an owned store's `releases/<archive-sha256>/` directories. Existing
versions are not overwritten or deleted, and profiles are not moved or migrated.
Installation uses a cross-process lock, a private staged copy checked against the
operator-provided SHA-256, bounded extraction with Python's `data` filter, path
and case-collision checks, platform/architecture validation and executable hash
verification before the candidate directory is published. Inspecting an existing
installation checks its executable again. This is not protection against an
attacker who can modify both the local manifest and executable.

Every bundle has a root-level `native-release.json`, for example:

```json
{
  "schema": 1,
  "native_version": "0.1.0-dev",
  "chromium_version": "148.0.7778.96",
  "platform": "win32",
  "architecture": "x64",
  "build_kind": "chromium-fork",
  "executable": "chrome.exe",
  "executable_sha256": "<actual executable SHA-256>"
}
```

Use `upstream-bootstrap` instead of `chromium-fork` for an upstream development
bundle; labels are publisher metadata, not independent proof of native patches.
The archive checksum must come from a trusted release catalog/operator, not from
an unchecked sidecar downloaded with the archive. Checksums are **not signatures**.
The store exposes asynchronous `activate(digest)` and `rollback()` operations.
Each candidate must pass real headless startup, exact Chromium version comparison
and teardown in a disposable profile before `current.json` is replaced atomically.
Failed checks preserve the active selection and report an error; no alternative
browser is selected. `resolve_active()` verifies the selected executable again.
Old releases remain installed. Chromium downgrades, including rollback to an older
Chromium version, are blocked because existing profile compatibility has not been
established. Rollback between releases of the same Chromium version is supported.
There is no configured public release feed or GUI installer yet. These
operations do not change running browsers or customer profiles, and do not prove
a published own Chromium distribution.

On Windows, two complete local upstream Chrome 148.0.7778.96 preview bundles
were checksummed, installed and activated through this API, then rolled back to
the first release. All three headless launches and cleanups passed; both immutable
installations remained present and the disposable health-profile directory was
empty. This verifies the store lifecycle, not the pending own-fork build or
Linux/macOS archive activation.

The Native settings page supports explicit **Local executable** and **Managed
release** modes. Managed mode requires an absolute store path and resolves its
verified active release for every launch and compatibility check. Invalid store
state or a changed executable is an error; the local executable is not a fallback.
Changing the selected release affects future launches, not already running ones.

Use the CLI to install locally obtained bundles or activate/roll back a release:

```powershell
& $python scripts/native_release.py --store D:\CamouFlowNative\releases install --archive D:\CamouFlowNative\bundle.tar.gz --sha256 <trusted-archive-sha256> --activate
& $python scripts/native_release.py --store D:\CamouFlowNative\releases current
& $python scripts/native_release.py --store D:\CamouFlowNative\releases rollback
```

The CLI does not download an untrusted catalog or enable managed mode in existing
profiles. Select the same store explicitly in Native settings and save settings.
On Windows, this path was exercised with complete upstream preview bundles:
CLI installation/activation, rollback, a real managed `BrowserInterface` launch
and the QML compatibility button all passed with a deliberately nonexistent
explicit executable path. No fallback occurred. Temporary browser profiles and
the test workspace were cleaned up; this still does not verify own-fork patches.

Windows bundles reject archive links. Unix bundles may preserve internal links
only on security-fixed Python (3.12.11+, 3.13.4+ or 3.14+); older runtimes fail
explicitly. This matters for macOS framework bundles: [Python 3.12.11 fixed
tarfile extraction-filter bypasses involving crafted links](https://www.python.org/downloads/release/python-31211/).

Windows GN/autoninja wrappers use the installed pinned CIPD Python directly, and
its executable directory is added only to build-child PATH. This avoids missing
`python3_bin_reldir.txt` launcher indirection and the Microsoft Store Python alias
selected by GN child scripts, without fake bootstrap markers or global PATH edits.

## Native WebRTC routing patch (not runtime-verified)

`0003-native-webrtc-routing-policy.patch` adds the browser-process switch
`--camouflow-webrtc-ip-handling-policy=disable_non_proxied_udp`. It sets real
Chromium renderer routing preferences and clears per-origin routing overrides
and local-IP exposure exceptions; unsupported or empty switch values fail a
native `CHECK`. Without the switch, existing browser preference behavior is
unchanged. It does not inject JavaScript, spoof an IP address, disable the
PeerConnection API or promise working TURN/media connectivity.

The legacy `--force-webrtc-ip-handling-policy=disable_non_proxied_udp` flag was
tested against the pinned Chromium 148 SDK binary on Windows: both baseline and
flagged launches produced five direct loopback STUN requests and UDP host
candidates. Treating that flag as protection would be misleading.

The new patch applies cleanly against the pinned source, but it has **not** been
applied to the live Windows build, compiled or runtime-verified. Finish and
verify that build before changing its source inputs. Application configuration
continues to reject unsupported WebRTC masking/blocking options.

After compiling this patch, run:

```powershell
& $python scripts/verify_native_webrtc.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\native-webrtc-fork.json
```

The gate first requires actual UDP traffic to an owned loopback STUN observer.
Protected document, same-origin and cross-origin frames must then complete ICE
gathering without direct STUN requests or UDP candidates. Empty, unsupported and
wrong-case switch values must fail with the specific native CHECK diagnostic,
not an unrelated launch error. No public STUN server,
camera/microphone access or host IP addresses are collected. The upstream
negative control passed its baseline and correctly failed the protected probe
on Windows. Matching Windows x64, Linux x64 and macOS ARM64 CI artifacts at
`8fe6bbb` each observed five STUN requests in both the baseline and unpatched
protected launch and rejected that ineffective policy. All own-fork WebRTC
results remain pending; a passing negative control is not a privacy capability.
