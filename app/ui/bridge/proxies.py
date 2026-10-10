"""Proxy pools bridge for QML."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from PyQt6.QtCore import QObject, QThread, pyqtProperty, pyqtSignal, pyqtSlot

from app.core.proxy_utils import proxy_display_address
from app.services.proxy_policy import is_proxy_quarantined
from app.services.server_client import (
    ServerClient,
    ServerClientError,
    get_server_session,
    server_enabled,
)
from app.storage import db
from app.storage.db import db_get_setting, db_set_setting
from app.ui.bridge.background import BackgroundRead
from app.ui.bridge.cloud_permissions import allows, deny_message
from app.ui.bridge.models import DictListModel


def _proxy_workspace_matches(cached, current) -> bool:
    return cached is not None and all(getattr(cached, key) == getattr(current, key)
                                      for key in ("enabled", "url", "team_id", "email"))


def _local_proxy_snapshot(entry) -> tuple[str, str, str]:
    if isinstance(entry, dict):
        return str(entry.get("name") or ""), str(entry.get("value") or ""), str(entry.get("assigned_to") or "")
    return "", str(entry), ""


class ProxiesBridge(QObject):
    modelChanged = pyqtSignal()
    statsChanged = pyqtSignal()
    uiCall = pyqtSignal(object)
    message = pyqtSignal(str)

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self.uiCall.connect(self._invoke_ui)
        self._app_state = app_state
        self._model = DictListModel(["pool", "name", "location", "address", "type", "latency", "status", "accent", "index", "selected"], parent=self)
        self._pools_model = DictListModel(["name", "total", "used", "selected", "source", "permission"], parent=self)
        self._server_pools: Dict[str, Dict[str, Any]] = {}
        self._pools_cache = {}
        self._address_cache: dict[str, str] = {}
        self._cache_session = None
        self._read = BackgroundRead(self, self._apply_refresh, self._emit_message)
        self._read.busyChanged.connect(self.modelChanged.emit)
        self._selected_pool = ""
        self._proxy_query = ""
        self._proxy_status = ""
        self._selected: set[tuple[str, int]] = set()
        self._active = 0
        self._checking = 0
        self._failed = 0
        self._unchecked = 0
        self._locations = 0
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)
            app_state.cloudChanged.connect(self.refresh)
        self.refresh()

    @pyqtSlot(object)
    def _invoke_ui(self, callback):
        callback()

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
        return is_proxy_quarantined(entry)

    def _store_local_check(self, pool_name: str, value: str, result: Dict[str, Any]) -> bool:
        if server_enabled():
            return False
        with db._STORAGE_LOCK:
            pools = json.loads(db_get_setting("proxy_pools") or "{}")
            pool = pools.get(pool_name)
            if not isinstance(pool, dict):
                return False
            matches = [entry for entry in pool.get("proxies", [])
                       if isinstance(entry, dict) and str(entry.get("value") or "") == value]
            if not matches:
                return False
            for entry in matches:
                self._record_check(entry, dict(result))
            db_set_setting("proxy_pools", json.dumps(pools, ensure_ascii=False))
        return True

    @pyqtProperty(bool, notify=modelChanged)
    def loading(self):
        return self._read.busy

    @pyqtProperty(QObject, constant=True)
    def model(self) -> QObject:
        return self._model

    @pyqtProperty(QObject, constant=True)
    def poolsModel(self) -> QObject:  # noqa: N802
        return self._pools_model

    @pyqtProperty(str, notify=modelChanged)
    def selectedPool(self) -> str:  # noqa: N802
        return self._selected_pool

    @pyqtProperty(int, notify=modelChanged)
    def selectedCount(self) -> int:  # noqa: N802
        return len(self._selected)

    @pyqtProperty(str, notify=modelChanged)
    def proxyQuery(self):  # noqa: N802
        return self._proxy_query

    @pyqtProperty(str, notify=modelChanged)
    def proxyStatus(self):  # noqa: N802
        return self._proxy_status

    @pyqtSlot(str, str)
    def setProxyFilters(self, query, status):  # noqa: N802
        status = status.strip().lower()
        if status not in {"", "active", "reachable", "unchecked", "checking", "failed", "quarantined"}:
            return
        if (query, status) == (self._proxy_query, self._proxy_status):
            return
        self._proxy_query, self._proxy_status = query, status
        self._selected.clear()
        self._render_pools()

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
    def unchecked(self) -> int:
        return self._unchecked

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
    def canReleaseQuarantine(self) -> bool:  # noqa: N802
        return not server_enabled() and self.canManage

    @pyqtProperty(bool, notify=modelChanged)
    def canAdmin(self) -> bool:  # noqa: N802
        return allows(self._app_state, "admin")

    def _ensure_allowed(self, min_role: str) -> bool:
        if allows(self._app_state, min_role):
            return True
        self._emit_message(deny_message(min_role))
        return False

    def _load(self, session=None) -> Dict[str, Dict[str, Any]]:
        session = session or get_server_session()
        client = ServerClient(session)
        if session.enabled:
            pools: Dict[str, Dict[str, Any]] = {}
            try:
                proxies = client.proxies()
            except ServerClientError as exc:
                raise ServerClientError(f"Server proxies error: {exc}") from exc
            for proxy in proxies:
                group = str(proxy.get("group_name") or "Default")
                check = proxy.get("last_check") if isinstance(proxy.get("last_check"), dict) else {}
                if not check:
                    raw_status = str(proxy.get("status") or "").lower()
                    check = {"status": raw_status if raw_status in {"fail", "failed", "checking", "quarantined"} else "unchecked", "country": proxy.get("country") or ""}
                else:
                    check = {**check, "mode": check.get("mode") or "tcp"}
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

    @staticmethod
    def _local_proxy_identity(entry: Dict[str, Any]) -> str:
        snapshot = json.dumps(_local_proxy_snapshot(entry), ensure_ascii=False)
        return "local:" + hashlib.sha256(snapshot.encode("utf-8")).hexdigest()

    def _load_local_targets(self, targets) -> Dict[str, Dict[str, Any]] | None:
        # Caller holds the storage lock through persistence.
        session = get_server_session()
        if session.enabled or not _proxy_workspace_matches(self._cache_session, session):
            self._emit_message("Workspace changed; select the proxies again")
            self._selected.clear()
            self.refresh()
            return None
        pools = self._load()
        for pool_name, index in targets:
            cached = self._pools_cache.get(pool_name)
            current = pools.get(pool_name)
            shown = cached.get("proxies", []) if isinstance(cached, dict) else []
            stored = current.get("proxies", []) if isinstance(current, dict) else []
            if (len(shown) != len(stored) or not 0 <= index < len(shown)
                    or _local_proxy_snapshot(shown[index]) != _local_proxy_snapshot(stored[index])):
                self._emit_message("Proxy list changed; select the proxies again")
                self._selected.clear()
                self.refresh()
                return None
        return pools

    def _server_proxy_entry(self, pool_name: str, index: int, expected_id: str = "") -> Dict[str, Any]:
        session = get_server_session()
        if not _proxy_workspace_matches(self._cache_session, session):
            return {}
        try:
            index = int(index)
        except Exception:
            return {}
        pool = self._pools_cache.get(str(pool_name or "").strip())
        proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
        if expected_id:
            return next((entry for entry in proxies if isinstance(entry, dict)
                         and str(entry.get("id") or "") == expected_id), {})
        if 0 <= index < len(proxies) and isinstance(proxies[index], dict):
            return proxies[index]
        return {}

    def _emit_message(self, text: str) -> None:
        if QThread.currentThread() != self.thread():
            self.uiCall.emit(lambda: self._emit_message(text))
            return
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    @pyqtSlot()
    def refresh(self) -> None:
        if QThread.currentThread() != self.thread():
            self.uiCall.emit(self.refresh)
            return
        session = get_server_session()
        if session != self._cache_session:
            self._selected.clear()
            self._address_cache.clear()
            self._server_pools = {}
            self._pools_cache = {}
            self._render_pools()
        self._read.submit(self._fetch_refresh)

    def _fetch_refresh(self, session):
        client = ServerClient(session)
        rows = client.request("GET", f"/api/v1/teams/{session.team_id}/pools?type=proxy") or [] if session.enabled else []
        return session, self._load(session), {str(row["name"]): row for row in rows if row.get("name")}

    def _apply_refresh(self, result):
        session, pools, _ = result
        def identities(data):
            return {name: [entry.get("id") if isinstance(entry, dict) else None for entry in pool.get("proxies", [])]
                    if session.enabled else [_local_proxy_snapshot(entry) for entry in pool.get("proxies", [])]
                    for name, pool in data.items() if isinstance(pool, dict)}
        if identities(pools) != identities(self._pools_cache):
            self._selected.clear()
        self._cache_session, self._pools_cache, self._server_pools = result
        self._address_cache.clear()
        self._render_pools()

    def _render_pools(self):
        pools = self._pools_cache
        pool_rows: List[Dict[str, Any]] = []
        total_all = 0
        used_all = 0
        for pool_name, pool in sorted(pools.items()):
            proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
            total = len(proxies)
            used = sum(1 for item in proxies if isinstance(item, dict) and item.get("assigned_to"))
            total_all += total
            used_all += used
            info = self._server_pools.get(pool_name, {})
            pool_rows.append({"name": pool_name, "total": total, "used": used, "selected": self._selected_pool == pool_name, "source": info.get("source", ""), "permission": info.get("permission", "")})
        # server ResourcePools with no proxies yet still show up as chips
        known = {row["name"] for row in pool_rows}
        for pool_name, info in sorted(self._server_pools.items()):
            if pool_name not in known:
                pool_rows.append({"name": pool_name, "total": 0, "used": 0, "selected": self._selected_pool == pool_name, "source": info.get("source", ""), "permission": info.get("permission", "")})
        self._pools_model.set_rows(
            [{"name": "All pools", "total": total_all, "used": used_all, "selected": not self._selected_pool, "source": "", "permission": ""}]
            + pool_rows
        )
        rows: List[Dict[str, Any]] = []
        query = self._proxy_query.strip().casefold()
        active = checking = failed = unchecked = 0
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
                status_raw = str(check.get("status") or "unchecked").lower() if isinstance(check, dict) else "unchecked"
                quarantined = isinstance(entry, dict) and self._is_quarantined(entry)
                if quarantined:
                    status = "Quarantined"
                elif status_raw in {"ok", "active"}:
                    status = "Reachable" if check.get("mode") == "tcp" else "Active"
                else:
                    status = {"checking": "Checking", "unchecked": "Unchecked"}.get(status_raw, "Failed")
                if status in {"Active", "Reachable"}:
                    active += 1
                elif status == "Checking":
                    checking += 1
                elif status == "Unchecked":
                    unchecked += 1
                else:
                    failed += 1
                country = str(check.get("country") or "") if isinstance(check, dict) else ""
                city = str(check.get("city") or "") if isinstance(check, dict) else ""
                geo_location = ", ".join(p for p in [city, country] if p)
                location = geo_location or pool_name
                if geo_location:
                    locations.add(geo_location)
                if value not in self._address_cache:
                    self._address_cache[value] = proxy_display_address(value)
                address = self._address_cache[value]
                type_label = address.split("://", 1)[0].upper() if "://" in address else "INVALID"
                latency = check.get("ms") if isinstance(check, dict) else None
                row = {
                    "pool": pool_name,
                    "name": str(entry.get("name") or f"{pool_name}-{pool_index + 1:02d}") if isinstance(entry, dict) else f"{pool_name}-{pool_index + 1:02d}",
                    "location": location,
                    "address": address,
                    "type": type_label,
                    "latency": f"{latency}ms" if isinstance(latency, int) else "?",
                    "status": status,
                    "accent": "#3f714a" if status == "Active" else "#94671c" if status in {"Checking", "Quarantined"} else "#b33d47" if status == "Failed" else "#737e6b",
                    "index": pool_index,
                    "selected": (pool_name, pool_index) in self._selected,
                }
                if self._proxy_status and status.lower() != self._proxy_status:
                    continue
                if query and not any(query in str(row[key]).casefold() for key in ("name", "address", "location", "pool", "type")):
                    continue
                rows.append(row)
        self._active, self._checking, self._failed, self._locations = active, checking, failed, len(locations)
        self._unchecked = unchecked
        self._model.set_rows(rows)
        self.modelChanged.emit()
        self.statsChanged.emit()

    @pyqtSlot(str)
    def selectPool(self, name: str) -> None:  # noqa: N802
        name = str(name or "")
        self._selected_pool = "" if name == "All pools" else name
        self._selected.clear()
        self._render_pools()


    def _load_server_pools(self) -> None:
        self._server_pools = {}
        client = self._server_client()
        if not (server_enabled() and client):
            return
        try:
            rows = client.request("GET", f"/api/v1/teams/{client.session.team_id}/pools?type=proxy") or []
        except ServerClientError:
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "")
            if name:
                self._server_pools[name] = {
                    "id": str(row.get("id") or ""),
                    "source": str(row.get("source") or ""),
                    "permission": str(row.get("permission") or ""),
                    "shared_by_team": str(row.get("shared_by_team") or ""),
                }

    @pyqtSlot(str, str, str)
    def sharePool(self, pool_name: str, team_slug: str, permission: str) -> None:  # noqa: N802
        client = self._server_client()
        if not (server_enabled() and client):
            self._emit_message("Connect to cloud to share pools")
            return
        info = self._server_pools.get(str(pool_name or ""))
        if not info or not info.get("id"):
            self._emit_message("Select an owned pool first")
            return
        try:
            client.request("POST", f"/api/v1/teams/{client.session.team_id}/pools/{info['id']}/shares", {"team_slug": str(team_slug or "").strip(), "permission": str(permission or "attach")})
            self._emit_message(f'Pool "{pool_name}" shared with {team_slug} ({permission})')
            self.refresh()
        except ServerClientError as exc:
            self._emit_message(f"Share failed: {exc}")

    @pyqtSlot(str)
    def createPool(self, name: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        name = str(name or "").strip()
        if not name:
            self._emit_message("Pool name is empty")
            return
        client = self._server_client()
        if server_enabled() and client:
            try:
                client.request("POST", f"/api/v1/teams/{client.session.team_id}/pools", {"name": name, "type": "proxy"})
                self._selected_pool = name
                self._emit_message(f"Server pool {name} created")
            except ServerClientError as exc:
                self._emit_message(f"Pool create failed: {exc}")
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
            pool_info = self._server_pools.get(pool_name, {})
            pool_id = pool_info.get("id") if pool_info.get("source") in {"owned", "global", "shared"} and pool_info.get("permission", "attach") == "attach" else None
            added = 0
            for value in lines:
                try:
                    payload = {"value": value, "group_name": pool_name}
                    if pool_id:
                        payload["pool_id"] = pool_id
                    client.create_proxy(payload)
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
        session = get_server_session()
        if not _proxy_workspace_matches(self._cache_session, session):
            return {}
        pool_name = str(pool_name or "").strip()
        try:
            index = int(index)
        except Exception:
            return {}
        if session.enabled:
            entry = self._server_proxy_entry(pool_name, index)
            return {**entry, "pool": pool_name, "index": index} if entry else {}
        pool = self._pools_cache.get(pool_name)
        if not isinstance(pool, dict):
            return {}
        proxies = pool.get("proxies", [])
        if not (0 <= index < len(proxies)) or not isinstance(proxies[index], dict):
            return {}
        entry = proxies[index]
        return {
            "id": self._local_proxy_identity(entry),
            "pool": pool_name,
            "index": index,
            "name": str(entry.get("name") or ""),
            "value": str(entry.get("value") or ""),
            "assigned_to": str(entry.get("assigned_to") or ""),
        }

    @pyqtSlot(str, int, str, str)
    @pyqtSlot(str, int, str, str, str)
    def saveProxy(self, pool_name: str, index: int, name: str, value: str, expected_id: str = "") -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        local_identity = expected_id == "local" or expected_id.startswith("local:")
        if expected_id and server_enabled() == local_identity:
            self._emit_message("Workspace changed; reopen proxy settings")
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
            entry = self._server_proxy_entry(pool_name, index, expected_id)
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
        with db._STORAGE_LOCK:
            if server_enabled():
                self._emit_message("Workspace changed; reopen proxy settings")
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
            entry = proxies[index]
            if expected_id.startswith("local:") and self._local_proxy_identity(entry) != expected_id:
                self._emit_message("Proxy changed; reopen proxy settings")
                self.refresh()
                return
            if str(entry.get("value") or "") != value:
                for field in ("last_check", "check_history", "health_score"):
                    entry.pop(field, None)
            entry["name"] = str(name or "").strip()
            entry["value"] = value
            self._save(pools)
        self._emit_message("Proxy saved")
        self.refresh()

    @pyqtSlot(str, int)
    @pyqtSlot(str, int, str)
    def deleteProxy(self, pool_name: str, index: int, expected_id: str = "") -> None:  # noqa: N802
        if not self._ensure_allowed("admin"):
            return
        local_identity = expected_id == "local" or expected_id.startswith("local:")
        if expected_id and server_enabled() == local_identity:
            self._emit_message("Workspace changed; select the proxy again")
            return
        pool_name = str(pool_name or "").strip()
        try:
            index = int(index)
        except Exception:
            return
        client = self._server_client()
        if server_enabled() and client:
            entry = self._server_proxy_entry(pool_name, index, expected_id)
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
        with db._STORAGE_LOCK:
            if server_enabled():
                self._emit_message("Workspace changed; select the proxy again")
                return
            pools = self._load()
            pool = pools.get(pool_name)
            proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
            if not (0 <= index < len(proxies)):
                return
            if expected_id.startswith("local:") and (not isinstance(proxies[index], dict) or self._local_proxy_identity(proxies[index]) != expected_id):
                self._emit_message("Proxy changed; select the proxy again")
                self.refresh()
                return
            proxies.pop(index)
            self._save(pools)
        self._selected = {
            (p, i if p != pool_name or i < index else i - 1)
            for p, i in self._selected
            if not (p == pool_name and i == index)
        }
        self._emit_message("Proxy deleted")
        self.refresh()

    @pyqtSlot(str, int, bool)
    def setProxySelected(self, pool_name: str, index: int, selected: bool) -> None:  # noqa: N802
        key = (str(pool_name or "").strip(), int(index))
        if selected:
            self._selected.add(key)
        else:
            self._selected.discard(key)
        self._render_pools()

    @pyqtSlot()
    def clearSelection(self) -> None:  # noqa: N802
        self._selected.clear()
        self._render_pools()

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
        released = 0
        assigned_names: set[str] = set()
        with db._STORAGE_LOCK:
            pools = self._load_local_targets(list(self._selected))
            if pools is None:
                return
            for pool_name, index in list(self._selected):
                proxies = pools.get(pool_name, {}).get("proxies", []) if isinstance(pools.get(pool_name), dict) else []
                if isinstance(proxies[index], dict):
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
        removed = 0
        with db._STORAGE_LOCK:
            pools = self._load_local_targets(list(self._selected))
            if pools is None:
                return
            for pool_name in sorted({pool for pool, _ in self._selected}):
                proxies = pools[pool_name]["proxies"]
                indices = sorted([idx for pool, idx in self._selected if pool == pool_name], reverse=True)
                for index in indices:
                    proxies.pop(index)
                    removed += 1
            self._save(pools)
        self._selected.clear()
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
        with db._STORAGE_LOCK:
            pools = self._load_local_targets([(pool_name, index)])
            if pools is None:
                return
            proxies = pools[pool_name]["proxies"]
            if not isinstance(proxies[index], dict):
                self._emit_message("Proxy not found")
                return
            proxies[index]["last_check"] = {"status": "checking"}
            value = str(proxies[index].get("value") or "")
            self._save(pools)
        self.refresh()

        def worker() -> None:
            try:
                from app.services.proxy_health import probe_proxy_endpoint
                ok, ms, err, meta = probe_proxy_endpoint(value, timeout_s=5.0)
                result = dict(meta or {})
                result["status"] = "ok" if ok else "fail"
                result["ms"] = ms
                if err:
                    result["error"] = err
                applied = self._store_local_check(pool_name, value, result)
                self._emit_message("Proxy check finished" if applied else "Proxy changed or workspace switched; check result discarded")
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
        targets = []
        for pool_name, pool in pools.items():
            for entry in pool.get("proxies", []) if isinstance(pool, dict) else []:
                if isinstance(entry, dict):
                    if self._is_quarantined(entry):
                        skipped += 1
                        continue
                    entry["last_check"] = {"status": "checking"}
                    targets.append((pool_name, str(entry.get("value") or "")))
        targets = list(dict.fromkeys(targets))
        if not targets:
            self._emit_message("No available proxies to check")
            return
        self._save(pools)
        self.refresh()
        self._emit_message(f"Proxy check started{f'; {skipped} quarantined' if skipped else ''}")

        def worker() -> None:
            try:
                from app.services.proxy_health import probe_proxy_endpoint
                for pool_name, value in targets:
                    ok, ms, err, meta = probe_proxy_endpoint(value, timeout_s=5.0)
                    result = dict(meta or {})
                    result["status"] = "ok" if ok else "fail"
                    result["ms"] = ms
                    if err:
                        result["error"] = err
                    self._store_local_check(pool_name, value, result)
                self._emit_message("Proxy check finished")
            except Exception as exc:
                self._emit_message(f"Proxy checks failed ({type(exc).__name__})")
            finally:
                self.refresh()

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot()
    def releaseQuarantineSelected(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        if server_enabled():
            self._emit_message("Quarantine release is available only in local workspaces")
            return
        released = 0
        with db._STORAGE_LOCK:
            pools = self._load_local_targets(list(self._selected))
            if pools is None:
                return
            for pool_name, index in list(self._selected):
                entries = pools[pool_name]["proxies"]
                if isinstance(entries[index], dict):
                    until = entries[index].pop("quarantine_until", None)
                    explicit = entries[index].get("status") == "quarantined"
                    if explicit:
                        entries[index]["status"] = "unchecked"
                    if until is not None or explicit:
                        released += 1
            if not released:
                self._emit_message("No quarantined proxies selected")
                return
            self._save(pools)
        self._emit_message(f"Released {released} proxy(s) from quarantine")
        self.refresh()
