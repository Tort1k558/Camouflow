# R11: opaque GPU image-source normalization

**Windows build, native groups and selected browser checks passed. Not admitted.**

| Measured result | Evidence |
| --- | --- |
| Incremental Windows build | [52 steps in 14m 15.80s](windows-build.json), maximum j4 |
| Native units | [29 groups, 586 executions / 429 distinct cases](native-all-observations.json) |
| Host regression | [5937 passed, one skipped](host-observations.json), exact recorded commit |
| Browser rendering/restarts | [All 14 selected-v2 phases passed](runtime-observations.json) |
| Opaque and alpha-enabled copies | 32 direct variants, 40 worker-frame copies passed |
| Matched GPU identities | Two profiles and restarts: 40 contexts / 240 texture observations passed |
| 4096-square RGBA8 | [All six full-image copies passed](large-image-resources.json) |
| Resource measurement | **Incomplete**: a process-tree transition invalidated one sample; original failure retained |

### GPU-process recovery: selected protected modes passed

[Actual recovery observations](gpu-recovery-observations.json) cover three
`Browser.crashGpuProcess` commands: a matched unselected baseline, protected
native rendering and protected gamma-1400/contrast-300. Each preserves the same
five documents without navigation or page crashes. A live device reports one
loss callback; mapping its old buffer rejects with `AbortError`.

Before/after checks cover eight document/frame/worker contexts per mode:
48 context executions and 288 texture observations, including 32 protected
context executions. Pixel/export/error consistency passes the existing explicit
v2 contract and state comparison; translated shader debug-source length is not
part of that identity comparison. The [exact public collector](measure_gpu_recovery.py)
was executed on the receipt-bound independent R11 runtime, with cleanup and
source/asset/driver postguards passed. Injected failure tests are separate.

This verifies the selected GPU-process restart path, not a physical GPU reset,
browser/renderer crash, retained pre-crash worker GPU objects, continuous resource
coverage or manager/package recovery admission. Older failed recovery controls
remain unchanged. No engine capability or production flag is activated.

### Resource follow-up: navigation transition isolated

Two additional full 4K runs retain all six exact image-copy results, but each
has one unavailable tree capture **during navigation, before image evaluation**.
The [timestamped observations](large-image-resource-timeline.json) preserve both
failures, every successful sample and the original resource-record hash.
Their sampled private-commit maxima were about 1.77 and 1.95 GiB; neither is an
exact peak. The whole resource gate still fails: navigation is not excluded.

The public [collector](measure_large_rgba.py) uses the existing creation-bound
process monitor and [image validator](validate_large_rgba.py). It takes an owned
runtime factory and explicit configuration through `await measure(make, configuration)`;
the factory receives a fixture name and configuration. Callers must select and
verify their binary/receipt/driver before supplying that factory. No credentials,
runtime discovery, fallback, topology retry or admission override is provided.
The second recorded run executed these exact public collector bytes. Separate
injected tests cover missing samples and cleanup; they are not browser results.

The measured 4K private-commit maximum is a successful **sample**, not an exact
peak or a memory limit. The 64 MiB raster budget does not bound whole-browser
memory. Legacy Audio, device cohorts, broader formats/resources and package/
manager/recovery acceptance remain separate gates. The older shared-worker
mismatch did not recur in this run; no specific worker-rendering fix is claimed.

The complete 136-patch recipe preserves the exact 135-patch R10 prefix and adds
the [opaque-source repair](../canvas-opaque-sources/README.md). Source replay
passes 136 forward/reverse patches, matches 406 final files and restores 273
upstream inputs. No dependency, SDK, compiler, args or resource floor changed.

| Gate | State |
| --- | --- |
| New native group | `gpu-opaque-sources`: all five exact blink_unittests cases passed |
| Existing native groups | All 28 R10 case definitions and binary mappings retained |
| Resources | Maximum j4; one heavy link; full-build reserve 180 GiB |
| R10 history | Exact earlier host sources retained through a reversible archive |
| Browser repair | Selected opaque copy/frame fixtures passed; independent R10/R11 runtimes retained |
| Manager / package admission | Unchanged; no capability activated |

Use the [normal Windows workflow](../../BUILDING.md) with the explicit candidate
`upstream-156-image-r11`. Preserve/reverse the verified owned R10 delta first;
never stack the complete recipe directly over its old prefix or reset foreign
changes. The preparation record is historical source-only evidence, not a
current build or native-unit result.

Next: process-churn/resource evidence, broader large-image/format/lifecycle checks,
repeat the original combined worker sequence and complete manager/package/update/
rollback/recovery and device-cohort gates. The old failures remain preserved.
No detector/CAPTCHA, privacy, installed-package or production verdict exists.
