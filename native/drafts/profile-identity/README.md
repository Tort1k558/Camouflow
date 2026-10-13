# Stable profile identity — derivation candidate

**Unregistered and uncompiled. No identity mode is enabled.**

## Native C++ type checks

The complete six-patch identity candidate now has a reproducible public gate:

```powershell
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-cpp-new.json --check-cpp
```

On registered 001-048, all **22 actual-target translation units passed** with
fresh v3 Mojo implementations/headers, no old PCH reuse and unchanged active
source/core/GN: `profile-identity-public-cpp-001-048-v1.json` on D. Coverage is
four core implementations, three key/context fixtures, three producer/preflight
units, two first-evaluation fixtures, two Chrome launch units, six production
consumers and two generated implementations. Compiler failure, timeout, missing
fresh implementations or input drift reject; raw diagnostics remain beside the
private report. This does not optimize/link code, execute the 41 identity
fixtures, enable the mode or admit protected browser behavior.

The current six-patch candidate passed real clang syntax checks with actual
generated target flags, in an isolated overlay without reusing old precompiled
headers. No active Chromium source, browser core or GN configuration changed.

| Scope | Checked translation units | Private evidence on D |
| --- | --- | --- |
| Core APIs | `privacy_key_derivation.cc`, `privacy_profile_key.cc`, `privacy_key_service.cc`, `privacy_context.cc` | `profile-identity-core-syntax-001-037-v1/proof.json` |
| Fixture definitions | `privacy_key_derivation_unittest.cc`, `privacy_key_service_unittest.cc`, `privacy_context_unittest.cc` | `profile-identity-fixtures-syntax-001-037-v1/proof.json` |
| V3 transport | `surface_policy_producer.cc`, its fixture file and `surface_policy_preflight_unittest.cc`, with freshly generated candidate Mojo headers | `profile-identity-transport-syntax-001-038-v3/proof.json` |
| First-evaluation fixture definitions | `document_loader_test.cc`, `worker_thread_test.cc`, with the same v3 candidate bindings | `profile-identity-handoff-syntax-001-038-v1/proof.json` |
| Chrome launch integration | `profile_impl.cc`, `off_the_record_profile_impl.cc`, using candidate context APIs | `profile-identity-launch-syntax-001-038-v1/proof.json` |
| Generated V3 implementations | Fresh candidate `native_privacy_surface_policy.mojom.cc` and `.mojom-shared.cc`, using exact generated-source Ninja target flags | `profile-identity-generated-cpp-001-040-v1/proof.json` |
| Production V3 consumers | Worker service/bootstrap, `render_frame_impl.cc`, `document_loader.cc`, `worker_thread.cc` and `service_worker_global_scope.cc`, with fresh candidate bindings | `profile-identity-consumers-cpp-001-040-v1/proof.json` |

This does **not** execute cryptography, service/context/transport fixtures,
generated serialization implementations, first-script delivery or browser
behavior. Optimized objects and
linkage remain unverified; `privacy_admitted` is false. The regular privacy
unit target currently links 6754 cached inputs, so its isolated future-mode
link/run must wait for resource headroom rather than compete with the active
four-job native build. Do not replace that gate with stubbed crypto or owners.

The handoff check parses real test target files, including the six new identity
cases, without suppressing compiler diagnostics or reusing old PCH state.
It does not launch a renderer/worker, evaluate JavaScript, or prove that trusted
mode/seed delivery happens before the first script. Those remain runtime gates.
The launch check likewise parses the regular and off-the-record profile paths;
it does not prove startup, persisted mode, incognito isolation or flag rejection
in an actual browser process.

The six production consumer units were checked separately from fixtures against
001-040: actual browser/renderer/Blink target flags, candidate v3 headers first,
no old PCH and no disabled diagnostics. This closes the parsing/type-compatibility
gap between fixture definitions and production consumers. It still does not
execute worker startup, document commits, IPC or any fingerprint surface.

This candidate adds an explicit browser-owned profile-identity derivation API
alongside the existing partitioned privacy API. It does not replace that API,
change existing privacy-domain bytes, expose the profile root key, or silently
reinterpret the current Canvas/GPU/Audio policy.

| Property | Candidate behaviour |
| --- | --- |
| Purpose | Separate versioned `Glint/profile-identity/v1` HMAC domain |
| Profile | Root remains owned by the existing profile/key service |
| Site partition | Still validated; excluded only from identity entropy |
| Surface | Four allowlisted, domain-separated surfaces |
| Lifecycle | Ready service required; loading/failure/shutdown reject |
| Ephemeral contexts | Independent existing ephemeral roots, not original-profile redirection |
| Current privacy API | Remains partition-dependent and unchanged |

