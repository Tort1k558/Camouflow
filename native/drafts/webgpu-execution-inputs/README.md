# Execution inputs — unselected native contracts

Logical indirect/count inputs are retained **before** Dawn replaces arguments
with validated scratch buffers. Compute, draw, indexed and multi-draw scopes
consider both logical and executed inputs, with owned references and exact ranges.
The selected browser is unchanged.

| Check | Evidence | Boundary |
| --- | --- | --- |
| Source chain | Sixteen packets, 81 paths; full replay/reverse verified | Four changed source files, unselected |
| Frontend contracts | Original inputs retained at all five indirect-command allocation sites | Real frontend encoding/lifetime execution remains untested |
| CPU normal / ASan | 2,391 assertions each; original/count provenance, ranges, overflow, capacity and owner lifetime | Exact extracted code; synthetic native objects |
| Attachment readiness | 720 synthetic aspect/load/read-only/PLS states; 49 eligible by the tested predicate | Not 720 real render passes or browser configurations |
| Native syntax | Thirteen target-flag translation units passed, including commands and both frontend encoders | No component linking or Dawn runtime |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-execution-inputs\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-execution-inputs-check
```

Uses the existing guarded source replay/CPU runner. All sixteen packets are
composed outside the checkout; the actual input structures and two native helper
functions are extracted into the measured fixture before normal/ASan execution.
No downloads, fallback or changes to the selected browser.

## Readiness is not projection

- A sanitized scratch buffer alone does not prove that the logical arguments or
  count buffer have no raw-pixel dependency. The CPU negative controls explicitly
  distinguish those cases; this is not proof of a demonstrated browser exploit.
- Missing original inputs or invalid ranges reject recording, rather than silently
  using only scratch metadata. Retention is enabled only for policy-bearing devices.
- Active depth/stencil aspects are eligible only when cleared by the current pass
  and not read-only. Absent aspects do not inherit unrelated load/read-only flags.
- Loaded/read-only depth/stencil and pixel-local storage remain unprojected. They
  mark the scope texture-dependent and withhold protected-output authorization;
  ordinary raster execution is not rejected by this readiness classification.
- Literal clears are only a known-input precondition. The existing controller must
  still validate all buffer ranges and projected sampled inputs before capture.

This does **not** implement loaded-depth/stencil or PLS projection, complete raster
output protection, GPU buffer-input projection or blending/format coverage.
Actual frontend encoding, native depth/stencil, Dawn queue, Wire and browser
consistency gates remain open. The preceding standalone GPU fixture does not test
these new contracts. No privacy, production or CAPTCHA admission follows.
