# Canvas readback algorithm candidate

Inactive research prototype, not an approved privacy algorithm or Chromium
patch. No hooks, renderer policy consumer or advertised protection are enabled.

The candidate transforms only detached unpremultiplied RGBA8/sRGB copies.
It canonically selects the RGB least-significant bits of fully opaque pixels
from an HMAC-SHA256 stream keyed by a trusted partition/surface seed. Absolute
coordinates determine blocks (85 pixels, three bits each); crop origins do not
reset the stream. This makes repeated transformation idempotent and limits each
changed channel to a one-level difference. Nonopaque pixels and out-of-canvas
padding remain untouched. No profile root key is accepted or transported here.

The domain explicitly says `candidate`; it is not a released version-1 contract.
HMAC is already provided by Chromium's BoringSSL, not a new dependency.
Invalid layouts/coordinate overflow fail. A crypto failure may leave the detached
copy partially transformed: callers must discard it, never fall back to export.

## Verification so far

The translation unit passed isolated clang syntax checks with Chromium's browser
flags. A separate Windows executable linked the candidate against the existing
pinned BoringSSL libraries and upstream libc++ abort object, entirely outside
the active Chromium output tree. It executed 12 checks successfully:

- independent Python HMAC vector;
- idempotence;
- full/cropped reads and their agreement across 85-pixel block boundaries;
- channel delta bound and unchanged alpha;
- transparent/partial-alpha pixels and out-of-bounds padding;
- rejected invalid layout/coordinate overflow without changing the buffer;
- two public fixture seeds produce distinct results;
- a one-megapixel transform (13 ms in one local run, not a benchmark guarantee).

Evidence: `D:/CamouFlowNative/canvas-candidate-native-tests-libcpp-abort/proof.json`
and `tests.log`. These are algorithm-only results, not BrowserContext key
isolation, Blink API compatibility, export equivalence or privacy admission.

Important unresolved tradeoffs:

- Flat opaque colors gain a detectable deterministic low-bit pattern. Do not
  call this undetectable, or approve it from repeat/crop tests alone.
- Editing/color-picker values can differ by one; quantify compatibility and
  detectability against more selective and alternative algorithms before adoption.
- Partial alpha, float16/HDR and other color spaces are not protected. Silently
  accepting them as a protected profile would violate capability admission.
- Export encoding must use the same canonical pixels without modifying drawImage,
  ImageBitmap, presentation or the live canvas backing store.
- Trusted policy must exist before the first synchronous read, in document and
  worker contexts. Current IPC drafts do not establish this startup guarantee.

Next gates: native vectors/idempotence/crop/padding/alpha/performance, then API
compatibility and adversarial detection tests. No getImageData/toDataURL/toBlob/
OffscreenCanvas hook may activate this candidate before those gates are reviewed.
