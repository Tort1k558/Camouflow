# Private WebGPU policy transport draft

**Unselected. Not installed in the browser.** This does not resolve the measured
Canvas/WebGPU export mismatch or admit WebGPU readback protection.

## Coupled renderer follow-up

The [renderer transport patch](../environment/webgpu-renderer-policy-transport-next.patch)
contains the original transport plus request-time policy ownership in
`GPUAdapter::requestDevice`, shared by document and worker execution contexts.
The successful callback attaches policy before initializing/resolving the device;
attachment failure rejects the request. Temporary seed bytes are cleansed.

`GlintWebGPUPolicyTransportCandidate` is disabled by default and local to this
module, without modifying the global Blink feature header. Device policy generation
starts at one and is immutable; it is not the policy schema or wire generation.

All **six translation units** in the coupled batch passed syntax checks; the
**28-file** patch applied exactly and reversed to the originals. Five decoder
rejection tests are prepared and syntax-checked, **not executed**. Positive delivery,
idempotence, cancellation, context loss and document/worker runtime checks remain.

## Initial transport and codec

The [transport patch](../environment/webgpu-private-policy-transport-next.patch)
targets the current Windows 001–076 source checkpoint. It adds:

- A versioned 64-byte policy packet with owned, cleansed seed memory.
- Internal command 263 carrying device ID/generation and shared-memory coordinates,
  never seed bytes. Existing command IDs 256–262 are unchanged.
- A dedicated client transfer allocation, decoder-consumption wait and cleansing.
- A GPU receiver rejecting malformed packets, unknown devices and policy replacement;
  exact retries are idempotent. Wire device generation zero remains valid.

Four translation units passed syntax checks with existing Chromium flags. This is
not linking or a renderer-to-GPU runtime test. The interface stub borrowed the
client implementation's compilation flags. The actual patched codec passed
152 assertions both normally and under AddressSanitizer.

Run the isolated codec checks from the repository root on Windows:

```powershell
python native/drafts/webgpu-private-policy/check.py `
  --chromium-root D:/Glint156Candidate/chromium/src `
  --sdk-root D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1 `
  --work-dir D:/GlintManagerQA/private-policy-check-fresh
```

This uses existing pinned toolchain/crypto objects; it never downloads or compiles
Chromium. Output must be a fresh external D: directory. When applying the draft,
use `git -c core.autocrlf=false apply` to preserve its measured source bytes.

Still required: renderer/worker attachment runtime verification,
actual device lifecycle and context-loss tests, native queue/capture hooks,
mapped readback integration and a combined browser regression. A successfully
received policy alone does not protect any WebGPU pixels.
