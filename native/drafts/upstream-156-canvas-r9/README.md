# R9: explicit Canvas rendering pipeline

**Built Windows research runtime. Native tests pass; combined browser admission fails.**

| Component | State |
| --- | --- |
| Base | Exact 131-patch R8, unchanged dependency/source pins |
| Extension | `0132-canvas-rendering-v2.patch` |
| Complete source replay | 132 forward / reverse; 403 final files matched, 270 upstream inputs restored |
| Browser build | Incremental 68 steps / 28m 07.12s; not a clean Chromium build |
| Native tests | All 27 groups: 560 executions / 403 distinct cases, including six new Canvas cases |
| Canvas runtime | 154 document/worker observations, 42 security observations, seven restart pairs |
| Rendering / exports | 280 images / 392 decoded PNG exports; known colours and repeats pass |
| Invalid launches | All 11 malformed policies rejected by the native check; positive control passes |
| Blocking failure | WebGL direct readback/PNG disagree with raw drawImage/ImageBitmap copies |
| Resource gates | Maximum four jobs; 180 GiB free-space preflight unchanged |
| Full runtime / managed-package admission | Failed / unchanged |

[Manifest](manifest.json), [source preparation](preparation.json),
[implementation and host policy draft](../canvas-rendering-v2/README.md).
[Browser build](windows-build.json), [all native results](native-all-observations.json),
[actual runtime results and retained failures](runtime-observations.json).
The recipe keeps historical readback behaviour unless version 2 is explicitly
requested with matching native rendering settings and owned profile-identity
bootstrap. It does not introduce automatic device-template selection or promise
external detector acceptance.

Use the [normal native build workflow](../../README.md) with the explicit
`upstream-156-canvas-r9` candidate. A populated R8 checkout must first undergo
the guarded owned-source transition and backup verification; do not reset foreign
changes or apply this complete chain directly over R8 modifications. Preserved
R8 runtime remains separate from writable output.

The browser run used seven explicit presets and production profile-surface
bootstrap through research launch arguments, not managed-package admission.
All 14 phases were measured; the combined verdict is **failed**, not partial PASS.
The old WebGL validator also expects unprotected WebGPU texture bytes. Captured
WebGPU repeats/sampled copies preserve padding, alpha and upper bits, but this
does not replace a protected WebGPU acceptance gate.

Next: fix source-image copy consistency without weakening its exact check,
establish the correct protected WebGPU gate, then repeat combined checks and
manager/package/recovery gates. Legacy Audio and real-device cohorts remain open.
