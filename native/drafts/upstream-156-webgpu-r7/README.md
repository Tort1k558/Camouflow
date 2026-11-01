# Glint Chromium 156 R7: bounded sparse readback

**Registered source recipe; not built or browser-admitted.**

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
| Canonical source transition / browser build | Transition passed; first attempt failed at an out-of-memory link |
| Retained-buffer browser regression | Required; not replaced by early buffer release |
| Legacy Audio compatibility | Unresolved; no Audio change in this recipe |
| Production admission | Not granted |

[Manifest](manifest.json) and [replay evidence](preparation.json) bind the recipe.
[First build attempt](windows-build-attempt1.json) retains four successful object
compiles and the linker failure; it does not prove a completed browser binary.
[Packet implementation and independent checks](../webgpu-readback-capacity/README.md)
remain distinct from linked-browser evidence. Preserve R6 binaries and original
failing retained-buffer reports for comparison; run the unchanged retention and
mutation cases, context/restart/isolation gates and resource-failure cases after
building R7. A passing syntax or CPU check does not prove browser repair.
