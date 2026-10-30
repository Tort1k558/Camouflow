# Native WebGPU readback components

**Unselected. Not connected to Chromium/Dawn or JavaScript mapped-buffer lifetime.**
The browser's PNG/direct-GPU mismatch remains open.

| Component | Implemented behavior |
| --- | --- |
| Layout | Detached RGBA8/BGRA8 transfer; bounds/overflow/alias checks; preserved alpha and padding |
| Provenance | Executed-write ordering, buffer copies, crop coordinates, partial reads, write invalidation and device/version tokens |
| Snapshot cache | Bounded full-surface original/protected copies using the existing native Canvas transform; detached mapping shadows |

Only a trusted native execution hook may register a copy or full-surface capture.
**Buffer shape or contents are not proof of provenance.** The hook/producer is
not implemented yet. Layered, compressed, depth and floating-point formats remain
outside this prototype.

The tracker rejects stale ordering, wrong devices and metadata exhaustion. The
cache rejects missing/stale snapshots, changed original bytes, overlapping plans
and memory-limit failures. No raw-data fallback is returned from these failures.
Unrelated compute bytes and row padding are not pixel-transformed.

The exact public check passed normally and under AddressSanitizer:

- Layout: 1024 deterministic variations and boundary checks.
- Provenance: 18 named cases and 256 independent byte-oracle variations.
- Snapshot pipeline: 26 named cases, two formats and 64 crop/partial-read variations.

[Current source-bound evidence](../environment/webgpu-readback-provenance-preparation.json).
[Historical layout-only evidence](../environment/webgpu-readback-layout-preparation.json)
retains its exact earlier sources in its patch archive.

## Reproduce on Windows

Use the existing pinned Chromium source, SDK, compiler and native crypto objects.
No downloads or Chromium rebuild occur; all objects, executables and logs go to a
fresh external D: directory. Normal and AddressSanitizer checks are both required.

```powershell
python native/drafts/webgpu-readback-layout/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/fresh-native-readback-check
```

The snapshot check links the existing native Canvas transform and crypto through
their pinned source/object hashes, not a replacement implementation. Its protected
data is compared with the same full-surface Canvas policy, including ROI reads and
copied buffers. This does not prove a browser GPU capture, policy transport,
mapped-JS detachment or cross-profile isolation.

Next: trusted GPU execution/capture integration, policy-context transport, native
mapped-buffer ownership/detachment, matching Canvas export routing and real runtime
checks. Do not publish a privacy capability from these standalone components.
