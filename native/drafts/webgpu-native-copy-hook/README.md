# Trusted native copy / write observer

**Unselected. Nine translation units passed syntax checks; callbacks have not run
in Dawn or the browser. No GPU-service consumer or protected map is installed.**

Static/component GN graphs and native source/API header checks also passed;
all 16 source paths, Git indexes (including Dawn) and existing build outputs were
restored/unchanged. This is not native linking:
[GN results](../environment/webgpu-native-copy-gn-observations.json).

The [16-file packet](../environment/webgpu-native-copy-hook-next.patch) replaces
the budgeted capture packet; do not apply both. It adds a trusted embedder API
that installs one observer on an alive D3D12 device. Default devices have none;
unsupported backends and replacement registration are rejected.

| Native boundary | Prepared behavior |
| --- | --- |
| Texture-to-buffer | Full snapshot copy recorded before ROI copy; successful snapshot delivered after native ROI recording |
| Temporary-copy failure / unsupported capture | Null snapshot, meaning uncertain data, not raw-read permission |
| Buffer-to-buffer | Source/destination offsets and size delivered after native recording |
| Queue / encoded writes, clear | Known byte-write ranges reported after success |
| Write-map unmap | Uncertain range, not a claim that every mapped byte was overwritten |
| Buffer destruction | Borrowed identity notification for releasing tracking state |
| Snapshot read | Owned capture; borrowed pixels only after submission marker and GPU fence complete |

[Exact source hashes and scoped checks](../environment/webgpu-native-copy-hook-preparation.json).
The capture/quota core is unchanged from the hardware-tested budget packet.
That hardware result does **not** verify observer delivery or Dawn retirement.

Callbacks must not reenter Dawn or retain Dawn device/buffer references. Observer
metadata must be synchronized by its consumer. Snapshot ownership does not retain
a Dawn Device; GPU allocation lifetime still uses the existing COM retirement queue.
Inline abstract destructors follow `MemoryDump`, without adding new out-of-line
destructor definitions to the upper `DawnNative.cpp` API library. Actual component
linkage still needs verification.

## Still required

- Register a GPU-service observer before exposing the device and attach its owned policy.
- Feed snapshots and native events into provenance; uncertain writes must not erase it.
- Protect map serialization, including directly shared-memory-backed buffers.
- Cover shader-derived data and the remaining native write/error paths.
- Resolve color/alpha and Canvas export consistency and run actual lifecycle tests.
- Link and execute the combined browser packet before any privacy/release admission.

These are native capture notifications, **not** a functioning WebGPU protection
module. The selected runtime remains 001-076; its measured export mismatch is open.
