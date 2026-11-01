# Glint Chromium 156: normal-profile launch and shared swapchain epochs

**Windows candidate compiled; native tests and browser admission are not proven yet.**

[Exact build evidence](windows-build-observations.json): 62 executed Siso steps,
27m15s build execution, 34m47s complete build stage, maximum j4.
The launcher hash is unchanged from R4; the actual browser DLL has changed.
The record binds all three runtime code files, not only `chrome.exe`.

Preserves the exact 122-patch R4 prefix, upstream revisions and resource limits.
Patch 123 adds explicit versioned normal-profile policy activation; patch 124
allows projection reuse only during a known active shared-memory access epoch.
The Dawn patch is applied inside `third_party/dawn`, not the Chromium repository.

- [Launch contract and prepared manager integration](../profile-surface-launch/README.md)
- [Measured standalone resource controls](../webgpu-shared-swapchain-epoch/README.md)
- [Retained R4 browser results](../environment/webgpu-r4-runtime-observations.json)

Use the normal `scripts/native_build.py --candidate upstream-156-webgpu-r5`
workflow after an owned, backed-up source transition. Maximum j4; preserve the
R4 runtime, source backups and existing build objects. Old receipts are not R5
build evidence.

After building, run `scripts/verify_native_privacy_units.py --target surface-launch`
with the explicit R5 candidate and normal workspace/toolchain/report options.
It requires all 37 identity-context tests and four new launch tests to execute
in `content_unittests`, rejecting skipped, missing or duplicate cases.

Real browser Canvas/WebGPU, documents, iframe, worker and resource recovery
checks remain mandatory. Registration and standalone tests do not repair the
recorded R4 large-Canvas or legacy Audio failures. Linux/macOS remain deferred.
