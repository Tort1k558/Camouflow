"""Owned ClientHello structure diagnostics, not TLS negotiation or anti-bot proof."""

import asyncio
import struct
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from native.drafts.network import client_hello


def vector(value, width=2):
    return len(value).to_bytes(width, "big") + value


def hello(*, grease=0x0A0A, extensions=None, reverse=False, ciphers=None):
    numbers = lambda values: b"".join(struct.pack("!H", value) for value in values)
    if extensions is None:
        extensions = [
            (grease, b""), (10, vector(numbers([grease, 29, 23]))), (11, b"\x01\x00"),
            (13, vector(numbers([0x0403, 0x0804]))),
            (16, vector(vector(b"h2", 1) + vector(b"http/1.1", 1) + vector(numbers([grease]), 1))),
            (43, vector(numbers([grease, 0x0304, 0x0303]), 1)), (45, b"\x01\x01"),
            (51, vector(numbers([grease]) + vector(b"\x00") + numbers([29]) + vector(b"k" * 32))),
            (65037, b"opaque fixture"), (21, b"\x00" * 8),
        ]
    if reverse:
        extensions = list(reversed(extensions))
    body = (b"\x03\x03" + b"R" * 32 + vector(b"S" * 32, 1)
            + vector(numbers([grease, 0x1301, 0x1302, 0xC02F]) if ciphers is None else ciphers)
            + b"\x01\x00" + vector(b"".join(numbers([kind]) + vector(value) for kind, value in extensions)))
    return b"\x01" + len(body).to_bytes(3, "big") + body


def record(payload, *, version=0x0301, kind=22):
    return bytes([kind]) + struct.pack("!HH", version, len(payload)) + payload


def test_selected_hello_shape_preserves_offers_but_not_grease_or_extension_order():
    first = client_hello.parse_client_hello(hello())
    second = client_hello.parse_client_hello(hello(grease=0xFAFA, reverse=True))
    assert first != second
    shape = client_hello.selected_shape(first)
    assert shape == client_hello.selected_shape(second)
    assert shape["ciphers"] == [0x1301, 0x1302, 0xC02F]
    assert shape["supported_versions"] == [0x0304, 0x0303]
    assert shape["alpn_hex"] == [b"h2".hex(), b"http/1.1".hex()]
    assert shape["key_shares"] == [{"group": 29, "key_length": 32}]
    assert all(shape[key] == 1 for key in ("ciphers_grease_count", "supported_groups_grease_count",
               "supported_versions_grease_count", "extensions_grease_count", "alpn_grease_count", "key_shares_grease_count"))
    assert "RRRR" not in repr(first) and "SSSS" not in repr(first) and "kkkk" not in repr(first)
    shape["compression_methods"].append(3)
    shape["key_shares"][0]["key_length"] = 0
    assert first["compression_methods"] == [0] and first["key_shares"][1]["key_length"] == 32
    different = client_hello.parse_client_hello(hello(ciphers=b"\x13\x01"))
    assert client_hello.selected_shape(first) != client_hello.selected_shape(different)
    assert len(client_hello.GREASE_VALUES) == 16 and 0x0A0B not in client_hello.GREASE_VALUES


@pytest.mark.parametrize("value", [None, b"", bytearray(b"a" * 40), b"a" * 65537,
    b"\x02" + hello()[1:], hello()[:-1], hello() + b"x"],
    ids=["none", "empty", "mutable", "oversized", "wrong-message-type", "truncated", "trailing"])
def test_hello_parser_rejects_wrong_type_bounds_and_message_framing(value):
    with pytest.raises(client_hello.ClientHelloError):
        client_hello.parse_client_hello(value)


@pytest.mark.parametrize("kind,body", [
    (10, b"\x00\x01\x00"), (13, b"\x00\x01\x00"), (11, b"\x01"),
    (43, b"\x01\x03"), (45, b"\x01\x01\x02"),
    (16, b"\x00\x01\x00"), (16, b"\x00\x02\x02\x68"),
    (51, b"\x00\x04\x00\x1d\x00\x01"),
])
def test_hello_parser_rejects_malformed_known_extension_vectors(kind, body):
    with pytest.raises(client_hello.ClientHelloError):
        client_hello.parse_client_hello(hello(extensions=[(kind, body)]))


