"""Proxy pool management mixin."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import socket
import ssl
import threading
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QListWidgetItem, QInputDialog, QMessageBox, QMenu
from app.utils.parsing import parse_proxy_line
from app.storage.db import db_get_accounts, db_get_setting, db_set_setting, db_update_account


class ProxyPoolMixin:
    _PROXY_INTERNET_CHECK_URL = "https://ipwho.is/"

    def _invoke_ui(self, func) -> None:
        invoker = getattr(self, "_invoke_on_ui_thread", None)
        if callable(invoker):
            invoker(func)
            return
        QTimer.singleShot(0, func)

    @staticmethod
    def _probe_proxy_endpoint_value(proxy_value: str, timeout_s: float = 5.0) -> Tuple[bool, Optional[int], str, Dict[str, object]]:
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
            return False, None, "empty proxy value", {"mode": "internet", "target": ProxyPoolMixin._PROXY_INTERNET_CHECK_URL}

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
                    {"mode": "internet", "target": ProxyPoolMixin._PROXY_INTERNET_CHECK_URL},
                )

        check_url = ProxyPoolMixin._PROXY_INTERNET_CHECK_URL
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
                {"mode": "internet", "target": ProxyPoolMixin._PROXY_INTERNET_CHECK_URL},
            )

    def _load_proxy_pools(self) -> None:
        import json

        raw = db_get_setting("proxy_pools") or "{}"
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
        normalized: Dict[str, Dict[str, object]] = {}
        for name, payload in (data or {}).items():
            if not isinstance(payload, dict):
                continue
            proxies_raw = payload.get("proxies") or []
            proxies: List[Dict[str, object]] = []
            for entry in proxies_raw:
                if isinstance(entry, str):
                    proxies.append({"value": entry, "assigned_to": ""})
                elif isinstance(entry, dict):
                    val = str(entry.get("value") or entry.get("proxy") or "").strip()
                    if not val:
                        continue
                    assigned = str(entry.get("assigned_to") or "")
                    proxy_entry: Dict[str, object] = {"value": val, "assigned_to": assigned}
                    last_check = entry.get("last_check")
                    if isinstance(last_check, dict):
                        proxy_entry["last_check"] = last_check
                    proxies.append(proxy_entry)
            normalized[str(name)] = {"proxies": proxies}
        self.proxy_pools = normalized
        self._refresh_proxy_pool_views()

    def _save_proxy_pools(self) -> None:
        import json

        db_set_setting("proxy_pools", json.dumps(self.proxy_pools, ensure_ascii=False))
        self._refresh_proxy_pool_views()

    def _refresh_proxy_pool_views(self) -> None:
        self._refresh_proxy_pool_list()
        self._refresh_proxy_pool_detail()

    def _refresh_proxy_pool_list(self) -> None:
        widget = getattr(self, "proxy_pool_list", None)
        if widget is None:
            return
        widget.blockSignals(True)
        current = self._selected_proxy_pool
        widget.clear()
        for name in sorted(self.proxy_pools):
            pool = self.proxy_pools[name]
            proxies = pool.get("proxies", [])
            total = len(proxies)
            busy = sum(1 for p in proxies if p.get("assigned_to"))
            text = f"{name}  •  {total} proxies ({busy} used)"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, name)
            widget.addItem(item)
            if current == name:
                widget.setCurrentItem(item)
        widget.blockSignals(False)

    def _refresh_proxy_pool_detail(self) -> None:
        title = getattr(self, "proxy_pool_title", None)
        stats = getattr(self, "proxy_pool_stats", None)
        list_widget = getattr(self, "proxy_items_list", None)
        if list_widget is None:
            return
        list_widget.clear()
        if not self._selected_proxy_pool or self._selected_proxy_pool not in self.proxy_pools:
            if title:
                title.setText("Select a pool")
            if stats:
                stats.setText("0 proxies")
            return
        pool = self.proxy_pools[self._selected_proxy_pool]
        proxies = pool.get("proxies", [])
        if title:
            title.setText(f"Pool: {self._selected_proxy_pool}")
        if stats:
            busy = sum(1 for item in proxies if item.get("assigned_to"))
            stats.setText(f"{len(proxies)} proxies, {busy} used")
        for idx, entry in enumerate(proxies):
            proxy_value = str(entry.get("value") or "")
            assigned = str(entry.get("assigned_to") or "")
            display = proxy_value
            check_meta = entry.get("last_check") if isinstance(entry, dict) else None
            prefix = ""
            tooltip_extra = ""
            item_color: Optional[QColor] = None
            if isinstance(check_meta, dict):
                status = str(check_meta.get("status") or "")
                ms = check_meta.get("ms")
                if status == "ok":
                    prefix = "[OK]"
                    item_color = QColor("#2ecc71")
                elif status == "fail":
                    prefix = "[FAIL]"
                    item_color = QColor("#ff4d4f")
                elif status == "checking":
                    prefix = "[…]"
                mode = str(check_meta.get("mode") or "")
                if mode:
                    tooltip_extra += f"\nMode: {mode}"
                target = str(check_meta.get("target") or "")
                if target:
                    tooltip_extra += f"\nTarget: {target}"
                ip = str(check_meta.get("ip") or "")
                if ip:
                    tooltip_extra += f"\nIP: {ip}"
                country = str(check_meta.get("country") or "")
                if country:
                    tooltip_extra += f"\nCountry: {country}"
                region = str(check_meta.get("region") or "")
                city = str(check_meta.get("city") or "")
                if region or city:
                    tooltip_extra += f"\nLocation: {', '.join([p for p in [region, city] if p])}"
                timezone = str(check_meta.get("timezone") or "")
                if timezone:
                    tooltip_extra += f"\nTimezone: {timezone}"
                http_status = check_meta.get("http_status")
                if isinstance(http_status, int):
                    tooltip_extra += f"\nHTTP: {http_status}"
                if isinstance(ms, int):
                    tooltip_extra += f"\nLatency: {ms} ms"
                err = str(check_meta.get("error") or "")
                if err:
                    tooltip_extra += f"\nError: {err}"
            if prefix:
                display = f"{prefix} {display}"
            if assigned:
                display += f"  •  {assigned}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            if item_color is not None:
                item.setForeground(QBrush(item_color))
            if tooltip_extra:
                item.setToolTip(display + tooltip_extra)
            else:
                item.setToolTip(display)
            list_widget.addItem(item)

    def _current_proxy_pool(self) -> Tuple[Optional[str], Optional[Dict[str, object]]]:
        if not self._selected_proxy_pool:
            return None, None
        return self._selected_proxy_pool, self.proxy_pools.get(self._selected_proxy_pool)

    def _on_proxy_pool_selected(self) -> None:
        widget = getattr(self, "proxy_pool_list", None)
        if widget is None:
            return
        items = widget.selectedItems()
        if not items:
            self._selected_proxy_pool = None
        else:
            name = items[0].data(Qt.ItemDataRole.UserRole) or items[0].text()
            self._selected_proxy_pool = str(name)
        self._refresh_proxy_pool_detail()

    def _add_proxy_pool(self) -> None:
        name, ok = QInputDialog.getText(self, "New proxy pool", "Pool name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if name in self.proxy_pools:
            QMessageBox.warning(self, "Error", "Pool already exists")
            return
        self.proxy_pools[name] = {"proxies": []}
        self._selected_proxy_pool = name
        self._save_proxy_pools()
        self.log(f"Proxy pool {name} created")

    def _rename_proxy_pool(self) -> None:
        pool_name, pool = self._current_proxy_pool()
        if not pool_name:
            QMessageBox.warning(self, "Error", "Select a pool to rename")
            return
        new_name, ok = QInputDialog.getText(self, "Rename pool", "Pool name:", text=pool_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == pool_name:
            return
        if new_name in self.proxy_pools:
            QMessageBox.warning(self, "Error", "Pool with this name already exists")
            return
        self.proxy_pools[new_name] = pool or {"proxies": []}
        del self.proxy_pools[pool_name]
        # update account metadata referencing the pool
        for acc in db_get_accounts():
            if str(acc.get("proxy_pool") or "") == pool_name:
                db_update_account(acc.get("name"), {"proxy_pool": new_name})
        self._selected_proxy_pool = new_name
        self._save_proxy_pools()
        self.log(f"Proxy pool {pool_name} renamed to {new_name}")

    def _delete_proxy_pool(self) -> None:
        pool_name, _ = self._current_proxy_pool()
        if not pool_name:
            QMessageBox.warning(self, "Error", "Select a pool to delete")
            return
        confirm = QMessageBox.question(
            self,
            "Delete pool",
            f"Remove pool {pool_name}? Assignments will be cleared but accounts keep their proxies.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.proxy_pools.pop(pool_name, None)
        for acc in db_get_accounts():
            if str(acc.get("proxy_pool") or "") == pool_name:
                db_update_account(acc.get("name"), {"proxy_pool": ""})
        if self._selected_proxy_pool == pool_name:
            self._selected_proxy_pool = None
        self._save_proxy_pools()
        self.log(f"Proxy pool {pool_name} deleted")

    def _append_proxies_to_pool(self) -> None:
        pool_name, pool = self._current_proxy_pool()
        if not pool:
            QMessageBox.warning(self, "Error", "Select a pool to append proxies")
            return
        text_edit = getattr(self, "proxy_batch_input", None)
        if text_edit is None:
            return
        lines = [ln.strip() for ln in text_edit.toPlainText().splitlines() if ln.strip()]
        if not lines:
            return
        existing = {entry.get("value") for entry in pool.get("proxies", [])}
        added = 0
        for value in lines:
            if value in existing:
                continue
            pool.setdefault("proxies", []).append({"value": value, "assigned_to": ""})
            existing.add(value)
            added += 1
        if added:
            text_edit.clear()
            self._save_proxy_pools()
            self.log(f"Added {added} proxies to {pool_name}")
        else:
            QMessageBox.information(self, "No changes", "All proxies already exist in this pool.")

    def _proxy_entries_from_selection(self) -> List[int]:
        list_widget = getattr(self, "proxy_items_list", None)
        if list_widget is None:
            return []
        indices: List[int] = []
        for item in list_widget.selectedItems():
            idx = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(idx, int):
                indices.append(idx)
        return sorted(set(indices))

    def _check_current_pool_proxies(self, selected_only: bool = False) -> None:
        pool_name, pool = self._current_proxy_pool()
        if not pool_name or not pool:
            QMessageBox.warning(self, "Error", "Select a pool to check")
            return
        proxies = pool.get("proxies", [])
        if not isinstance(proxies, list) or not proxies:
            QMessageBox.information(self, "No proxies", "This pool has no proxies to check.")
            return

        indices = self._proxy_entries_from_selection() if selected_only else []
        if not indices:
            indices = list(range(len(proxies)))

        btn = getattr(self, "btn_check_proxies", None)
        if btn is not None:
            btn.setEnabled(False)
            btn.setText("Checking...")

        self._proxy_check_token = int(getattr(self, "_proxy_check_token", 0)) + 1
        token = self._proxy_check_token

        now = int(time.time())
        for idx in indices:
            try:
                entry = proxies[idx]
            except Exception:
                continue
            if isinstance(entry, dict):
                entry["last_check"] = {
                    "status": "checking",
                    "mode": "internet",
                    "target": self._PROXY_INTERNET_CHECK_URL,
                    "ts": now,
                }

        self._refresh_proxy_pool_detail()

        def worker() -> None:
            ok_count = 0
            fail_count = 0
            done = 0
            total = len(indices)
            last_ui_update = 0.0

            def update_ui(force: bool = False) -> None:
                nonlocal last_ui_update
                now_perf = time.perf_counter()
                if not force and (now_perf - last_ui_update) < 0.2:
                    return
                last_ui_update = now_perf

                def _apply() -> None:
                    self._refresh_proxy_pool_detail()
                    btn3 = getattr(self, "btn_check_proxies", None)
                    if btn3 is not None:
                        btn3.setText(f"Checking... {done}/{total}")

                self._invoke_ui(_apply)

            def probe_one(entry_value: str) -> Tuple[bool, Optional[int], str, Dict[str, object]]:
                try:
                    return self._probe_proxy_endpoint_value(entry_value)
                except Exception as exc:
                    return (
                        False,
                        None,
                        str(exc),
                        {"mode": "internet", "target": self._PROXY_INTERNET_CHECK_URL},
                    )

            tasks: List[Tuple[int, str]] = []
            for idx in indices:
                try:
                    entry = proxies[idx]
                except Exception:
                    continue
                if not isinstance(entry, dict):
                    continue
                tasks.append((idx, str(entry.get("value") or "")))

            max_workers = min(12, max(1, len(tasks)))
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                future_map = {ex.submit(probe_one, value): idx for idx, value in tasks}
                for fut in as_completed(future_map):
                    idx = future_map.get(fut)
                    try:
                        ok, ms, error, meta = fut.result()
                    except Exception as exc:
                        ok, ms, error, meta = False, None, str(exc), {"mode": "internet", "target": self._PROXY_INTERNET_CHECK_URL}

                    if isinstance(idx, int):
                        try:
                            entry = proxies[idx]
                        except Exception:
                            entry = None
                        if isinstance(entry, dict):
                            result: Dict[str, object] = {
                                "status": "ok" if ok else "fail",
                                "mode": "internet",
                                "target": self._PROXY_INTERNET_CHECK_URL,
                                "ms": ms,
                                "error": error,
                                "ts": int(time.time()),
                            }
                            if isinstance(meta, dict):
                                result.update(meta)
                            entry["last_check"] = result

                    done += 1
                    if ok:
                        ok_count += 1
                    else:
                        fail_count += 1
                    update_ui()
            update_ui(force=True)

            def finish() -> None:
                self._save_proxy_pools()
                total_checked = ok_count + fail_count
                self.log(
                    f"Proxy internet check finished for {pool_name}: "
                    f"{ok_count} OK, {fail_count} failed (total {total_checked})"
                )
                btn2 = getattr(self, "btn_check_proxies", None)
                if btn2 is not None:
                    btn2.setEnabled(True)
                    btn2.setText(f"Done: {ok_count} OK, {fail_count} FAIL")

                    def reset_label() -> None:
                        if getattr(self, "_proxy_check_token", None) != token:
                            return
                        btn3 = getattr(self, "btn_check_proxies", None)
                        if btn3 is not None and btn3.isEnabled():
                            btn3.setText("Check internet")

                    QTimer.singleShot(2000, reset_label)

            self._invoke_ui(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _release_selected_pool_proxies(self) -> None:
        pool_name, pool = self._current_proxy_pool()
        if not pool:
            return
        indices = self._proxy_entries_from_selection()
        if not indices:
            return
        changed = 0
        for idx in indices:
            try:
                entry = pool["proxies"][idx]
            except Exception:
                continue
            assigned = str(entry.get("assigned_to") or "")
            if assigned:
                self._clear_account_proxy_fields(assigned)
            entry["assigned_to"] = ""
            changed += 1
        if changed:
            self._save_proxy_pools()
            self.log(f"Released {changed} proxies in {pool_name}")

    def _remove_selected_pool_proxies(self) -> None:
        pool_name, pool = self._current_proxy_pool()
        if not pool:
            return
        indices = self._proxy_entries_from_selection()
        if not indices:
            return
        for idx in reversed(indices):
            try:
                entry = pool["proxies"].pop(idx)
                assigned = str(entry.get("assigned_to") or "")
                if assigned:
                    self._clear_account_proxy_fields(assigned)
            except Exception:
                continue
        self._save_proxy_pools()
        self.log(f"Removed {len(indices)} proxies from {pool_name}")

    def _show_proxy_context_menu(self, pos) -> None:
        list_widget = getattr(self, "proxy_items_list", None)
        if list_widget is None:
            return
        if not list_widget.itemAt(pos):
            return
        menu = QMenu(self)
        act_check = menu.addAction("Check internet")
        act_release = menu.addAction("Release")
        act_remove = menu.addAction("Remove")
        chosen = menu.exec(list_widget.mapToGlobal(pos))
        if chosen == act_check:
            self._check_current_pool_proxies(selected_only=True)
            return
        if chosen == act_release:
            self._release_selected_pool_proxies()
        elif chosen == act_remove:
            self._remove_selected_pool_proxies()

    def _available_proxy_count(self, pool_name: Optional[str]) -> int:
        if not pool_name:
            return 0
        pool = self.proxy_pools.get(pool_name)
        if not pool:
            return 0
        return sum(1 for entry in pool.get("proxies", []) if not entry.get("assigned_to"))

    def _claim_proxy_from_pool(self, pool_name: str, account_name: str) -> Optional[str]:
        pool = self.proxy_pools.get(pool_name)
        if not pool:
            return None
        for entry in pool.get("proxies", []):
            if not entry.get("assigned_to"):
                entry["assigned_to"] = account_name
                value = str(entry.get("value") or "")
                self._save_proxy_pools()
                return value
        return None

    def _clear_account_proxy_fields(self, account_name: str) -> None:
        if not account_name:
            return
        try:
            db_update_account(
                account_name,
                {
                    "proxy_host": "",
                    "proxy_port": None,
                    "proxy_user": "",
                    "proxy_password": "",
                    "proxy_pool": "",
                    "proxy_pool_value": "",
                },
            )
        except Exception:
            pass

    def _assign_proxy_to_account_from_pool(self, account_name: str, pool_name: str) -> bool:
        proxy_value = self._claim_proxy_from_pool(pool_name, account_name)
        if not proxy_value:
            return False
        try:
            host, port, user, password = parse_proxy_line(proxy_value)
        except ValueError as exc:
            QMessageBox.warning(self, "Proxy error", f"{exc}\nValue:\n{proxy_value}")
            self._release_proxy_for_account(account_name)
            return False
        db_update_account(
            account_name,
            {
                "proxy_host": host,
                "proxy_port": port,
                "proxy_user": user,
                "proxy_password": password,
                "proxy_pool": pool_name,
                "proxy_pool_value": proxy_value,
            },
        )
        return True

    def _release_proxy_for_account(self, account_name: str) -> None:
        if not account_name:
            return
        changed = False
        for pool in self.proxy_pools.values():
            for entry in pool.get("proxies", []):
                if str(entry.get("assigned_to") or "") == account_name:
                    entry["assigned_to"] = ""
                    changed = True
        if changed:
            self._save_proxy_pools()

    def _remove_proxy_for_account(self, account_name: str) -> bool:
        if not account_name:
            return True
        removed = 0
        for pool in self.proxy_pools.values():
            proxies = pool.get("proxies", [])
            if not isinstance(proxies, list) or not proxies:
                continue
            keep: List[Dict[str, object]] = []
            for entry in proxies:
                if str(entry.get("assigned_to") or "") == account_name:
                    removed += 1
                else:
                    keep.append(entry)
            pool["proxies"] = keep
        if removed:
            try:
                self._save_proxy_pools()
            except Exception as exc:
                self._load_proxy_pools()
                QMessageBox.warning(self, "Error", f"Cannot save proxy pools: {exc}")
                return False
        return True

    def _rename_proxy_assignment(self, old_name: str, new_name: str) -> None:
        if not old_name or not new_name or old_name == new_name:
            return
        changed = False
        for pool in self.proxy_pools.values():
            for entry in pool.get("proxies", []):
                if str(entry.get("assigned_to") or "") == old_name:
                    entry["assigned_to"] = new_name
                    changed = True
        if changed:
            self._save_proxy_pools()

    def _proxy_string_for(self, acc: Dict[str, object]) -> str:
        host = acc.get("proxy_host")
        port = acc.get("proxy_port")
        user = acc.get("proxy_user")
        pwd = acc.get("proxy_password")
        if host and port:
            if user and pwd:
                return f"socks5://{host}:{port}:{user}:{pwd}"
            return f"socks5://{host}:{port}"
        return ""
