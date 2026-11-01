# Bounded WebGPU readback capacity

**Source packet and isolated checks; not a compiled browser repair or admission.**

[Measured isolated checks](observations.json) bind the exact public checker,
fixture, packet and six source postimages.

| Problem | Change |
| --- | --- |
| Literal-byte padding fragments exhaust 16 regions | Compact strided masks preserve exact byte ownership through clipping, copying and publication |
| Six retained array probes exceed a shared 16-snapshot pool | Separate checked snapshot metadata capacity from the per-buffer region limit |
| CPU/GPU consumers must agree on coverage | Sparse publication validates masks; the observer validates captured-byte eligibility |
| Limits must still work | Keep 16 regions per buffer and existing 64 MiB snapshot/shadow data budgets |

The service derives metadata capacity from its live-buffer budget times the
per-buffer region budget, bounded at 4096 slots. Allocation is checked; only used
pending slots are scanned. The common four-argument constructor retains its old
16-slot contract. This is not an unlimited-resource guarantee or proof that every
resource-denial path is recoverable.

## Reproduce

Requires the exact R6 source preimages and its generated Windows targets:

```powershell
python native/drafts/webgpu-readback-capacity/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/readback-capacity-fresh
```

The checker copies hash-matched files to a fresh D: directory, applies the six-file
[packet](packet.json), runs the native fixture normally and with AddressSanitizer,
then checks three translation units using generated Chromium flags and a private
VFS overlay. It does not patch the canonical checkout or disable unsafe-buffer
diagnostics. Cached native modules and crypto libraries remain build inputs; this
is not a hermetic Chromium rebuild.

Coverage includes RGBA/BGRA, tall padded layers, exact byte/pixel coverage,
producer overwrite, partial/copy/repeat publication, tampering, stale policy,
24 retained captures, bounded 48-slot configuration, slot reuse, data quotas,
invalid capacities, move/destruction and the unchanged per-buffer region cap.

R6's original retained-buffer browser failure is preserved. Releasing completed
buffers makes the same geometry pass, independently identifying global snapshot
pressure; it does not turn that failed retained-buffer gate green.

Next: register a complete candidate, build Windows max j4, rerun the original
retained-buffer, mutation, context/restart, resource and recovery matrices. Legacy
Audio, full resource recovery and managed package admission remain open.
