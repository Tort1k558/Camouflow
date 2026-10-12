# Native Chromium source workspace

This directory tracks the public CamouFlow Native build inputs. Chromium source,
dependencies, tools and output stay **outside this repository**, on the approved
`D:\CamouFlowNative` workspace. Backend source and credentials are not included.

Current development scope is Windows only, at the user's request. Local Linux
downloads, hooks, builds and repeated runtime tests are deferred until explicitly
resumed; existing Linux workspaces and verified results are preserved. Desktop
CI now schedules only Windows jobs. Linux/macOS support remains unfinished and
must not be represented as released own-fork runtimes.

## Public privacy unit rerun

The current 33-case key/container/owner verification is available in the public
repository, without machine-specific D: wrapper scripts:

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_privacy_units.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\privacy-units-new.json --vs-installation D:\CamouFlowNative\toolchain\BuildTools --jobs 4
```

Use a fresh report name. The verifier preserves raw GoogleTest output and
compiler/test logs, checks exact required case names and successful completion,
binds the unit executable hash and source patches, and requires baseline browser
code/receipt/GN arguments to remain unchanged. It refuses a detected active
compiler/build process instead of launching another build. This is not a global
mutex shared with legacy build wrappers: run one build command at a time.
Current support is Windows only, with at most four jobs; GOMEMLIMIT is a soft Go
heap limit, not a cap on the total build process memory. These unit results do
not admit fingerprint capabilities or prove real Chrome/incognito/worker runtime.

## Windows storage path normalization (0008; intermediate failure resolved by 0009/0010)

`patches/0008-native-leveldb-path-separators.patch` normalizes the 17 LevelDB
environment UTF-8-to-native path conversions before filesystem operations.
LevelDB appends `/LOCK`; with Windows extended path syntax that forward slash
is not normalized by the OS and causes `CreateFileW` error 123. This was
reproduced against an owned temporary lock file, not inferred from unit tests.
`FilePath::NormalizePathSeparators()` preserves POSIX path semantics and adds
no dependency. The exact applied source and patch checksum are checked by the
build helper and recorded in the own-build receipt.

The four-job own Windows rebuild succeeded in 10m05.72s, with 51 executed build
steps. Exact source validation and receipt generation completed with exit zero.
The subsequent direct extended-path matrix retained correct IndexedDB, local
storage, CacheStorage and service-worker observations across restart, and cache
deletion succeeded in every case. However, cookies disappeared after restart
in all eight cases, so the complete matrix still failed. The unchanged-code
report is `D:\CamouFlowNative\owned-normalized-extended-store-proof.json`.
This patch does not remove Chromium's explicit `MAX_PATH` guards or enable
extended launch paths in the manager. It is not a complete storage fix.

## SQLite Windows namespace handling (0009; direct storage runtime passed)

An ordinary-versus-extended launch control preserved cookies on the ordinary
path but lost them on the extended path, where no persistent Cookies database
was created. Chromium's exclusive SQLite open rejects any `?` in a path,
including the legitimate Windows namespace marker. `0009` excludes only the
initial `\\?\` marker from that query-delimiter check; all later question marks
remain rejected and the existing `EscapePath` URI encoding remains intact.
It retains exclusive locking and does not disable cookie encryption.

The own-fork four-job rebuild succeeded in 5m02.51s (54 executed build steps,
exit zero). All eight direct extended-path desktop/mobile cases passed creation,
replacement and restart of cookies, localStorage, IndexedDB, CacheStorage and
service-worker registrations, plus cache entry/cache deletion. All three runtime
code hashes were unchanged through the probe. Evidence is retained in
`D:\CamouFlowNative\owned-sql-namespace-extended-store-proof.json`.

The Windows native SQL target subsequently compiled and all **54 native tests
passed**: 18 ordinary special-character opens, 18 extended-namespace write/reopen
and exclusive-lock cases, and 18 appended-query rejection cases. Browser code,
receipt, GN arguments and exact source patches were unchanged through that build
and execution. Proof: `D:\CamouFlowNative\native-sql-namespace-unit-proof.json`;
raw GoogleTest output: `native-sql-namespace-unit-results.json` on D.
The direct probe and SQL tests do not activate extended paths in the manager.
Original failed controls remain on D; see `docs/NATIVE_VERIFICATION.md`.

## Browser-owned profile namespace (0010; storage and lifecycle runtime passed)

After the native SQL target exited successfully, `0010` was applied to the
pinned Chromium source. It initializes Windows `DIR_USER_DATA` with extended
filesystem syntax inside the browser, preserving the same physical directory.
Already extended and device namespace paths are not prefixed twice; UNC syntax
is handled separately from drive paths. No profile relocation, alias, retry,
app-side launch formatting, ownership-path change or non-Windows change is made.

The four-job own-fork rebuild completed successfully (1m26.85s, five executed
build steps, exit zero). The ordinary-launch storage matrix now passed all eight
desktop/mobile cases at root lengths 90/130/150/170 through the unchanged
`NativeRuntime`, without an app-side extended prefix. The full lifecycle gate
also passed all 18 checks, including Recorder/replay, backup/restore, proxy,
permissions, process locks, crash recovery and three independent profiles across
three restart/crash rounds with no surviving owned processes. Evidence:
`D:\CamouFlowNative\storage-path-matrix-browser-owned-namespace-20261012.json` and
`verification-browser-owned-profile-namespace-full-20261012/runtime.json` on D.

The full eight-gate own-fork suite subsequently passed: runtime (18 checks),
hardware (9), WebRTC (7), automation (55), fonts (42), identity (18), inspector
accessor serialization (6), and combined policies (5). The suite bound every
child to the unchanged executable/DLL measurements; report:
`verification-browser-owned-profile-namespace-full-20261012/suite.json` on D.
Official shipping staging completed without executing an installer. The new
261-file development archive is
`D:\CamouFlowNative\camouflow-native-001-010-windows-dev.tar.gz`, SHA-256
`b1e62811e9e1ea2ee52095e329191ad4a25f49605ee0a30ad9bc90f913b8b883`.
It was installed only into the isolated `owned-release-store-001-010` on D,
without activation in the user app. All 18 relocated package lifecycle checks
passed with the archive identity and every payload hash verified before/after.
Real packaged `chrome://credits` rendered 19,465,020 bytes. Proofs on D:
`runtime-own-packaged-full-payload-001-010-20261012.json` and
`own-packaged-real-credits-001-010.json`.
This is an unsigned, unactivated development baseline, not an authenticated
customer release or fingerprint capability admission. Root paths above
the Windows bootstrap buffer limit and actual UNC storage remain outside
verified coverage. Do not claim arbitrary path-length support or activate
fingerprint capabilities from this filesystem patch.