def test_hello_parser_rejects_duplicate_extensions_and_odd_cipher_vector():
    with pytest.raises(client_hello.ClientHelloError, match="Duplicate"):
        client_hello.parse_client_hello(hello(extensions=[(21, b""), (21, b"")]))
    with pytest.raises(client_hello.ClientHelloError, match="odd"):
        client_hello.parse_client_hello(hello(ciphers=b"\x13"))


def test_hello_reader_reassembles_fragmented_records_without_exposing_random_bytes():
    async def run():
        raw = hello()
        reader = asyncio.StreamReader()
        reader.feed_data(record(raw[:3]) + record(raw[3:31], version=0x0303) + record(raw[31:]))
        reader.feed_eof()
        observed = await client_hello.read_client_hello(reader)
        assert observed["record_count"] == 3 and observed["record_versions"] == [0x0301, 0x0303, 0x0301]
        assert observed["handshake_bytes"] == len(raw)
        assert observed["hello"] == client_hello.parse_client_hello(raw)
    asyncio.run(run())


@pytest.mark.parametrize("raw", [b"", record(b"x", kind=23), record(b"x", version=0x03FF),
    record(b""), b"\x16\x03\x01\x40\x01", record(b"\x01\x01\x00\x00"),
    record(b"\x01\x00\x00\x64") + record(b"x") * 15])
def test_hello_reader_rejects_incomplete_unsupported_and_excessive_records(raw):
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(raw)
        reader.feed_eof()
        with pytest.raises(client_hello.ClientHelloError):
            await client_hello.read_client_hello(reader)
    asyncio.run(run())


def test_hello_reader_retains_an_explicit_deadline_for_a_stalled_peer(monkeypatch):
    timeout = asyncio.timeout
    monkeypatch.setattr(client_hello.asyncio, "timeout", lambda seconds: timeout(0.001))

    async def run():
        with pytest.raises(TimeoutError):
            await client_hello.read_client_hello(asyncio.StreamReader())
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["normal", "malformed", "unexpected-error", "unexpected-success", "page-closed"])
def test_owned_loopback_capture_closes_listener_and_preserves_failures(mode):
    from playwright.async_api import Error as PlaywrightError
    from native.drafts.network.loopback import capture_client_hello

    class Page:
        context = SimpleNamespace(browser=SimpleNamespace(is_connected=lambda: True))
        url = None

        def is_closed(self):
            return mode == "page-closed"

        async def goto(self, url, *, timeout):
            self.url = urlsplit(url)
            assert self.url.scheme == "https" and self.url.hostname == "localhost" and timeout == 10000
            if mode == "unexpected-success":
                return
            if mode == "unexpected-error":
                raise PlaywrightError("Target closed before capture")
            reader, writer = await asyncio.open_connection("127.0.0.1", self.url.port)
            try:
                writer.write(record(hello() if mode != "malformed" else b"invalid"))
                await writer.drain()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
            raise PlaywrightError("net::ERR_CONNECTION_CLOSED at owned loopback")

    async def run():
        page = Page()
        if mode == "normal":
            observed = await capture_client_hello(page)
            assert observed["navigation_failed_as_designed"]
            assert observed["selected_shape"] == client_hello.selected_shape(client_hello.parse_client_hello(hello()))
        else:
            expected = PlaywrightError if mode == "unexpected-error" else client_hello.ClientHelloError
            with pytest.raises(expected):
                await capture_client_hello(page)
        with pytest.raises(ConnectionRefusedError):
            await asyncio.open_connection("127.0.0.1", page.url.port)
    asyncio.run(run())


