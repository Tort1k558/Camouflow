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
