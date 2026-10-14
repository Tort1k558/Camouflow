# Windows font rasterization candidate

**Unregistered, not applied to the active 001–060 build. No capability admitted.**

This candidate changes actual Windows text-rendering parameters, not Canvas
readback bytes, JavaScript APIs, installed font names, OS identity or GPU strings.
It is an alternative rendering experiment, **not a repair of the existing
Canvas readback candidate** or a promise of undetectable/unique fingerprints.

| Mode | Antialiasing | Fractional positioning | Pixel order |
| --- | --- | --- | --- |
| `native` | Host value | Host value | Host value |
| `aliased` | Off | Off | None |
| `grayscale` | On | On | None |
| `cleartype-rgb` | On | On | RGB |
| `cleartype-bgr` | On | On | BGR |

Gamma, contrast, hinting, embedded bitmap and autohinter fields are preserved.
The explicit switch is validated before copying it to renderer commands.
Windows cached font parameters apply the selected mode before Skia cache setup;
upstream renderer preferences already carry these parameters into Blink.
Cache refresh reapplies the same command-line choice. No host registry changes.

`windows_font_rasterization_candidate.patch` includes the policy, Windows cache
hook, renderer forwarding and Windows-only build/test registration. Its five
GTest definitions cover parsing, invalid names/enums, native preservation, field
bounds and idempotence. They have been **type-checked, not executed**.

## Current evidence

- Actual-source preparation and `git apply --check` passed on source 001–060.
- Two isolated C++ type checks passed with actual generated Chromium target
  flags: Windows parameter hook and policy fixtures. Active sources, core,
  compiler/target inputs and GN remained unchanged.
- Private proof: `windows-font-rendering-cpp-001-060-v1/proof.json` on D.
- Three Python preparation/replay/refusal tests passed.
- Renderer forwarding C++ compilation, optimized linking, native fixture
  execution and actual visual/runtime effects are **not yet verified**.

Regenerate only into a fresh output outside Chromium:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_native_font_rendering.py --source D:\CamouFlowNative\chromium\src --output D:\CamouFlowNative\windows-font-rendering-new.patch
git -C D:\CamouFlowNative\chromium\src apply --check D:\CamouFlowNative\windows-font-rendering-new.patch
```

## Admission work

After the active build finishes, validate full forwarding/DEPS, register the
reviewed package, compile the five native cases and compare actual modes in
document/iframe/dedicated/shared/service workers, before-script and restart runs.
Check Canvas/DOM/SVG text and ordinary page rendering with real installed fonts.
Verify raw pixel fidelity, P3/float16 APIs, PNG/ImageBitmap/drawImage and screenshots
without the old Canvas readback candidate enabled. Combining both candidates is
a separate test and does not fix the old candidate's failures automatically.

ClearType may be suppressed by normal rendering rules on transparent surfaces;
RGB/BGR need not produce distinct Canvas output. Aliased rendering can visibly
degrade text. Do not randomly assign modes or expose selectable manager controls
until measured behavior, compatibility, profile persistence and platform-specific
capabilities are established. This does not emulate Linux/macOS/mobile hardware.
