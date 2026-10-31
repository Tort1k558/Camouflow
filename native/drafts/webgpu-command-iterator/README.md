# Native command storage and pool check

This check compiles and executes the **actual Dawn** `CommandAllocator.cpp`,
`MemoryBlockAllocator.cpp`, reference counting, math and assertion/logging sources
against the checkpoint header from the unselected 29-packet render source batch.
It does not replace these classes with fixture implementations.

| Gate | Result | Boundary |
| --- | --- | --- |
| Normal / ASan | 182 cursor-position cases, 1,064,016 checks each | Standalone MSVC STL build, not Chromium target flags |
| Ownership | 9,284 tracked objects destroyed per run | Actual Dawn Ref counts; explicit command/data destruction |
| Storage paths | Empty/end/reset, early return, nesting, move-only/void results, merged blocks, bundle-like streams | Not the complete render-bundle decoder |
| Pool | No premature return, actual recycled-block reuse, tick expiry and trim | Official standalone no-op raw_ptr, not Chromium MiraclePtr |
| Invalid preview mutation | Storage destruction and move-out rejected in both modes | Actual native restore-guard assertion, not a generic crash |
| Changed inputs | 8 refusals before compilation | Does not authenticate external runtime binaries |

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-command-iterator\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\fresh-native-command-iterator-check
```

The checker first reuses the existing render source gate, then builds six pinned
upstream translation units plus the fixture. Include traces verify the patched
header and official Dawn standalone raw_ptr implementation. Ninety upstream
source/header/config files are hash-bound and checked again after execution.

Chromium allocator/MiraclePtr instrumentation, the full preview/execute render
decoder and actual Dawn GPU queue/Wire paths remain unverified. This check does
not select a runtime or admit browser consistency, privacy or production.
