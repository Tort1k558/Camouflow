# Shader dependency scopes — interim, unselected

The [four-path delta](../environment/webgpu-shader-scope-next.patch) follows the
service/Wire packet. Native direct/indirect dispatches and completed render-pass
recording report potential whole-buffer reads/writes and texture inputs.

| Prepared behavior | Boundary |
| --- | --- |
| Inspect inputs before changing outputs | Handles read-write aliases and shader/copy chains |
| Mark texture/readback-derived storage outputs | Reads are refused; results are **not** transformed compatibly |
| Ordinary untracked buffer-only compute | Does not allocate tracking slots solely for unrelated writes |
| Unknown, incomplete or oversized metadata | Device tracking fails closed; maximum 256 scope buffers |
| Native metadata allocation | Bound checked before allocating the event vector |
| Snapshot lifetime | Existing provenance/snapshot collection reused; no retained Dawn references |

Normal and AddressSanitizer CPU tests passed **29 assertions and 400 concurrent
scope operations** each. Two translation units passed actual target-flag syntax
checks without diagnostics. [Test source](shader_scope_test.cc) uses synthetic
handles/snapshots; the isolated CPU driver has not been integrated into a public
CLI. These results do not execute native shader callbacks or GPU work.

## Not finished

The combined 69-path tree passed static/component GN generation and eleven
target header checks each. Source files, Git indexes and existing outputs were
restored exactly. This is not component linking or native shader execution.

- This is a dependency/safety foundation, **not compatible shader protection**.
- Whole-buffer scopes can refuse legitimate image-derived compute and partial
  writes. Exact binding ranges and compatible data-path protection remain open.
- Ordinary arithmetic with no tracked inputs is not covered by this mechanism.
- Link and run the full native packet; verify dispatches, render bundles, indirect
  operations, cancellation/device loss, and ordinary compute compatibility.
- The public copy/shader/PNG gate must pass with actual protected data, not merely
  return an error instead of pixels. The measured 001-076 mismatch is unresolved.

The feature remains disabled and this packet is not selected. No new runtime,
shader compatibility, anti-bot result, privacy or production admission is claimed.
