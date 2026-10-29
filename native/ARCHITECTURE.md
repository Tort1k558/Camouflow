# Glint architecture

## Current implementation boundary

The reviewed Windows runtime is **Chromium 148 / 001-062**. Its exact managed
package admits only the individually reviewed experimental capabilities;
source ports, Python tests and diagnostic reports cannot expand that admission.
Chromium **156.0.8078.36 / 001–065** linked successfully in its separate D:
workspace: 19,487 build steps in 3h46m37.79s, followed by passing source/toolchain
postguards and a three-core-file build receipt. Disposable startup passed; two
repeats passed all 18 baseline lifecycle/integration checks. An earlier shutdown
timeout remains unexplained and retained as failed evidence. This is **not full
policy-suite, browser-identity or release admission**.
The first identity verifier stopped before running tests because its global
process guard detected an unrelated project's Ninja. Guards now support an
explicit workspace/binary scope; unreadable process identity remains a conflict,
and default unscoped checks remain conservative. Real owned sleeping-Ninja
controls distinguish foreign and conflicting scopes without terminating either.
The resumed identity-key target passed 62 C++ cases with postguards; remaining
identity/native targets and the canonical eight-gate/installed suite are pending.
The unprotected 156 Audio baseline also matched the standalone native156 DSP
matrix bit-for-bit in 45 captures. This does not execute AudioMath 0068.
Compiled 156 main/app-list icons match `logo.ico`; EXE/DLL ProductName and the
internal version page identify Glint. Taskbar/shortcut caching is not covered.
The verifier evidence-retention fix is staged separately and tested on an
isolated copy; it is not applied to the frozen queue or a browser-timeout fix.
The current candidate chain is 001–065;
0063–0064 address the actual unsafe-buffer compilation failures without disabling
diagnostics. Test-only 0065 updates worker synchronization/API calls and the GPU
canary layout; all 38 mapped fixture object targets now compile, but the full
fixture suite has not executed. The two system module targets and their
source/toolchain guards passed; object compilation is not execution of the
fixture suite. Linux/macOS runtime work remains deferred.

Persistent profiles own their separate browser processes/contexts; tabs inside
one profile share its identity and storage. The rendering verifier can keep at
most two private profiles live for bounded cross-profile checks, reusing the
existing five-store persistence fixture. This is a verification-runner limit,
not a two-profile product restriction. Current evidence and open gates live in
the [test matrix](../docs/GLINT_TEST_MATRIX.md) and
[roadmap](../docs/GLINT_ROADMAP.ru.md).

## Manager integration

`app/core/native/` owns configuration, identity, diagnostics, browser lifecycle
and local binary distribution. The existing browser interface dispatches to this
runtime while preserving Camoufox/CloakBrowser. Engine IDs and profile schemas
remain compatible; the display/product name is Glint.

The runtime launches an explicit installed executable or a selected managed
release. It never substitutes another engine or adopts its profile directory.
Profiles use persistent Chromium contexts with process-owner exclusion and
bounded teardown. Recorder, scenarios and AI use the common browser contract.

Local session backup takes the same Native owner lock for the complete ZIP
snapshot, not just an in-memory UI check. A live runtime blocks session export;
an export blocks runtime start. Metadata-only export does not read browser files.
Restore remains a new local identity: private profile keys and owner locks are
excluded, not transferred as a key-preserving rollback.

Running-profile diagnostics use a disposable, page-routed loopback document and
same-origin iframe, each with a dedicated-worker observation. Existing document
and worker checks run independently, then document identity groups are compared
across the frame boundary. Original tabs/routes remain untouched. The extra
scope is recorded under `contexts.same_origin_frame` and its mismatches join
the root report. This post-load fixture is not cross-origin or first-script
coverage; standalone binary probes still use their original two scopes.

## Configuration and privacy

### Product contract: coherent browser identity

The primary objective is a plausible, stable browser environment, not blanket
suppression of every exposed value. Treat OS, UA/Client Hints/HTTP, graphics
capabilities, fonts, display, language and timezone as one versioned identity.
Document, frames and workers must agree; profile restart must preserve identity,
while independent profiles retain independent keys and storage.

