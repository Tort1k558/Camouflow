import logging
import select
import socket
import socketserver
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import unquote, urlparse

import socks


LOGGER = logging.getLogger("proxy_log")
LOGGER.propagate = True


@dataclass
class ProxyDetails:
    scheme: str
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]


class _ProxyTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, handler_cls, proxy_details: ProxyDetails):
        self.proxy_details = proxy_details
        self.logger = logging.getLogger("proxy_log")
        super().__init__(address, handler_cls)


class SocksBridgeHandler(socketserver.StreamRequestHandler):
    """
    Minimal SOCKS5 server that forwards via an upstream SOCKS4/5 proxy.
    Local side: no authentication.
    """

    timeout = 10

    def handle(self):
        try:
            if not self._handshake():
                return
            cmd, _, target_host, target_port = self._read_request()
            if cmd != 0x01:
                self._send_reply(0x07)  # Command not supported
                return
            upstream = self._open_socks_connection(target_host, target_port)
            if not upstream:
                self._send_reply(0x01)  # General failure
                return

            bound_addr, bound_port = upstream.getsockname()[:2]
            self._send_reply(0x00, bound_addr, bound_port)
            self._pipe(upstream)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            return
        except OSError:
            return
        except Exception:
            return

    def _recv_exact(self, size: int) -> Optional[bytes]:
        buf = b""
        while len(buf) < size:
            chunk = self.connection.recv(size - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _handshake(self) -> bool:
        header = self._recv_exact(2)
        if not header:
            return False
        ver, nmethods = header[0], header[1]
        if ver != 5:
            return False
        methods = self._recv_exact(nmethods)
        if methods is None:
            return False
        # Respond with "no authentication"
        try:
            self.connection.sendall(b"\x05\x00")
        except Exception:
            return False
        return True

    def _read_request(self):
        header = self._recv_exact(4)
        if not header:
            raise ConnectionError("SOCKS request header missing")
        ver, cmd, _, atyp = header
        if ver != 5:
            raise ConnectionError("Unsupported SOCKS version")

        if atyp == 0x01:  # IPv4
            raw_addr = self._recv_exact(4)
            host = socket.inet_ntoa(raw_addr)
        elif atyp == 0x03:  # Domain
            length_raw = self._recv_exact(1)
            if not length_raw:
                raise ConnectionError("Domain length missing")
            length = length_raw[0]
            raw_addr = self._recv_exact(length)
            host = raw_addr.decode("idna")
        elif atyp == 0x04:  # IPv6
            raw_addr = self._recv_exact(16)
            host = socket.inet_ntop(socket.AF_INET6, raw_addr)
        else:
            raise ConnectionError("Unsupported address type")
        raw_port = self._recv_exact(2)
        if not raw_port:
            raise ConnectionError("Port missing")
        port = int.from_bytes(raw_port, "big")
        return cmd, atyp, host, port

    def _send_reply(self, rep: int, bound_host: str = "0.0.0.0", bound_port: int = 0):
        try:
            try:
                addr_bytes = socket.inet_aton(bound_host)
                atyp = 0x01
            except OSError:
                try:
                    addr_bytes = socket.inet_pton(socket.AF_INET6, bound_host)
                    atyp = 0x04
                except OSError:
                    host_bytes = bound_host.encode("idna")
                    addr_bytes = bytes([len(host_bytes)]) + host_bytes
                    atyp = 0x03
            reply = b"\x05" + bytes([rep, 0x00, atyp]) + addr_bytes + bound_port.to_bytes(2, "big")
            self.connection.sendall(reply)
        except Exception:
            pass

    def _open_socks_connection(self, host: str, port: int) -> Optional[socket.socket]:
        details: ProxyDetails = self.server.proxy_details
        scheme = details.scheme.lower()
        proxy_type = socks.SOCKS5 if "5" in scheme else socks.SOCKS4
        try:
            return socks.create_connection(
                (host, port), timeout=10, proxy_type=proxy_type,
                proxy_addr=details.host, proxy_port=details.port, proxy_rdns=True,
                proxy_username=details.username, proxy_password=details.password,
            )
        except OSError:
            return None

    def _pipe(self, upstream: socket.socket):
        client = self.connection
        client.setblocking(False)
        upstream.setblocking(False)
        sockets = [client, upstream]
        while True:
            try:
                # Keep the tunnel alive; don't drop on inactivity to avoid surprising disconnects.
                readable, _, _ = select.select(sockets, [], [], 60)
            except OSError:
                break
            if not readable:
                # Idle period: keep waiting instead of closing the connection.
                continue
            if client in readable:
                try:
                    data = client.recv(8192)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    break
                except OSError:
                    break
                if not data:
                    break
                try:
                    upstream.sendall(data)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    break
                except OSError:
                    break
            if upstream in readable:
                try:
                    data = upstream.recv(8192)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    break
                except OSError:
                    break
                if not data:
                    break
                try:
                    client.sendall(data)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    break
                except OSError:
                    break
        try:
            upstream.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        upstream.close()


class LocalSocksProxyServer:
    """
    Local SOCKS5 server without authentication that forwards through an upstream SOCKS proxy.
    """

    def __init__(self, details: ProxyDetails, profile_name: Optional[str] = None):
        self._details = details
        self._server: Optional[_ProxyTCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.port: Optional[int] = None
        self._logger = logging.LoggerAdapter(LOGGER, {"profile": profile_name or "-"})

    def start(self) -> str:
        if self._server:
            return f"socks5://127.0.0.1:{self.port}"
        try:
            self._server = _ProxyTCPServer(("127.0.0.1", 0), SocksBridgeHandler, self._details)
            self._server.logger = self._logger
            self.port = self._server.server_address[1]
        except Exception:
            raise
        self._logger.info(
            "Local proxy started on 127.0.0.1:%s (upstream %s://%s:%s)",
            self.port,
            self._details.scheme,
            self._details.host,
            self._details.port,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"socks5://127.0.0.1:{self.port}"

    def stop(self):
        if not self._server:
            return
        self._logger.info("Local proxy: stopping SOCKS bridge on 127.0.0.1:%s", self.port)
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None


def parse_proxy(proxy: str, profile_name: Optional[str] = None) -> Tuple[Optional[Dict[str, str]], Optional[ProxyDetails]]:
    """
    Convert proxy string formats into Playwright/Camoufox proxy configuration.

    Supports formats like:
    * scheme://host:port
    * scheme://host:port:user:pass
    * scheme://user:pass@host:port
    """

    if not proxy:
        return None, None

    raw = proxy.strip()
    if not raw:
        return None, None

    def _build(scheme: str, host: str, port: str, username: Optional[str], password: Optional[str]):
        display_host = f"[{host}]" if ":" in host else host
        server = f"{scheme}://{display_host}:{port}"
        cfg: Dict[str, str] = {"server": server}
        if username:
            cfg["username"] = username
        if password:
            cfg["password"] = password
        return cfg

    if "://" not in raw:
        raw = "socks5://" + raw
    if raw.split("://", 1)[0].lower() not in {"http", "https", "socks4", "socks5"}:
        return None, None
    if "@" in raw or raw.split("://", 1)[1].startswith("["):
        try:
            parsed = urlparse(raw)
            host, port = parsed.hostname, parsed.port
        except ValueError:
            return None, None
        if not host or any(character.isspace() for character in host) or port is None or not 1 <= port <= 65535:
            return None, None
        username = unquote(parsed.username) if parsed.username is not None else None
        password = unquote(parsed.password) if parsed.password is not None else None
        details = ProxyDetails(
            scheme=parsed.scheme.lower(),
            host=host,
            port=port,
            username=username,
            password=password,
        )
        return _build(details.scheme, host, str(port), username, password), details

    try:
        scheme, rest = raw.split("://", 1)
    except ValueError:
        return None, None

    parts = rest.split(":")
    if len(parts) not in (2, 4):
        return None, None

    host, port = parts[0], parts[1]
    username = parts[2] if len(parts) == 4 else None
    password = parts[3] if len(parts) == 4 else None

    if not host or any(character.isspace() for character in host) or not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        return None, None

    details = ProxyDetails(
        scheme=scheme.lower(),
        host=host,
        port=int(port),
        username=username,
        password=password,
    )
    return _build(details.scheme, host, port, username, password), details


def proxy_display_address(proxy: str) -> str:
    value = str(proxy or "").strip()
    if not value:
        return "None"
    try:
        _, details = parse_proxy(value if "://" in value else "socks5://" + value)
    except ValueError:
        return "Invalid proxy"
    if details is None:
        return "Invalid proxy"
    host = f"[{details.host}]" if ":" in details.host else details.host
    return f"{details.scheme}://{host}:{details.port}"