## Current Windows source build

### Owned profile key loader (0013; 17 native tests passed)

`0013-native-owned-profile-key-loader.patch` adds a noncopyable browser-only
key container. It parses the existing bounded schema-1 Python identity JSON,
rejects invalid schema/type/shape, uppercase or malformed seed and BOM, and
returns only derived surface keys. Owned JSON/decoded buffers and retained key
bytes are cleared with the existing BoringSSL primitive; no root-key getter or
logging path is exposed. This is not at-rest encryption or a guarantee that
every allocator/parser temporary is securely erased.

The Windows loader opens only the fixed identity filename from a caller-owned
absolute profile directory. It opens the leaf reparse point itself and rejects
reparse/directory handles, non-disk files, multiple hard links and invalid size.
It does not share write/delete access while reading and does not create or
regenerate missing/invalid identities. Parent-directory ownership and process
locking are caller preconditions, not a new protection against arbitrary
ancestor-directory replacement. Other-platform file loading is unsupported.

The first compiler attempt rejected a raw pointer member; it was corrected to
Chromium's existing `raw_ptr` pattern only after the failed build was terminal.
All 17 corrected native tests passed: the ten derivation/vector tests plus seven
profile-container/loading cases, including snapshot retention, missing/invalid
file behavior, schema rejection and real Windows hard-link rejection. Proof on
D: `native-privacy-profile-key-loader-corrected-unit-proof.json`; raw results:
`native-privacy-profile-key-loader-corrected-unit-results.json`. The 0010 browser
baseline, receipt and GN arguments were unchanged. The browser keyed service,
off-the-record lifetime, renderer/worker IPC and readback protection still need
integration; this source set is not active in the production browser.

### Browser key derivation (0012; ten native tests passed)

`0012-native-browser-privacy-key-derivation.patch` adds a browser-layer source
set and native test target. `DerivePrivacyPartitionKey()` accepts a fixed-size
256-bit profile key, a trusted StorageKey and one supported surface; it returns
only the HMAC-SHA256 partition/surface key or nullopt. The domain-separated
message header is copied exactly from `native/core/privacy_partition.h`, with a
project regression check to prevent divergence. No new dependency is introduced;
the code uses the pinned Chromium `crypto::hmac::SignSha256` API.

