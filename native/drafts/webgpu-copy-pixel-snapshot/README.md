# Execution-position paired pixel snapshots

The native texture-to-buffer snapshot factory now records a projected GPU pixel
snapshot and retains it in the **same owned ticket** as the raw CPU readback.
The existing observer's token, provenance and collection lifecycle still own that
ticket; no second registry or renderer resource pointer is introduced.

`RecordCopy` validates the native texture directly, without creating a frontend
view. View-based projection and copy-based projection reuse the same private
policy/seed/queue recording path. CPU `Read()` still returns raw pixels, so the
existing CPU transformation is not applied twice.
After recording succeeds, the copy command restores Dawn descriptor heaps and
invalidates both binding trackers through the existing projection-state helper.

| Gate | Result | Boundary |
| --- | --- | --- |
| Source replay / reverse | 19 packets, 84 paths | Unselected external staging only |
| Native target-flag syntax | 14 translation units passed | No component link or native copy execution |
| Extracted factory, normal / ASan | 6,149 synthetic cases, 52,232 assertions each | Fake native owners/resources/queue, not hardware |
| Failure / ownership | Wrong owner/access/format, missing projector, projection/readback failures; paired ownership and raw CPU read | Actual native allocator/queue failure handling not executed |
| Altered input guards | 6 refusals before compilation | Not a runtime security audit |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-copy-pixel-snapshot\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-copy-pixel-snapshot-check
```

The checker reconstructs all nineteen packets, verifies extracted native factory,
copy-validation and snapshot-class bytes, and executes them with explicit fake
dependencies in normal/ASan builds. Earlier hardware snapshot checks do not prove
this native factory or the actual copy command has run.

## Integration boundary

The GPU snapshot is retained, but **not yet exported as a validated input lease**.
Buffer input planning, registry-token/lease association, policy/epoch commit checks,
bindings/aliases/write-back and actual Dawn/Wire execution remain unfinished.
The native queue retains the existing retirement handles in source; runtime
cancellation/device loss still require real tests. Additional projected resources
share the existing device budget: exhaustion returns an error, never raw permission.

No selected patches/runtime, browser consistency, DXC or privacy/production gate
is changed or admitted by this source packet.
