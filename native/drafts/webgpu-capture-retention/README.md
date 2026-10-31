# Capture capability retention — unselected

## Actual standalone Wire delivery

The same compiled fixture additionally passed **24 render runs**, three per route:

| Native render input | Direct draw | Render bundle | Observed scope |
| --- | --- | --- | --- |
| Read-only storage | Passed | Passed | Full 8×8 output compared through Wire |
| Vertex binding, instance step | Passed | Passed | Projected `Uint32` attribute supplies the colour |
| Index binding | Passed | Passed | `Uint16` point draw; vertex index encoded into a 1×1 output |
| Writable fragment storage | Passed | Passed | First-word XOR, complete 2 KiB copyback including padding, then dependent compute |

All routes start after CPU delivery of the source capture and finish with the
ordinary 64-value compute check. They execute actual native pass/bundle decoding,
buffer address/descriptor routing and shader work, not an extracted backend model.
The tracked capture budget drains to zero. These are normal standalone builds,
**not ASan/Chromium allocator runs**. Uniform/dynamic-root, indirect, arbitrary
mesh/range/heap stress and Chromium renderer integration remain separate gates.

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

### Measured independent Wire extensions

[`wire-drafts.json`](wire-drafts.json) binds three **independent** patches against
the measured `wire_probe.cc`. Apply each patch in its own disposable staging
directory containing that exact base file; do not apply them consecutively or
change an active Chromium checkout.

Preserve LF bytes when replaying: `git -c core.autocrlf=false apply <patch>`.
Verify the base, patch and resulting source SHA-256 against `wire-drafts.json`
before compiling; this does not change the user's global Git configuration.

| Source variant | Intended checks | Current evidence |
| --- | --- | --- |
| [`wire-uniform.patch`](wire-uniform.patch) | Static/dynamic uniform bindings, direct/render-bundle paths; offset 256; protected input copied on GPU, not uploaded as substituted CPU pixels | Compiled; 51/51 standalone cases passed |
| [`wire-device-lifetime.patch`](wire-device-lifetime.patch) | Real Wire `ForceLoss` before map and client device destruction before map response; one aborted map callback, one device-lost callback, unmapped buffer, capture-budget drain | Compiled; 21/21 standalone cases passed |
| [`wire-byte-budget.patch`](wire-byte-budget.patch) | GPU-cleared 2048x2048 source, fewer than 16 retained slots, measured per-capture byte charges, allocation pressure against the actual 64 MiB budget, failed mapping and drain | Compiled; 21/24 passed, all three original byte-budget cases failed before the expected loop; not quota recovery |

Existing render, mapping-denial and no-filter negative controls must be repeated
for all variants. Native API-injected loss is not a hardware TDR, Chromium GPU
process crash or proof of browser recovery. These drafts grant no capability or
release admission. The standalone MSVC STL/no-op `raw_ptr` limitation remains.

The byte-budget variant does not upload a large CPU texture, mutate the device's
budget or deliberately exhaust physical GPU/system memory. It first measures
successful retained captures, then submits one more when the same capture charge
no longer fits. The current native capture path classifies allocation failure via
`CheckHRESULT`; the diagnostic therefore requires the actual Glint/E_OUTOFMEMORY
device-loss callback, aborted mapping and zero retained capture bytes after
destruction. Reproducing this failure would justify investigating recoverable
quota handling; it would not prove that such handling already works. There is no
claim of isolated peak/total GPU memory measurement or physical OOM attribution.

Chromium Wire/renderer integration, same-submit CPU/GPU orderings, writable and chained
dispatch stress, render/bundle paths, cancellation/device loss, native allocation
quotas and retirement, ASan/full Chromium allocator builds, and browser consistency.
This patch does not change runtime selection, privacy admission or production.

### 2026-11-01 measured byte-budget diagnosis

[Runtime observations](wire-runtime-observations-20261101.json) retain all 96
original cases, including the three failures. The final queue binds the exact
per-case report hashes; those report files retain their pre-finalization
`passed: false` checkpoint. They have not been rewritten as passing reports.

The original 2048-square capture exceeds the 64 MiB native budget during its
first protected projection. Its lost-device validation callback aborts the
fixture before the intended pressure loop. The standalone
[diagnostic-only patch](wire-byte-budget-loss-diagnostic.patch) applies after
`wire-byte-budget.patch`: it uses 1024-square inputs and records only bounded,
explicit device-lost validation errors while retaining all other assertions.
Three actual runs each retained three captures (21,037,056 bytes per capture),
then observed Glint/E_OUTOFMEMORY, one lost callback, one aborted/unmapped map
and zero capture bytes after destruction. This calibrates the fault probe;
it does not fix large-surface compatibility or implement recoverable quotas.
The source, executable, dependency and original report hashes remain separate.
