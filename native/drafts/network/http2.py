"""Bounded initial HTTP/2 framing diagnostics; not an HTTP/2 implementation."""

PREFACE = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"
SERVER_PREFACE = b"\x00\x00\x00\x04\x00\x00\x00\x00\x00"
MAX_FRAME_BYTES = 16384
MAX_CAPTURE_BYTES = 65536
MAX_FRAMES = 32


class HTTP2CaptureError(ValueError):
    pass


def _settings(payload):
    if len(payload) % 6:
        raise HTTP2CaptureError("SETTINGS payload is not a sequence of six-byte parameters")
    result = []
    for offset in range(0, len(payload), 6):
        identifier = int.from_bytes(payload[offset:offset + 2], "big")
        value = int.from_bytes(payload[offset + 2:offset + 6], "big")
        if identifier == 2 and value not in (0, 1):
            raise HTTP2CaptureError("Invalid SETTINGS_ENABLE_PUSH")
        if identifier == 4 and value > 0x7fffffff:
            raise HTTP2CaptureError("Invalid SETTINGS_INITIAL_WINDOW_SIZE")
        if identifier == 5 and not 16384 <= value <= 16777215:
            raise HTTP2CaptureError("Invalid SETTINGS_MAX_FRAME_SIZE")
        result.append({"identifier": identifier, "value": value})
    return result


def _priority(payload, stream):
    dependency = int.from_bytes(payload[:4], "big")
    if dependency & 0x7fffffff == stream:
        raise HTTP2CaptureError("A stream cannot depend on itself")
    return {"exclusive": bool(dependency & 0x80000000),
            "dependency": dependency & 0x7fffffff, "weight": payload[4] + 1}


def read_initial_connection(connection):
    """Read through the first HEADERS frame from a caller-owned timed socket.

    The caller negotiates ALPN h2 and sends SERVER_PREFACE before calling this.
    No header-block bytes, cookies, URLs or arbitrary frame payloads are returned.
    A successful capture is not a successful HTTP response or HPACK validation.
    """
    consumed = 0

    def exact(length):
        nonlocal consumed
        if consumed + length > MAX_CAPTURE_BYTES:
            raise HTTP2CaptureError("Initial HTTP/2 capture exceeds the byte bound")
        value = bytearray()
        while len(value) < length:
            chunk = connection.recv(length - len(value))
            if not chunk:
                raise HTTP2CaptureError("Truncated initial HTTP/2 connection")
            value.extend(chunk)
        consumed += length
        return bytes(value)

    if exact(len(PREFACE)) != PREFACE:
        raise HTTP2CaptureError("Invalid HTTP/2 client connection preface")
    frames = []
    for index in range(MAX_FRAMES):
        header = exact(9)
        length = int.from_bytes(header[:3], "big")
        kind, flags = header[3:5]
        stream = int.from_bytes(header[5:9], "big") & 0x7fffffff
        if length > MAX_FRAME_BYTES:
            raise HTTP2CaptureError("Frame exceeds the fixture's default maximum frame size")
        if index == 0 and (kind != 4 or flags & 1 or stream != 0):
            raise HTTP2CaptureError("The first client frame must be non-ACK SETTINGS on stream zero")
        payload = exact(length)
        row = {"type": kind, "flags": flags, "stream": stream, "length": length}
        if kind == 4:
            if stream != 0 or (flags & 1 and payload):
                raise HTTP2CaptureError("Invalid SETTINGS stream or ACK payload")
            row['settings'] = _settings(payload)
        elif kind == 8:
            if length != 4:
                raise HTTP2CaptureError("WINDOW_UPDATE requires four bytes")
            increment = int.from_bytes(payload, 'big') & 0x7fffffff
            if not increment:
                raise HTTP2CaptureError("WINDOW_UPDATE increment must not be zero")
            row['window_increment'] = increment
        elif kind == 2:
            if stream == 0 or length != 5:
                raise HTTP2CaptureError("Invalid PRIORITY stream or length")
            row['priority'] = _priority(payload, stream)
        elif kind == 6:
            if stream != 0 or length != 8:
                raise HTTP2CaptureError("Invalid PING stream or length")
        elif kind == 1:
            if stream == 0 or stream % 2 == 0:
                raise HTTP2CaptureError("Initial request HEADERS requires an odd client stream")
            offset, padding = 0, 0
            if flags & 8:
                if not payload:
                    raise HTTP2CaptureError("Padded HEADERS is missing its pad length")
                padding, offset = payload[0], 1
            if flags & 32:
                if len(payload) - padding - offset < 5:
                    raise HTTP2CaptureError("HEADERS priority is truncated")
                row['priority'] = _priority(payload[offset:offset + 5], stream)
                offset += 5
            if padding > len(payload) - offset:
                raise HTTP2CaptureError("HEADERS padding exceeds the payload")
            row.update(header_block_bytes=len(payload) - offset - padding,
                       end_headers=bool(flags & 4), end_stream=bool(flags & 1))
            frames.append(row)
            return {"frames": frames, "captured_bytes": consumed,
                    "header_block_decoded": False, "http_response_verified": False}
        elif kind in (0, 3, 5, 7, 9):
            raise HTTP2CaptureError("Unexpected standard frame before the first request HEADERS")
        # Extension frame payloads stay opaque; unknown frame types/flag bits are retained.
        frames.append(row)
    raise HTTP2CaptureError("Initial HTTP/2 capture exceeds the frame-count bound")
