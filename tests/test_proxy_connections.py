"""Proxy connections must fail closed and release owned resources."""

import socket
import threading
import time
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest

from app.core import proxy_utils
from app.core.proxy_utils import SocksBridgeHandler
from app.services import proxy_health


def test_health_check_closes_socket_after_response_timeout(monkeypatch):
    connection = Mock()
    connection.recv.side_effect = TimeoutError("Synthetic response timeout")
    monkeypatch.setattr(proxy_health.socket, "create_connection", lambda *args, **kwargs: connection)
    monkeypatch.setattr(proxy_health, "PROXY_INTERNET_CHECK_URL", "http://geo.example.invalid/")

    passed, _, error, _ = proxy_health.probe_proxy_endpoint("http://proxy.example.invalid:8080")

    assert not passed and "timeout" in error.lower()
    connection.close.assert_called_once()


def test_health_check_closes_socket_after_tls_failure(monkeypatch):
    connection = Mock()
    connection.recv.side_effect = [b"HTTP/1.1 200 Connection Established\r\n\r\n"]
    context = Mock()
    context.wrap_socket.side_effect = OSError("Synthetic TLS failure")
    monkeypatch.setattr(proxy_health.socket, "create_connection", lambda *args, **kwargs: connection)
    monkeypatch.setattr(proxy_health.ssl, "create_default_context", lambda: context)

    passed, _, error, _ = proxy_health.probe_proxy_endpoint("http://proxy.example.invalid:8080")

    assert not passed and "TLS failure" in error
    connection.close.assert_called_once()


@pytest.mark.parametrize("greeting", [b"\x05\x01\x02", b"\x05\x00"])
def test_socks_bridge_rejects_unoffered_no_authentication_method(greeting):
    chunks = iter([greeting[:2], greeting[2:]])
    connection = Mock()
    connection.recv.side_effect = lambda size: next(chunks)
    handler = object.__new__(SocksBridgeHandler)
    handler.connection = connection

    assert not handler._handshake()
    connection.sendall.assert_called_once_with(b"\x05\xff")


def test_socks_bridge_accepts_offered_no_authentication_method():
    chunks = iter([b"\x05\x02", b"\x02\x00"])
    connection = Mock()
    connection.recv.side_effect = lambda size: next(chunks)
    handler = object.__new__(SocksBridgeHandler)
    handler.connection = connection

    assert handler._handshake()
    connection.sendall.assert_called_once_with(b"\x05\x00")


def test_socks_bridge_preserves_response_after_client_half_close():
    client, local = socket.socketpair()
    upstream, target = socket.socketpair()
    client.settimeout(2)
    target.settimeout(2)
    handler = object.__new__(SocksBridgeHandler)
    handler.connection = local
    worker = threading.Thread(target=handler._pipe, args=(upstream,), daemon=True)
    worker.start()
    try:
        client.sendall(b"Synthetic request")
        client.shutdown(socket.SHUT_WR)
        assert target.recv(100) == b"Synthetic request"
        assert target.recv(100) == b""
        target.sendall(b"Synthetic response")
        target.shutdown(socket.SHUT_WR)
        assert client.recv(100) == b"Synthetic response"
        assert client.recv(100) == b""
        worker.join(timeout=2)
        assert not worker.is_alive()
    finally:
        for connection in [client, local, upstream, target]:
            connection.close()
        worker.join(timeout=2)


def test_socks_bridge_retries_partial_and_temporarily_blocked_writes(monkeypatch):
    client, upstream = Mock(), Mock()
    client.recv.side_effect = [b"request", b""]
    upstream.recv.side_effect = [b"response", b""]
    captured = {client: bytearray(), upstream: bytearray()}
    blocked = {client, upstream}

    def send(connection, data):
        if connection in blocked:
            blocked.remove(connection)
            raise BlockingIOError()
        size = min(2, len(data))
        captured[connection].extend(data[:size])
        return size

    client.send.side_effect = lambda data: send(client, data)
    upstream.send.side_effect = lambda data: send(upstream, data)
    monkeypatch.setattr(proxy_utils.select, "select", lambda reading, writing, errors, timeout: (reading, writing, []))
    handler = object.__new__(SocksBridgeHandler)
    handler.connection = client

    handler._pipe(upstream)

    assert captured[client] == b"response"
    assert captured[upstream] == b"request"
    client.shutdown.assert_called_once_with(socket.SHUT_WR)
    upstream.shutdown.assert_called_once_with(socket.SHUT_WR)
    upstream.close.assert_called_once()