GPU metadata minimization is an optional privacy experiment, not the default
identity strategy. Missing extensions or empty identifying fields do not prove
plausibility. Future identity presets require measured reference environments
and native capability/behaviour checks; do not independently randomize hardware
strings while retaining contradictory driver capabilities. Cross-OS and mobile
identities remain unverified until their complete observable environment agrees.
Current Mobile Web remains desktop Chromium viewport/touch emulation.

The canonical `drafts/profile-identity` sequence separates partitioned privacy
derivation from stable profile identity and prepares an immutable browser-owned
selection per key service. Invalid selections reject initialization; installed
owners cannot switch modes. Initial source replay prepared twenty-six native
fixture definitions; their later execution is recorded below. A fourth, eight-file
candidate integrates selected derivation into the surface producer and a v3
wire mode with five more fixture definitions. Unknown modes and v2 reject before
seed copies; final-partition validation remains mandatory. Pinned Mojo parsing
and C++ binding generation passed in an isolated copy. The later native and
linked-browser checks are recorded below; product UI capability admission remains separate.
The fifth candidate adds six Blink fixture definitions for before-script mode
retention, independent document clones, invalid mode rejection and worker-origin
binding. These were initially source-only checks; their native execution is recorded below.
The sixth candidate prepares browser-only launch selection with strict service,
full document/worker surface and legacy-conflict checks. Persistent/incognito
initialization passes the immutable mode to its own service; renderer command
lines do not receive it. The four launch fixtures subsequently executed in the
001-059 BrowserContext target; linked Chrome ProfileImpl behavior remains unverified.
The manager key utility now has a separate profile-purpose derivation reference.
Its four fixed vectors, persisted reload and root/surface separation are executed
in Python tests; existing partitioned privacy vectors remain unchanged. It does
not activate either mode or replace native BrowserContext/IPC checks.
All six candidates are now registered exactly as 0049–0054, alongside GPU
transport 0055–0058. Integrated source 001-058 matched the reviewed composition
and passed full ordered replay. The key/service native target subsequently
passed **62/62 cases** (19 new, 43 legacy), with unchanged browser core/GN/receipt:
`identity-keys-001-058-v1.json` on D. The complete native selection is 134 cases;
41 new definitions expand to 50 new cases because DocumentLoader has four modes.
Context **37/37** and transport **20/20** cases subsequently passed on 001-059.
Blink handoff **15/15** also passed on 001-059: 12 document cases across four
modes and three worker-thread cases. Keys also passed 62/62 on 001-059, completing
134/134 on that source. The linked 001-059 browser subsequently passed extended
profile-identity and partitioned-privacy combined checks, including simultaneous
profiles and restart. This does not admit product privacy capabilities or prove
first-script GPU/nested Audio/GPU coverage; see the current test matrix.
Historical source-only preparation below is not current admission.

Manager diagnostics also compare measured WebGL/WebGL2 extensions, six limits and
context attributes between document and dedicated worker. A feature-off 001-027
browser passed en-US/de-DE loopback checks with unchanged core hashes; these
observations do not validate metadata spoofing, the new policy batch or presets.
Identity diagnostics reject contradictions between known navigator platform
values, explicit Windows/macOS/Chrome OS UA markers and Client Hints OS. They do
not infer OS versions from reduced UA text or treat Linux navigator.platform as
proof of desktop Linux: Android and Chrome/Chromium OS also use that family.
Windows en-US/de-DE observations passed on the unchanged 001-027 baseline;
synthetic platform cases are not Linux/macOS/Android runtime validation.
`verify_native_identity_readback_batch.py` composes all six identity candidates
with the six halo/clipping/GPU metadata candidates in one isolated source tree.
The exact combined source and pinned Mojo/GPU generation passed before
integration. C++ type checks covered 22 identity and six GPU units. These
preflight results do not replace the remaining native/runtime gates or admit
protection. At that stage the earlier browser was 001-047 and the next linked
baseline was 001-059; subsequent 001-062 evidence is recorded in the test matrix.

Configuration validates viewport, DPR, locale, timezone, permissions and privacy
requests before startup. Unsupported requests fail rather than silently falling
back. Diagnostics observe actual document/worker browser values; they do not
replace APIs or invent hardware/GPU values.

