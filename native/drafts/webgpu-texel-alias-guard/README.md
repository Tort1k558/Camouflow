# Projected texel-buffer alias guard — unselected

The input-scope collector includes texel-buffer views, but current private buffer
overrides only construct ordinary CBV/raw-SRV/raw-UAV bindings. Chromium's pinned
Dawn D3D12 backend explicitly marks texel-buffer descriptor creation unsupported
(`DAWN_UNREACHABLE` in `BindGroup::InitializeImpl`). This is a defensive invariant
for unsupported/future input families, **not a demonstrated reachable raw-input
leak in the selected Windows browser**. If typed views become supported, they must
not retain the original buffer while a receipt attests projected inputs.

The native tracker now rejects visible texel views whose logical buffer has a
projected shadow. It checks compute alias installation and render binding refresh
before shader binding/receipt issuance. Unprojected and nonvisible texel bindings
retain their existing path. A missing view/buffer or foreign group is rejected.

| Gate | Result | Boundary |
| --- | --- | --- |
| Replay / reverse | 28 packets, 87 paths | Unselected source composition |
| Native syntax | 15 target-flag units passed | No component link |
| Native predicate normal / ASan | 3,840 cases / 11,584 assertions each | Actual extracted lookup/guard; binding/layout/backend objects mocked |
| Changed inputs | 8 refusals before compilation | Not runtime attestation |

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-texel-alias-guard\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-texel-alias-guard-check
```

This is a conditional unsupported-alias rejection, **not typed texel-buffer
projection support**. Typed SRV/UAV formats/ranges need a separate implementation
and native execution tests if upstream support is enabled. Actual Dawn queue/Wire, combined binding dispatch,
browser consistency and runtime/production admission remain unverified or closed.
