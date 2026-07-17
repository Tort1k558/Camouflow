"""Proxy pools bridge for QML."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.storage.db import db_get_setting, db_set_setting
from app.services.server_client import ServerClient, ServerClientError, server_enabled
from app.ui.bridge.cloud_permissions import allows, deny_message
from app.ui.bridge.models import DictListModel


class ProxiesBridge(QObject):
    modelChanged = pyqtSignal()
    statsChanged = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._model = DictListModel(["pool", "name", "location", "address", "type", "latency", "status", "accent", "index", "selected"], parent=self)
        self._pools_model = DictListModel(["name", "total", "used", "selected"], parent=self)
        self._selected_pool = ""
        self._selected: set[tuple[str, int]] = set()
        self._active = 0
        self._checking = 0
        self._failed = 0
        self._locations = 0
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)
            app_state.cloudChanged.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _record_check(entry: Dict[str, Any], result: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        error_text = str(result.get("error") or "").lower()
        if str(result.get("status") or "") != "ok":
            if "auth" in error_text or "407" in error_text:
                result["failure_type"] = "auth_failed"
            elif "timeout" in error_text or "timed out" in error_text:
                result["failure_type"] = "connect_timeout"
            elif "block" in error_text or "forbidden" in error_text or "403" in error_text:
                result["failure_type"] = "blocked"
            elif "geo" in error_text or "country mismatch" in error_text or "location mismatch" in error_text:
                result["failure_type"] = "geo_mismatch"
            else:
                result["failure_type"] = "connection_failed"
        history = entry.get("check_history") if isinstance(entry.get("check_history"), list) else []
        record = {
            "checked_at": now.isoformat(),
            "status": str(result.get("status") or "fail"),
            "ms": result.get("ms"),
            "ip": str(result.get("ip") or ""),
            "country": str(result.get("country") or ""),
            "error": str(result.get("error") or ""),
            "failure_type": str(result.get("failure_type") or ""),
        }
        history.append(record)
        history = history[-20:]
        failures = 0
        for item in reversed(history):
            if str(item.get("status") or "") == "ok":
                break
            failures += 1
        entry["check_history"] = history
        entry["health_score"] = round(sum(1 for item in history if str(item.get("status") or "") == "ok") / len(history) * 100) if history else 0
        if failures >= 3:
            entry["quarantine_until"] = (now + timedelta(minutes=min(60, 5 * (2 ** (failures - 3))))).isoformat()
        elif str(result.get("status") or "") == "ok":
            entry.pop("quarantine_until", None)
        entry["last_check"] = result

    @staticmethod
    def _is_quarantined(entry: Dict[str, Any]) -> bool:
        try:
            return datetime.fromisoformat(str(entry.get("quarantine_until") or "").replace("Z", "+00:00")) > datetime.now(timezone.utc)
        except ValueError:
            return False

    @pyqtProperty(QObject, constant=True)
    def model(self) -> QObject:
        return self._model

    @pyqtProperty(QObject, constant=True)
    def poolsModel(self) -> QObject:  # noqa: N802
        return self._pools_model

    @pyqtProperty(str, notify=modelChanged)
    def selectedPool(self) -> str:  # noqa: N802
        return self._selected_pool

    @pyqtProperty(int, notify=statsChanged)
    def active(self) -> int:
        return self._active

    @pyqtProperty(int, notify=statsChanged)
    def checking(self) -> int:
        return self._checking

    @pyqtProperty(int, notify=statsChanged)
    def failed(self) -> int:
        return self._failed

    @pyqtProperty(int, notify=statsChanged)
    def locations(self) -> int:
        return self._locations

    @pyqtProperty(bool, notify=modelChanged)
    def canRun(self) -> bool:  # noqa: N802
        return allows(self._app_state, "operator")

    @pyqtProperty(bool, notify=modelChanged)
    def canManage(self) -> bool:  # noqa: N802
        return allows(self._app_state, "manager")

    @pyqtProperty(bool, notify=modelChanged)
    def canAdmin(self) -> bool:  # noqa: N802
        return allows(self._app_state, "admin")

    def _ensure_allowed(self, min_role: str) -> bool:
        if allows(self._app_state, min_role):
            return True
        self._emit_message(deny_message(min_role))
        return False

    def _load(self) -> Dict[str, Dict[str, Any]]:
        client = self._server_client()
        if server_enabled() and client:
            pools: Dict[str, Dict[str, Any]] = {}
            try:
                proxies = client.proxies()
            except ServerClientError as exc:
                self._emit_message(f"Server proxies error: {exc}")
                return {}
            for proxy in proxies:
                group = str(proxy.get("group_name") or "Default")
                check = proxy.get("last_check") if isinstance(proxy.get("last_check"), dict) else {}
                if not check:
                    check = {"status": proxy.get("status") or "active", "country": proxy.get("country") or ""}
                pools.setdefault(group, {"proxies": []})["proxies"].append({
                    "id": str(proxy.get("id") or ""),
                    "name": str(proxy.get("name") or ""),
                    "value": str(proxy.get("value") or ""),
                    "assigned_to": str(proxy.get("assigned_profile_id") or ""),
                    "last_check": check,
                })
            return pools
        try:
            data = json.loads(db_get_setting("proxy_pools") or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self, pools: Dict[str, Dict[str, Any]]) -> None:
        if server_enabled() and self._server_client():
            return
        db_set_setting("proxy_pools", json.dumps(pools, ensure_ascii=False))

    def _server_client(self):
        client = ServerClient()
        return client if client.configured else None

    def _server_proxy_entry(self, pool_name: str, index: int) -> Dict[str, Any]:
        try:
            index = int(index)
        except Exception:
            return {}
        pool = self._load().get(str(pool_name or "").strip())
        proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
        if 0 <= index < len(proxies) and isinstance(proxies[index], dict):
            return proxies[index]
        return {}

    def _emit_message(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    @pyqtSlot()
    def refresh(self) -> None:
        pools = self._load()
        pool_rows: List[Dict[str, Any]] = []
        total_all = 0
        used_all = 0
        for pool_name, pool in sorted(pools.items()):
            proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
            total = len(proxies)
            used = sum(1 for item in proxies if isinstance(item, dict) and item.get("assigned_to"))
            total_all += total
            used_all += used
            pool_rows.append({"name": pool_name, "total": total, "used": used, "selected": self._selected_pool == pool_name})
        self._pools_model.set_rows(
            [{"name": "All pools", "total": total_all, "used": used_all, "selected": not self._selected_pool}]
            + pool_rows
        )
        rows: List[Dict[str, Any]] = []
        active = checking = failed = 0
        locations = set()
        for pool_name, pool in sorted(pools.items()):
            if self._selected_pool and pool_name != self._selected_pool:
                continue
            for pool_index, entry in enumerate(pool.get("proxies", []) if isinstance(pool, dict) else []):
                value = entry.get("value") if isinstance(entry, dict) else str(entry)
                value = str(value or "").strip()
                if not value:
                    continue
                check = entry.get("last_check") if isinstance(entry, dict) else {}
                status_raw = str(check.get("status") or "active").lower() if isinstance(check, dict) else "active"
                quarantined = isinstance(entry, dict) and self._is_quarantined(entry)
                status = "Quarantined" if quarantined else ("Active" if status_raw in {"ok", "active"} else "Checking" if status_raw == "checking" else "Failed")
                if status == "Active":
                    active += 1
                elif status == "Checking":
                    checking += 1
                else:
                    failed += 1
                country = str(check.get("country") or "") if isinstance(check, dict) else ""
                city = str(check.get("city") or "") if isinstance(check, dict) else ""
                location = ", ".join(p for p in [city, country] if p) or pool_name
                locations.add(location)
                type_label = "SOCKS5" if "socks" in value.lower() else "HTTP"
                latency = check.get("ms") if isinstance(check, dict) else None
                rows.append({
                    "pool": pool_name,
                    "name": str(entry.get("name") or f"{pool_name}-{pool_index + 1:02d}") if isinstance(entry, dict) else f"{pool_name}-{pool_index + 1:02d}",
                    "location": location,
                    "address": value,
                    "type": type_label,
                    "latency": f"{latency}ms" if isinstance(latency, int) else "?",
                    "status": status,
                    "accent": "#06b6d4" if status == "Active" else "#f59e0b" if status in {"Checking", "Quarantined"} else "#ef4444",
                    "index": pool_index,
                    "selected": (pool_name, pool_index) in self._selected,
                })
        self._active, self._checking, self._failed, self._locations = active, checking, failed, len(locations)
        self._model.set_rows(rows)
        self.modelChanged.emit()
        self.statsChanged.emit()

    @pyqtSlot(str)
    def selectPool(self, name: str) -> None:  # noqa: N802
        name = str(name or "")
        self._selected_pool = "" if name == "All pools" else name
        self._selected.clear()
        self.refresh()


    @pyqtSlot(str)
    def createPool(self, name: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        name = str(name or "").strip()
        if not name:
            self._emit_message("Pool name is empty")
            return
        if server_enabled() and self._server_client():
            self._selected_pool = name
            self._emit_message(f"Server proxy group {name} selected")
            self.refresh()
            return
        pools = self._load()
        if name in pools:
            self._emit_message("Proxy pool already exists")
            return
        pools[name] = {"proxies": []}
        self._selected_pool = name
        self._save(pools)
        self._emit_message(f"Proxy pool {name} created")
        self.refresh()

    @pyqtSlot(str)
    def renameSelectedPool(self, name: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        old_name = self._selected_pool
        new_name = str(name or "").strip()
        if not old_name:
            self._emit_message("Select proxy pool first")
            return
        if not new_name or new_name == old_name:
            return
        client = self._server_client()
        if server_enabled() and client:
            try:
                for entry in self._load().get(old_name, {}).get("proxies", []):
                    if isinstance(entry, dict) and entry.get("id"):
                        client.update_proxy(str(entry["id"]), {"group_name": new_name})
            except ServerClientError as exc:
                self._emit_message(f"Cannot rename server group: {exc}")
                return
            self._selected_pool = new_name
            self._emit_message(f"Server proxy group renamed to {new_name}")
            self.refresh()
            return
        pools = self._load()
        if old_name not in pools:
            self._emit_message("Selected proxy pool not found")
            return
        if new_name in pools:
            self._emit_message("Proxy pool already exists")
            return
        pools[new_name] = pools.pop(old_name)
        self._selected_pool = new_name
        self._save(pools)
        self._emit_message(f"Proxy pool renamed to {new_name}")
        self.refresh()

    @pyqtSlot()
    def deleteSelectedPool(self) -> None:  # noqa: N802
        if not self._ensure_allowed("admin"):
            return
        name = self._selected_pool
        if not name:
            self._emit_message("Select proxy pool first")
            return
        client = self._server_client()
        if server_enabled() and client:
            try:
                for entry in list(self._load().get(name, {}).get("proxies", [])):
                    if isinstance(entry, dict) and entry.get("id"):
                        client.delete_proxy(str(entry["id"]))
            except ServerClientError as exc:
                self._emit_message(f"Cannot delete server group: {exc}")
                return
            self._selected_pool = ""
            self._emit_message(f"Server proxy group {name} deleted")
            self.refresh()
            return
        pools = self._load()
        if name not in pools:
            return
        pools.pop(name, None)
        self._selected_pool = ""
        self._save(pools)
        self._emit_message(f"Proxy pool {name} deleted")
        self.refresh()

    @pyqtSlot(str)
    def addProxies(self, values: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        lines = [line.strip() for line in str(values or "").replace("\r", "\n").split("\n") if line.strip()]
        if not lines:
            self._emit_message("Proxy list is empty")
            return
        client = self._server_client()
        if server_enabled() and client:
            pool_name = self._selected_pool or "Default"
            added = 0
            for value in lines:
                try:
                    client.create_proxy({"value": value, "group_name": pool_name})
                    added += 1
                except ServerClientError as exc:
                    self._emit_message(f"Cannot add server proxy: {exc}")
                    break
            self._selected_pool = pool_name
            self._emit_message(f"Added {added} server proxies to {pool_name}")
            self.refresh()
            return
        pools = self._load()
        pool_name = self._selected_pool or "Default"
        pool = pools.setdefault(pool_name, {"proxies": []})
        proxies = pool.setdefault("proxies", [])
        existing = {str(item.get("value") or "") for item in proxies if isinstance(item, dict)}
        added = 0
        for value in lines:
            if value in existing:
                continue
            proxies.append({"value": value, "assigned_to": ""})
            existing.add(value)
            added += 1
        self._selected_pool = pool_name
        self._save(pools)
        self._emit_message(f"Added {added} proxies to {pool_name}")
        self.refresh()

    @pyqtSlot(str)
    def addProxy(self, value: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        value = str(value or "").strip()
        if not value:
            self._emit_message("Proxy value is empty")
            return
        client = self._server_client()
        if server_enabled() and client:
            try:
                client.create_proxy({"value": value, "group_name": self._selected_pool or "Default"})
            except ServerClientError as exc:
                self._emit_message(f"Cannot add server proxy: {exc}")
                return
            self._emit_message("Server proxy added")
            self.refresh()
            return
        pools = self._load()
        pool_name = self._selected_pool or "Default"
        pool = pools.setdefault(pool_name, {"proxies": []})
        proxies = pool.setdefault("proxies", [])
        proxies.append({"value": value, "assigned_to": ""})
        self._save(pools)
        self._emit_message("Proxy added")
        self.refresh()

    @pyqtSlot(str, int, result="QVariant")
    def getProxy(self, pool_name: str, index: int) -> Dict[str, Any]:  # noqa: N802
        pool_name = str(pool_name or "").strip()
        try:
            index = int(index)
        except Exception:
            return {}
        pool = self._load().get(pool_name)
        if not isinstance(pool, dict):
            return {}
        proxies = pool.get("proxies", [])
        if not (0 <= index < len(proxies)) or not isinstance(proxies[index], dict):
            return {}
        entry = proxies[index]
        return {
            "pool": pool_name,
            "index": index,
            "name": str(entry.get("name") or ""),
            "value": str(entry.get("value") or ""),
            "assigned_to": str(entry.get("assigned_to") or ""),
        }

    @pyqtSlot(str, int, str, str)
    def saveProxy(self, pool_name: str, index: int, name: str, value: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        pool_name = str(pool_name or "").strip()
        value = str(value or "").strip()
        if not value:
            self._emit_message("Proxy value is empty")
            return
        try:
            index = int(index)
        except Exception:
            self._emit_message("Proxy not found")
            return
        client = self._server_client()
        if server_enabled() and client:
            entry = self._server_proxy_entry(pool_name, index)
            if not entry or not entry.get("id"):
                self._emit_message("Proxy not found")
                return
            try:
                client.update_proxy(str(entry["id"]), {"name": str(name or "").strip(), "value": value, "group_name": pool_name})
            except ServerClientError as exc:
                self._emit_message(f"Cannot save server proxy: {exc}")
                return
            self._emit_message("Server proxy saved")
            self.refresh()
            return
        pools = self._load()
        pool = pools.get(pool_name)
        if not isinstance(pool, dict):
            self._emit_message("Proxy pool not found")
            return
        proxies = pool.get("proxies", [])
        if not (0 <= index < len(proxies)) or not isinstance(proxies[index], dict):
            self._emit_message("Proxy not found")
            return
        proxies[index]["name"] = str(name or "").strip()
        proxies[index]["value"] = value
        self._save(pools)
        self._emit_message("Proxy saved")
        self.refresh()

    @pyqtSlot(str, int)
    def deleteProxy(self, pool_name: str, index: int) -> None:  # noqa: N802
        if not self._ensure_allowed("admin"):
            return
        pool_name = str(pool_name or "").strip()
        try:
            index = int(index)
        except Exception:
            return
        client = self._server_client()
        if server_enabled() and client:
            entry = self._server_proxy_entry(pool_name, index)
            if not entry or not entry.get("id"):
                return
            try:
                client.delete_proxy(str(entry["id"]))
            except ServerClientError as exc:
                self._emit_message(f"Cannot delete server proxy: {exc}")
                return
            self._emit_message("Server proxy deleted")
            self.refresh()
            return
        pools = self._load()
        pool = pools.get(pool_name)
        proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
        if not (0 <= index < len(proxies)):
            return
        proxies.pop(index)
        self._selected = {
            (p, i if p != pool_name or i < index else i - 1)
            for p, i in self._selected
            if not (p == pool_name and i == index)
        }
        self._save(pools)
        self._emit_message("Proxy deleted")
        self.refresh()

    @pyqtSlot(str, int, bool)
    def setProxySelected(self, pool_name: str, index: int, selected: bool) -> None:  # noqa: N802
        key = (str(pool_name or "").strip(), int(index))
        if selected:
            self._selected.add(key)
        else:
            self._selected.discard(key)
        self.refresh()

    @pyqtSlot()
    def clearSelection(self) -> None:  # noqa: N802
        self._selected.clear()
        self.refresh()

    @pyqtSlot()
    def releaseSelected(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        if not self._selected:
            self._emit_message("No selected proxies")
            return
        client = self._server_client()
        if server_enabled() and client:
            released = 0
            for pool_name, index in list(self._selected):
                entry = self._server_proxy_entry(pool_name, index)
                if entry and entry.get("id"):
                    try:
                        client.update_proxy(str(entry["id"]), {"assigned_profile_id": ""})
                        released += 1
                    except ServerClientError:
                        pass
            self._selected.clear()
            self._emit_message(f"Released {released} server proxy(s)")
            self.refresh()
            return
        pools = self._load()
        released = 0
        assigned_names: set[str] = set()
        for pool_name, index in list(self._selected):
            proxies = pools.get(pool_name, {}).get("proxies", []) if isinstance(pools.get(pool_name), dict) else []
            if 0 <= index < len(proxies) and isinstance(proxies[index], dict):
                assigned = str(proxies[index].get("assigned_to") or "").strip()
                if assigned:
                    assigned_names.add(assigned)
                proxies[index]["assigned_to"] = ""
                released += 1
        self._save(pools)
        if assigned_names:
            try:
                from app.storage.db import db_get_accounts, db_update_account

                for acc in db_get_accounts():
                    name = str(acc.get("name") or "")
                    if name in assigned_names:
                        db_update_account(name, {
                            "proxy_host": "",
                            "proxy_port": None,
                            "proxy_user": "",
                            "proxy_password": "",
                            "proxy_scheme": "",
                            "proxy_pool": "",
                        })
            except Exception:
                pass
        self._emit_message(f"Released {released} proxy(s)")
        self.refresh()

    @pyqtSlot()
    def removeSelected(self) -> None:  # noqa: N802
        if not self._ensure_allowed("admin"):
            return
        if not self._selected:
            self._emit_message("No selected proxies")
            return
        client = self._server_client()
        if server_enabled() and client:
            removed = 0
            for pool_name, index in list(self._selected):
                entry = self._server_proxy_entry(pool_name, index)
                if entry and entry.get("id"):
                    try:
                        client.delete_proxy(str(entry["id"]))
                        removed += 1
                    except ServerClientError:
                        pass
            self._selected.clear()
            self._emit_message(f"Removed {removed} server proxy(s)")
            self.refresh()
            return
        pools = self._load()
        removed = 0
        for pool_name in sorted({pool for pool, _ in self._selected}):
            pool = pools.get(pool_name)
            proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
            indices = sorted([idx for pool, idx in self._selected if pool == pool_name], reverse=True)
            for index in indices:
                if 0 <= index < len(proxies):
                    proxies.pop(index)
                    removed += 1
        self._selected.clear()
        self._save(pools)
        self._emit_message(f"Removed {removed} proxy(s)")
        self.refresh()


    @pyqtSlot(str, int)
    def checkProxy(self, pool_name: str, index: int) -> None:  # noqa: N802
        if not self._ensure_allowed("operator"):
            return
        pool_name = str(pool_name or "").strip()
        index = int(index)
        client = self._server_client()
        if server_enabled() and client:
            entry = self._server_proxy_entry(pool_name, index)
            if not entry or not entry.get("id"):
                self._emit_message("Proxy not found")
                return
            self._emit_message("Server proxy check started")

            def worker() -> None:
                try:
                    client.check_proxy(str(entry["id"]))
                    self._emit_message("Server proxy check finished")
                except Exception as exc:
                    self._emit_message(f"Server proxy check failed: {exc}")
                finally:
                    self.refresh()

            threading.Thread(target=worker, daemon=True).start()
            return
        pools = self._load()
        pool = pools.get(pool_name)
        if not isinstance(pool, dict):
            self._emit_message("Proxy pool not found")
            return
        proxies = pool.get("proxies", [])
        if not (0 <= index < len(proxies)) or not isinstance(proxies[index], dict):
            self._emit_message("Proxy not found")
            return
        proxies[index]["last_check"] = {"status": "checking"}
        self._save(pools)
        self.refresh()

        def worker() -> None:
            try:
                from app.ui.main_window.proxy_mixin import ProxyPoolMixin
                data = self._load()
                entry = data.get(pool_name, {}).get("proxies", [])[index]
                ok, ms, err, meta = ProxyPoolMixin._probe_proxy_endpoint_value(str(entry.get("value") or ""), timeout_s=5.0)
                result = dict(meta or {})
                result["status"] = "ok" if ok else "fail"
                result["ms"] = ms
                if err:
                    result["error"] = err
                self._record_check(entry, result)
                self._save(data)
                self._emit_message("Proxy check finished")
            except Exception as exc:
                self._emit_message(f"Proxy check failed: {exc}")
            finally:
                self.refresh()

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot()
    def checkAll(self) -> None:  # noqa: N802
        if not self._ensure_allowed("operator"):
            return
        client = self._server_client()
        if server_enabled() and client:
            entries = [
                entry
                for pool in self._load().values()
                for entry in (pool.get("proxies", []) if isinstance(pool, dict) else [])
                if isinstance(entry, dict) and entry.get("id")
            ]
            if not entries:
                self._emit_message("No server proxies to check")
                return
            self._emit_message("Server proxy checks started")

            def worker() -> None:
                checked = 0
                for entry in entries:
                    try:
                        client.check_proxy(str(entry["id"]))
                        checked += 1
                    except Exception:
                        continue
                self._emit_message(f"Server proxy checks finished: {checked}")
                self.refresh()

            threading.Thread(target=worker, daemon=True).start()
            return
        pools = self._load()
        skipped = 0
        for pool in pools.values():
            for entry in pool.get("proxies", []) if isinstance(pool, dict) else []:
                if isinstance(entry, dict):
                    if self._is_quarantined(entry):
                        skipped += 1
                        continue
                    entry["last_check"] = {"status": "checking"}
        self._save(pools)
        self.refresh()
        self._emit_message(f"Proxy check started{f'; {skipped} quarantined' if skipped else ''}")

        def worker() -> None:
            try:
                from app.ui.main_window.proxy_mixin import ProxyPoolMixin
                data = self._load()
                for pool in data.values():
                    for entry in pool.get("proxies", []) if isinstance(pool, dict) else []:
                        if not isinstance(entry, dict):
                            continue
                        if self._is_quarantined(entry):
                            continue
                        ok, ms, err, meta = ProxyPoolMixin._probe_proxy_endpoint_value(str(entry.get("value") or ""), timeout_s=5.0)
                        result = dict(meta or {})
                        result["status"] = "ok" if ok else "fail"
                        result["ms"] = ms
                        if err:
                            result["error"] = err
                        self._record_check(entry, result)
                self._save(data)
                self._emit_message("Proxy check finished")
            finally:
                self.refresh()

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot()
    def releaseQuarantineSelected(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        pools = self._load()
        released = 0
        for pool_name, index in list(self._selected):
            entries = (pools.get(pool_name) or {}).get("proxies", [])
            if 0 <= index < len(entries) and isinstance(entries[index], dict):
                if entries[index].pop("quarantine_until", None) is not None:
                    released += 1
        if not released:
            self._emit_message("No quarantined proxies selected")
            return
        self._save(pools)
        self._emit_message(f"Released {released} proxy(s) from quarantine")
        self.refresh()
