# WebGPU readback controller — unselected

The [seven-path delta](../environment/webgpu-readback-controller-next.patch) adds
an owned-policy GPU-service controller. Apply after the native-copy packet,
shared GPU readback core and renderer-policy transport. It does not replace those
packets. No observer is registered and no browser map serialization is filtered.

| Boundary | Prepared behavior |
| --- | --- |
| Native identities | Borrowed buffer handle plus immutable size; callbacks never query Dawn |
| Texture copies | Full native snapshot ticket and ROI provenance retained together |
| Buffer copies / writes | Provenance propagated; known writes invalidate ranges; uncertain overlap denies reads |
| Snapshot completion | Pending permits retry; failed/malformed capture denies affected buffer until destruction |
| Protected CPU result | Detached, repeatable shadow; mapped input and row padding are not modified |
| Ownership / bounds | 256 tracked buffers, 16 snapshots, 64 MiB CPU snapshot budget and 64 MiB per shadow |
| Destruction | Unreferenced snapshots released; copied provenance survives source-buffer destruction |

Normal and AddressSanitizer CPU tests each passed **113 assertions and 400
concurrent map preparations**. Four translation units passed actual target-flag
syntax checks without diagnostics. These tests use synthetic native tickets and
opaque buffer handles, not Dawn devices or a browser. The native GPU capture quota
is separate from these CPU limits; neither is a process-global resource budget.

The combined **56-path** source tree was reproduced from five public packets.
Static/component GN generation and seven target header checks each passed;
original sources, Git indexes and build outputs were restored exactly.
This verifies graph/header dependencies, not component linking.
Full Python regression at `059894d`: **5058 passed, 1 skipped**, with source guards
preserved. This is not a native runtime or privacy result.

Run the public isolated check on Windows, using existing pinned sources/SDK and
a fresh external D: output:

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-readback-controller\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\controller-check-new
```

[Bound source hashes and scoped measurements](../environment/webgpu-readback-controller-preparation.json).

## Remaining integration

- Link the composed packet, including an actual component build.
- Register the controller before device exposure, with immutable policy retries.
- Filter ordinary map serialization and directly shared-memory-backed mappings.
- Cover shader-derived data and remaining write/error paths. `Unrelated` means
  no tracked texture-copy provenance, **not** proof that a buffer is nonsensitive.
- Verify real submission, cancellation, device loss, buffer reuse and retirement.
- Link and execute the full browser packet and compare Canvas/GPU exports.

The selected runtime is still 001-076. Its measured Canvas/WebGPU export mismatch
remains open. This source packet is not privacy or production admission.
