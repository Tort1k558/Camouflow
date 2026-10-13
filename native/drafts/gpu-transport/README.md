# GPU attachment metadata transport — candidate

**Unregistered, uncompiled, not a verified browser capability.**

Apply after the two candidates in `../next-readback/`, in order:

1. `webgl_halo_readback_candidate.patch`
2. `webgl_clipped_publication_candidate.patch`
3. `gpu_readback_metadata_candidate.patch`

## Native path

| Layer | Candidate implementation |
| --- | --- |
| Command ABI | Append command 580; preserve all 324 existing command IDs |
| Client | Fixed seven-value result; exact result length before copying |
| Service | Both validating and passthrough decoders; checked shared-memory result |
| Attachment | Native selected read attachment dimensions, format and samples |
| Textures | Actual level/face/layer queries; explicit unavailable if unsupported |
| Blink | Consume validated metadata; reject unsupported formats/multisampling |
| Default | `GlintReadbackMetadataCandidate` disabled; no WebGL JS API added |

The descriptor contains schema, availability, width, height, actual internal
format, samples and byte-format compatibility. It contains no profile keys.
Texture queries require the real ANGLE query capability. They do not infer
dimensions from the viewport or invent GPU identities/capabilities.

## Source replay

From the CamouFlow repository with the exact applied 001–034 checkout:

```powershell
.venv\Scripts\python.exe scripts/verify_native_gpu_transport_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\gpu-transport-replay.json
```

Use a new private report path. The verifier applies all three patches to an
isolated copy, compares canonical helpers, checks command IDs, and verifies that
active sources remain unchanged. **It does not compile or admit privacy features.**

## Required before promotion

- Compile the generated command, both decoders, Blink consumer and 12 codec fixtures.
- Test shared-memory bounds, initialized/short results, feature-off and context loss.
- Verify real renderbuffer, 2D/cube/array/3D texture levels and attachment changes.
- Verify completeness, native object ownership and unsupported formats/layers.
- Preserve GL bindings, pending errors, pack state, CPU/PBO destination boundaries.
- Run protected readback and combined document/worker/restart gates against the
  exact newly built binary; upstream/model/source replay is insufficient.

Float/integer/HDR attachments and WebGPU readback remain outside this candidate.