`canvas_fidelity.py` is shared by runtime diagnostics and the verification helper.
Document and dedicated-worker probes measure explicit opaque ImageData fidelity,
repeat/single-pixel/PNG/rewrite consistency and alpha preservation using bounded
32x24 inputs. Diagnostics report opaque pixel mutation, malformed observations
and inconsistent operations as mismatches; half-transparent RGB rounding alone
is not treated as a regression. These metrics do not certify fingerprint
plausibility or replace stock calibration. Real 001-059 observations confirmed
zero baseline issues and four protected opaque-mutation warnings across the two
scopes, with unchanged core/receipt. The actual routed health probe also passed
its baseline document/worker checks and removed its disposable profile.

Persistent identity uses an owned profile-root file containing a versioned
private key. On Windows the manager uses owner-permission QFile creation and
same-directory atomic OS publication on an ACL-capable filesystem. Loading a
valid legacy key republishes its exact bytes with the creation ACL, without seed
rotation. This protects key-file contents, not writable parent directories or
against privileged/same-user processes; it does not bulk-harden workspace ACLs.
Export excludes the key; restored/cloned profiles obtain a distinct
identity. Cryptographic domain strings and filenames are compatibility contracts,
not branding text, and must not be renamed without migration analysis.

Chromium patches provide hardware ceilings, real installed-font selection,
WebRTC routing, automation/headless policy and Windows storage-path handling.
Newer patches derive per-surface keys from a trusted browser StorageKey and own
the key service per BrowserContext. Off-the-record contexts have independent
ephemeral identities; they must never redirect to the persistent original.

Key loading is asynchronous on a blocking worker; derivation fails until ready.
Readiness callbacks are registered in patch 0016 and passed 43 native cases.
Real-context tests are registered in
patch 0017 and all twenty passed in the linked content unit target.
Patches 0018-0020 register lifetime-bound document/worker endpoints using
browser-owned partition state and an independently timed worker consumer.
Their 34 native cases passed, as did a combined 54-case context/delivery run.
Patches 0021-0026 register dedicated/shared/service-worker startup gates and owned
seed transport into Blink scope creation, plus four handoff unit definitions.
Startup gates require the developer-only `glint-worker-canvas-bootstrap-test`
switch; normal launches retain the upstream path. Patch 0027 adds host failure
notification before shared-worker rejection teardown. The linked 001-027 browser
passed 40 owned startup/restart/shared-client/rejection checks, with exact receipt
and core-code measurements. This is not proof of internal Blink seed bytes or
cross-partition key equality. The first four-case Blink handoff run passed two
cases, then aborted on an extra never-started worker in the sequential fixture.
Test-only patch 0028 corrects that fixture lifetime; all four cases passed on
retry with the baseline browser core, receipt and GN arguments unchanged.
Document
bootstrap and Canvas/WebGL/WebGPU/audio protection remain incomplete.

Patch 0029 registers a shared final-partition validator header and nine native
cases, all passed through the public document-partition target. Registered
document commit/renderer candidates reuse that header rather than defining a
second copy. The validator checks exact native partition encoding, not IPC
sender authentication or safe cancellation after document teardown.

Patch 0030 registers the developer-only document commit prototype: shared
StorageKey resolution, final wire-origin payload construction and token-bound rejection of the
selected pending navigation. The public `--target document-navigation` gate
requires twelve exact NavigationSimulator cases. That gate uses real browser
navigation machinery with simulated renderer/network behavior; first-script
Blink execution, previous-page usability and candidate Canvas hooks require
separate checks. Source registration is not browser linkage or privacy admission.

## Source reproducibility

### Registered surface batch (not admitted)

| Candidate | Prepared behavior | Evidence boundary |
| --- | --- | --- |
| Surface policy v2 | One owned partition snapshot with independent Canvas/WebGL/WebGPU/Audio seeds; bounded preflight, typed browser partition, binary Mojo schema and owned codec | Source replay and generated bindings; 25 native fixture definitions, not compiled |
| Worker surface delivery | Shared endpoint readiness, explicit v2 consumer/modes, all three launchers, immutable Blink scope and first-script rejection | Source replay; 8 browser, 22 consumer/mode and 4 Blink fixture definitions, not compiled |
| GPU metadata minimization | Disabled-by-default native feature; remove WebGL debug extension and identifying WebGPU info without fabricating hardware | Source replay; candidate runtime not verified |
| Offline Audio | Deterministic scalar prototype and bounded detached AudioBuffer copy; no live processing or JS method replacement | Registered API integration; native fixtures and protected runtime pending |

