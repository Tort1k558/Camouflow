# WebGPU device / Canvas export seed selection

**Unselected. Four syntax checks and coupled static/component GN checks passed.
No native linking or browser execution.**

The [seven-file patch](../environment/webgpu-export-seed-next.patch) distinguishes
Canvas, WebGL and WebGPU exports instead of treating WebGPU as ordinary Canvas.
It moves the existing disabled transport feature into GPU common, so device policy
and export code consult the same feature. It does not modify the global Blink
feature header or enable the experiment by default.

| Path | Behavior |
| --- | --- |
| Existing feature-off mode | Previous Canvas export behavior retained |
| WebGPU experiment enabled | Device policy and Canvas export request `kWebGPU` seed |
| Required seed missing / invalid | Error, not permission to return raw pixels |
| HTML Canvas | Both `toDataURL` and `toBlob` call sites updated |
| OffscreenCanvas | `convertToBlob` classifies its actual rendering context |
| Native GPU copy/map interception | Still not installed |

Apply only after the shared-core and renderer-transport prerequisite packets.
Their overlapping `common/BUILD.gn` changes were composed through sequential
patch replay, **not** by copying the last file over the first. Source hashes,
prerequisite hashes and scoped syntax results are in the
[preparation record](../environment/webgpu-export-seed-preparation.json).

The composed 37-path source packet passed GN generation and header dependency
checks for GPU common, Blink core/modules and GPU service in both static and
component configurations. Sources, Git indexes and the previous build outputs
were restored/unchanged: [coupled GN results](../environment/webgpu-export-coupled-gn-observations.json).

This prepares matching seed selection; it does **not** prove matching exported
pixels. Native readback, canonical color/alpha behavior, source versions, shader
data flow and document/worker lifecycle still need integration and browser tests.
The measured 001-076 Canvas/WebGPU mismatch remains open. Do not enable this
transport experiment as a privacy guarantee or release admission.
