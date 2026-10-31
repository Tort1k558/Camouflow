# Shared Canvas / GPU readback core

**Unselected source packet. Not a new browser binary or WebGPU protection.**

The [patch](../environment/shared-gpu-readback-core-next.patch) moves the existing
Canvas math into `gpu/command_buffer/common:common_sources`. Blink keeps a
forwarding header; its old implementation is removed, not duplicated. GPU code
can use the same implementation without depending on Blink. The math is unchanged.

| Check | Result |
| --- | --- |
| Sparse patch forward / reverse | Exact hashes for all 13 paths |
| Pinned Chromium syntax | Five translation units; no diagnostics |
| CPU checks, normal and ASan | Layout 525,936; provenance 1,232,777; snapshots 748; callbacks 201; uncertain writes 191,874 assertions each |
| Public Python baseline | 5,014 passed, 1 skipped at `9539fc2`, before this packet |
| GN / Chromium component link / browser execution | Not verified |

[Source hashes and scoped measurements](../environment/shared-gpu-readback-core-preparation.json).

The snapshot owner uses an out-of-line destructor and explicit move operations;
readback indexing uses allocation-sized spans. GPU headers expose the existing
component export macro. No GPU-common source includes a Blink header.

Uncertain native writes touching tracked pixels make provenance conservatively
unreliable; disjoint or padding-only writes do not erase it. This is a CPU model,
**not shader input/output taint propagation or an installed native hook**.

## Before selection

- Complete-chain validation now replays all patches in a private Git index and
  compares net paths and exact final content. Added-then-removed and restored
  files are supported; unknown edits still fail. Fifteen real-Git cases and the
  actual unchanged 001-076 checkout passed. This proves final-tree identity, not
  the historical order in which a user applied patches.
- Generate GN and verify actual static/component linkage and dependency checks.
- Connect policy, trusted copy execution, full-surface capture and mapped shadows.
- Track shader-derived data and charge GPU memory until fence retirement.
- Resolve the measured Canvas/WebGPU export mismatch and run browser lifecycle,
  compatibility and combined privacy gates. Moving the code alone does not fix it.

The active `001-076` chain and preserved runtime are unchanged. Do not apply this
packet to an active build or bypass the normal build resource reserve.

## Reproduce the isolated DLL boundary check

```powershell
python native/drafts/shared-readback-core/check_component.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/shared-component-check-fresh
```

Extracts the hash-bound shared sources into fresh external D: output without
changing Chromium. Builds an actual DLL with the GPU-common export macro, then
five importing executables, normally and under ASan. All ten passed with the same
assertion counts above. Requires the existing compiler/SDK/crypto objects; no
downloads, software fallback or Chromium build.

[DLL measurements](../environment/shared-gpu-readback-component-observations.json).
This uses the MSVC standard library for the isolated check. Chromium's GN graph,
its libc++ component ABI and browser execution **still require separate checks**.
