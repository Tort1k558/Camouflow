# Glint Chromium 156: normal-profile launch and shared swapchain epochs

**Windows candidate compiled and browser-tested; unresolved gates prevent admission.**

[Host regression](host-regression-observations.json): 5,481 passed, one skipped,
zero failures; all source postguards passed. This is application/test evidence,
not a browser capability or package-admission result.

[Browser observations](browser-observations.json) retain the complete original
11-gate outcome: eight passed, three failed. The additional large Canvas/WebGPU
gate passed all eight baseline/protected RGBA/BGRA measurements at 1921/2048
pixels. Selected baseline/protected GPU-crash recovery also passed.

Protected array/mip maps still fail in all eight tested contexts, before and
after restart. A preserved R4 counterfactual reproduces the same failure: this
is an existing descriptor-coverage limitation, not evidence of a new R5-only
regression. [Subresource capture draft](../webgpu-subresource-capture/README.md)
is hardware-tested but does not yet repair paired GPU projection or the browser.
The [selected-slice GPU projection](../webgpu-subresource-projection/README.md)
also passed hardware and ASan checks, including canonical-buffer equality.
Assembled array views, cache identity and native routing remain unintegrated.
The [complete-array primitive](../webgpu-array-projection/README.md) now passes
array/narrow-view hardware checks and actual Dawn-target syntax. It still needs
paired native snapshots, view validation and cache integration before any browser
repair can be claimed.
The [Dawn adapter packet](../webgpu-array-native-integration/README.md) now passes
source composition and six target-flag syntax checks. R5's actual binary and
its recorded failed map gate are unchanged; the packet requires a new candidate.

Legacy Audio remains failed. Long-buffer AudioMath passed with both diagnostic
selectors chosen before measurement; its original random cohort missed one
selector and remains recorded as failed. The separate driver-merge prototype
passed exact screenshot pixels in both modes after explicitly enabling the
automation-only command-line inspection endpoint; its original harness failure
is retained. Neither recheck modifies the browser or admits the manager package.

[Native unit evidence](native-unit-observations.json): 41 launch/context, 20 transport
and 55 worker endpoint cases executed successfully. Full original case names and
statuses are retained in the linked normalized GTest reports. These are not
real renderer/worker first-script measurements.

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

Complete normal-profile surfaces, array/mip shader projection, legacy Audio and
recoverable quota exhaustion remain required. R4's failed large-Canvas result
remains historical evidence; the actual R5 large-Canvas recheck passed.
Linux/macOS remain deferred.