def test_stock_clienthello_evidence_is_bound_and_does_not_admit_negotiation():
    import hashlib
    import json
    from pathlib import Path

    draft = Path(__file__).resolve().parents[1] / "native/drafts/network"
    raw = (draft / "stock-clienthello-observations.json").read_bytes()
    data = json.loads(raw)
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    for key, expected in (("parser", "client_hello.py"), ("capture", "loopback.py")):
        assert data[key]["file"] == expected
        code = (draft / expected).read_bytes()
        assert b"\r" not in code and not code.startswith(b"\xef\xbb\xbf")
        assert hashlib.sha256(code).hexdigest() == data[key]["sha256"]
    stock_raw = (draft / data["stock_control_file"]).read_bytes()
    stock = json.loads(stock_raw)
    assert hashlib.sha256(stock_raw).hexdigest() == data["stock_control_sha256"]
    assert data["stock_core_sha256"] == stock["stock_core_sha256"]
    assert data["browser_get_version"]["revision"] == "@" + stock["target_revision"]
    assert data["passed"] and data["resources_closed"] and data["postguards_passed"]
    assert data["selected_shapes_repeat_equal"] and data["fresh_profile_count"] == len(data["captures"]) == 3
    assert data["headless"] is True
    assert data["selected_shape"]["supported_versions"] == [0x0304, 0x0303]
    assert data["selected_shape"]["alpn_hex"] == [b"h2".hex(), b"http/1.1".hex()]
    for row in data["captures"]:
        assert row["navigation_failed_as_designed"] and 4 <= row["handshake_bytes"] <= client_hello.MAX_HELLO_BYTES
        assert row["record_count"] == len(row["record_versions"]) <= client_hello.MAX_RECORDS
        assert sorted(value for value in row["extension_order"] if value not in client_hello.GREASE_VALUES) == data["selected_shape"]["extensions"]
    for field in ("tls_negotiated", "http2_verified", "http3_verified", "glint_verified", "privacy_admitted", "production_admitted"):
        assert data[field] is False
    assert data["remaining_unverified"]


def test_matched_clienthello_evidence_preserves_the_known_native_checkpoint_boundary():
    import hashlib
    import json
    from pathlib import Path

    draft = Path(__file__).resolve().parents[1] / "native/drafts/network"
    data = json.loads((draft / "matched-clienthello-observations.json").read_bytes())
    assert data["schema"] == 1 and data["passed"] and data["measurement_complete"] and data["postguards_passed"]
    assert data["headless"] and data["all_selected_shapes_equal"] and data["fresh_profile_count"] == len(data["captures"]) == 9
    for name, digest in data["scripts"].items():
        assert name in ("client_hello.py", "loopback.py") and hashlib.sha256((draft / name).read_bytes()).hexdigest() == digest
    assert hashlib.sha256((draft / data["required_native_manifest"]).read_bytes()).hexdigest() == data["candidate_manifest_sha256"]
    stock_raw = (draft / data["stock_control_file"]).read_bytes()
    stock = json.loads(stock_raw)
    assert hashlib.sha256(stock_raw).hexdigest() == data["stock_control_sha256"]
    baseline = json.loads((draft.parent / "upstream-156/windows-runtime-observations.json").read_bytes())
    assert data["native_core_sha256"] == baseline["runtime_core_sha256"]
    assert data["native_receipt_sha256"] == baseline["build_receipt_sha256"]
    assert data["stock_core_sha256"] == stock["stock_core_sha256"]
    assert [(row["phase"], row["index"]) for row in data["captures"]] == [
        (phase, index) for phase in ("native-before", "stock", "native-after") for index in range(3)]
    for row in data["captures"]:
        assert row["resources_closed"] and row["navigation_failed_as_designed"]
        assert row["browser_get_version"]["product"] == "Chrome/156.0.8078.36"
        revision = stock["target_revision"] if row["phase"] == "stock" else "0" * 40
        assert row["browser_get_version"]["revision"] == "@" + revision
        assert sorted(value for value in row["extension_order"] if value not in client_hello.GREASE_VALUES) == data["selected_shape"]["extensions"]
    assert data["native_dummy_revision_expected"] is True
    for field in ("native_policy_enabled", "native_runtime_git_revision_verified", "tls_negotiated", "full_tls_fingerprint_verified",
                  "http2_verified", "http3_verified", "privacy_admitted", "production_admitted"):
        assert data[field] is False
    assert data["remaining_unverified"]