The native derivation/context/profile/service implementation is included in the
patch. Eleven C++ fixtures are prepared: four independent vectors, purpose/site/
root/surface separation, invalid surfaces, and service readiness/failure/reload/
ephemeral ownership. **They have not been compiled or executed.**

```powershell
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\profile-identity-replay.json
```

Use a new private report path. Source replay and Python reference-vector matching
are not native cryptographic/runtime proof.

## Immutable browser-mode candidate

`immutable_identity_mode_candidate.patch` applies **after** the derivation
candidate. It adds an immutable, browser-owned derivation selection per key
service: partitioned privacy (unchanged compatibility default) or stable profile
identity. Invalid modes reject installation and both initialization paths;
loading, failure and shutdown still reject derivation. Existing explicit privacy
and identity APIs remain separate. No setter or renderer-controlled selection
is introduced.

Eight additional C++ fixtures cover default compatibility, cross-partition
identity, readiness/shutdown, invalid modes, owner replacement rejection,
persisted reload and ephemeral isolation. **Prepared, not executed.**

`identity_context_tests_candidate.patch` is the third patch in the sequence.
Seven further fixtures exercise real `TestBrowserContext` owners: per-context
mode separation, loading/shutdown rejection, invalid mode installation, loading
owner replacement, same-root restart, independent incognito roots and null/failed
contexts. These are native test definitions, **not executed BrowserContext proof**.
The `--include-mode` replay checks all three patches in order.

```powershell
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\immutable-mode-replay.json --include-mode
```

This is a source/API component, **not an enabled fingerprint mode**. Producers,
wire-mode delivery, renderer/worker consumption, launch settings and UI admission
are not integrated. The default is preserved for existing callers, not a product
decision to use partitioned noise as an ordinary browser identity.

## Policy v3 producer/transport candidate

`identity_transport_v3_candidate.patch` is the fourth patch. It selects all four
seeds through the immutable browser service, maps its mode explicitly, and carries
that mode in the owned policy and Mojo payload. Policy v3 rejects v2 and unknown
modes before copying seeds. Document and worker preflight preserve the received
mode and still require exact final-partition binding, even when identity seeds
remain equal across sites.

Five additional native fixtures cover stable/default production, owned
document/worker roundtrip, unsupported versions/modes and cross-partition
rejection. Pinned Mojo parsing and isolated C++ binding generation passed,
including the mode, typed partition and four seed arrays. The producer and two
transport fixture translation units subsequently passed C++ syntax checks with
those candidate headers. Both freshly generated regular/shared `.cc`
implementations subsequently passed type checking with pinned target flags on
001-040. Optimized objects, linkage, serialization execution and fixture
execution remain unverified.

```powershell
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-transport-replay.json --include-transport
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-transport-bindings.json --check-bindings
```

This batch is unregistered and has not changed the active build. Native binding
compilation, first-script document/worker handoff, renderer retention, launch/UI
selection and combined runtime remain required. It must not be mixed with v2
consumers or admitted as a tested fingerprint feature.

## Blink handoff fixtures

`identity_handoff_tests_candidate.patch` is the fifth patch, adding six fixture
definitions to the existing document loader and worker thread test targets:
identity mode before first script/evaluation, owned document clones, rejection of
unknown modes, and final worker-origin binding. It reuses existing fixture
lifecycle and rejection helpers. **None has been compiled or executed.**

```powershell
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-handoff-replay.json --include-handoff --check-bindings
```

Source replay validates composition, not browser or Blink execution. The worker
fixture exercises a worker global scope, not independent production coverage of
all dedicated/shared/service-worker launchers. Chrome launch selection still
requires native execution; manager capability admission remains blocked.

## Strict Chrome launch candidate

`identity_launch_candidate.patch` is the sixth patch. The browser-only
`--glint-fingerprint-derivation-mode` switch accepts exactly `partitioned-privacy`
or `profile-identity`. An explicit value requires key service `=1`; profile
identity also requires both full document/worker surface bootstrap switches and
rejects either legacy Canvas bootstrap. Unknown/empty values reject launch.
Absent selection preserves existing callers' partitioned-privacy behaviour.

Persistent and incognito profile initialization pass the resolved mode to their
own service. Incognito still uses an empty root and independent ephemeral key;
the selection switch is not copied to renderer processes. Four native launch
fixture definitions are prepared, **not executed**. This is a development opt-in,
not a new admitted manager capability or a user release.

```powershell
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-launch-replay.json --include-launch --check-bindings
```

## Manager derivation reference

`NativePrivacyIdentity.derive_profile_identity(partition_key, surface)` computes
the same versioned profile-purpose HMAC using the existing locally owned root.
It validates the supplied partition shape but excludes that partition from
entropy. It does not authorize IPC, change the identity-file schema, regenerate
invalid keys, enable launch switches, or admit any browser capability.

