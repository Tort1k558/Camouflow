# Private buffer backing — unselected policy

Imported, shared and persistently host-mapped buffers can change outside Glint's
write callbacks. The shader-capture policy must not trust their recorded bytes.

| Check | Evidence | Boundary |
| --- | --- | --- |
| Source chain | 14 packets, 78 composed paths; complete replay and reverse verified | Not selected in the runtime |
| Native predicate | Resource exists; no host-mapped heap, shared contents or external allocation | Three source files; not a full write-path audit |
| Entry points | Binding scopes, indirect inputs and private byte capture use the same predicate | Actual Dawn imports/queue execution remain untested |
| CPU normal / ASan | 216 assertions each across 16 origin combinations, ranges and capacity edges | Exact extracted code, synthetic backend objects |
| Native syntax | Ten target-flag translation units passed | No component link or browser admission |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-private-backing\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-private-backing-check
```

Requires Windows, the pinned 001–076 checkout and existing SDK/compiler. The command
replays all fourteen packets in a fresh external D: directory, verifies every
source hash, extracts the four actual predicates and runs normal/ASan tests.
The checkout and selected browser are not modified. No downloads or fallback.

The preceding thirteen-packet shader-capture batch passed static/component GN
generation and dependency checks. **That GN result does not cover this extension.**
Full native write-path coverage, actual shared/host-mapped imports, component
linking, Dawn/Wire execution and browser consistency remain required. This policy
does not implement raster-output capture or GPU buffer-input projection, and
does not change the selected browser's negative Canvas/GPU consistency result.