All ten native tests passed, including four independently constructed Python
vectors for canvas/WebGL/WebGPU/audio, repeated/copy stability, profile and
top-level-site separation, opaque partition separation and unknown-surface
rejection. Exact source, baseline browser code, receipt and GN arguments were
unchanged through this test target's build/run. Proof on D:
`native-privacy-key-derivation-unit-proof.json`; raw output:
`native-privacy-key-derivation-unit-results.json`.

This is not profile-file loading, a browser keyed service, renderer/worker IPC
or protected readback. The verified immutable browser/archive remain 0010.
The new derivation source set is not yet linked into the production browser or
used to activate fingerprint capabilities. Next integration must keep the root
key browser-only and enforce partitioned worker lifecycle before protection.

### Trusted partition codec (0011; eight native unit tests passed)

`0011-native-privacy-partition-serialization.patch` adds the bounded, versioned
`StorageKey::SerializeForNativePrivacy()` input for future browser-owned key
derivation. It reuses StorageKey's existing friendship with SchemefulSite;
no new public Net accessor or testing-only hook is used. Original disk storage
serialization is unchanged. Origin/site tuples, opaque precursor tuples and
trusted 128-bit nonces are encoded separately, along with retained top-level
site/ancestor fields and the optional storage nonce. Disabling storage
partitioning cannot silently erase the retained site from this codec.

Eight native tests cover repeat/copy stability, a literal format vector,
disabled-feature site separation, opaque origin/site/precursor separation,
storage nonce and ancestor bits, and tuple canonicalization. The Windows
`blink_common_unittests` target built with four jobs and all eight tests passed.
Exact source patches, GN arguments, baseline browser code and receipt were
unchanged through the native test build/run. Proof on D:
`native-privacy-partition-unit-proof.json`; raw GoogleTest output:
`native-privacy-partition-unit-results.json`. The verified browser/archive remain
0010; this unit target does not issue a new own-browser
receipt or enable privacy protections. Root-key transport, partitioned worker
lifecycle enforcement and Canvas/GPU/audio modules remain unfinished.

The first four-job Windows compilation, with hardware/MIDL patches 0001/0002,
stopped after 27,364 completed actions and four failed Inspector compilations.
All four reported `LLVM ERROR: out of memory`; this was a terminal compiler
failure, not a polling timeout. The captured session exited with code 1.
The output directory and successful object files were preserved.

After the process exited, prepared patches 0003/0004/0005 were applied together
to the pinned source, and compilation was resumed with `--jobs 1`. The build
helper validates the exact recognised patch set and dependency rules before
generating/building. Existing compatible objects remain reusable; changed
generated feature headers will legitimately invalidate some Blink objects.
The own-fork binary and every patched runtime gate remain unverified.

The build helper now revalidates the exact source-patch set and GN arguments
after successful compilation, before writing the build receipt. A source/input
change fails explicitly, and a new build attempt removes its stale prior receipt
before GN/build; no successful receipt is retained for that failed attempt.
Three controlled compiler-callback tests changed the patch set, generated GN
arguments or tracked GN inputs and confirmed rejection; the unchanged-input
control still records success. The already-running build loaded the earlier
helper code, so it must undergo the new post-build validation before packaging.

