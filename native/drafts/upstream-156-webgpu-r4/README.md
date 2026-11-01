# Glint Chromium 156: access-epoch resource batch

**Source-replayed 122-patch candidate, not a compiled/admitted browser.**

Preserves the exact 120-patch R3 prefix and all upstream pins, adding the two
native access-epoch corrections. All 122 patches apply/reverse, 270 upstream
files restore, the canonical source detector recognizes the complete chain,
and seven final source files match the compiled standalone shared-read prototype.

Standalone evidence: [exclusive epochs](../webgpu-external-access-cache/README.md)
and [concurrent readers/resource controls](../webgpu-shared-read-epoch/README.md).
No failed R3 browser result is rewritten. New browser diagnostics must use a
fresh receipt and independent preserved runtime; the R3 receipt is not reusable.

Build via the normal `scripts/native_build.py --candidate upstream-156-webgpu-r4`
workflow, maximum j4, after an owned backed-up source transition and resource
preflight. No Linux/macOS, production, CAPTCHA or privacy admission is claimed.
