# WebGPU readback layout foundation

**Unselected native prototype. No Chromium/Dawn hook or pixel protection yet.**
The existing PNG/direct-GPU mismatch remains open.

- Detached one-layer RGBA8/BGRA8 extraction and storage.
- Checked offsets, dimensions, row pitch, overflow and mapping bounds.
- Rejection of partial mappings, aliasing and unsupported formats before writes.
- Preserved alpha, padding, prefix/suffix bytes and source storage.

The caller must establish trusted copy provenance and API validation first.
These helpers neither classify compute buffers nor apply fingerprint transforms.
Layered, compressed, depth and floating-point formats are outside this prototype.
Layout validation follows the relevant subset of the
[WebGPU copy-layout rules](https://www.w3.org/TR/webgpu/#abstract-opdef-validating-linear-texture-data).

## Measured checks

The exact sources compiled with the pinned Windows Clang/MSVC SDK, `/W4 /WX`,
and passed **1024 deterministic layout variations** plus boundary checks, both
normally and with AddressSanitizer. This is not a Chromium unit/runtime batch.
[Source-bound evidence](../environment/webgpu-readback-layout-preparation.json).

## Reproduce the isolated check

Use the existing pinned toolchain; keep objects/executables on D:.

```powershell
$src = (Resolve-Path native/drafts/webgpu-readback-layout).Path
$out = 'D:/GlintManagerQA/layout-manual'
$sdk = 'D:/Glint156Candidate/toolchain/local-msvc-sdk-28000-v1'
$clang = 'D:/Glint156Candidate/chromium/src/third_party/llvm-build/Release+Asserts/bin/clang-cl.exe'
New-Item -ItemType Directory -Path $out -ErrorAction Stop | Out-Null
& $clang /nologo /std:c++20 /W4 /WX /EHsc /MT /Zc:__cplusplus "/winsysroot:$sdk" `
  "/imsvc$sdk/VC/Tools/MSVC/14.51.36231/include" `
  "/imsvc$sdk/Windows Kits/10/Include/10.0.28000.0/ucrt" `
  "/imsvc$sdk/Windows Kits/10/Include/10.0.28000.0/shared" `
  "/imsvc$sdk/Windows Kits/10/Include/10.0.28000.0/um" `
  "$src/webgpu_readback_layout.cc" "$src/layout_test.cc" "/Fo$out/" "/Fe$out/layout_test.exe" `
  -fuse-ld=lld /link "/LIBPATH:$sdk/VC/Tools/MSVC/14.51.36231/lib/x64" `
  "/LIBPATH:$sdk/Windows Kits/10/Lib/10.0.28000.0/ucrt/x64" `
  "/LIBPATH:$sdk/Windows Kits/10/Lib/10.0.28000.0/um/x64"
if ($LASTEXITCODE -ne 0) { throw 'Layout compile failed' }
& "$out/layout_test.exe"
if ($LASTEXITCODE -ne 0) { throw 'Layout check failed' }
```

Next integration needs validated copy/submission provenance, write invalidation,
full-surface canonical data for partial reads, and consistent export routing.
Do not transform arbitrary compute/storage results or publish a privacy capability
from these standalone checks.
