# Glint Chromium 156 R6: array/mip candidate

**Windows binary built and measured; incomplete browser gates, not admitted.**

Preserves the exact **124-patch R5 prefix** and appends four Dawn-owned packets:
selected CPU capture, selected GPU projection, transactional complete-array
projection and the paired-snapshot/copy/view adapter integration.

| Gate | Status |
| --- | --- |
| Full repository-aware replay | 128 forward / reverse; 270 upstream files restored |
| Final source comparison | 400 files match the composed packet |
| Resource/upstream pins | Unchanged; Windows maximum j4, full-build reserve 180 GiB |
| Primitive hardware and adapter syntax | Separate linked evidence below |
| Source transition / native build | Passed; 90 Siso steps in 17m 27.66s, max j4 |
| Native context / launch / worker cases | 116 passed; source/core postguards passed |
| Full host regression | 5503 passed, 1 skipped at the measured source commit |
| Core browser runtime suite | 160 checks passed |
| Normal policy, exact keyed texture reference | Corrected recheck passed; 288 captured cases match independent CPU reference |
| Selected mip/layer views, large textures, GPU recovery | Passed in the owned local fixtures |
| Full padded multi-layer transfer / mutation fixture | Readback policy rejection; unresolved |
| Legacy Audio | Fidelity/analyser/worklet failed; Math and Math restart passed |
| Browser/manager/package admission | Not granted |

[Recipe evidence](preparation.json) is not build evidence.
[Windows build](windows-build-observations.json),
[native cases](native-unit-observations.json),
[host regression](host-regression-observations.json) and
[browser observations](browser-observations.json) record separate measured gates.
The original normal-policy stock-pixel oracle failure is retained: the corrected
keyed reference passed a 656-test host regression and a fresh browser recheck.
The additional padded-array failure is a real outstanding compatibility issue,
not reclassified as success by that oracle correction.
[Native integration packet](../webgpu-array-native-integration/README.md) records
the source composition and six target-flag syntax checks; its prerequisites
record hardware/ASan tests. Neither proves a linked Chromium runtime.

```powershell
python scripts/native_build.py build --workspace D:/Glint156Candidate `
  --candidate upstream-156-webgpu-r6 --jobs 4 --local-windows-toolchain
```

Only run the build after the owned, backed-up source transition and official
dependency/patch stages have produced matching receipts. Do not overwrite a
running browser or alter output mtimes. Preserve the R5/148 binaries and caches.

Next: fix the full padded-array readback rejection, then rerun the multi-layer
context and mutation matrices without dropping padding, remap or shader checks.
Preserve the completed R6 binary and failed reports for counterfactual comparison.

Legacy Audio and recoverable pipeline quotas remain open. Linux/macOS remain
deferred; no CAPTCHA/detector result follows from this registration.