Canonical public source and historical integration inputs live under
`drafts/policy`, `drafts/gpu` and `drafts/audio`. They were promoted together into
registered patches 0031–0034 after the corrected 12-case document gate passed.
Exact registered-source replay passed across 125 paths; the full browser batch
is compiling. Do not modify these frozen inputs during that build.
Document/worker v2 transport and final-owner handoff have
candidate code, not compiled/runtime proof. Canvas and OfflineAudio API candidates
consume explicit owned seed results; API admission and GPU readback
admission remain unfinished. Existing profile-key derivation domains must stay
stable across a transport-version change.

`verify_native_gpu.py` and `verify_native_audio.py` provide local compatibility
diagnostics before enabling new hooks. Their successful 001-027 baseline runs
do not verify the drafts or claim anti-bot acceptance. Worker APIs unavailable
in upstream remain explicit exclusions, not fabricated coverage.

`verify_native_next_batch.py` replays thirty canonical integration inputs
in an owned temporary overlay, checks exact canonical copies and rejects source,
receipt, GN-input or browser-core drift. Run it with a new evidence path outside
both repositories; it never runs GN, compilation or modifies active sources.
For the promoted state it reverses 0031–0034 only in that owned copy, then
recomposes the canonical inputs and requires equality with registered source.
Partial registration is rejected.

The document v2 candidate owns the browser-selected partition and independent
surface seeds, and requires validation against Blink's final StorageKey, not
only its provisional key. The browser producer uses the existing context key
service without regeneration or another root-key store. Its 30 content fixture
definitions are source-only. Additional handoff/readiness/navigation fixtures
bring the expected document v2 case set to 112; none has executed.
Final handoff does not use `CalculateOrigin` as a read-only pre-unload probe:
origin privilege changes and sandbox-token consumption must retain upstream
semantics. The current late Canvas prototype check does not prove old-document
rollback. Early renderer rejection precedes teardown; the late final-key guard
creates an inert replacement, not restoration of the previous document. Blank
and srcdoc inheritance requires exact partition matching. Root initial empty
documents and different-partition children need authenticated delivery rather
than parent-key borrowing. No document v2 policy or new readback hook is admitted
by source replay or generated bindings.

The shared surface reader treats flag-off and invalid required policy as
different results. All candidate Canvas web entry points reject the latter;
they do not export an unprotected image. OfflineAudio captures its independent
seed before rendering starts, checks the additional-copy budget and produces
one detached mutable buffer before both completion event and Promise. Native
seed-reader and startRendering rejection fixtures are prepared, not executed.
No realtime Audio or analyser protection, complete ImageData-format support,
complete GPU readback protection or verified fingerprint-resistance claim is implied.

The registered WebGL hook covers default sRGB RGBA8/RGB8 and single-sample
RGB8/RGBA8 renderbuffer attachments, using actual selected attachment extents.
CPU/PBO pack handling, pending GL errors, resize and export consistency have
prepared gates; only the feature-off 001–027 fixture baseline has run.
Texture, float/integer/HDR attachments and WebGPU readback remain unsupported.
The subsequent unregistered `drafts/next-readback` candidate replaces redundant
full-frame allocation with an exact full-frame private transform or a clipped
one-pixel halo. Its 58,860 independent model comparisons and source replay passed;
11 native fixtures, driver compatibility and performance measurements are pending.

`scripts/native_build.py` pins upstream revisions, records sync/hooks dependency
snapshots and checks applied changes by replaying registered patches into a
temporary Git index. Patch 0007 belongs to the separate V8 checkout. Unknown
changes and changed build inputs prevent generation of a successful receipt.

Next-batch replay owns its temporary Git configuration and disables `autocrlf`:
composed-source hashes use LF regardless of the developer's machine settings.
Regrouping candidate patches must reproduce those exact bytes and preserve all
source/build/runtime input hashes; source equivalence is not compilation proof.

Do not edit an active checkout, GN arguments or registered patch content while
compilation is running. An object build proves only those translation units;
production linking and actual browser execution are separate gates.