After a reported host freeze, process inspection found the one-job build and
compiler absent, with its log stopping during compilation and no terminal build
receipt. The same cached output was resumed without cleaning, still at one job,
using process-scoped `GOMEMLIMIT=3GiB` for Siso's Go runtime. This is a soft Go
memory target, not a hard process/system cap or a proven cause/fix of the freeze.
The pinned Siso binary contains Go 1.26.1 and supports this setting. New capture
uses a UTF-8 log rather than Windows PowerShell's UTF-16 redirection. Global
memory/pagefile settings and unrelated processes remain unchanged.
See the [Go memory-limit documentation](https://go.dev/doc/gc-guide).

The user subsequently requested returning to four jobs. The one-job invocation
was interrupted, its old Siso/compiler processes were verified absent, and the
same cached output was resumed with `--jobs 4`. The new Siso command and four
concurrent clang-cl processes were observed; no output directory was cleaned.
The 3-GiB Go target remains soft and does not cap compiler memory. Additional
patches prepared during this invocation remain drafts, not hot source edits.

## Own-fork Windows packaging (development archive only, delivery checks pending)

`scripts/package_native_windows.py` converts Chromium's official mini-installer
staged `Chrome-bin` directory into the existing managed Native `.tar.gz` format.
It does not recursively archive the build output or directly use GN's
`runtime_deps`: a read-only query against our pinned Windows graph included
thousands of development assets, Python helpers, PDBs and `initialexe/chrome.exe`.
The official `chrome/installer/mini_installer/chrome.release` and
`mini_installer_archive` target define the shipping layout instead.

Only use this after compilation has terminated, the latest build helper has
validated its receipt, the own-fork runtime gate has passed, and the official
archive target has produced its staging tree. Do not run the generated installer
on this machine just to obtain its files. Building the archive target is separate
from installing Chromium. After the own Windows binary and repeated runtime
gate passed on 2026-10-12, the four-job `mini_installer_archive` build completed
37 steps in 1m15s. A first development archive was installed into an isolated
test store on D:, not activated for the application. Shipping is still blocked:
the credits page was a sample and a relocated runtime probe exposed an early
database-import regression. Real credits generation is enabled for the next
build; fresh isolated runtime and full relocated-payload checks are required.
No installer has been executed. The tested executable/DLL hashes, receipt, GN
arguments and source patches must remain unchanged through archive generation.

The packager requires matching pinned revisions, executable/GN hashes and all
18 runtime-check names from a passing report for the exact binary. Every staged
file must match its compiled-output counterpart; missing DLLs/locales, changed
files, links, collisions and debug/build files fail explicitly. BSD Chromium and
MIT CamouFlow source notices are retained. Embedded third-party notices and
`chrome://credits` still require inspection on the completed own binary before
public distribution.

Archive timestamps/owners and gzip metadata are normalized for reproducibility.
All payload hashes and the build/report provenance are recorded, but packaging
does not assert successful fingerprint-patch gates. The final archive is created
without overwriting existing files, outside source/staging on D:. Synthetic tests
proved reproducibility, payload hashes, existing-store installation and rejection
of invalid reports, changed executables/DLLs/arguments, missing notices and
mid-archive changes. These fixtures are not a compiled own-fork release.

Managed `chromium-fork` releases require this complete file checksum manifest.
Installation, inspection, selection and rollback verify the entire payload,
not just `chrome.exe`: altered DLLs/resources, missing or unexpected files,
links, unsafe paths and manifest collisions fail before browser startup or
active-release replacement. Legacy `upstream-bootstrap` manifests retain their
existing contract; if they include a file manifest, it is also enforced.
Selection/rollback tests confirmed that a modified library neither launches a
browser nor changes the active-release record. Hashes are checked against the
installed trusted manifest, not a remote signature or protection against an
attacker who can rewrite both payload and manifest. Large-bundle verification
cost still needs measurement on the finished own binary; no unchecked hash cache
is used. Compatibility checks resolve/hash a captured settings snapshot inside
their existing worker; browser startup offloads resolution with `asyncio.to_thread`
so whole-bundle reads do not block the GUI or other event-loop tasks.

```powershell
& $python scripts/package_native_windows.py --build-output D:\CamouFlowNative\chromium\src\out\CamouFlowNative --staged D:\CamouFlowNative\chromium\src\out\CamouFlowNative\gen\chrome\installer\mini_installer\mini_installer\temp_installer_archive\Chrome-bin --runtime-report D:\CamouFlowNative\native-runtime-fork.json --archive D:\CamouFlowNative\releases\camouflow-native-windows.tar.gz
```

The existing destination directory must be created deliberately. The printed
SHA-256 is suitable for the existing local trusted-publisher install command;
it is not a signed online update feed. The completed bundle must still pass
relocated-binary health/runtime checks and own-patch gates before production.

## Native headless UA patch (0006 applied; own runtime pending)

`0006-native-headless-user-agent.patch` adds the opt-in boolean switch
`--camouflow-native-user-agent` to Chromium's native user-agent construction.
It skips the headless-only product prefix while retaining the actual Chromium
version, native platform/CPU text and unchanged low/high-entropy Client Hints.
It does not install an arbitrary UA override, replace JavaScript getters, add
Google-branded Client Hints or claim Chrome 152 on our Chromium 148 build.
Nonempty flag values fail a native CHECK; the default remains upstream behavior.
The patch includes two upstream unit-test cases but they have not been compiled
or run. Pinned-source `git apply --check` passed on an isolated draft generated
from original HEAD files. The patch was applied after the immutable baseline passed on 2026-10-12; its translation unit compiled, but full build and own runtime checks remain pending.

`scripts/verify_native_identity.py` observes the UA in owned HTTP echo requests
and native document, same/cross-origin frame, new-target, dedicated/shared/service
worker APIs. It checks real browser-version Client Hints, native getter shape,
unchanged plugins/window.chrome, and preservation of each scope's HTTP hint policy.
High-entropy HTTP hints are not forced into frames where upstream permissions
omit them. Unsupported flag values, including Unicode, must fail with the actual
native diagnostic after the protected checks pass.

The Windows upstream SDK control passed all seven baseline contexts and correctly
failed the first protected context because the unknown Native flag was ignored.
Its genuine headless browser already exposed five PDF plugins and window.chrome
as an object: those table entries do not justify fabricated plugin objects or
extra patches. This gate does not verify CAPTCHA scores, production Turnstile,
third-party bot classifications, TLS fingerprints or CDP invisibility.

After applying and compiling the draft, run:

```powershell
& $python scripts/verify_native_identity.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\native-identity-fork.json
```

## V8 inspector accessor patch (0007 applied; own runtime pending)

`0007-native-inspector-error-accessors.patch` targets V8's own repository,
not the Chromium Git index. Its pinned base is
`ddc9a95905de5268332a8f0216dc2bc67d26e829`, the `src/v8` revision in the
verified gclient dependency snapshot. Pinned V8 `git apply --check` passed,
and the draft-time read-only check confirmed a clean V8 baseline. The patch was applied after the immutable Windows baseline passed on 2026-10-12; its translation unit compiled. Full build and own runtime checks remain pending.

The draft resolves Error property descriptors along a bounded prototype chain,
without falling back to ordinary lookup when it encounters unknown/proxy
descriptors. Data properties retain their real values; scripted, proxy and bound
accessors are not invoked for previews. Lazy native stack formatting is withheld
when custom name/message accessors could execute user code. The policy is a
C++ inspector change, not injected browser API replacements. It is not yet
compiled or runtime-verified, and does not prove general CDP invisibility.

Error previews also use the pinned inspector's existing
`DisallowJavascriptExecutionScope::THROW_ON_FAILURE` pattern inside `TryCatch`.
This guards lazy formatting against `Error.prepareStackTrace` and other scripted
conversion paths instead of intentionally crashing on execution. It is still a
draft: runtime checks must prove that blocked preview formatting does not poison
the Error's cached stack or change later explicit JavaScript reads.

The build helper now validates Chromium and V8 independently before/after
compilation. V8 must match the verified dependency snapshot; applied V8 patches
must exactly match known diffs and receipts include their repository/revision.
Temporary alternate indexes stay outside both source trees. Real indexes remain
unchanged; unknown edits and mid-build V8 changes reject a successful receipt.
Real nested-Git fixtures also verify rejection of extra edits, unknown files,
deletions and staged extra edits while preserving both original Git indexes
and leaving no temporary index directory in either source tree.
The current helper is now building patches 0001-0007 after the immutable baseline passed. Do not modify active compilation inputs.
The identity/inspector runtime gates remain pending until the current build terminates.

`scripts/verify_native_cdp.py` logs six owned Error accessor fixtures (own and
inherited stack/name/message) and all seven standard native Error types with
initially lazy stacks through
an actual Runtime CDP session. Thirteen console events, unchanged real error
messages/stacks for every type and working explicit-accessor-read controls are
required before asserting zero serialization-triggered getter calls.
The expanded Windows SDK negative control passed those three positive checks
and correctly failed the accessor assertion: own/inherited stack 0/2,
name 2/4 and message 1/3 calls. The own name/message cases demonstrate lazy
stack formatting invoking accessors even where direct accessor previews are
already skipped upstream. Validator tests reject lost events, missing or
misidentified Error types, broken counters, stack changes and invented previews.
A separate owned custom `Error.prepareStackTrace` fixture requires a genuine
console event and successful later stack reads for both the same Error and a
fresh Error. The unpatched Windows SDK invoked the formatter once during CDP
serialization; both explicit-read controls passed, and the no-execution check
correctly failed. Arbitrary object previews and other CDP detection signals are
not covered. The active build's V8 checkout remains untouched.

After compiling the draft, run:

```powershell
& $python scripts/verify_native_cdp.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\native-cdp-fork.json
```

The read-only post-failure Windows sample showed 13.4 GiB free physical RAM,
but only about 7.3 GiB of available committed memory under a 36.5-GiB commit
limit. Physical RAM alone is not a sufficient build-memory check. Neither other
applications nor the global pagefile/system settings were changed. Never hot
edit the source or generated headers while the compiler is running.

`0004-native-automation-exposure.patch` adds an opt-in Blink runtime feature,
`CamouFlowAutomationConcealed`, disabled by default. Enable it only in an
experimental own-fork run with
`--enable-blink-features=CamouFlowAutomationConcealed`. The C++ Navigator getter
returns false before either AutomationControlled or the inspector override.
The prototype getter, descriptor and illegal-invocation behavior are unchanged;
workers do not acquire a nonstandard `webdriver` property. Existing Chromium
feature-switch forwarding is reused. No page scripts or synthetic getters are
injected. The app does not expose this as a verified capability yet.

The patch applies cleanly to the pinned revision. The pinned upstream feature
generator was run in a separate D: draft directory and generated the getter
with a false default. This is not proof of C++ compilation or runtime behavior.
The real Windows SDK negative control passed 22 baseline/frame/worker/CDP
checks, then correctly rejected the ignored Native feature at the first
protected document. It must not be counted as own-fork success.

After compiling the batch, run:

```powershell
& $python scripts/verify_native_automation.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\fork-automation.json
```

The gate checks the first page script, same/cross-origin frames, new targets,
dedicated/shared/service workers, explicit feature disable, native getter shape,
and CDP automation overrides. It separately disables upstream
AutomationControlled to prove that the inspector positive control really works.
Suppressing this one indicator is **not** CDP invisibility, coherent full-device
fingerprinting, or proof of passing anti-bot sites.

Reference direction: study the documented native configuration surfaces of
[CloakBrowser](https://github.com/CloakHQ/CloakBrowser) and
[Camoufox](https://github.com/daijro/camoufox), but implement our own Chromium
changes. Cloak's wrapper MIT license does not cover its proprietary native
patches/binary; see its
[binary license](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md).
Camoufox documents why invented text widths and inconsistent GPU/canvas values
can themselves identify a modified browser. Next priorities are a coherent
Windows-only device policy, genuine-font selection/metrics and graphics API
agreement, not random per-call noise or fabricated unsupported GPU limits.
Canvas/audio/font/device diversity remains unfinished and must not be advertised
as implemented. WebRTC draft 0003 still needs its own compiled runtime gate.

### Windows font collection draft

`0005-native-windows-font-collection.patch` prepares opt-in genuine-font
selection with `--camouflow-font-families=Arial,Times New Roman,Segoe UI`.
The argument is a bounded list of exact printable ASCII family names, without
leading/trailing whitespace, duplicates, or empty entries. Arial is required
for Blink's last-resort rendering. Every requested font must actually exist;
an invalid/missing family produces a native CHECK, not a silent system-font
fallback. Omitting the switch keeps upstream behavior.

The patch builds a DirectWrite font collection from the original selected
families and their original styles. It does not invent names, glyphs, canvas
pixels, or text widths. A custom glyph fallback maps only into that collection;
scripts without a supported glyph may render missing-glyph boxes. A useful
profile must select sufficient real fonts for its intended languages.

The selected collection is wired into all three Windows font entry points:

- The current default FontDataService and its Skia font manager.
- The legacy renderer DirectWrite broker, including unique `local()` matching
  and glyph fallback.
- Local Font Access enumeration, still behind normal permissions.

Chromium source was not modified during the running first build. The draft
applies to the pinned revision. Its complete C++ draft files passed upstream
dependency rules in an isolated overlay; a forbidden Blink include was rejected
as the negative control. Only two exact `ui/gfx/win` includes were added to
FontDataService's DEPS; its existing GN dependency on `//ui/gfx` is reused.

The standalone Windows C++ gate compiled with `/W4 /WX` and ran the real
DirectWrite APIs: only Arial remained, every original Arial style and the
checked genuine metrics were retained, restricted fallback construction
succeeded, and a missing requested family failed without returning a collection.
The pure parser also passed malformed/duplicate/count/length controls.
The standalone gate also exercises real DirectWrite glyph mapping for Latin,
a combining mark, CJK and an emoji. Every returned font face must belong to
the restricted collection, and the Latin positive control must map a genuine
font at its original scale. On the local Windows host the unrestricted system
fallback supplied two outside-collection glyph controls; the restricted route
did not return those fonts. Hosts without such fonts report zero outside-font
controls rather than claiming a multilingual negative control passed.
These are **not** compiled Chromium, CSS/canvas/worker/local-font runtime proof
or complete font-file isolation. A font file/TTC can contain multiple faces;
this draft restricts accessible collections, not the bytes inside allowed font
files. The app's `fonts` setting remains rejected until the own-fork runtime
gate verifies the complete selection path.

`scripts/verify_native_fonts.py` prepares that Windows runtime gate. It uses
owned loopback pages and a genuine Courier New font obtained through explicitly
granted Local Font Access. The font bytes are served only by the temporary
loopback fixture and are neither committed nor packaged. The downloaded font
is a separate control: restricting installed families must not break web fonts.

The gate covers the current FontDataService and explicitly selected legacy
DirectWrite path, six document/frame/worker scopes with their actual origins,
CSS versus canvas widths, native canvas pixel hashes, excluded `local()` faces,
selected family enumeration and original Arial style metadata. Both protected
paths must pass again after closing/reopening the same persistent profile.
The real SDK control passed all 14 unrestricted checks, including the actual
cross-origin frame, and rejected the ignored Native switch at Local Font Access.
This is negative-control evidence, not successful own-fork masking or restart
evidence. Own-fork compilation/runtime verification remains pending.

```powershell
& $python scripts/verify_native_fonts.py --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe --work-dir D:\CamouFlowNative\tmp --report D:\CamouFlowNative\fork-fonts.json
```

`build-lock.json` pins full upstream Chromium and bootstrap depot_tools commits.
Chromium's pinned `DEPS` defines its own dependency revisions/CIPD instances,
including its vendored depot_tools; the bootstrap tool is pinned separately and
self-updates are disabled. `args.gn` sets an unbranded, local release build with
reduced symbols and no paid remote build service. Four jobs is the configured
maximum/default; the current recovery uses one explicit job on this 24-GiB
machine to reduce committed-memory pressure.

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

The runtime gate also runs three rounds with three independent concurrent
profiles. Each round writes distinct values to all five stores, verifies
isolation, gracefully checkpoints one rotating profile, crashes its browser,
checks the other profiles remain usable, and restores its committed data.
It observes independent Playwright drivers and actual descendant identities
before and after restart, then requires every observed owned process to exit.
Existing user processes are excluded by PID plus creation identity, not killed.
This is a bounded restart/crash check, not a long-running soak or memory-budget
verification. Running it on the bootstrap Chromium binary proves the runtime
layer only; the own fork must independently pass it after compilation.
The Windows bootstrap run passed all 18 checks, including all three restart
rounds with three observed independent drivers and zero remaining observed
owned processes after each round. Matching downloaded artifacts for
[`706c65f` CI](https://github.com/Tort1k558/Camouflow/actions/runs/38115530154)
independently passed these same 18 checks on Windows x64, Linux x64 and macOS
ARM64. Each reported all three restart rounds and zero remaining observed owned
processes. All three explicitly report `fingerprint_patched: false`; these
results are not completed own-fork builds.

**Crash durability boundary:** a successful JavaScript storage write or read
does not prove that Chromium has flushed every store to disk. An owned Windows
bootstrap probe that immediately invoked `Browser.crash` lost freshly written
cookies and localStorage while IndexedDB, Cache Storage and service workers
survived. The committed-data gate therefore verifies a graceful close/reopen
checkpoint before crashing. Native does not currently guarantee preservation of
pending writes during an abrupt browser crash, nor provide instant disk flush
or automatic recovery supervision.

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
origin and no Git alternates. Git connectivity verification passed. Full Linux
dependency sync subsequently completed, including actual CIPD ensure and measured
Git/GCS/CIPD snapshots. Its matching `camouflow-sync.json` stage record was
written by the successful command; hooks and a Linux Chromium build are separate.

The initial network fetch failed with Git exit 128 (`curl 56`, GnuTLS packet decode
error and early EOF). A bounded HTTP/1.1 retry also failed after 300 seconds without
data (`curl 28`). Instead of repeatedly downloading the same objects, the existing
verified Windows Git object cache was copied through local Git transport into the
separate D:-hosted ext4 checkout. No Windows worktree changes or Native patches
were copied; its active build was not modified. Repository ownership exceptions
were scoped to the exact trusted cache paths in an owned, process-selected config,
not the user's global Git configuration. Failed fetch data was preserved.

```powershell
wsl.exe -d CamouFlowNativeBuilder -u nativebuilder --exec python3 /mnt/c/Users/lolod/Desktop/camouflow-app/camouflow/scripts/native_build.py sync --workspace /home/nativebuilder/CamouFlowNative --backing-volume /mnt/d --jobs 2
```

Always provide `--backing-volume /mnt/d` for this D:-hosted WSL workspace.
Preflight checks both filesystems and uses the smaller free-space value: a real
local check reported 922.3 GiB inside ext4 but only 318.5 GiB on D:. Logical VHDX
capacity alone must not authorize another large download or compilation.
`--jobs` explicitly limits sync/build concurrency to 1..4 without editing the
shared build lock; successful build receipts record the actual selected count.
Use one Linux compile job while assessing available memory. Job count is not a
hard RAM quota; hooks/build still require fresh resource checks and completed
stage records. These options do not alter an already running build or sync.

Existing Docker WSL data, its default-distribution setting and stopped state were
preserved. No global `.wslconfig`, host security/VPN settings or production server
configuration was changed. Linux compilation has not been started alongside the
active Windows build: host available RAM was approximately 6-8 GiB. Recheck memory
and the real D: drive's free space before further work; free space reported inside
the virtual ext4 disk reflects its logical maximum, not actual host disk headroom.

The pinned upstream `build/install-build-deps.py` completed successfully in this
isolated distro, using `--no-prompt --no-arm --no-chromeos-fonts
--no-backwards-compatible --no-syms`. It installed the official Ubuntu build/runtime
packages and generated its required locales; Windows and other WSL distributions
were not modified. Chromium dependency sync was independently completed; this
installer result alone does not prove hooks or compilation.

CamouFlow application runtime checks require Python 3.12, whereas this distro's
system interpreter is 3.10. A separate CPython 3.12.15 build completed with one
compiler job under `/home/nativebuilder/CamouFlowNative/toolchain/python-3.12.15`.
The official source archive was verified against publisher SHA-256
`c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a` before extraction.
Its installation prefix is private to that workspace; neither system Python nor
the existing Windows application `.venv` is replaced. The installed interpreter
reported 3.12.15 and imported SSL, SQLite, compression, ctypes and venv modules;
`verified-build.json` records the measured source hash and private prefix.
The exact public application requirements were installed in a separate
`app-env` under this workspace. `pip check`, Native core imports and timezone
validation passed; the environment reports Python 3.12.15, Qt 6.11.0 and
Playwright 1.60.0. Its unit run passed 809 tests with seven Windows-only skips.
The pinned Linux bootstrap Chromium 148.0.7778.96 independently passed all 18
runtime checks in this actual WSL environment, including three concurrent
profiles, rotating browser crashes, committed-data restoration and zero
remaining observed owned processes. These are application-runtime results,
not compilation or verification of our own Linux fork.

The first full Linux dependency sync failed after repeated TLS/early-EOF and
no-data timeout errors fetching the pinned SwiftShader commit. That dependency
was copied through local Git transport from the verified Windows object cache
into its own Linux checkout, with no shared objects or alternates. Its exact
HEAD, official origin, clean status and `git fsck --connectivity-only` passed.
The failed checkout was preserved outside `src`, not deleted or left as
untracked input. A fresh real sync completed its upstream CIPD ensure and
dependency snapshots successfully. The actual recorded snapshot SHA-256 values
are `156c261284384f873f9506e4de6578995a92838251e9b8ebab260c7dc08e7a29`
for Git/GCS revisions and
`fcd8c1ab3b4c1ee7e8cd9790ddf62e48c6fdce7c8a8b665dc36da357ced54a8a`
for installed CIPD packages. Native hooks are now running with the verified
application interpreter and explicit backing-volume check; hooks completion
and the Linux Chromium build remain unverified.

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
only on security-fixed Python (3.12.15+, 3.13.16+, 3.14.8+ or 3.15.x); older and
unreviewed future minor versions fail explicitly. This matters for macOS framework
bundles: the September 2026 releases fixed additional tarfile extraction-filter
bypasses, so the previous 3.12.11/3.13.4/3.14.0 thresholds are no longer sufficient.
See [Python 3.12.15](https://www.python.org/downloads/release/python-31215/),
[3.13.16](https://www.python.org/downloads/release/python-31316/) and
[3.14.8](https://www.python.org/downloads/release/python-3148/).

Windows GN/autoninja wrappers use the installed pinned CIPD Python directly, and
its executable directory is added only to build-child PATH. This avoids missing
`python3_bin_reldir.txt` launcher indirection and the Microsoft Store Python alias
selected by GN child scripts, without fake bootstrap markers or global PATH edits.

## Native WebRTC routing patch (Windows own-fork runtime verified)

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

The new patch has been applied to the pinned Windows source. The current
001-010 own-fork baseline passed all seven Windows WebRTC checks; evidence is
`D:\CamouFlowNative\verification-browser-owned-profile-namespace-full-20261012\webrtc.json`.
Do not change live build inputs. Application configuration
continues to reject unsupported WebRTC masking/blocking options.
The build's dependency gate now also invokes the pinned upstream
`CheckAddedCppIncludes` API on the real browser renderer-preferences file.
The two added Native WebRTC headers passed that checker; an intentionally
forbidden Blink renderer header was rejected as its negative control.
This checks layering only, not compilation or effectiveness of the policy.

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
results for Linux/macOS remain pending; a passing negative control is not a privacy capability.
