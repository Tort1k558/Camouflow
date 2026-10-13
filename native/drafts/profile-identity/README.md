# Stable profile identity — derivation candidate

**Unregistered and uncompiled. No identity mode is enabled.**

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

```powershell
.venv\Scripts\python.exe scripts/verify_native_profile_identity_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\immutable-mode-replay.json --include-mode
```

This is a source/API component, **not an enabled fingerprint mode**. Producers,
wire-mode delivery, renderer/worker consumption, launch settings and UI admission
are not integrated. The default is preserved for existing callers, not a product
decision to use partitioned noise as an ordinary browser identity.

## Remaining gates

- Execute native fixtures, including unchanged legacy privacy vectors.
- Verify real BrowserContext/OTR lifetime and persisted profile restart.
- Integrate the immutable browser-owned mode into trusted policy production and
  versioned delivery; reject unknown wire modes before consuming any seeds.
- Preserve final-partition authorization and renderer/worker IPC binding regardless
  of the entropy mode; a renderer must never choose another profile or mode.
- Validate cross-context, cross-origin and cross-API consistency before using
  identity-derived keys for fingerprint surfaces. Stable keys alone do not make
  an arbitrary noise algorithm or fabricated GPU/OS identity plausible.
- Keep UI/capability admission blocked until the selected mode and exact binary
  pass those gates. Presets, renderer mode delivery and mobile identity are not
  implemented by this derivation candidate.
