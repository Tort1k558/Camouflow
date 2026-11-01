# Canvas rendering v2 — unselected source package

**Implementation draft, not a built or admitted replacement.**

The [rendering experiments](../canvas-native-rendering/) measured native font/text
controls with readback masking off. This packet makes the requested pipeline
explicit rather than silently replacing the historical readback algorithm.

| Layer | Implemented in this draft |
| --- | --- |
| Host settings | `canvas_pipeline_version: 2` and an explicit `canvas_rendering_preset` |
| Legacy settings | Absent version stays unchanged; no rewrite, randomization or migration |
| Preset contract | Seven measured Windows presets; actual raster/gamma/contrast switches must match |
| Browser/renderer | Validate intent, forward pipeline/preset, reject conflicting or incomplete settings |
| Documents/workers | Native Canvas readback only after required, ready, owned **profile-identity** policy |
| PNG exports | Follow the same Canvas routing; disabled GPU protection cannot silently fall back to raw Canvas |
| Other surfaces | WebGL/WebGPU/Audio routing is not replaced |
| Admission | New `canvas-rendering-v2` capability; **no existing managed package admits it** |

`canvas-rendering-v2.patch` extends the exact 131-patch R8 source state, touching
11 files including two headers and six prepared native unit tests. Source replay
applied and reversed exactly, including removal of newly added files.
`host-policy.patch` extends the hash-bound current `app/core/native/privacy.py`.
Apply only to independent disposable trees; neither patch is registered as an
active candidate. Canonical source, manager runtime and existing profile settings
remain unchanged.

Six translation units passed C++ parsing/type-checking using pinned generated
target flags and VFS overlays: browser privacy context, renderer launch, renderer
startup, Canvas scope routing, HTML Canvas export and the new unit-test source.
Active source/core and input postguards passed. This generated no browser or
test binary and executed **none** of the six prepared native test cases.
The initial wrong-generated-target lookup failed before compilation and remains
bound in `source-observations.json`; the correct target was not guessed past a gate.

```sh
git -c core.autocrlf=false apply canvas-rendering-v2.patch
# In a separate disposable CamouFlow checkout:
git -c core.autocrlf=false apply host-policy.patch
```

Example persisted intent after applying the host draft:

```json
{
  "surface_policy_version": 1,
  "fingerprint_derivation_mode": "profile-identity",
  "canvas_pipeline_version": 2,
  "canvas_rendering_preset": "grayscale",
  "font_rasterization": "grayscale"
}
```

This example is not a launch workaround: reviewed-package admission remains
mandatory. Partitioned-privacy mode is rejected because these process-wide
rendering controls do not implement origin-specific rendering identities.
Non-Windows v2 intent is rejected, not silently emulated.

## Required before activation

- Compile/link the complete browser and execute the six native tests.
- Exercise actual v2 policy bootstrap, iframe/workers, restart, teardown and
  missing/stale policy failures; baseline controls alone do not prove v2 routing.
- Test 2D/readback/PNG and GPU/Audio together, including disabled-feature rejection,
  translucent pixels, colour spaces, fonts and text metrics/layout.
- Bind profile configuration changes and restore/clone semantics explicitly.
- Establish measured coherent device templates before any automatic preset selection.
- Review/package the resulting binary, then run manager/update/rollback gates.

Presets are explicit, **not seed-selected or validated real-device cohorts**.
Native rendering mode intentionally stops 2D post-readback masking; that alone
does not establish privacy, profile uniqueness or external detector acceptance.
Old colour-fidelity failures remain in their historical records.
