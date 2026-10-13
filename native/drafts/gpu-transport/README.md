# GPU attachment metadata transport — candidate

**Unregistered; command/decoder/Blink integration is uncompiled and not a verified browser capability.**

## Executed metadata codec fixtures

The actual candidate `glint_readback_metadata_unittest.cc` and header were
compiled and executed with MSVC C++20, `/O2 /W4 /WX`, and the real GoogleTest
sources from the pinned Chromium checkout: **14/14 cases passed**. No test
framework, GL type or assertion was stubbed. This is a standalone standard-library
test executable, not a Chromium GN target, IPC/decoder/attachment execution,
GPU-driver test or browser admission. Browser core, GN and receipt remained
unchanged. Raw compile/test logs, results, copied candidate files and the
executable remain beside the private report on D.
Current proof: `gpu-metadata-codec-001-048-v3.json`, with raw `tests.json`
inside its `-artifacts` directory. The complete candidate composition also
passed fresh code generation after the fixture correction:
`identity-readback-codec-fixture-001-048-v1.json`. These reports do not enable
the candidate in the existing 001-047 browser.

```powershell
.venv\Scripts\python.exe scripts/verify_native_gpu_metadata_codec.py --workspace D:\CamouFlowNative --report D:\CamouFlowNative\gpu-codec-new.json --vs-installation D:\CamouFlowNative\toolchain\BuildTools
```

The first run failed under `/WX` on signed/unsigned fixture comparisons of
`GLenum` with integer GL macros. Both expected values now have the actual
`GLenum` type, in the canonical fixture and its candidate patch. No diagnostic
or test was disabled; the failed report and logs remain retained.

The current draft follows registered 001–047. It preserves explicit expected-result
checks in CPU publication and uses stateless `base::BindOnce` cleanup callbacks
with separately bound native decoder/binding arguments. The callbacks restore
renderbuffer/texture bindings on every exit and retain error-state checking;
they run synchronously within the query, not after decoder destruction.

Combined identity/readback replay and isolated Mojo/GPU code generation passed:
`identity-readback-001-037-batch-v3.json` on D. Active registered sources stayed
unchanged. This is source/bindings evidence, **not C++ decoder compilation or
browser execution**; older reports predate the 0037-compatible draft.

The decoder implementations, handler and client additionally passed actual
clang C++ syntax checks using their current `gles2_sources` and
`gles2_implementation` targets' definitions, include paths,
language and diagnostic flags, with candidate headers first in an isolated
overlay. Precompiled-header reuse was disabled so old headers cannot hide new
declarations. No diagnostics were suppressed for the candidate.

| Translation unit | Private evidence on D |
| --- | --- |
| `gles2_cmd_decoder.cc` | `future-gpu-validating-syntax-001-037-v1/proof.json` |
| `gles2_cmd_decoder_passthrough_doers.cc` | `future-gpu-doers-syntax-001-037-v2/proof.json` |
| `gles2_cmd_decoder_passthrough_handlers.cc` | `future-gpu-handlers-syntax-001-037-v1/proof.json` |
| `gles2_implementation.cc` | `future-gpu-client-syntax-001-037-v1/proof.json` |

These checks retained unchanged active source/browser/GN guards. They do not run
the optimizer or linker, compile the Blink callers, or execute protocol and
attachment fixtures. Feature-on runtime admission remains blocked.

The passthrough attachment and protocol fixture translation units also passed
syntax checking with actual `gpu_unittests` target flags:
`future-gpu-framebuffer-fixtures-syntax-001-037-v3/proof.json` and
`future-gpu-protocol-fixtures-syntax-001-037-v1/proof.json`. Initial attachment
checks failed under `-Werror` on signed/unsigned comparisons. The candidate now
matches signed result counts and unsigned GLenum formats explicitly, without
disabling diagnostics. These fixture definitions have **not executed**.

The current Windows generated `ui/gl/buildflags.h` sets
`ENABLE_VALIDATING_COMMAND_DECODER` to **0**; upstream `gpu/BUILD.gn` therefore
excludes the validating-decoder fixture files from `gpu_unittests`. A separate
reviewed validating-enabled configuration is required to run those tests.
Do not claim their execution from the default build or change the active GN
configuration while it compiles.

### Repeatable public C++ check

The public gate passed all six units against 001–037:
`gpu-transport-public-cpp-001-037-v2.json` on D.

It was rechecked on the corrected 001–047 source with fresh isolated command
generation and the actual current target flags:
`gpu-transport-cpp-001-047-v1.json` on D. All six units passed; the 324 existing
command IDs, active source, runtime core and GN arguments remained unchanged.
The paired halo/clipped repair is registered as 0046/0047; the remaining four
transport/protocol/attachment patches are still unregistered. These are C++
type checks, not optimized objects, executed fixtures or browser admission.

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_gpu_transport_draft.py `
  --workspace D:\CamouFlowNative `
  --report D:\CamouFlowNative\gpu-transport-cpp-new.json --check-cpp
```

`--check-cpp` also requires isolated GPU code generation to agree with the
candidate, then type-checks all six translation units sequentially using their
actual generated target flags. It rejects absent target sources and unresolved
Ninja substitutions. Old precompiled headers are not reused; crash diagnostics
are redirected to owned scratch space. The private `.cpp.log` is retained.
Compiler/target hashes and unchanged active browser/GN checks enter the report.
The report retains `compiled: false` and `privacy_admitted: false`: this is not
optimized object generation, linking, fixture execution or browser admission.

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

Candidate C++ syntax logs now keep response files and Clang crash diagnostics
in a new sibling `<log>.artifacts` directory, surviving owned-overlay cleanup.
Existing evidence is never overwritten. This does not make syntax checks a
linked decoder or browser proof, nor restore old discarded crash artifacts.

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
