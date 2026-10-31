# Capture capability retention — unselected

## Actual standalone Wire delivery

`glint_wire_probe` additionally runs actual Dawn Wire client/server serialization,
default inline memory transfer and the real Glint filter factory over a hardware
D3D12 device. Three runs passed: 100 protected texture channels, repeated mapping,
CPU-first delivery followed by 64 projected compute values, and 16 unchanged
unrelated values. No observer delivery method is called manually. Disabling only
the filter factory makes the pixel comparison fail with actual bytes equal to raw
pixels; an arbitrary crash is not accepted as this negative control.

Three runs per failure mode also passed: unsupported sRGB capture returns a mapping
error; destroying a buffer after sending its map request to the server aborts
delivery; exhausting the 16 capture slots denies the overflowing mapping. After
explicit buffer destruction, a fresh capture maps with the expected protected
pixels, demonstrating slot reuse. These checks do not measure all native allocation
bytes or replace cancellation/device-loss stress.

White-box checks additionally use the actual device's 64 MiB capture-budget counter,
with the native objects' compile configuration. Sampled usage stays within that
limit and returns to zero after device destruction in all 12 successful runs.
This is tracked capture/projection accounting, not total VRAM profiling, a peak
measurement or forced exhaustion of the native byte budget.

This checks the standalone Wire implementation, not Chromium GPU-process embedding,
renderer/worker APIs or Chromium shared-memory transfer services. Hostile transport,
shared backing, broader races, cancellation stress and device-loss integration remain open.

CPU delivery must not retire a snapshot still referenced by buffer provenance.
The next GPU dispatch needs that same native capability to project the logical
buffer input. Releasing it in `Complete()` caused a real native device loss.

`next.patch` follows the **29-packet render-buffer source batch**. It keeps pixel
and shader-byte native snapshots until the existing `Collect()` / `Drop()` / failure
cleanup releases their provenance. Snapshot slots and CPU shadow limits are not
increased. Native allocation/retirement budgets still require combined stress tests.

| Actual standalone D3D12 check | Result |
| --- | --- |
| Hardware queue, unprotected compute | 64 values matched |
| Texture capture → explicit observer CPU delivery | 8×8 RGBA; 100 changed channels matched the CPU reference |
| CPU delivery → native projected buffer → compute | 64 transformed output values matched |
| Shader output → observer CPU delivery → next input plan | Protected bytes unchanged; subsequent plan accepted |
| Explicit buffer destruction | Observer remained healthy |
| Repeated complete executable runs | 3 passed |
| Uncorrected negative control | Metadata plan denied; device lost |

`native_probe.cc` uses actual Dawn devices, command encoding, shader compilation,
queue submission, snapshots, descriptor routing and mapping. No fake GPU snapshot
or native issuer replaces the path. **CPU delivery invokes the observer contract
explicitly; it does not execute Chromium's Wire filter.** Native MapAsync is the raw
transport endpoint, not the renderer-visible API. The shader reads the original
logical buffer, not a CPU-uploaded transformed substitute.

## Component build prerequisites

This is a standalone experiment, not a Chrome build or an enabled runtime.
Use a separate Dawn worktree at commit
`0a2c7df818e285d6db0f085135139cda04cee8bb`; overlay the Dawn files produced by
[`webgpu-render-buffer-routing/check.py`](../webgpu-render-buffer-routing/check.py).
Copy the generated observer to a separate staging tree and apply `next.patch`
there, never to an active browser build or the measured source-gate output.

The parent `CMakeLists.txt` accepts these explicit inputs:

| CMake input | Meaning |
| --- | --- |
| `CHROMIUM_ROOT` | Pinned Chromium 156 checkout with its existing dependencies |
| `DAWN_SOURCE` | Separate Dawn worktree with the 29-packet Dawn overlay |
| `GLINT_SOURCE` | Unmodified generated 29-packet source tree |
| `GLINT_OBSERVER_SOURCE` | Separate observer copy after this retention patch |
| `GLINT_LIBRARIAN` | Owned SDK `VC/Tools/MSVC/<version>/bin/Hostx64/x64/lib.exe` |
| `CMAKE_TOOLCHAIN_FILE` | Windows clang-cl/lld-link/RC/MT configuration |
| `Python3_EXECUTABLE` | Project virtualenv Python |

Use `/winsysrootD:/path/to/sdk` (no colon after `winsysroot`), static MSVC CRT,
Ninja, Release and at most four workers. Upstream dependency fetching and other
backends are disabled. Existing Chromium BoringSSL libraries and `verbose_abort.obj`
are linked; they must already exist. No packages need installing.

Build target: `glint_dawn_probe`. Run it with the existing Chromium output directory
on the child process PATH so DXC DLLs can be found. Check the exit code **and** JSON
result. The source and recorded observations are public; machine-local build logs
are not a portable release receipt. A fully automated clean reproduction harness
and exhaustive dependency attestation remain to be added.

## Remaining gates

Chromium Wire/renderer integration, same-submit CPU/GPU orderings, writable and chained
dispatch stress, render/bundle paths, cancellation/device loss, native allocation
quotas and retirement, ASan/full Chromium allocator builds, and browser consistency.
This patch does not change runtime selection, privacy admission or production.
