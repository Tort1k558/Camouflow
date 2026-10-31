# Token-bound GPU input metadata plans

The actual CPU observer can now export immutable region plans containing exact
buffer ranges, copy layout, source crop and retained GPU capabilities from its
existing snapshot registry. It checks token epoch/generation and snapshot
dimensions/layout without reading pixels or calling Dawn under its mutex.

Plans merge overlapping/adjacent uses, preserve disjoint fragments and support
at most sixteen regions per logical buffer. Already trusted shader-byte captures
keep their existing eligibility without a redundant pixel rewrite. Missing GPU
capabilities, unsafe provenance or incompatible metadata are denied.

`CommitGpuInputPlan` checks the **same plan object**, current sequence and policy
identity, then consumes it once. Copies/writes, destruction, execution errors,
shader scopes and replacement plans invalidate prior plans. A foreign observer's
numerically identical metadata is insufficient.

**Commit acknowledges metadata only. It does not prove that GPU shadow bindings
were installed and does not change `ByteEligible` or output readiness.** Native
consumers must still resolve each lease's logical owner and perform real routing.
The experimental native observer interface gains explicit plan/commit methods;
the selected browser and CamouFlow manager APIs are unchanged.

| Gate | Measured result | Boundary |
| --- | --- | --- |
| Replay / reverse | 21 packets, 84 paths | Unselected external staging |
| Native target-flag syntax | 14 units passed | No component link or native queue execution |
| CPU controller normal / ASan | 256 iterations, 12,802 assertions each | Real controller/policy/provenance; fake GPU capabilities |
| Prior controller compatibility | 2,000 cycles / 10,154 assertions each | Reused existing CPU fixture on the new controller |
| Invalidated plans | Foreign/consumed/replaced plans, writes, destruction, errors, shader scopes rejected | Not real Dawn submission/cancellation |
| Changed inputs | 7 refusals before compilation | Includes modified legacy fixture logic, not runtime attestation |

## Reproduce

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-input-plan\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-input-plan-check
```

The checker reconstructs the entire chain and compiles the actual controller and
CPU policy/provenance sources. Its explicit friend mock supplies metadata-only
GPU capabilities, not native resources. The existing shader-capture controller
fixture is reused with its executable body hash-bound to the record.

Real GPU binding/alias/write-back routing, logical-owner resolution at that
boundary, validated indirect ancestry, Dawn/Wire/DXC, device loss and combined
browser consistency remain unfinished or unverified. No selected runtime,
privacy or production admission follows from these CPU results.