@pytest.mark.parametrize("reverse", [False, True])
def test_socks_bridge_preserves_large_transfer_with_slow_reader(reverse):
    client, local = socket.socketpair()
    upstream, target = socket.socketpair()
    for connection in [client, local, upstream, target]:
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)
        connection.settimeout(5)
    sender, receiver = (target, client) if reverse else (client, target)
    payload = bytes(range(256)) * 8192
    errors = []

    def transmit():
        try:
            sender.sendall(payload)
            sender.shutdown(socket.SHUT_WR)
        except OSError as error:
            errors.append(error)

    handler = object.__new__(SocksBridgeHandler)
    handler.connection = local
    relay = threading.Thread(target=handler._pipe, args=(upstream,), daemon=True)
    producer = threading.Thread(target=transmit, daemon=True)
    relay.start()
    producer.start()
    try:
        receiver.shutdown(socket.SHUT_WR)
        received = bytearray()
        while True:
            chunk = receiver.recv(8192)
            if not chunk:
                break
            received.extend(chunk)
            time.sleep(0.0001)
        producer.join(timeout=2)
        relay.join(timeout=2)
        assert not errors and not producer.is_alive() and not relay.is_alive()
        assert received == payload
    finally:
        for connection in [client, local, upstream, target]:
            connection.close()
        producer.join(timeout=2)
        relay.join(timeout=2)


@pytest.fixture
def http_socks_bridge(monkeypatch):
    observations = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            observations.append({"path": self.path, "headers": dict(self.headers), "body": body})
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=target.serve_forever, daemon=True)
    worker.start()
    connections = []

    def connect(handler, host, port):
        connections.append((host, port))
        return socket.create_connection(target.server_address, timeout=2)

    monkeypatch.setattr(proxy_utils.HttpSocksBridgeHandler, "_open_socks_connection", connect)
    details = proxy_utils.ProxyDetails("socks5", "upstream.example.invalid", 1080, "synthetic-user", "synthetic-password")
    bridge = proxy_utils.LocalHttpProxyServer(details)
    parsed = urlsplit(bridge.start())
    try:
        assert parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
        assert bridge.start() == parsed.geturl()
        yield bridge, observations, connections
    finally:
        bridge.stop()
        target.shutdown()
        target.server_close()
        worker.join(timeout=2)


def test_http_socks_bridge_rewrites_origin_request_and_preserves_body(http_socks_bridge):
    bridge, observations, connections = http_socks_bridge
    body = bytes(range(256)) * 4096
    connection = http.client.HTTPConnection("127.0.0.1", bridge.port, timeout=5)
    try:
        connection.request("POST", "http://fixture.example.invalid:8081/path?q=1", body=body,
                           headers={"Host": "wrong.example.invalid", "Proxy-Authorization": "synthetic-secret", "Proxy-Connection": "keep-alive"})
        response = connection.getresponse()
        assert response.status == 200 and response.read() == body
    finally:
        connection.close()
    assert connections == [("fixture.example.invalid", 8081)]
    assert observations[0]["path"] == "/path?q=1"
    assert observations[0]["body"] == body
    assert observations[0]["headers"]["Host"] == "fixture.example.invalid:8081"
    assert observations[0]["headers"]["Connection"] == "close"
    assert "Proxy-Authorization" not in observations[0]["headers"]
    assert "Proxy-Connection" not in observations[0]["headers"]


@pytest.mark.parametrize("wire_request", [
    b"CONNECT fixture.example.invalid HTTP/1.1\r\n\r\n",
    b"CONNECT fixture.example.invalid:0 HTTP/1.1\r\n\r\n",
    b"CONNECT fixture.example.invalid:65536 HTTP/1.1\r\n\r\n",
    b"CONNECT fixture.example.invalid:443/path HTTP/1.1\r\n\r\n",
    b"CONNECT user:password@fixture.example.invalid:443 HTTP/1.1\r\n\r\n",
    b"GET /relative HTTP/1.1\r\n\r\n",
    b"GET ftp://fixture.example.invalid/ HTTP/1.1\r\n\r\n",
    b"GET http://fixture.example.invalid:0/ HTTP/1.1\r\n\r\n",
    b"GET http://fixture.example.invalid/ HTTP/1.1\r\nInvalid header\r\n\r\n",
    b"GET http://fixture.example.invalid/ HTTP/1.1\r\n" + b"X: " + b"a" * 32768 + b"\r\n\r\n",
], ids=["missing-port", "zero-port", "large-port", "connect-path", "userinfo", "relative", "wrong-scheme", "http-zero-port", "invalid-header", "large-header"])
def test_http_socks_bridge_rejects_malformed_request_before_connect(http_socks_bridge, wire_request):
    bridge, _, connections = http_socks_bridge
    with socket.create_connection(("127.0.0.1", bridge.port), timeout=2) as connection:
        connection.sendall(wire_request)
        assert connection.recv(100).startswith(b"HTTP/1.1 400 ")
    assert not connections


