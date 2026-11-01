# Initial HTTP/2 connection diagnostics

**Unselected collector. No browser result or network identity override.**

[`http2.py`](http2.py) reads a caller-owned, timed socket through the first
request HEADERS frame. It preserves initial SETTINGS order and duplicate/unknown
identifiers, frame order, WINDOW_UPDATE increments and PRIORITY metadata.
Header blocks and opaque payload contents are discarded, not logged.

| Captured | Not established |
| --- | --- |
| Exact client preface and first non-ACK SETTINGS | TLS negotiation or ordinary certificate validation |
| Selected control-frame structure and values | Complete protocol/state-machine validity |
| First HEADERS length, padding/priority metadata and flags | HPACK contents, header order or completed header block |
| Bounded fragmented socket reads | Successful HTTP response, HTTP/3, JA4 or detector acceptance |

The caller must first negotiate **ALPN `h2`**, set its owned connection deadline
and send `SERVER_PREFACE` (an empty SETTINGS frame). This module does not create
a listener, generate keys, modify certificates or start a browser. Never feed
HTTP/1.1 or an unnegotiated TLS connection into the collector and describe it as
measured HTTP/2. A complete end-to-end fixture remains required.

Limits: 16 KiB per frame (the fixture advertises the default), 64 KiB total,
32 frames. Invalid framing, truncation and bound violations raise
`HTTP2CaptureError`; socket errors/timeouts propagate. Unknown extension frame
types and unused flag bits remain observable rather than being rejected.
Duplicate SETTINGS remain ordered, not collapsed into a dictionary.

Framing follows [RFC 9113 sections 3.4, 4.1, 6.2, 6.3, 6.5 and 6.9](https://www.rfc-editor.org/rfc/rfc9113.html).
This deliberately does not implement HPACK, an HTTP server, a TLS stack or a full
HTTP/2 validator. There are no new dependencies or changes to the active build.

```powershell
.venv\Scripts\python.exe -B -m pytest -q tests/test_native_http2_capture.py `
  -o cache_dir=D:/GlintChecks/http2-cache --basetemp D:/GlintChecks/http2-temp
```

Next measurement: owned TLS/ALPN fixture with explicit ephemeral-key handling,
stock Chromium control and independent verified Glint runtime; preserve failed
attempts, source/core postguards and owned-process cleanup. Do not infer a
cross-platform transport identity from matching initial control frames alone.
