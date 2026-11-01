# Native Canvas rendering investigation

**Measured rendering controls, not an admitted Canvas v2 policy.**

Instead of modifying known pixel colours on readback, this experiment measures
existing native font rasterization and text-tuning controls. Readback masking
is **off** in every phase. No domain exceptions or JavaScript API wrappers.

| R8 Windows measurement | Result |
| --- | --- |
| Presets | Native, aliased, grayscale, ClearType RGB/BGR, two native gamma/contrast pairs |
| Contexts | HTML canvas, OffscreenCanvas, same-origin iframe, classic/module worker |
| Coverage | 7 presets × first launch/restart × 5 contexts × 2 alpha modes = **140 images** |
| Repeated reads / same-profile restart | Exact in all measured images |
| Same-preset images across contexts | Exact |
| Known uniform opaque colour | Exact in all 70 context observations |
| Distinct transparent/opaque image pairs | **6**, not 7; Native and ClearType RGB coincide |

[observations.json](observations.json) binds the runtime, raw reports, runner,
measured validator, portable probe patch and stricter publication validator.
The first attempt's rejected grayscale + gamma combination remains recorded;
the existing native-only text-tuning guard was not weakened.

Apply `probe-extension.patch` to an independent disposable copy of the repository
with its unchanged `native/drafts/canvas-roundtrip/probe.js`. It replaces only
the diagnostic measurement, reusing the existing context/worker orchestration.
The reconstructed probe must match `probe_sha256` before executing it. Never
apply it to the canonical measured fixture or an active build checkout.

```sh
git -c core.autocrlf=false apply native/drafts/canvas-native-rendering/probe-extension.patch
```

## Scope and next implementation gates

- All 2D contexts use `willReadFrequently: true`; no default/GPU backing claim.
- The colour check is one uniform fill, **not** the earlier multicolour contract.
- Windows, headless, loopback only; no proxy or external detector verdict.
- Manual native controls are not yet derived from a versioned profile identity.
- Six rendering outcomes do not establish six real-device cohorts or anonymity.
- Aliased rendering also changes text metrics. Presets cannot be treated as
  interchangeable without checking layout and font/OS consistency.
- No Canvas exports, P3/float16, GPU combination, real-device comparison or
  manager activation is validated by this packet.

Next: bind rendering settings to explicit versioned profile configuration;
preserve old settings and keys without silent migration; verify default backing,
multicolour drawing, exports, metrics, restart and cross-context delivery. Only
then evaluate a replacement for [the measured readback colour failure](../canvas-roundtrip/).
Turning masking off alone is not a new privacy protection.

## Expanded backing and PNG experiment

[Expanded record](expanded-observations.json), same R8 runtime, **280 images /
392 PNG exports** across seven presets, first launch/restart and five contexts:

| Additional contract | Measured result |
| --- | --- |
| `willReadFrequently: false` and `true` requests | Both completed; actual GPU allocation not established |
| Known 8×8 multicolour CSS fill / uniform fill | Exact in all 140 context/backing observations |
| HTML/iframe `toDataURL`, `toBlob` | Decoded PNG pixels equal native readback |
| Offscreen/worker `convertToBlob` | Decoded PNG pixels equal native readback |
| Repeat reads, cross-context pixels/metrics, seven profile restart pairs | Exact |

Ordinary and frequent-read backing requests can produce different glyph pixels
even in the Native baseline. No validator demands equality across these requests;
each is compared with its own exports, repeated reads and same-profile restart.
PNG drawings here have an opaque white background even for alpha-enabled
contexts: this does not validate translucent export rounding or colour spaces.

`expanded-probe-extension.patch` applies to the **original** roundtrip fixture,
not after `probe-extension.patch`. Use an independent disposable copy and
`git -c core.autocrlf=false apply` as above, then verify `probe_sha256`.
`validate_expanded.py` reuses the strict text validator and independently checks
backing coverage, PNG methods, decoded hashes, multicolour counts and verdicts.
All measured phases were rechecked by the publication validator.

The expanded attempt initially stopped before browser launch because Python
generated caches in the pinned driver stage. Those caches and the failure record
were preserved on D:, all pinned assets were verified unchanged, and the rerun
disabled bytecode creation before imports. No staging guard was bypassed.
Seed-bound rendering, protected/mixed-policy combinations and device realism
remain open; this is still research, not an activated Canvas replacement.