The first compiled NavigationSimulator commit/rejection run passed 11 of 12
cases; its browser-initiated `about:blank` case exposed an opaque-origin mismatch.
Policy construction had run before `ReadyToCommitNavigation` selected the origin
stored in the commit parameters. Recomputing an opaque origin can change its
nonce. The corrected source binds both the Canvas prototype and prepared v2
policy to the exact final wire origin, after upstream weak-lifetime and selected
frame checks. It does not change Chromium's origin selection or weaken the test.
The corrected binary passed all 12 cases (`document-navigation-001-030-j4-v3.json`
on D). This proves simulated content-layer commit/rejection behavior, not actual
Blink first-script execution, full renderer/worker policy or browser admission.

## Combined surface runtime gate

`scripts/verify_native_surfaces.py` prepares seven owned-browser phases for the
next compiled surface batch: baseline and two independent profiles, each with a
persistent restart, followed by missing-document-policy rejection. It combines
all four Canvas readback entry points with OfflineAudio completion in the same
eight document/frame/worker contexts. OfflineAudio is expected in five document
contexts; worker unavailability is not audio coverage.

The gate requires repeated reads, export/crop/transparent-pixel consistency,
existing Canvas security checks, Audio event/Promise buffer identity and mutation
semantics, same-partition agreement, different cross-origin/profile results and
stable restarts. A fetched owned page must abort without its script beacon when
document policy is unavailable; timeouts are not accepted as rejection.

Before creating profiles or launching a browser, the gate requires exact
registered surface patches and a build receipt binding **every runtime core
file**, not just `chrome.exe` while Blink resides in `chrome.dll`. Reserved patch
names 0031 (worker policy), 0032 (document policy) and 0033 (surface readback)
are registered and applied, **not yet compiled or runtime verified**.
The current 001–027 browser is deliberately rejected before launch.

Measured float32 bit arrays are bound to each Audio digest. The combined gate
compares them against the unprotected baseline: at most the lowest mantissa bit
may change, signed silence/subnormals/out-of-range samples remain exact, a signal
must actually change, and measured signal-to-noise must be at least 130 dB.
Render durations are retained separately and excluded from restart identity;
they do not prove a performance budget. The baseline Audio runner accepts
`--sample-quality` to capture the same bits and durations without enabling policy.

These are prepared checks, not executed protected-browser results. Performance
budgets, GPU readback, malformed-policy injection,
root-initial/sandbox delivery and public anti-bot diagnostics remain separate
work. `privacy_admitted` stays false even if this functional gate passes.

The combined gate also measures Canvas and OfflineAudio from the owned page's
first inline parser script, rather than injecting the first measurement after
load. All six baseline/profile/restart phases require `readyState == loading`,
one fetched fixture, one completed execution beacon and matching settled-document
results. The parser script also creates a connected iframe and starts a read in
its initial `about:blank` immediately, without awaiting a navigation or readiness
event; that same-partition child must match both readings. Audio float bits remain
bound to their digest; render durations are not identity. The 001–027 unprotected
baseline passed the expanded fixture on actual initial/restarted browsers
(`first-script-initial-child-001-027-baseline-v2.json` on D). This checks the probe,
not v2 protection. Root-initial about:blank, popup and sandboxed child first-script
delivery still require separate lifecycle tests.

## Distribution

`distribution.py` manages checksum-verified local bundles and release selection.
`scripts/package_native_windows.py` checks official staged files against compiled
output, retains licenses/credits and requires matching runtime evidence.
`scripts/native_release.py` provides install, activate, inspect and rollback.

Complete payload integrity includes executable code, DLLs and resources.
Activation checks compatibility/health; compilation alone is not release admission.
There is no signed online update catalog. Development bundles are unsigned.

## Known boundaries

Python startup rejects hard-linked privacy-key files before starting the browser
driver, matching the native key-loader contract. A shared filesystem inode must
not silently become the identity of two independently locked profiles. Rejection
does not replace the key and releases the acquired profile lock. ZIP export and
restore continue to omit/discard this private identity: restored profiles receive
new keys, while ordinary restarts preserve existing owned keys.

- Graceful close/reopen commits are tested; abrupt crashes may lose pending writes.
- Thread/owner checks do not prove operating-system memory sanitization.
- Unpartitioned shared/service workers need explicit partition policy before
  cross-site privacy protection can be activated.
- Own-fork Linux/macOS runtime, GPU/audio/Canvas protection and production
  security rebasing are not complete.
