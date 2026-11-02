# R11: opaque GPU image-source normalization

**Registered Windows research recipe. Not built or admitted.**

The complete 136-patch recipe preserves the exact 135-patch R10 prefix and adds
the [opaque-source repair](../canvas-opaque-sources/README.md). Source replay
passes 136 forward/reverse patches, matches 406 final files and restores 273
upstream inputs. No dependency, SDK, compiler, args or resource floor changed.

| Gate | State |
| --- | --- |
| New native group | `gpu-opaque-sources`: five exact blink_unittests cases, unexecuted |
| Existing native groups | All 28 R10 case definitions and binary mappings retained |
| Resources | Maximum j4; one heavy link; full-build reserve 180 GiB |
| R10 history | Exact earlier host sources retained through a reversible archive |
| Browser repair | Unverified; preserve the independently measured R10 runtime |
| Manager / package admission | Unchanged; no capability activated |

Use the [normal Windows workflow](../../BUILDING.md) with the explicit candidate
`upstream-156-image-r11`. Preserve/reverse the verified owned R10 delta first;
never stack the complete recipe directly over its old prefix or reset foreign
changes. The preparation record is historical source-only evidence, not a
current build or native-unit result.

Next: current host regression, rollback/source binding, guarded transition and
one Windows build, all 29 native groups, then the original opaque transfer/frame
fixtures, both alpha modes, matched GPU/restart/isolation and resource checks.
The old combined shared-worker mismatch remains open despite the focused retry.
No detector/CAPTCHA, privacy, installed-package or production verdict exists.
