# Glint Chromium 156 R7: bounded sparse readback

**Windows build and baseline verified; full R7 compatibility not admitted.**

The [measured build/baseline](windows-build-baseline.json) completed 50 Siso steps
in 16m 21.87s; the build stage including checks took 21m 58.219s. All 116 selected
native cases and 160 baseline browser checks passed on the measured R7 core.
The [completed runtime diagnostics](runtime-observations.json) now pass 15 of 16
named groups after a separate corrected normal-profile WebGPU launch. The original
R6-only runner rejection remains recorded. Legacy Audio compatibility still fails.

Preserves the exact 128-patch R6 prefix and adds one Chromium-owned patch:
[`0129-webgpu-readback-capacity.patch`](patches/0129-webgpu-readback-capacity.patch).

The patch addresses two separately reproduced limits: padded captured-byte
provenance fragmentation and the shared 16-snapshot ceiling under retained
readback buffers. Sparse masks preserve padding semantics; bounded snapshot
capacity follows the existing live-buffer budget without increasing byte quotas.

| Gate | Evidence |
| --- | --- |
| Repository-aware source replay | 129 forward / reverse; 270 upstream files restored |
| Composed final source | 400 files matched |
| Standalone C++ normal / AddressSanitizer | Passed in the linked packet |
| Native target syntax | Three translation units passed |
| Host registration | Reversible archive preserves exact older tooling |
| Resources | Windows max j4; one heavy link; full-build reserve 180 GiB |
| Canonical source transition / browser build | Passed on retry; first out-of-memory link report retained |
| Selected native context/launch/worker cases | 116 passed; input/core postguards passed |
| Eight-gate baseline browser suite | 160 checks passed; not third-party anti-bot acceptance |
| Retained-buffer browser regression | Original probe passed: 24 observations / 144 cases; no early-release substitution |
| Retained producer mutation | Passed: two formats, three mips, three layers, two epochs |
| Wider owned runtime diagnostics | 15/16 named groups passed after corrected normal WebGPU launch; original failure retained |
| Legacy Audio compatibility | Unresolved; no Audio change in this recipe |
| Production admission | Not granted |

The long AudioMath probe covers both selectors, exact restarts and unchanged
linear graphs; the alternate selector changed 12 long-buffer rows. Short fixtures
alone showed no math/baseline difference. Legacy readback's observed one-ULP
changes still fail exact fidelity/analyser/worklet checks. Retained-array tests
do not independently prove cross-profile isolation or third-party acceptance.

[Manifest](manifest.json) and [replay evidence](preparation.json) bind the recipe.
[First build attempt](windows-build-attempt1.json) retains four successful object
compiles and the linker failure; it does not prove a completed browser binary.
[Packet implementation and independent checks](../webgpu-readback-capacity/README.md)
remain distinct from linked-browser evidence. Preserve R6 binaries and original
failing retained-buffer reports for comparison; run the unchanged retention and
mutation cases, context/restart/isolation gates and resource-failure cases after
building R7. A passing syntax or CPU check does not prove browser repair.
