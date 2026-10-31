# Full WebGPU candidate, revision 3 — not compiled

This explicit research candidate preserves the exact 001–118 prefix and adds:

1. Texture-input scratch reuse and tight-row canonical/output sharing.
2. Weak internal-texture projection reuse with fence-retained leases and write invalidation.

The measured source packets remain separate:
[scratch reuse](../webgpu-scratch-reuse/README.md) and
[projection cache](../webgpu-projection-cache/README.md).
Their standalone evidence is not a Chromium runtime result.

| Preparation gate | Result | Boundary |
| --- | --- | --- |
| Forward/reverse replay | All 120 patches | No selected checkout changes |
| Upstream restoration | 270 files | Includes two newly required pinned Dawn texture files |
| Final standalone source match | Seven files | Same code used in native prototype measurements |
| Chromium compilation/runtime | Pending | No installed release or capability promotion |

Select `--candidate upstream-156-webgpu-r3` explicitly. Chromium/V8/Dawn pins,
the 180 GiB reserve and maximum four build workers remain unchanged. The default
candidate and earlier manifests, receipts and preserved runtimes are untouched.
Candidate-specific sync/hooks/build receipts cannot be relabeled from revision 2.

An existing patched checkout requires an exact, backed-up source transition
before sync/patch/build. Do not reset or clean a user worktree to switch variants.
See the [build guide](../../README.md) for the normal Windows toolchain workflow.

Legacy Audio compatibility remains failed. Retained-budget exhaustion still
loses the GPU device. External/shared texture caching, broad browser/worker
validation, privacy admission and production admission remain separate gates.
