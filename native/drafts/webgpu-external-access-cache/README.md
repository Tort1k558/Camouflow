# External texture access-epoch cache

**Compiled standalone draft; not selected in Chromium.**

R3 passes large internal-texture checks but still loses its device while
projecting large Canvas sources, even without PNG export. This draft permits
weak projection reuse only during explicit exclusive SharedTextureMemory access.
BeginAccess, EndAccess, writes and destruction clear reuse. Unknown external,
swap-chain, no-access and concurrent-read sources remain excluded.

| Native measurement | Result | Limit |
| --- | --- | --- |
| Existing internal Wire matrix | 54 passed | Standalone Dawn, not Chromium allocator/ASan |
| Real imported D3D12 resource through Wire | 3 passed | 8 x 8 RGBA, CPU read and 64 shader values |
| EndAccess / BeginAccess | Cache detached in all three runs | Structural cache check, not external producer mutation |
| Device teardown | Capture budget returns to zero | Not live-device drain certification |

`next.patch` follows the R3 Dawn sources pinned in `observations.json`.
`wire-import-probe.cc` is the exact executed fixture; its alternative patch is
bound to the recorded original fixture hash. Build against the isolated R3 Dawn
library with this draft's TextureD3D12.cpp replacement and the existing Wire and
Glint service libraries. Do not apply to an active Chromium source/build.

The fixture enables `allow_unsafe_apis` only on its own native Dawn instance,
following upstream DawnTest.cpp, to import native D3D12 resources. It does not
enable experimental APIs in the browser or change global security settings.
Both fence array lengths are preserved across EndAccess / BeginAccess.

Still required: large imported resources, external producer mutation, retained
snapshot immutability, deliberate missing-invalidation GPU failure, exclusion
controls, live-device drain and actual Chromium Canvas before/after. This is
not a verified Canvas repair, a browser release or privacy admission.

## Subsequent producer and large-resource measurements

The earlier preparation/observations above are retained unchanged. The later
[`epoch-resource-observations.json`](epoch-resource-observations.json) records:

| Additional standalone check | Result |
| --- | --- |
| Distinct producer texture between consumer access epochs | 3 passed; updated CPU and all 64 shader values exact; old CPU capture unchanged |
| Remove only BeginAccess/EndAccess cache clearing | 3 expected stale GPU failures with exact pixel mismatch marker, not OOM |
| Imported 1921/2048-square RGBA/BGRA | All four passed; complete CPU image and 16 spatial shader samples |
| Capture limit | Unchanged 64 MiB; zero tracked capture bytes after teardown |
| Native patch plus negative-control apply/reverse | Two actual R3 source files restored byte-exact |

Each `*-fixture.patch` is an alternative against the published
`wire-import-probe.cc`, not a patch stack. `missing-epoch-negative.patch` applies
only after `next.patch`; never select it in a browser build. It demonstrates that
the mutation test detects stale reuse rather than merely observing hook calls.

Producer and consumer use distinct texture objects on the same native device
and shared-memory object. This does not certify separate-device producers,
concurrent reading, arbitrary external resource ownership, or live-device drain.
Large variants perform no PNG export. Chromium Canvas remains unverified with
this draft; its last measured browser result still fails. No release admission.

### Integration gap found before browser selection

Pinned Chromium `D3DImageBacking::BeginAccessDawn` requests
`desc.concurrentRead = !write_access && is_clear` for initialized read-only
textures. This draft deliberately excludes concurrent reads, so its passing
exclusive-access tests do **not** establish coverage of that Chromium path.
Next: validate shared-read epochs with multiple readers, writer exclusion and
producer mutation before selecting a browser patch. Do not weaken the external
resource guard solely to obtain a passing Canvas result.

The [shared-read follow-up](../webgpu-shared-read-epoch/README.md) now has 54
internal controls and six actual reader runs, including two GPU readers and
writer exclusion. Its remaining mutation/large/browser gates are separate from
this draft's exclusive-mode results.
