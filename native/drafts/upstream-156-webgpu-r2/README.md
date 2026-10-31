# Full WebGPU candidate, revision 2 — not admitted

This explicit variant preserves the exact 001–116 patch prefix and adds:

1. Native sampled-texture SRV routing for Dawn's single-slice 2D-array representation.
2. Readonly shader-buffer projection for indirect dispatch with unchanged controls.

The [source packet and standalone evidence](../webgpu-srv-routing/README.md)
contain 54 corrected case results and 12 comparative controls. They do not prove
the corrected Chromium runtime. The original `upstream-156-webgpu` manifest and
preserved runtime remain unchanged and available for comparison.

## Windows build evidence

The exact 118-patch Windows candidate compiled successfully on 2026-11-01:
52 executed incremental Siso steps in 15m59.29s, maximum four jobs. The complete
build command and postguards exited 0 in 1,278.414 seconds. All 269 QA runtime
assets have been independently copied and hash-verified. Browser diagnostics
have started; no passing protected WebGPU or legacy Audio result follows yet.
Receipt, DLL and manifest hashes are recorded in the
[test matrix](../../../docs/GLINT_TEST_MATRIX.md).

The pinned Chromium/V8/Dawn revisions, 180 GiB reserve and maximum four build
workers are unchanged. Select `--candidate upstream-156-webgpu-r2` explicitly.
Sync/hooks and build receipts bind this exact new manifest; an old receipt cannot
be relabeled as revision 2. No runtime, packaging or production admission follows
from source replay or standalone tests.
