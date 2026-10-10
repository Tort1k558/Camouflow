"""Proxy connections must fail closed and release owned resources."""

import socket
import threading
import time
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
