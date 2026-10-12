# GPU metadata minimization candidate

`gpu_metadata_minimization.patch` is unregistered and not compiled or enabled in
the current browser. It is prepared for the next batch without changing active
0030 build sources.

The disabled-by-default `GlintGpuMetadataMinimization` Blink feature proposes:

| API | Candidate change | Preserved |
| --- | --- | --- |
| WebGL / WebGL2 | Do not offer WEBGL_debug_renderer_info | Actual backend, other extensions, limits, shaders and pixels |
| WebGPU adapter info | Empty identification strings; omit developer-specific adapter details | Actual subgroup sizes, fallback status, device features, limits and rendering |

No different video card or operating system is fabricated. A later experimental
binary may opt in with `--enable-features=GlintGpuMetadataMinimization`; renderer
and worker propagation must be verified, not assumed. Feature-off behavior should
remain upstream behavior. A privacy setting can itself be observable.

Four-file source replay passed in an isolated overlay, with active files unchanged:
`D:/CamouFlowNative/gpu-metadata-candidate-overlay-v2/proof.json`.
The revised path preserves real experimental subgroup matrix configurations too;
it does not return before the upstream capability population loop.
This is not C++ compilation or runtime evidence.

## Diagnostic runner

```powershell
.\.venv\Scripts\python.exe scripts/verify_native_gpu.py `
  --executable D:\CamouFlowNative\chromium\src\out\CamouFlowNative\chrome.exe `
  --work-dir D:\CamouFlowNative\gpu-checks --report D:\CamouFlowNative\gpu-new.json
```

The unprotected 001-027 binary passed two feature-off/restart phases: WebGL1,
WebGL2 and WebGPU were available in all eight document/worker contexts. Actual
clear/readPixels, buffer round-trip and WGSL compute operations passed, alongside
metadata/limit consistency. Evidence: `gpu-001-027-baseline-v3.json` on D.
This measures existing GPU behavior, not this candidate's privacy. Add
`--minimized` only for a binary actually containing the candidate; ignored flags
with exposed metadata fail the checks. Reports always retain
`privacy_admitted: false`; unavailable APIs are excluded from coverage.

Required tests: WebGL1/2 getSupportedExtensions/getExtension agreement, upstream
INVALID_ENUM behavior for unavailable debug parameters, document/iframe/worker
coverage, repeated adapter.info and device.adapterInfo observations, feature-off
regression, real device creation, rendering/compute and unchanged limits/features.
Unavailable WebGPU must be reported as unavailable, not a passing masking result.
GPU readback protection, extension/limit reduction and profile-policy admission
are separate unfinished work; metadata minimization is not complete GPU privacy.
