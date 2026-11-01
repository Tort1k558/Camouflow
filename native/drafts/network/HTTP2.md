# Initial HTTP/2 connection diagnostics

**Unselected diagnostics. Stock calibration only; no Glint result or identity override.**

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
HTTP/2 validator. There are no new application dependencies or changes to the active build.

## Owned TLS/HTTP response fixture

[`http2_loopback.py`](http2_loopback.py) reuses the existing canonical D: key/path
guards and bounded IPv4 loopback TLS server. Its capture-only handler sends a
SETTINGS preface and closes after the initial request; it is not an HTTP response.

[`http2_response.py`](http2_response.py) separately uses **hyper-h2** for request
HPACK/state validation and a complete owned GET response. It imports this explicit
diagnostic tool only when creating the server; a missing tool raises rather than
installing or substituting anything. Stage it outside the application environment:

```powershell
.venv\Scripts\python.exe -B -m pip install --no-cache-dir `
  --target D:/GlintChecks/http2-tools h2==4.3.0 hpack==4.1.0 hyperframe==6.1.0
```

Add that explicit tool directory to the diagnostic process's `sys.path`, then call
`http2_response.create_server(certificate_path, private_key_path, report)`. The
caller owns server threads, certificate/key removal, fresh profiles and shutdown.
Use only the fixture's `/owned` HTTPS GET path. Do not enable global certificate
exceptions; the measured run allowed one ephemeral SPKI in disposable processes.

### Stock156 calibration

[Measured record](stock-http2-observations.json): three fresh official Chromium
156.0.8078.36 profiles each received status 200 and the expected page over TLS 1.3
with ALPN/browser `nextHopProtocol` **h2**. All three completed initial control
shapes matched. Runtime core, driver/source guards, runtime/thread cleanup and
temporary private-key removal passed.

Two additional TLS connections closed with **zero application bytes**. They remain
explicit non-successful request captures, not additional passes. Any partial or
malformed application data remains a failure. Tests distinguish these cases.
The earlier capture-only and first responding-fixture attempts remain failed:
both incorrectly required every accepted TLS connection to contain a request;
their uninstrumented truncations cannot retrospectively be classified as empty.

The selected comparison omits payload lengths, HPACK bytes, TLS records and
timings. This is not JA3/JA4 equality, resumption, ordinary certificate-path
validation, cross-platform identity, privacy or production admission.

### Matched Glint R8 / stock156 controls

[Matched measurement](matched-r8-http2-observations.json): Glint R8 → stock156 →
Glint R8, three fresh profiles per phase. All nine completed requests passed;
their selected initial control shapes match. Core/source guards, fixture-thread
cleanup and ephemeral-key removal passed. All runs were headless with protected
policies off and one diagnostic SPKI allowlist, not ordinary certificate-path
validation. Earlier baseline failure is preserved, not admitted by this result.

```powershell
.venv\Scripts\python.exe -B -m pytest -q tests/test_native_http2_capture.py `
  -o cache_dir=D:/GlintChecks/http2-cache --basetemp D:/GlintChecks/http2-temp
```

Next measurement: protected-profile transport, resumption and HTTP/3 as separate
gates. Do not infer cross-platform TLS identity or JA3/JA4 equality from matching
initial HTTP/2 control frames alone.
