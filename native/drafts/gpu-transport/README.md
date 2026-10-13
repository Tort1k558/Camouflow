# GPU attachment metadata transport — candidate

**Unregistered, uncompiled, not a verified browser capability.**

Apply after the two candidates in `../next-readback/`, in order:

1. `webgl_halo_readback_candidate.patch`
2. `webgl_clipped_publication_candidate.patch`
3. `gpu_readback_metadata_candidate.patch`
4. `gpu_readback_metadata_protocol_tests.patch`
5. `gpu_readback_metadata_attachment_tests.patch`
6. `gpu_readback_metadata_passthrough_attachment_tests.patch`

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
.venv\Scripts\python.exe scripts/verify_native_gpu_transport_draft.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\gpu-transport-replay.json --check-codegen
```

Use a new private report path. The verifier applies all six patches to an
isolated copy, compares canonical helpers, checks command IDs, and verifies that
active sources remain unchanged. `--check-codegen` also reruns the pinned GPU
generator and formatter in that copy and checks every copied generated header.
This option currently requires the Windows checkout's formatter.
**It does not compile or admit privacy features.**

## Required before promotion

- Compile the generated command, both decoders, Blink consumer and 12 codec fixtures.
- Execute the 10 prepared decoder fixtures: feature-off unavailable response,
  invalid shared-memory ID, overflowing offset, truncated storage and initialized
  result rejection, on both decoder backends. Error cases check the entire shared
  buffer remains unchanged; the unavailable response checks its trailing sentinel.
- Execute the three prepared feature-on validating-decoder attachment fixtures:
  actual RGBA8 dimensions, integer format remaining non-byte-compatible, and
  renderbuffer redefinition updating dimensions. These execute the native command,
  not just the standalone codec.
- Compile and execute the four feature-on passthrough attachment fixture
  definitions: RGBA8 dimensions with restored renderbuffer binding, current
  dimensions after redefinition, integer format remaining non-byte-compatible,
  and metadata querying while preserving a pending client GL error. These use
  the existing GLES3 passthrough context/command helpers; no skip or success
  substitute is supplied. They are prepared, not executed.
- Test shared-memory bounds, initialized/short results, feature-off and context loss.
- Verify real renderbuffer, 2D/cube/array/3D texture levels and attachment changes.
- Verify completeness, native object ownership and unsupported formats/layers.
- Preserve GL bindings, pending errors, pack state, CPU/PBO destination boundaries.
- Run protected readback and combined document/worker/restart gates against the
  exact newly built binary; upstream/model/source replay is insufficient.

Float/integer/HDR attachments and WebGPU readback remain outside this candidate.

## Prepared identity observation contract

`verify_native_gpu_readback.validate_readback` accepts explicit
`derivation_mode="profile-identity"` for prepared owned runners. It requires
equal protected WebGL and renderbuffer outputs across all document/worker
contexts; the default partitioned-privacy contract still requires cross-site
differences. Both retain PNG/pixel agreement, CPU/PBO padding, GL state/errors,
context loss, upper colour bits and alpha checks. Unknown modes reject.

`validate_profile_isolation` validates the baseline and both protected profiles
before comparing their WebGL and renderbuffer outputs. Both profiles must differ
from the baseline and each other in every context. The registered runtime runner
uses this same check with the existing partitioned-privacy default.

These are synthetic validator checks, not protected browser results. The runtime
CLI/receipt gate still exercises registered partitioned privacy only; identity
activation and binary admission are not enabled by this parameter.
