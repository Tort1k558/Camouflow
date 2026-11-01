# R9: explicit Canvas rendering pipeline

**Registered Windows research recipe, not a compiled or admitted runtime.**

| Component | State |
| --- | --- |
| Base | Exact 131-patch R8, unchanged dependency/source pins |
| Extension | `0132-canvas-rendering-v2.patch` |
| Complete source replay | 132 forward / reverse; 403 final files matched, 270 upstream inputs restored |
| C++ validation | Six translation units type-checked in the component packet; no browser link |
| New native group | `canvas-rendering`, six exact cases in `blink_common_unittests` |
| Existing groups | All 26 R8 target definitions and binary selections preserved |
| Resource gates | Maximum four jobs; 180 GiB free-space preflight unchanged |
| Runtime / managed-package admission | Not verified / unchanged |

[Manifest](manifest.json), [source preparation](preparation.json),
[implementation and host policy draft](../canvas-rendering-v2/README.md).
The recipe keeps historical readback behaviour unless version 2 is explicitly
requested with matching native rendering settings and owned profile-identity
bootstrap. It does not introduce automatic device-template selection or promise
external detector acceptance.

Use the [normal native build workflow](../../README.md) with the explicit
`upstream-156-canvas-r9` candidate. A populated R8 checkout must first undergo
the guarded owned-source transition and backup verification; do not reset foreign
changes or apply this complete chain directly over R8 modifications. Preserved
R8 runtime remains separate from writable output.

The six prepared native cases still need compilation/execution. Browser bootstrap,
mixed GPU/Audio behaviour, recovery and manager/package gates remain mandatory
before any new capability can be admitted.
