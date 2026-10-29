# Owned ClientHello diagnostics

**Unselected diagnostics, not a TLS stack or fingerprint override.** No BoringSSL
patch, certificate installation, proxy interception or security-policy change.

| Implemented | Boundary |
| --- | --- |
| Read the browser's initial ClientHello on an IPv4 loopback listener | Disposable owned page only; no successful TLS session |
| Parse bounded, fragmented TLS records and selected offer vectors | Not a complete TLS validator; unknown extension payloads remain opaque |
| Record ciphers, groups, signatures, versions, ALPN and key-share sizes | Offers, not negotiated protocol/cipher or HTTP/2 settings |
| Compare selected offers without reserved GREASE values or extension order | Not JA3/JA4, full packet equality, or a detector score |
| Retain record sizes and original extension order for diagnosis | Random/session/key bytes and extension payloads are not returned |

Parsing follows the ClientHello framing in
[RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html#section-4.1.2);
reserved GREASE values follow [RFC 8701](https://www.rfc-editor.org/rfc/rfc8701.html#section-2).
Cipher/group/signature/version order is preserved after removing GREASE;
extension identifiers are sorted for the **selected-shape comparison only**.
Opaque extension contents and their lengths are not part of that comparison.

## Stock calibration

Three fresh headless official CfT **156.0.8078.36** profiles produced equal selected
shapes. Their original extension orders and total message sizes differed.
Browser source/core bindings, runtime cleanup and input postguards passed.
[Scoped evidence](stock-clienthello-observations.json).

**Glint comparison is pending.** This does not verify successful TLS negotiation,
session resumption, certificate validation, DNS/proxy routes, HTTP/2, HTTP/3,
external detector acceptance or cross-platform identity.

## Use on an owned page

Select and verify explicit browser artifacts first. Use a fresh D: fixture
profile, never a user's existing tabs/profile:

```python
from pathlib import Path
from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime
from native.drafts.network.loopback import capture_client_hello

runtime = NativeRuntime(
    Path("D:/GlintChecks/fresh-owned-profile"),
    Path("D:/verified-browser/chrome.exe"),
    NativeConfiguration(),
)
try:
    context = await runtime.start(headless=True)
    observed = await capture_client_hello(context.pages[0])
    print(observed["selected_shape"])
finally:
    await runtime.close()
```

The HTTPS navigation **must fail**: the listener closes after the initial Hello
and never sends a ServerHello/certificate. Unexpected navigation failures or
browser/page closure reject the observation. There are no capture retries or
replacement browsers. This fixture does not isolate all browser network traffic.

Bounds: 64 KiB handshake, 16 plaintext records, 16 KiB per record, five-second
read deadline and ten-second navigation deadline. Oversized, truncated, duplicate
or malformed selected fields fail explicitly. Parser/lifecycle tests include
fragmentation, GREASE/order handling, stalls and listener cleanup.

Private calibration: `D:\Glint156Candidate\stock-clienthello156-20261029-v2`.
The earlier private-adapter calibration remains in `stock-clienthello156-20261029-v1`.
