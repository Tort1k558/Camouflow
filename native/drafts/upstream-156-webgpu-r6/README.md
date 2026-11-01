# Glint Chromium 156 R6: array/mip candidate

**Registered source recipe, not a compiled or admitted browser.**

Preserves the exact **124-patch R5 prefix** and appends four Dawn-owned packets:
selected CPU capture, selected GPU projection, transactional complete-array
projection and the paired-snapshot/copy/view adapter integration.

| Gate | Status |
| --- | --- |
| Full repository-aware replay | 128 forward / reverse; 270 upstream files restored |
| Final source comparison | 400 files match the composed packet |
| Resource/upstream pins | Unchanged; Windows maximum j4, full-build reserve 180 GiB |
| Primitive hardware and adapter syntax | Separate linked evidence below |
| Source transition / native build | Pending |
| Browser/manager/package admission | Not granted |

[Recipe evidence](preparation.json) is not build evidence.
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

After building: rerun the actual failed map probe, every document/iframe/worker
context, direct/sampled/multi-layer copies, row/image padding, producer mutation,
restarts, large textures and GPU recovery. Repeat the full host regression and
native context/worker units before any managed package admission.

Legacy Audio and recoverable pipeline quotas remain open. Linux/macOS remain
deferred; no CAPTCHA/detector result follows from this registration.
