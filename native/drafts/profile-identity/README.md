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

## Required next

- Execute native fixtures, including unchanged legacy privacy vectors.
- Verify real BrowserContext/OTR lifetime and persisted profile restart.
- Introduce an explicit versioned browser-owned mode and trusted policy selection.
- Preserve final-partition authorization and renderer/worker IPC binding regardless
  of the entropy mode; a renderer must never choose another profile or mode.
- Validate cross-context, cross-origin and cross-API consistency before using
  identity-derived keys for fingerprint surfaces. Stable keys alone do not make
  an arbitrary noise algorithm or fabricated GPU/OS identity plausible.
- Keep UI/capability admission blocked until the selected mode and exact binary
  pass those gates. Presets, renderer mode delivery and mobile identity are not
  implemented by this derivation candidate.
