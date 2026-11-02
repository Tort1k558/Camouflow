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

### Renderer recovery passes; last-write browser durability fails

The [no-checkpoint crash matrix](crash-recovery-observations.json) is complete,
but its overall verdict is **failed**:

| Crash target | Baseline | Protected native | Protected gamma-1400/contrast-300 |
| --- | --- | --- | --- |
| Renderer | All five stores preserved | All five preserved | All five preserved |
| Entire browser, no graceful checkpoint | Fresh cookies/localStorage lost | Same loss | Same loss |
| GPU readback identity after recovery | Passed for both crash kinds | Passed for both | Passed for both |

IndexedDB, CacheStorage and the dedicated storage service-worker registration
survive these browser-crash cases. Neighbouring profiles remain unchanged; locks
stay held until owned teardown. The 96 before/after GPU context executions
(64 protected) pass the existing v2 contract. Renderer cases keep the same browser
root; browser cases require an actual disconnect and restart.

The [executed collector](measure_crash_recovery.py) isolates the storage worker's
scope from the GPU worker fixture. It records actual crash signals, shields the
pending CDP command across observation timeouts and consumes its result after
teardown. Final cleanup/postguards pass and the captured final log has no
unretrieved-future warnings. Both earlier harness attempts remain recorded;
their failures are not relabelled as passes.

Pinned upstream source batches cookie commits with a 30-second default and
localStorage with a five-second default. The observed loss is consistent with
those defaults, including the unprotected baseline; per-case disk flush timing
was not traced. Web API acknowledgement is not a durable checkpoint, and the
current fire-and-forget storage Flush interfaces do not prove a completed barrier.
Next: design an explicit, acknowledged native checkpoint without closing a profile,
then test errors, cancellation, cross-profile isolation and crash-after-ack. This
will not imply power-loss safety or silently make the no-checkpoint row pass.

### Source-runtime integration and selected profile recovery

[Runtime gate observations](runtime-gate-observations.json) separate two scopes:

| Scope | Measured result |
| --- | --- |
| Experimental policies off | All 18 existing source-runtime checks pass: concurrent storage, locks, permissions, local authenticated proxy, automation, Recorder/replay, backup/restore, cancellation and crash recovery |
| Two research rendering presets | Three concurrent profiles over three rounds each; six browser crashes with pre-crash checkpoints, five stores preserved and zero remaining observed owned processes |

The [full-gate collector](measure_runtime_gate.py) verifies that the base-interpreter
controller imports the same reviewed Playwright package before starting fixtures.
The first compatibility attempt passed its checks but shadowed the selected
driver through the parent interpreter's `purelib`; its result and import audit
are preserved, not used as proof of the reviewed controller chain.

The authoritative repeat used a fresh D: Python venv created with `--without-pip`.
The reviewed driver precedes existing dependency packages on `PYTHONPATH`; no
installed Python/Playwright package was modified. Set `CAMOUFLOW_DATA_DIR` to the
factory profile root's `workspace` before importing application services. Callers
still verify the explicit runtime/receipt/driver; the collector does not discover
or admit them. The [selected-profile collector](measure_profile_restarts.py)
reuses the existing multi-profile gate with explicit research configurations.

The source-runtime integration control does **not** establish those same
permissions/proxy/Recorder combinations with selected policies, an installed
package, renderer-crash recovery or durability of writes without a checkpoint.
Mobile coverage is viewport/touch Web Emulation, not Android/iOS identity.
Manager capabilities, continuous resource coverage and full admission stay open.

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
