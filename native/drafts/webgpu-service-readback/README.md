# WebGPU service / Wire readback — unselected

The [17-path delta](../environment/webgpu-service-readback-next.patch) connects
the policy-owned controller to native device registration and Dawn Wire.
Apply after the five prerequisites listed in the
[source record](../environment/webgpu-service-readback-preparation.json).
Six public packets reproduce the complete 69-path source composition.
Static/component GN generation and eleven target header checks per mode passed.
Original sources, Git indexes and existing build outputs were restored exactly;
this is not component linking or execution of the new Wire tests.

| Layer | Prepared behavior | Evidence boundary |
| --- | --- | --- |
| Policy setup | Owned policy, one observer, immutable healthy retries, saturating device epochs | Source and target-flag syntax only |
| Default behavior | Existing disabled experiment gates both the filter and policy command | No default runtime activation |
| Buffer creation | Protected devices skip direct renderer-visible GPU backing; existing memory-transfer serialization remains | Two backing tests prepared, not executed |
| Read-map transfer | Detached protected bytes serialized synchronously; denied/invalid results unmap and return an error | Real Wire execution still required |
| Destruction | Generation checks, explicit-destroy flag and missing-mapping checks before data transfer | Lifecycle tests still required |
| CPU bridge | 36 assertions and 800 concurrent preparations in both normal/ASan runs | Native device lookup mocked; not Wire serialization |
| Real Wire tests | Eight cases, two test translation units syntax-checked | Not linked or executed |

The generic Wire interface does not depend on Dawn Native. A GPU-service adapter
queries the alive native device instead of maintaining a raw-device-address
registry. Its owned observer survives asynchronous buffer callbacks without
retaining a native Device. Buffer sizes travel separately; observer callbacks do
not reenter Dawn.

## Run the isolated CPU check

Use the existing pinned **unselected** Chromium source baseline, existing SDK,
and a fresh external D: output. It replays all six packets outside Chromium and
checks source hashes before compiling the actual adapter/controller.

```powershell
.venv\Scripts\python.exe native\drafts\webgpu-service-readback\check.py `
  --chromium-root D:\Glint156Candidate\chromium\src `
  --sdk-root D:\Glint156Candidate\toolchain\local-msvc-sdk-28000-v1 `
  --work-dir D:\GlintManagerQA\service-readback-check-new
```

## Before admission

- Link the complete static/component packet and execute the eight real Wire tests.
- Test actual ordinary and shared-memory transfer, not only backing selection.
- Exercise mapped-at-creation/write mappings, cancellation, stale callbacks,
  injected buffers, device loss, address reuse and failed submission.
- Cover shader-derived data and remaining native write/error paths. An untracked
  buffer is not proof that it contains no fingerprint-derived data.
- Recheck Canvas/GPU color, alpha, export and worker consistency in the browser.
- Verify device/process resource limits and default-disabled compatibility.

Current runtime remains 001-076. No new browser binary, shared-memory privacy,
Canvas/GPU mismatch resolution, anti-bot result or production admission is claimed.
