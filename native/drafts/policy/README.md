# Surface policy v2 candidate

Unregistered, uncompiled and not transported into Blink. Existing Canvas v1 IPC
and active 0030 build sources are unchanged.

`CreateSurfacePolicy` prepares one UI-sequence, browser-owned snapshot containing
independently derived Canvas, WebGL, WebGPU and Audio partition seeds. It reuses
the existing BrowserContext key service and derivation domains; no new root key,
page-provided origin, renderer derivation or profile identifier is introduced.
Unready/failed/shutting-down contexts and incomplete snapshots produce no policy.
Typed validation rejects unsupported versions, invalid encoding, any pair of
reused surface seeds and a different final partition, including nonce, retained
top-level site and exact binary encoding. A preflight owns all four seeds only
after checking every payload length; it reuses document StorageKey resolution
and still requires final-partition validation. Ten validator, five preflight
and four producer fixtures plus two wire ownership/validation fixtures are not
compiled or executed yet.

`surface_policy_helpers_integration.patch` registers helper/fixture sources in
candidate GN targets only. It replays alongside GPU and Audio drafts without
applying changes to the active checkout; it does not replace any v1 IPC.

`surface_policy_wire_schema.patch` registers a separate, currently unused Mojo
schema. Its four fixed-length seed arrays and binary ByteString encoding passed
the pinned Mojo parser and C++ binding generator in an isolated directory
(`surface-policy-bindings-v1/proof.json` on D). `surface_policy_wire.h` prepares
validated owned encoding/decoding without connecting an endpoint. Generated
bindings are not C++ compilation, navigation/worker delivery or admission.

Before installation: compile/test the codec; connect its one owned v2 payload to
document/worker bootstrap coherently; validate all four seed lengths before copying;
retain old v1 behavior only for explicitly Canvas-only development launches.
Validate the final document/worker StorageKey, preserve token-bound rejection,
and make first-script, restart, multi-client worker and failure tests cover every
surface. Do not derive Audio keys from the Canvas seed or expose this snapshot
through JavaScript. v2 versioning must not change the established v1 profile key
derivation domain: transport format and identity derivation are separate contracts.

This snapshot alone enables no protection. Worker Audio API absence remains
explicit; no real-time AudioContext hook or emulated OS/GPU is claimed.

## Reproduce batch composition

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_next_batch.py `
  --workspace D:\CamouFlowNative `
  --report D:\CamouFlowNative\next-batch-new.json
```

Use a new absolute report outside the application and Chromium repositories.
The public checker passed across 26 composed paths on registered 001-030 source:
`gpu-audio-policy-public-replay-v3.json` on D. It verifies registered source
replay, exact canonical copies, active source/core/receipt/GN invariants and
records input hashes. No compiler, linker, browser or capability admission runs
inside this composition checker.
