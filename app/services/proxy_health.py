from __future__ import annotations

import base64
import json
import re
import socket
import ssl
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from app.utils.parsing import parse_proxy_line

PROXY_INTERNET_CHECK_URL = "https://ipwho.is/"


def probe_proxy_endpoint(proxy_value: str, timeout_s: float = 5.0) -> Tuple[bool, Optional[int], str, Dict[str, object]]:
    """
    Checks that the proxy can actually reach the internet by querying a geo-IP JSON endpoint
    (default: https://ipwho.is/).

    Returns: (ok, latency_ms, error_text, meta).
    """

    def _recv_until(sock_obj: socket.socket, marker: bytes, limit: int) -> bytes:
        buf = b""
        while marker not in buf and len(buf) < limit:
            chunk = sock_obj.recv(8192)
            if not chunk:
                break
            buf += chunk
        return buf

    def _read_http_response(sock_obj: socket.socket) -> Tuple[Optional[int], Dict[str, str], bytes, str]:
        head = _recv_until(sock_obj, b"\r\n\r\n", 256 * 1024)
        if b"\r\n\r\n" not in head:
            return None, {}, b"", "invalid response headers"
        header_raw, remainder = head.split(b"\r\n\r\n", 1)
        lines = header_raw.split(b"\r\n")
        if not lines:
            return None, {}, b"", "empty response"
        first = lines[0].decode("iso-8859-1", errors="replace").strip()
        match = re.match(r"^HTTP/\d\.\d\s+(\d{3})\b", first)
        if not match:
            return None, {}, b"", f"invalid response: {first[:120]}"
        status = int(match.group(1))
        headers: Dict[str, str] = {}
        for raw_line in lines[1:]:
            line = raw_line.decode("iso-8859-1", errors="replace")
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

        body = b""
        if "content-length" in headers:
            try:
                need = int(headers["content-length"])
            except Exception:
                need = None
            if isinstance(need, int) and need >= 0:
                body = remainder
                while len(body) < need and len(body) < 2 * 1024 * 1024:
                    chunk = sock_obj.recv(min(8192, need - len(body)))
                    if not chunk:
                        break
                    body += chunk
                body = body[:need]
                return status, headers, body, ""

        # Transfer-Encoding: chunked
        if "transfer-encoding" in headers and "chunked" in headers["transfer-encoding"].lower():
            data = remainder
            out = b""
            while len(out) < 2 * 1024 * 1024:
                # Ensure we have a full chunk-size line
                while b"\r\n" not in data and len(data) < 256 * 1024:
                    chunk = sock_obj.recv(8192)
                    if not chunk:
                        break
                    data += chunk
                if b"\r\n" not in data:
                    break
                size_line, data = data.split(b"\r\n", 1)
                size_str = size_line.split(b";", 1)[0].decode("ascii", errors="replace").strip()
                try:
                    size = int(size_str, 16)
                except Exception:
                    break
                if size == 0:
                    return status, headers, out, ""
                while len(data) < size + 2 and len(data) < 2 * 1024 * 1024:
                    chunk = sock_obj.recv(8192)
                    if not chunk:
                        break
                    data += chunk
                if len(data) < size + 2:
                    break
                out += data[:size]
                data = data[size + 2 :]  # skip data + CRLF
            return status, headers, out, ""

        # Fallback: read until close (bounded).
        body = remainder
        while len(body) < 2 * 1024 * 1024:
            chunk = sock_obj.recv(8192)
            if not chunk:
                break
            body += chunk
        return status, headers, body, ""

    def _json_ok(payload: Dict[str, object]) -> bool:
        # ipwho.is -> {"success": true, ...}
        if isinstance(payload.get("success"), bool):
            return bool(payload.get("success"))
        # ip-api -> {"status":"success", ...}
        status = payload.get("status")
        if isinstance(status, str):
            return status.lower() == "success"
        return True

    def _open_tls(sock_obj: socket.socket, server_hostname: str) -> ssl.SSLSocket:
        ctx = ssl.create_default_context()
        return ctx.wrap_socket(sock_obj, server_hostname=server_hostname)

    def _proxy_connect_http(
        proxy_host: str,
        proxy_port: int,
        target_host: str,
        target_port: int,
        user: str,
        password: str,
    ) -> Tuple[Optional[socket.socket], str]:
        try:
            sock_obj = socket.create_connection((proxy_host, proxy_port), timeout=timeout_s)
            sock_obj.settimeout(timeout_s)
        except OSError as exc:
            return None, str(exc)

        auth_line = ""
        if user:
            token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
            auth_line = f"Proxy-Authorization: Basic {token}\r\n"
        req = (
            f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            f"Host: {target_host}:{target_port}\r\n"
            f"{auth_line}"
            "Connection: close\r\n"
            "\r\n"
        )
        try:
            sock_obj.sendall(req.encode("iso-8859-1", errors="replace"))
            status, _, _, err = _read_http_response(sock_obj)
        except OSError as exc:
            try:
                sock_obj.close()
            except Exception:
                pass
            return None, str(exc)
        if status != 200:
            try:
                sock_obj.close()
            except Exception:
                pass
            return None, err or (f"connect failed (http status {status})" if status else "connect failed")
        return sock_obj, ""

    raw = str(proxy_value or "").strip()
    if not raw:
        return False, None, "empty proxy value", {"mode": "internet", "target": PROXY_INTERNET_CHECK_URL}

    scheme = "socks5"
    if "://" in raw:
        scheme_part, raw = raw.split("://", 1)
        scheme = (scheme_part or "").strip().lower() or "socks5"

    user = ""
    password = ""
    if "@" in raw:
        auth_part, raw = raw.rsplit("@", 1)
        if ":" in auth_part:
            user, password = auth_part.split(":", 1)
        else:
            user = auth_part

    try:
        parts = [p.strip() for p in raw.split(":") if p.strip()]
        if len(parts) < 2:
            raise ValueError("expected host:port")
        host = parts[0]
        port = int(parts[1])
        if not user and len(parts) >= 4:
            user = parts[2]
            password = parts[3]
    except Exception:
        try:
            host, port, user, password = parse_proxy_line(proxy_value)
        except Exception as exc:
            return (
                False,
                None,
                f"invalid proxy format: {exc}",
                {"mode": "internet", "target": PROXY_INTERNET_CHECK_URL},
            )

    check_url = PROXY_INTERNET_CHECK_URL
    parsed = urlparse(check_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False, None, f"unsupported check url: {check_url}", {"mode": "internet", "target": check_url}
    target_host = parsed.hostname
    target_port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    target_path = parsed.path or "/"
    if parsed.query:
        target_path += "?" + parsed.query

    start = time.perf_counter()
    try:
        meta: Dict[str, object] = {"mode": "internet", "target": check_url}
        scheme_l = (scheme or "socks5").lower()
        if scheme_l.startswith("socks"):
            try:
                import socks  # type: ignore
            except Exception as exc:
                ms = int((time.perf_counter() - start) * 1000)
                return False, ms, f"missing PySocks dependency: {exc}", meta
            proxy_type = socks.SOCKS5 if "5" in scheme_l else socks.SOCKS4
            sock_obj = socks.socksocket()
            sock_obj.set_proxy(
                proxy_type,
                host,
                port,
                True,
                user or None,
                password or None,
            )
            sock_obj.settimeout(timeout_s)
            sock_obj.connect((target_host, target_port))
            if parsed.scheme.lower() == "https":
                sock_obj = _open_tls(sock_obj, target_host)
            request_target = target_path
        elif scheme_l in {"http", "https"}:
            if parsed.scheme.lower() == "https":
                sock_obj, err = _proxy_connect_http(host, port, target_host, target_port, user, password)
                if not sock_obj:
                    ms = int((time.perf_counter() - start) * 1000)
                    return False, ms, err or "CONNECT failed", meta
                sock_obj = _open_tls(sock_obj, target_host)
                request_target = target_path
            else:
                sock_obj = socket.create_connection((host, port), timeout=timeout_s)
                sock_obj.settimeout(timeout_s)
                request_target = check_url
        else:
            ms = int((time.perf_counter() - start) * 1000)
            return False, ms, f"unsupported proxy scheme: {scheme_l}", meta

        headers = [
            f"Host: {target_host}",
            "User-Agent: AlmazProxyCheck/1.0",
            "Accept: application/json",
            "Connection: close",
        ]
        req = "GET " + request_target + " HTTP/1.1\r\n" + "\r\n".join(headers) + "\r\n\r\n"
        sock_obj.sendall(req.encode("iso-8859-1", errors="replace"))
        status, _, body, status_err = _read_http_response(sock_obj)
        try:
            sock_obj.close()
        except Exception:
            pass

        ms = int((time.perf_counter() - start) * 1000)
        if status is None:
            return False, ms, status_err, meta
        meta["http_status"] = int(status)
        if not (200 <= status < 400):
            return False, ms, f"http status {status}", meta
        try:
            payload = json.loads(body.decode("utf-8", errors="replace") or "{}")
        except Exception as exc:
            return False, ms, f"invalid json: {exc}", meta
        if isinstance(payload, dict) and not _json_ok(payload):
            msg = payload.get("message") if isinstance(payload.get("message"), str) else payload.get("error")
            return False, ms, str(msg or "geo lookup failed"), meta

        if isinstance(payload, dict):
            ip = payload.get("ip") or payload.get("query")
            country = payload.get("country")
            city = payload.get("city")
            timezone = payload.get("timezone")
            if isinstance(timezone, dict):
                timezone = timezone.get("id") or timezone.get("name")
            region = payload.get("region") or payload.get("regionName")
            if isinstance(ip, str) and ip:
                meta["ip"] = ip
            if isinstance(country, str) and country:
                meta["country"] = country
            if isinstance(region, str) and region:
                meta["region"] = region
            if isinstance(city, str) and city:
                meta["city"] = city
            if isinstance(timezone, str) and timezone:
                meta["timezone"] = timezone
        return True, ms, "", meta
    except OSError as exc:
        ms = int((time.perf_counter() - start) * 1000)
        return (
            False,
            ms,
            str(exc),
            {"mode": "internet", "target": PROXY_INTERNET_CHECK_URL},
        )

