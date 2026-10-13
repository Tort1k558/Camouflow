# GPU attachment metadata transport — candidate

**Unregistered; command/decoder/Blink integration is uncompiled and not a verified browser capability.**

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

The 14 standalone codec fixtures compiled with the checkout's `clang-cl` and
executed successfully on Windows. This uses the VS C++ runtime/standard library,
not the full Chromium build/link configuration. Strict verification rejects
missing, duplicate, skipped, foreign and failed cases; inputs and the active
browser/GN files are checked for changes. Private proof:
`D:\CamouFlowNative\gpu-metadata-codec-classification-native-v1.json`.

The codec now rejects a byte-colour claim attached to float, integer, packed
low-bit or unknown formats, in both encoding and decoding. Only RGB/RGBA and
RGB8/RGBA8 can carry that claim; actual native channel/type measurements still
decide whether it is true. A false claim and real multisample count are preserved,
not promoted into a compatible single-sample attachment.

```powershell
.venv\Scripts\python.exe scripts/verify_native_gpu_codec.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\gpu-codec-new-report.json --vs-installation D:\CamouFlowNative\toolchain\BuildTools
```

This compiles only into a disposable private directory, never the active output.
It does not verify decoder execution, GPU calls, Blink ABI or privacy admission.

- Compile/link the generated command, both decoders, Blink consumer and codec fixtures in Chromium.
- Execute the 10 prepared decoder fixtures: feature-off unavailable response,
  invalid shared-memory ID, overflowing offset, truncated storage and initialized
  result rejection, on both decoder backends. Error cases check the entire shared
  buffer remains unchanged; the unavailable response checks its trailing sentinel.
- Execute the three prepared feature-on validating-decoder attachment fixtures:
  actual RGBA8 dimensions, integer format remaining non-byte-compatible, and
  renderbuffer redefinition updating dimensions. These execute the native command,
  not just the standalone codec.
- Compile and execute the fourteen feature-on passthrough attachment fixture
  definitions: RGBA8 dimensions with restored renderbuffer binding, current
  dimensions after redefinition, integer format remaining non-byte-compatible,
  metadata querying while preserving a pending client GL error, native RGBA8
  texture dimensions with restored texture binding, and reattachment selecting
  the new framebuffer texture rather than the currently bound texture. The next
  two definitions cover a complete selected mip level (not base dimensions) and
  a selected cube face with preserved cube-map binding. Two further definitions
  exercise selected layers of complete 2D-array and 3D textures while restoring
  their target-specific bindings. Three more definitions verify selected read
  attachment format, `GL_NONE` and incomplete-framebuffer unavailable responses,
  including unchanged read selection and absence of added client GL errors. A
  multisample definition compares metadata with a real renderbuffer sample query,
  rather than assuming that the driver allocates the requested sample count;
  byte-colour format compatibility remains separate from sample count. These use
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

Passing `previous=` validates both observations before requiring restart-stable
readback, export and metadata. Only translated shader debug-source length is
excluded from identity comparison because ANGLE may reuse its shader cache;
the existing GPU validator still checks that field's presence/type/semantics.
The registered runtime runner uses this same restart check.

`validate_profile_isolation` validates the baseline and both protected profiles
before comparing their WebGL and renderbuffer outputs. Both profiles must differ
from the baseline and each other in every context. The registered runtime runner
uses this same check with the existing partitioned-privacy default.

These are synthetic validator checks, not protected browser results. The runtime
CLI/receipt gate still exercises registered partitioned privacy only; identity
activation and binary admission are not enabled by this parameter.