Python tests execute all four fixed vectors against both the independent HMAC
reference and the C++ candidate literals, plus cross-partition stability, surface/
root separation and persisted reload. Legacy privacy derivation remains unchanged.
This is executable manager-side reference evidence, **not native execution**.

## Combined observation contract

The existing `verify_native_surfaces` validators accept an explicit
`derivation_mode="profile-identity"` for prepared owned runners. This requires
equal Canvas observations across documents/workers and equal Offline Audio across
all available document contexts, while still rejecting profile reuse, restart
drift, silent-buffer changes and malformed observations. The compatibility default
remains `partitioned-privacy`, including mandatory cross-site differences.
Unknown modes reject rather than relaxing checks.

Synthetic validator tests passed for both contracts. **The public runtime CLI
still tests registered partitioned privacy only**: identity launch/receipt admission
is not enabled merely because the observation validator supports that mode.

## Combined identity/readback source gate

The next build batch combines the six identity patches above with the six
GPU/readback patches in `../gpu-transport/README.md`. The combined verifier runs
both reviewed component validators, rejects conflicting overlapping edits, and
replays all twelve patches into one fresh owned copy. Every resulting file must
match the component proofs; the active checkout and canonical inputs must remain
unchanged. Optional code generation covers pinned Mojo bindings and GPU command
headers without invoking a compiler or GN.

```powershell
.venv\Scripts\python.exe scripts/verify_native_identity_readback_batch.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-readback-batch.json --check-codegen
```

Source composition is not evidence of linking, API compatibility or protected
GPU output. Both candidate sets remain unregistered and feature admission stays
blocked. WebGPU readback, floating-point/HDR surfaces and believable OS/GPU/mobile
presets are not implemented by this combined gate.

Use `--check-cpp` to check the **same combined tree**, not just the components
separately. This regenerates its Mojo bindings and GPU commands, then type-checks
22 identity/consumer/generated units and six GPU/client/passthrough-fixture units
with actual target flags. Compiler failures reject the gate; source/core/GN and
unchanged consumers are guarded. Logs stay beside the private report.

```powershell
.venv\Scripts\python.exe scripts/verify_native_identity_readback_batch.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\identity-readback-combined-cpp.json --check-cpp
```

This still does not execute native fixtures or link a browser, and does not admit
identity mode, attachment metadata or protected GPU output. The current GN
configuration disables the validating decoder; parsing its translation unit
does not establish coverage of that backend's excluded code or fixtures.

The first complete combined C++ attempt on source 001-048 **failed**:
`identity-readback-combined-cpp-001-048-v2.json` on D. GPU's six units passed;
identity stopped at `document_loader.cc` with `LLVM ERROR: out of memory`
after 17 successful units. Remaining identity units were not checked in this
composition. Source/core/GN remained unchanged and the CLI returned failure.
The standalone 22-unit identity success does not replace this combined gate.
Repeat it without another heavy native build running; do not disable diagnostics.

The full twelve-patch composition was rechecked against registered source 001-040
across 113 paths, including isolated Mojo and GPU command generation:
`identity-readback-001-040-batch-v1.json` on D. Active source/core/GN remained
unchanged; `compiled=false`, `mode_enabled=false`, `privacy_admitted=false`.

The same twelve-patch composition also passed against registered 001-045:
`identity-readback-001-045-batch-v1.json` on D, including isolated Mojo and
GPU command generation. This does not register the candidates or validate
their optimized code, linked fixtures or browser behavior.

Composition also passed on source 001-047 after promotion of the paired halo/
clipped-publication repair: `identity-readback-001-047-batch-v2.json` on D
(rechecked after the typed-result correction in the unverified halo patch).
The checker reverses those two exact registered patches only inside its owned
copy before reconstructing the full composition. The six identity and four
remaining GPU transport patches are still unregistered; no identity mode is enabled.

## Still required

- Execute native fixtures, including unchanged legacy privacy vectors.
- Verify real BrowserContext/OTR lifetime and persisted profile restart.
- Compile and execute the selected producer and versioned delivery candidates;
  verify rejection of unknown wire modes before consuming any seeds.
- Preserve final-partition authorization and renderer/worker IPC binding regardless
  of the entropy mode; a renderer must never choose another profile or mode.
- Validate cross-context, cross-origin and cross-API consistency before using
  identity-derived keys for fingerprint surfaces. Stable keys alone do not make
  an arbitrary noise algorithm or fabricated GPU/OS identity plausible.
- Keep UI/capability admission blocked until the selected mode and exact binary
  pass those gates. Presets, renderer mode delivery and mobile identity are not
  implemented by this derivation candidate.
