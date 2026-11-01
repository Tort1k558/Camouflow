# Single owned Canvas raster — unselected extension

**Source/type checks pass; native cases and browser runtime have not executed.**

Extends the [image-source](../canvas-gpu-image-sources/README.md) and
[frame-provenance](../canvas-frame-provenance/README.md) drafts. The existing
image adapter allocated a readback raster and then another full transformed
copy. This extension consumes the private readback raster instead.

| Contract | Implementation |
| --- | --- |
| Private pixel allocation | One full raster, read → transform → freeze |
| Memory limit | Existing 64 MiB unchanged; no raw fallback on failure |
| Pixel algorithm | Same edge-coherent RGBA8/F16 transform |
| Ownership | Require a unique mutable full-extent SkPixelRef; reject aliases, immutable/subset/padded input |
| Format | Require normalized RGBA8/F16; preserve sRGB/P3, alpha handling and source orientation/origin |
| Cache identity | Notify pixel changes before returning immutable data |

[Patch](canvas-owned-raster.patch) · [source evidence](source-observations.json)

The three composed patches apply/reverse exactly. Eight translation units pass
type checking, including both copy adapters, the four rendering callers,
platform frame transport and the combined native fixture. Ten new cases bring
the composed draft to **21 prepared native cases, zero executed**.

The complete [pre-registration source replay](full-composition-observations.json)
also passed **135 forward / 135 reverse patches**, matched 406 final files and
restored 273 upstream inputs. That record describes the earlier pre-registration
stage. The [R10 recipe](../upstream-156-image-r10/README.md) is now registered but
still unbuilt; neither source result is native-case execution.

The fixture includes an exact 4096×4096 RGBA8 image at the unchanged 64 MiB
boundary, plus alias/immutable/subset/padding/format rejection and a pixel oracle.
The earlier 4×4 adapter budget test changes from 127/128 to 63/64 bytes because
only one private raster remains; this is allocation accounting, not a weaker
pixel comparison or an increased limit.

The bound is for the adapter's private pixel buffer, **not total browser/GPU
memory**. Skia/driver staging and source resources remain separate. Ownership
checks cover the internal allocation sites, not arbitrary external-memory
sandboxing. Images beyond 64 MiB still fail explicitly.

## Next gates

- Register the composed source recipe; link and execute all 21 native cases.
- Measure real large GPU/worker images, retained frames, formats, profile
  ownership, compatibility and total resource use; repeat exact copy checks.
- Establish the protected WebGPU gate, then mixed-policy/lifecycle and manager/
  package/update/rollback admission.

The active R9 source tree/binary is unchanged and its measured interoperability
failures remain. This draft does not prove natural GPU colours, realistic device
cohorts or external detector acceptance. Linux/macOS remain deferred.
