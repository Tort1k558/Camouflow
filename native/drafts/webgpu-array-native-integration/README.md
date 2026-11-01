# Dawn array/mip integration packet

**Source integration prepared; six translation units passed native-target syntax.
Not linked, browser-tested or admitted.**

| Source change | Contract |
| --- | --- |
| Paired CPU/GPU snapshots | Both use the same validated mip/layer and mip dimensions |
| Multi-layer texture copies | Separate snapshots and destination offsets per layer; row-stride, overflow and logical buffer bounds checked |
| Sampled views | Shared validator for projection, compute/render bindings and descriptor replacement; exact 2D/array range and mapping |
| Projection cache | One complete-resource projection per logical texture/projector/format; cached geometry must match all mips/layers |
| Invalidation | Existing producer-write and shared-memory begin/end access invalidation retained |

The cache deliberately stores a **complete resource**, not a selected slice.
Snapshot selection is carried separately and cannot silently return mip/layer
zero. Existing unsupported formats, external inputs and unknown provenance
remain rejected; no unprotected readback fallback is introduced.

[Immutable packet](packet.json) binds the three prerequisite patches and this
six-file Dawn adapter patch. [Measured observations](observations.json) bind the
composed ten-file overlay, compiler flags, generated module inputs and postguards.
The canonical R5 checkout is only read, not patched.

## Reproduce

Requires the existing, patched R5 checkout and generated native target files:

```powershell
python native/drafts/webgpu-array-native-integration/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/array-native-integration-fresh
```

The checker copies hash-matched source files to a fresh D: overlay, applies each
patch in order and validates every pre/postimage. It then uses the generated
Dawn target flags and a private VFS overlay for syntax checks. Existing generated
headers and cached system modules are inputs, not a hermetic native rebuild.

## Next gate

Register the complete packet as a new candidate while preserving the exact R5
prefix and binary. Link/build it, then test direct and sampled reads across all
mips/layers, multi-layer copies with row/image padding, mutation/invalidation,
documents/iframe/workers and profile restarts. Also repeat the large-resource,
GPU-crash and unprotected-baseline gates before manager/package admission.

Recoverable exhaustion of the complete pipeline is not established by the
standalone projection's atomicity tests. Existing readable storage-texture,
external-input and render read/write-dependency restrictions are not resolved
here. R5's recorded protected array/mip map failure remains **unfixed in its
actual binary** until a new candidate passes those runtime gates.