def test_http_socks_bridge_tunnels_after_connect_and_stops_owned_connections(http_socks_bridge):
    bridge, observations, connections = http_socks_bridge
    server = bridge._server
    with socket.create_connection(("127.0.0.1", bridge.port), timeout=2) as connection:
        connection.sendall(b"CONNECT fixture.example.invalid:443 HTTP/1.1\r\nHost: fixture.example.invalid:443\r\n\r\n")
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += connection.recv(1)
        assert header == b"HTTP/1.1 200 Connection Established\r\n\r\n"
        connection.sendall(b"POST /tunnel HTTP/1.1\r\nHost: fixture.example.invalid\r\nContent-Length: 4\r\nConnection: close\r\n\r\ndata")
        response = http.client.HTTPResponse(connection)
        response.begin()
        assert response.status == 200 and response.read() == b"data"
    assert connections == [("fixture.example.invalid", 443)]
    assert observations[0]["path"] == "/tunnel"
    with socket.create_connection(("127.0.0.1", bridge.port), timeout=2) as connection:
        connection.sendall(b"CONNECT fixture.example.invalid:443 HTTP/1.1\r\n\r\n")
        assert connection.recv(100).startswith(b"HTTP/1.1 200 ")
        bridge.stop()
        assert connection.recv(100) == b""
    assert server.stopping.is_set()
    deadline = time.monotonic() + 2
    while server._connections and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not server._connections


@pytest.mark.parametrize("framing, passed", [
    ("content-length", True), ("truncated-length", False), ("invalid-length", False),
    ("oversized-length", False), ("chunked", True), ("truncated-chunked", False),
    ("invalid-chunk-ending", False), ("conflicting-framing", False),
    ("chunked-trailer", True), ("truncated-trailer", False), ("negative-chunk", False),
    ("oversized-chunk", False), ("close-delimited", True), ("unsupported-encoding", False),
])
def test_health_check_requires_complete_valid_http_body(monkeypatch, framing, passed):
    body = b'{"success":true,"ip":"192.0.2.1"}'
    headers = b""
    encoded = body
    if "length" in framing:
        length = len(body)
        if framing == "truncated-length":
            length += 5
        elif framing == "oversized-length":
            length = 3 * 1024 * 1024
        headers = b"Content-Length: " + (b"invalid" if framing == "invalid-length" else str(length).encode()) + b"\r\n"
    elif framing == "close-delimited":
        pass
    elif framing == "unsupported-encoding":
        headers = b"Transfer-Encoding: notchunked\r\n"
        encoded = f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n"
    else:
        headers = b"Transfer-Encoding: chunked\r\n"
        encoded = f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n"
        if framing == "truncated-chunked":
            encoded = f"{len(body):x}\r\n".encode() + body + b"\r\n"
        elif framing == "invalid-chunk-ending":
            encoded = f"{len(body):x}\r\n".encode() + body + b"xx0\r\n\r\n"
        elif framing == "conflicting-framing":
            encoded = body
            headers += f"Content-Length: {len(body)}\r\n".encode()
        elif framing == "chunked-trailer":
            encoded = encoded[:-2] + b"X-Trailer: synthetic\r\n\r\n"
        elif framing == "truncated-trailer":
            encoded = encoded[:-2]
        elif framing == "negative-chunk":
            encoded = b"-1\r\n" + body + b"\r\n0\r\n\r\n"
        elif framing == "oversized-chunk":
            encoded = b"300000\r\n" + body + b"\r\n0\r\n\r\n"
    connection = Mock()
    connection.recv.side_effect = [b"HTTP/1.1 200 OK\r\n" + headers + b"\r\n" + encoded, b""]
    monkeypatch.setattr(proxy_health.socket, "create_connection", lambda *args, **kwargs: connection)
    monkeypatch.setattr(proxy_health, "PROXY_INTERNET_CHECK_URL", "http://geo.example.invalid/")

    result, _, _, _ = proxy_health.probe_proxy_endpoint("http://proxy.example.invalid:8080")

    assert result is passed
    connection.close.assert_called_once()
