"""Bounded parsing of an owned initial TLS ClientHello, not a TLS implementation."""

import asyncio


MAX_HELLO_BYTES = 65536
MAX_RECORD_BYTES = 16384
MAX_RECORDS = 16
GREASE_VALUES = frozenset(0x0A0A + 0x1010 * index for index in range(16))
GREASE_ALPN_HEX = frozenset(value.to_bytes(2, "big").hex() for value in GREASE_VALUES)


class ClientHelloError(ValueError):
    pass


class _Cursor:
    def __init__(self, value: bytes):
        self.value = value
        self.offset = 0

    def take(self, length: int) -> bytes:
        end = self.offset + length
        if length < 0 or end > len(self.value):
            raise ClientHelloError("Truncated ClientHello field")
        result = self.value[self.offset:end]
        self.offset = end
        return result

    def number(self, width: int) -> int:
        return int.from_bytes(self.take(width), "big")

    def vector(self, width: int) -> bytes:
        return self.take(self.number(width))

    def finish(self) -> None:
        if self.offset != len(self.value):
            raise ClientHelloError("Trailing bytes in a ClientHello field")


def _numbers(raw: bytes) -> list[int]:
    if len(raw) % 2:
        raise ClientHelloError("A two-byte TLS identifier vector has an odd length")
    return [int.from_bytes(raw[index:index + 2], "big") for index in range(0, len(raw), 2)]


def parse_client_hello(message: bytes) -> dict:
    if type(message) is not bytes or not 4 <= len(message) <= MAX_HELLO_BYTES:
        raise ClientHelloError("ClientHello exceeds the owned-fixture size bound")
    cursor = _Cursor(message)
    if cursor.number(1) != 1 or cursor.number(3) != len(message) - 4:
        raise ClientHelloError("Expected exactly one ClientHello handshake message")
    legacy_version = cursor.number(2)
    cursor.take(32)  # Random and session/key bytes are deliberately not returned.
    session = cursor.vector(1)
    if len(session) > 32:
        raise ClientHelloError("Invalid legacy session identifier length")
    ciphers = _numbers(cursor.vector(2))
    compression = list(cursor.vector(1))
    if not ciphers or not compression:
        raise ClientHelloError("Empty cipher or compression vector")
    extensions = _Cursor(cursor.vector(2))
    cursor.finish()
    result = {"legacy_version": legacy_version, "session_id_length": len(session),
              "ciphers": ciphers, "compression_methods": compression,
              "extensions": [], "extension_payload_lengths": {}}
    while extensions.offset < len(extensions.value):
        kind = extensions.number(2)
        body = extensions.vector(2)
        if kind in result["extensions"]:
            raise ClientHelloError("Duplicate ClientHello extension")
        result["extensions"].append(kind)
        result["extension_payload_lengths"][str(kind)] = len(body)
        field = _Cursor(body)
        if kind in (10, 13):
            result["supported_groups" if kind == 10 else "signature_algorithms"] = _numbers(field.vector(2))
        elif kind == 11:
            result["point_formats"] = list(field.vector(1))
        elif kind == 43:
            result["supported_versions"] = _numbers(field.vector(1))
        elif kind == 45:
            result["psk_modes"] = list(field.vector(1))
        elif kind == 16:
            protocols = _Cursor(field.vector(2))
            result["alpn_hex"] = []
            while protocols.offset < len(protocols.value):
                protocol = protocols.vector(1)
                if not protocol:
                    raise ClientHelloError("Empty ALPN identifier")
                result["alpn_hex"].append(protocol.hex())
        elif kind == 51:
            shares = _Cursor(field.vector(2))
            result["key_shares"] = []
            while shares.offset < len(shares.value):
                group = shares.number(2)
                key = shares.vector(2)
                result["key_shares"].append({"group": group, "key_length": len(key)})
        else:
            continue
        field.finish()
    return result


def selected_shape(hello: dict) -> dict:
    """Compare selected offers, ignoring GREASE values and extension ordering only."""
    result = {key: hello[key] for key in ("legacy_version", "session_id_length")}
    result["compression_methods"] = list(hello["compression_methods"])
    for key in ("ciphers", "supported_groups", "signature_algorithms", "supported_versions"):
        if key in hello:
            result[key] = [value for value in hello[key] if value not in GREASE_VALUES]
            result[key + "_grease_count"] = sum(value in GREASE_VALUES for value in hello[key])
    result["extensions"] = sorted(value for value in hello["extensions"] if value not in GREASE_VALUES)
    result["extensions_grease_count"] = sum(value in GREASE_VALUES for value in hello["extensions"])
    for key in ("point_formats", "psk_modes"):
        if key in hello:
            result[key] = list(hello[key])
    if "alpn_hex" in hello:
        result["alpn_hex"] = [value for value in hello["alpn_hex"] if value not in GREASE_ALPN_HEX]
        result["alpn_grease_count"] = sum(value in GREASE_ALPN_HEX for value in hello["alpn_hex"])
    if "key_shares" in hello:
        result["key_shares"] = [dict(row) for row in hello["key_shares"] if row["group"] not in GREASE_VALUES]
        result["key_shares_grease_count"] = sum(row["group"] in GREASE_VALUES for row in hello["key_shares"])
    return result


async def read_client_hello(reader: asyncio.StreamReader) -> dict:
    handshake = bytearray()
    versions = []
    try:
        async with asyncio.timeout(5):
            for _ in range(MAX_RECORDS):
                header = await reader.readexactly(5)
                kind, version, length = header[0], int.from_bytes(header[1:3], "big"), int.from_bytes(header[3:5], "big")
                if kind != 22 or version not in (0x0301, 0x0302, 0x0303) or not 0 < length <= MAX_RECORD_BYTES:
                    raise ClientHelloError("Unsupported initial handshake record in owned fixture")
                if len(handshake) + length > MAX_HELLO_BYTES:
                    raise ClientHelloError("ClientHello exceeds the owned-fixture size bound")
                versions.append(version)
                handshake.extend(await reader.readexactly(length))
                if len(handshake) >= 4:
                    total = 4 + int.from_bytes(handshake[1:4], "big")
                    if total > MAX_HELLO_BYTES:
                        raise ClientHelloError("Declared ClientHello exceeds the owned-fixture size bound")
                    if len(handshake) >= total:
                        return {"record_versions": versions, "record_count": len(versions),
                                "handshake_bytes": len(handshake), "hello": parse_client_hello(bytes(handshake))}
    except asyncio.IncompleteReadError as error:
        raise ClientHelloError("Connection ended before a complete ClientHello") from error
    raise ClientHelloError("ClientHello exceeds the owned-fixture record-count bound")
