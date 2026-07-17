"""Profiles bridge for QML."""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from app.core.browser_interface import BrowserInterface
from app.storage.db import (
    db_add_account,
    db_delete_account,
    db_get_accounts,
    db_get_setting,
    db_set_setting,
    db_update_account,
    profile_dir_for_email,
)
from app.services.server_client import ServerClient, ServerClientError, server_enabled
from app.ui.bridge.cloud_permissions import allows, deny_message
from app.ui.bridge.models import DictListModel
from app.utils.parsing import DEFAULT_ACCOUNT_TEMPLATE, parse_account_line

LOGGER = logging.getLogger(__name__)
LOCK_TTL_MINUTES = 3
LOCK_HEARTBEAT_MS = 45_000


class ProfilesBridge(QObject):
    modelChanged = pyqtSignal()
    countsChanged = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._model = DictListModel([
            "name", "id", "browser", "proxy", "lastActive", "status", "stage", "tags", "running", "lockedBy", "lockExpires"
        ], parent=self)
        self._stages_model = DictListModel(["name", "count", "selected"], parent=self)
        self._selected_stage = ""
        self._live_browsers: Dict[str, BrowserInterface] = {}
        self._live_server_profile_ids: Dict[str, str] = {}
        self._heartbeat_in_flight = False
        self._app_state = app_state
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(LOCK_HEARTBEAT_MS)
        self._heartbeat_timer.timeout.connect(self._heartbeat_server_profiles)
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)
            app_state.cloudChanged.connect(self.refresh)
        self.refresh()

    @pyqtProperty(QObject, constant=True)
    def model(self) -> QObject:
        return self._model

    @pyqtProperty(QObject, constant=True)
    def stagesModel(self) -> QObject:  # noqa: N802
        return self._stages_model

    @pyqtProperty(str, notify=modelChanged)
    def selectedStage(self) -> str:  # noqa: N802
        return self._selected_stage

    @pyqtProperty(int, notify=countsChanged)
    def total(self) -> int:
        return self._model.rowCount()

    @pyqtProperty(int, notify=countsChanged)
    def running(self) -> int:
        return len(self._live_browsers)

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

    def live_browsers(self) -> Dict[str, BrowserInterface]:
        return self._live_browsers

    def _emit_message(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    def _server_client(self) -> Optional[ServerClient]:
        client = ServerClient()
        return client if client.configured else None

    def _server_accounts(self) -> List[Dict[str, Any]]:
        client = self._server_client()
        if not client:
            return []
        proxies = {str(item.get("id") or ""): item for item in client.proxies()}
        accounts: List[Dict[str, Any]] = []
        for profile in client.profiles():
            settings = profile.get("settings") if isinstance(profile.get("settings"), dict) else {}
            acc: Dict[str, Any] = {
                "id": str(profile.get("id") or ""),
                "name": str(profile.get("name") or ""),
                "stage": str(profile.get("group_name") or ""),
                "_browser_engine": str(profile.get("browser_engine") or "camoufox"),
                "status": str(profile.get("status") or "idle"),
                "lock_user_id": str(profile.get("lock_user_id") or ""),
                "lock_user_email": str(profile.get("lock_user_email") or ""),
                "lock_expires_at": str(profile.get("lock_expires_at") or ""),
                "camoufox_settings": settings,
                "cloakbrowser_settings": settings,
                "extra_fields": settings.get("variables") if isinstance(settings.get("variables"), dict) else {},
                "_server_profile": profile,
            }
            proxy = proxies.get(str(profile.get("proxy_id") or ""))
            if proxy:
                acc.update(self._parse_proxy_value(str(proxy.get("value") or "")))
                acc["proxy_pool"] = str(proxy.get("group_name") or "")
                acc["_server_proxy"] = proxy
            accounts.append(acc)
        return accounts

    def _server_account(self, name: str) -> Optional[Dict[str, Any]]:
        target = str(name or "").strip()
        return next((acc for acc in self._server_accounts() if str(acc.get("name") or "") == target), None)

    def _server_proxy_id_from_fields(
        self,
        client: ServerClient,
        *,
        stage: str,
        proxy_host: str,
        proxy_port: str,
        proxy_user: str,
        proxy_password: str,
    ) -> Optional[str]:
        host = str(proxy_host or "").strip()
        port = str(proxy_port or "").strip()
        if not host or not port:
            return None
        user = str(proxy_user or "").strip()
        password = str(proxy_password or "").strip()
        auth = f"{user}:{password}@" if user and password else ""
        value = f"socks5://{auth}{host}:{port}"
        group_name = str(stage or "").strip() or "Default"
        for proxy in client.proxies():
            if str(proxy.get("value") or "") == value:
                return str(proxy.get("id") or "")
        created = client.create_proxy({"value": value, "group_name": group_name})
        return str(created.get("id") or "") or None

    def _proxy_label(self, acc: Dict[str, Any]) -> str:
        host = str(acc.get("proxy_host") or "")
        port = acc.get("proxy_port")
        if host and port:
            return f"{host}:{port}"
        return str(acc.get("proxy_pool") or "None")

    @staticmethod
    def _settings_dict(value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None

    @staticmethod
    def _parse_proxy_value(value: str) -> Dict[str, Any]:
        raw = str(value or "").strip()
        if not raw:
            return {}
        scheme = "socks5"
        host = ""
        port: Any = None
        user = ""
        password = ""
        if "://" in raw:
            parsed = urlparse(raw)
            scheme = parsed.scheme or scheme
            if parsed.hostname and parsed.port:
                host = parsed.hostname
                port = parsed.port
                user = parsed.username or ""
                password = parsed.password or ""
            else:
                tail = raw.split("://", 1)[1]
                parts = [p.strip() for p in tail.split(":")]
                if len(parts) >= 2:
                    host, port = parts[0], parts[1]
                if len(parts) >= 4:
                    user, password = parts[2], parts[3]
        elif "@" in raw:
            creds, address = raw.rsplit("@", 1)
            if ":" in creds:
                user, password = creds.split(":", 1)
            if ":" in address:
                host, port = address.rsplit(":", 1)
        else:
            parts = [p.strip() for p in raw.split(":")]
            if len(parts) >= 2:
                host, port = parts[0], parts[1]
            if len(parts) >= 4:
                user, password = parts[2], parts[3]
        if not host or not port:
            return {}
        try:
            port = int(port)
        except Exception:
            return {}
        return {
            "proxy_scheme": scheme,
            "proxy_host": host,
            "proxy_port": port,
            "proxy_user": user,
            "proxy_password": password,
        }

    def _take_proxy_from_pool(self, pool_name: str, profile_name: str) -> Dict[str, Any]:
        pool_name = str(pool_name or "").strip()
        if not pool_name:
            return {}
        try:
            pools = json.loads(db_get_setting("proxy_pools") or "{}")
        except Exception:
            pools = {}
        pool = pools.get(pool_name) if isinstance(pools, dict) else None
        proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
        for entry in proxies:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("assigned_to") or "").strip():
                continue
            details = self._parse_proxy_value(str(entry.get("value") or ""))
            if not details:
                continue
            entry["assigned_to"] = profile_name
            db_set_setting("proxy_pools", json.dumps(pools, ensure_ascii=False))
            details["proxy_pool"] = pool_name
            return details
        return {"proxy_pool": pool_name}

    @pyqtSlot()
    def refresh(self) -> None:
        rows: List[Dict[str, Any]] = []
        try:
            accounts = self._server_accounts() if server_enabled() and self._server_client() else db_get_accounts()
        except ServerClientError as exc:
            self._emit_message(f"Server profiles error: {exc}")
            accounts = []
        stage_counts: Dict[str, int] = {}
        for acc in accounts:
            stage_counts[str(acc.get("stage") or "No tag")] = stage_counts.get(str(acc.get("stage") or "No tag"), 0) + 1
        try:
            configured_stages = json.loads(db_get_setting("stages_json") or "[]")
        except Exception:
            configured_stages = []
        for stage in configured_stages if isinstance(configured_stages, list) else []:
            clean_stage = str(stage or "").strip()
            if clean_stage:
                stage_counts.setdefault(clean_stage, 0)
        self._stages_model.set_rows(
            [{"name": "All tags", "count": len(accounts), "selected": not self._selected_stage}]
            + [
                {"name": stage, "count": count, "selected": self._selected_stage == stage}
                for stage, count in sorted(stage_counts.items(), key=lambda item: item[0].lower())
            ]
        )
        sorted_accounts = sorted(accounts, key=lambda a: (str(a.get("stage") or "No tag").lower(), str(a.get("name") or "").lower()))
        for index, acc in enumerate(sorted_accounts, start=1):
            name = str(acc.get("name") or f"profile{index}")
            stage = str(acc.get("stage") or "")
            stage_label = stage or "No tag"
            if self._selected_stage and self._selected_stage != stage_label:
                continue
            running = name in self._live_browsers
            tags = []
            if stage:
                tags.append(stage)
            for key in ("tag", "type"):
                val = str(acc.get(key) or "")
                if val and val not in tags:
                    tags.append(val)
            engine = str(acc.get("_browser_engine") or acc.get("browser_engine") or "camoufox")
            if engine == "cloakbrowser":
                browser_label = "CloakBrowser"
            else:
                browser_label = "Camoufox"
            rows.append({
                "name": name,
                "id": str(acc.get("id") or f"#{index:04d}"),
                "browser": browser_label,
                "proxy": self._proxy_label(acc),
                "lastActive": str(acc.get("last_active") or "now" if running else acc.get("last_active") or "idle"),
                "status": "Running" if running else ("Locked" if acc.get("lock_user_email") else "Stopped"),
                "stage": stage or "No tag",
                "tags": "  ".join(f"#{tag}" for tag in tags) if tags else "#profile",
                "running": running,
                "lockedBy": str(acc.get("lock_user_email") or ""),
                "lockExpires": str(acc.get("lock_expires_at") or ""),
            })
        self._model.set_rows(rows)
        self.modelChanged.emit()
        self.countsChanged.emit()

    @pyqtSlot(str)
    def setStageFilter(self, stage: str) -> None:  # noqa: N802
        stage = str(stage or "")
        if stage == "All tags":
            stage = ""
        self._selected_stage = stage
        self.refresh()

    @pyqtSlot()
    def createProfile(self) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        client = self._server_client()
        if server_enabled() and client:
            try:
                existing = self._server_accounts()
                names = {str(acc.get("name") or "").lower() for acc in existing}
                index = len(existing) + 1
                while f"profile{index}".lower() in names:
                    index += 1
                name = f"profile{index}"
                client.create_profile({"name": name, "group_name": "Default", "browser_engine": "camoufox"})
                self._emit_message(f"Server profile {name} created")
                self.refresh()
            except ServerClientError as exc:
                self._emit_message(f"Cannot create server profile: {exc}")
            return
        existing = db_get_accounts()
        next_index = len(existing) + 1
        names = {str(acc.get("name") or "").lower() for acc in existing}
        while f"profile{next_index}".lower() in names:
            next_index += 1
        name = f"profile{next_index}"
        try:
            db_add_account({"name": name, "stage": ""})
        except Exception as exc:
            self._emit_message(f"Cannot create profile: {exc}")
            return
        self._emit_message(f"Profile {name} created")
        self.refresh()

    @pyqtSlot(str, str, str, str)
    def importProfiles(self, lines: str, template: str, default_stage: str, proxy_pool: str) -> None:  # noqa: N802
        raw_lines = [line.strip() for line in str(lines or "").replace("\r", "\n").split("\n") if line.strip()]
        if not self._ensure_allowed("manager"):
            return
        if not raw_lines:
            self._emit_message("Profile import list is empty")
            return
        template = str(template or "").strip() or DEFAULT_ACCOUNT_TEMPLATE
        default_stage = str(default_stage or "").strip()
        proxy_pool = str(proxy_pool or "").strip()
        added = 0
        errors = 0
        client = self._server_client() if server_enabled() else None
        for line in raw_lines:
            try:
                parsed = parse_account_line(line, template)
                name = str(parsed.get("name") or parsed.get("email") or "").strip()
                if not name:
                    name = f"profile{len(self._server_accounts() if client else db_get_accounts()) + 1}"
                account: Dict[str, Any] = {
                    "name": name,
                    "stage": default_stage,
                    "extra_fields": dict(parsed),
                }
                for key, value in parsed.items():
                    account[str(key)] = str(value)
                if client:
                    client.create_profile({
                        "name": name,
                        "group_name": default_stage or "Default",
                        "browser_engine": "camoufox",
                        "settings": {"variables": dict(parsed)},
                    })
                else:
                    account.update(self._take_proxy_from_pool(proxy_pool, name))
                    db_add_account(account)
                added += 1
            except Exception:
                LOGGER.exception("Profile import failed for line: %s", line)
                errors += 1
        self._emit_message(f"Imported {added} profile(s)" + (f", {errors} failed" if errors else ""))
        self.refresh()

    @pyqtSlot(str, str, result="QVariant")
    def getProfile(self, name: str, engine: str = "camoufox") -> Dict[str, Any]:  # noqa: N802
        target = str(name or "").strip()
        if server_enabled() and not self._ensure_allowed("manager"):
            return
        acc = self._server_account(target) if server_enabled() and self._server_client() else next((item for item in db_get_accounts() if str(item.get("name") or "") == target), None)
        if not acc:
            return {}
        engine = str(engine or "camoufox").lower()
        settings_key = "cloakbrowser_settings" if engine == "cloakbrowser" else "camoufox_settings"
        settings = acc.get(settings_key)
        if isinstance(settings, str):
            try:
                import json

                parsed = json.loads(settings)
                settings = parsed if isinstance(parsed, dict) else {}
            except Exception:
                settings = {}
        if not isinstance(settings, dict):
            settings = {}
        return {
            "name": str(acc.get("name") or ""),
            "stage": str(acc.get("stage") or ""),
            "proxy_host": str(acc.get("proxy_host") or ""),
            "proxy_port": "" if acc.get("proxy_port") in (None, "") else str(acc.get("proxy_port")),
            "proxy_user": str(acc.get("proxy_user") or ""),
            "proxy_password": str(acc.get("proxy_password") or ""),
            "locale": str(settings.get("locale") or ""),
            "timezone": str(settings.get("timezone") or ""),
            "user_agent": str(settings.get("user_agent") or ""),
            "webgl_vendor": str(settings.get("webgl_vendor") or settings.get("gpu_vendor") or ""),
            "hardware_concurrency": "" if settings.get("hardware_concurrency") in (None, "", 0) else str(settings.get("hardware_concurrency")),
        }

    @pyqtSlot(str, result=str)
    def getProfileVariables(self, name: str) -> str:  # noqa: N802
        target = str(name or "").strip()
        if server_enabled() and not self._ensure_allowed("manager"):
            return
        acc = self._server_account(target) if server_enabled() and self._server_client() else next((item for item in db_get_accounts() if str(item.get("name") or "") == target), None)
        if not acc:
            return "{}"
        hidden = {
            "id",
            "stage",
            "proxy_host",
            "proxy_port",
            "proxy_user",
            "proxy_password",
            "proxy_scheme",
            "proxy_pool",
            "camoufox_settings",
            "cloakbrowser_settings",
            "_browser_engine",
            "browser_engine",
            "last_active",
        }
        variables: Dict[str, Any] = {}
        extra = acc.get("extra_fields")
        if isinstance(extra, dict):
            variables.update(extra)
        for key, value in acc.items():
            if key not in hidden and key != "extra_fields":
                variables[str(key)] = value
        return json.dumps(variables, ensure_ascii=False, indent=2)

    @pyqtSlot(str, str, result=str)
    def getProfileBrowserSettingsJson(self, name: str, engine: str) -> str:  # noqa: N802
        target = str(name or "").strip()
        acc = self._server_account(target) if server_enabled() and self._server_client() else next((item for item in db_get_accounts() if str(item.get("name") or "") == target), None)
        if not acc:
            return "{}"
        engine = str(engine or acc.get("_browser_engine") or acc.get("browser_engine") or "camoufox").lower()
        key = "cloakbrowser_settings" if engine == "cloakbrowser" else "camoufox_settings"
        settings = self._settings_dict(acc.get(key)) or {}
        return json.dumps(settings, ensure_ascii=False, indent=2)

    @pyqtSlot(str, str, str)
    def saveProfileBrowserSettingsJson(self, name: str, engine: str, settings_json: str) -> None:  # noqa: N802
        target = str(name or "").strip()
        if not target:
            return
        try:
            payload = json.loads(str(settings_json or "{}"))
        except Exception as exc:
            self._emit_message(f"Browser settings JSON error: {exc}")
            return
        if not isinstance(payload, dict):
            self._emit_message("Browser settings must be a JSON object")
            return
        engine = str(engine or "camoufox").lower()
        settings_key = "cloakbrowser_settings" if engine == "cloakbrowser" else "camoufox_settings"
        client = self._server_client()
        if server_enabled() and client:
            acc = self._server_account(target)
            if not acc:
                self._emit_message("Profile not found")
                return
            try:
                client.update_profile(str(acc.get("id") or ""), {"settings": payload})
            except ServerClientError as exc:
                self._emit_message(f"Cannot save server browser settings: {exc}")
                return
            self._emit_message(f"Browser overrides saved for {target}")
            self.refresh()
            return
        try:
            updates = {settings_key: payload} if payload else {"__delete_keys__": [settings_key]}
            db_update_account(target, updates)
        except Exception as exc:
            self._emit_message(f"Cannot save browser overrides: {exc}")
            return
        self._emit_message(f"Browser overrides saved for {target}")
        self.refresh()

    @pyqtSlot(str, str)
    def saveProfileVariables(self, name: str, variables_json: str) -> None:  # noqa: N802
        target = str(name or "").strip()
        if not target:
            return
        try:
            payload = json.loads(str(variables_json or "{}"))
        except Exception as exc:
            self._emit_message(f"Variables JSON error: {exc}")
            return
        if not isinstance(payload, dict):
            self._emit_message("Variables must be a JSON object")
            return
        client = self._server_client()
        if server_enabled() and client:
            acc = self._server_account(target)
            if not acc:
                self._emit_message("Profile not found")
                return
            profile = acc.get("_server_profile") if isinstance(acc.get("_server_profile"), dict) else {}
            settings = profile.get("settings") if isinstance(profile.get("settings"), dict) else {}
            settings = dict(settings)
            settings["variables"] = payload
            try:
                client.update_profile(str(acc.get("id") or ""), {"settings": settings})
            except ServerClientError as exc:
                self._emit_message(f"Cannot save server variables: {exc}")
                return
            self._emit_message(f"Variables saved for {target}")
            self.refresh()
            return
        updates = {"extra_fields": payload}
        for key, value in payload.items():
            if str(key) == "name":
                continue
            updates[str(key)] = value
        try:
            db_update_account(target, updates)
        except Exception as exc:
            self._emit_message(f"Cannot save variables: {exc}")
            return
        self._emit_message(f"Variables saved for {target}")
        self.refresh()

    @staticmethod
    def _read_cookie_rows(profile_name: str) -> List[Dict[str, Any]]:
        import os
        import shutil
        import sqlite3
        import tempfile

        profile_dir = Path(profile_dir_for_email(profile_name))
        if not profile_dir.exists():
            return []

        def read_rows(db_path: Path, query: str) -> List[tuple]:
            tmp_path: Optional[str] = None
            try:
                try:
                    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1.0)
                except Exception:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3")
                    tmp_path = tmp.name
                    tmp.close()
                    shutil.copy2(str(db_path), tmp_path)
                    con = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True, timeout=1.0)
                try:
                    cur = con.cursor()
                    cur.execute(query)
                    return list(cur.fetchall())
                finally:
                    con.close()
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        rows_out: List[Dict[str, Any]] = []
        candidates = [
            ("firefox", profile_dir / "cookies.sqlite"),
            ("chromium", profile_dir / "Cookies"),
            ("chromium", profile_dir / "Network" / "Cookies"),
            ("chromium", profile_dir / "Default" / "Cookies"),
            ("chromium", profile_dir / "Default" / "Network" / "Cookies"),
        ]
        for source, path in candidates:
            if not path.exists():
                continue
            try:
                if source == "firefox":
                    for host, cookie_name, value, cookie_path, expiry, secure, http_only in read_rows(
                        path,
                        "SELECT host, name, value, path, expiry, isSecure, isHttpOnly FROM moz_cookies",
                    ):
                        rows_out.append({
                            "domain": str(host or ""),
                            "name": str(cookie_name or ""),
                            "value": str(value or ""),
                            "path": str(cookie_path or "/"),
                            "expires": int(expiry or 0),
                            "secure": bool(secure),
                            "httpOnly": bool(http_only),
                        })
                else:
                    for host, cookie_name, value, encrypted, cookie_path, expires_utc, secure, http_only in read_rows(
                        path,
                        "SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly FROM cookies",
                    ):
                        cookie_value = str(value or "")
                        if not cookie_value and encrypted:
                            cookie_value = "<encrypted>"
                        rows_out.append({
                            "domain": str(host or ""),
                            "name": str(cookie_name or ""),
                            "value": cookie_value,
                            "path": str(cookie_path or "/"),
                            "secure": bool(secure),
                            "httpOnly": bool(http_only),
                        })
            except Exception:
                LOGGER.exception("Cannot read cookies from %s", path)
        return [row for row in rows_out if row.get("domain") and row.get("name")]

    @pyqtSlot(str, result=str)
    def getProfileCookiesJson(self, name: str) -> str:  # noqa: N802
        return json.dumps(self._read_cookie_rows(str(name or "")), ensure_ascii=False, indent=2)

    @pyqtSlot(str, str)
    def saveProfileCookiesJson(self, name: str, cookies_json: str) -> None:  # noqa: N802
        target = str(name or "").strip()
        try:
            cookies = json.loads(str(cookies_json or "[]"))
        except Exception as exc:
            self._emit_message(f"Cookies JSON error: {exc}")
            return
        if not isinstance(cookies, list):
            self._emit_message("Cookies must be a JSON array")
            return
        acc = next((item for item in db_get_accounts() if str(item.get("name") or "") == target), None)
        if not acc:
            self._emit_message("Profile not found")
            return

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            engine = str(acc.get("_browser_engine") or acc.get("browser_engine") or "camoufox")
            settings = self._settings_dict(
                acc.get("cloakbrowser_settings")
                if engine == "cloakbrowser"
                else acc.get("camoufox_settings")
            )
            browser = BrowserInterface(
                profile_name=target,
                proxy=self._proxy_for(acc),
                keep_browser_open=False,
                browser_engine=engine,
                browser_settings=settings,
            )
            try:
                async def run() -> None:
                    await browser.start()
                    context = getattr(browser, "context", None)
                    if context is None:
                        raise RuntimeError("Browser context is not initialized")
                    await context.clear_cookies()
                    clean = []
                    for cookie in cookies:
                        if not isinstance(cookie, dict):
                            continue
                        item = {
                            "name": str(cookie.get("name") or "").strip(),
                            "value": str(cookie.get("value") or ""),
                            "domain": str(cookie.get("domain") or "").strip(),
                            "path": str(cookie.get("path") or "/") or "/",
                        }
                        if not item["name"] or not item["domain"]:
                            continue
                        for key in ("expires", "httpOnly", "secure", "sameSite"):
                            if key in cookie:
                                item[key] = cookie[key]
                        clean.append(item)
                    if clean:
                        await context.add_cookies(clean)
                    await browser.close(force=True)

                loop.run_until_complete(run())
                QTimer.singleShot(0, lambda: self._emit_message(f"Cookies saved for {target}"))
            except Exception as exc:
                LOGGER.exception("Cannot save cookies for %s", target)
                QTimer.singleShot(0, lambda exc=exc: self._emit_message(f"Cannot save cookies: {exc}"))
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot(str, str, str, str, str, str, str, str, str, str, str, str, str)
    def saveProfile(
        self,
        original_name: str,
        name: str,
        stage: str,
        proxy_host: str,
        proxy_port: str,
        proxy_user: str,
        proxy_password: str,
        engine: str,
        locale: str,
        timezone: str,
        user_agent: str,
        webgl_vendor: str,
        hardware_concurrency: str,
    ) -> None:  # noqa: N802
        original_name = str(original_name or "").strip()
        if server_enabled() and not self._ensure_allowed("manager"):
            return
        clean_name = str(name or "").strip()
        if not original_name or not clean_name:
            self._emit_message("Profile name is required")
            return
        updates: Dict[str, Any] = {
            "name": clean_name,
            "stage": str(stage or "").strip(),
            "_browser_engine": str(engine or "camoufox").lower(),
            "proxy_host": str(proxy_host or "").strip(),
            "proxy_user": str(proxy_user or "").strip(),
            "proxy_password": str(proxy_password or "").strip(),
        }
        port_text = str(proxy_port or "").strip()
        if port_text:
            try:
                updates["proxy_port"] = int(port_text)
            except Exception:
                self._emit_message("Proxy port must be a number")
                return
        else:
            updates["proxy_port"] = None

        browser_settings: Dict[str, Any] = {}
        for key, value in {
            "locale": locale,
            "timezone": timezone,
            "user_agent": user_agent,
            "webgl_vendor": webgl_vendor,
            "gpu_vendor": webgl_vendor,
        }.items():
            value = str(value or "").strip()
            if value:
                browser_settings[key] = value
        cpu_text = str(hardware_concurrency or "").strip()
        if cpu_text:
            try:
                browser_settings["hardware_concurrency"] = int(cpu_text)
            except Exception:
                self._emit_message("CPU cores must be a number")
                return
        settings_key = "cloakbrowser_settings" if str(engine or "").lower() == "cloakbrowser" else "camoufox_settings"
        if browser_settings:
            updates[settings_key] = browser_settings
        else:
            updates["__delete_keys__"] = [settings_key]
        client = self._server_client()
        if server_enabled() and client:
            acc = self._server_account(original_name)
            if not acc:
                self._emit_message("Profile not found")
                return
            profile = acc.get("_server_profile") if isinstance(acc.get("_server_profile"), dict) else {}
            existing_settings = profile.get("settings") if isinstance(profile.get("settings"), dict) else {}
            merged_settings = dict(existing_settings)
            merged_settings.update(browser_settings)
            try:
                proxy_id = self._server_proxy_id_from_fields(
                    client,
                    stage=stage,
                    proxy_host=proxy_host,
                    proxy_port=proxy_port,
                    proxy_user=proxy_user,
                    proxy_password=proxy_password,
                )
                client.update_profile(str(acc.get("id") or ""), {
                    "name": clean_name,
                    "group_name": str(stage or "").strip() or "Default",
                    "browser_engine": str(engine or "camoufox").lower(),
                    "proxy_id": proxy_id,
                    "settings": merged_settings,
                })
            except ServerClientError as exc:
                self._emit_message(f"Cannot save server profile: {exc}")
                return
            self._emit_message(f"Server profile {clean_name} saved")
            self.refresh()
            return
        try:
            db_update_account(original_name, updates)
        except Exception as exc:
            self._emit_message(f"Cannot save profile: {exc}")
            return
        self._emit_message(f"Profile {clean_name} saved")
        self.refresh()

    @pyqtSlot(str)
    def deleteProfile(self, name: str) -> None:  # noqa: N802
        name = str(name or "").strip()
        if server_enabled() and not self._ensure_allowed("admin"):
            return
        if not name:
            return
        self.stopProfile(name)
        client = self._server_client()
        if server_enabled() and client:
            acc = self._server_account(name)
            if not acc:
                return
            try:
                client.delete_profile(str(acc.get("id") or ""))
            except ServerClientError as exc:
                self._emit_message(f"Cannot delete server profile: {exc}")
                return
            self._emit_message(f"Server profile {name} deleted")
            self.refresh()
            return
        db_delete_account(name)
        self._emit_message(f"Profile {name} deleted")
        self.refresh()

    @pyqtSlot(str)
    def startProfile(self, name: str) -> None:  # noqa: N802
        name = str(name or "").strip()
        if not name or name in self._live_browsers:
            return
        if server_enabled() and not self._ensure_allowed("operator"):
            return
        client = self._server_client() if server_enabled() else None
        acc = self._server_account(name) if client else next((item for item in db_get_accounts() if str(item.get("name") or "") == name), None)
        if not acc:
            self._emit_message(f"Profile {name} not found")
            return
        if client:
            profile_id = str(acc.get("id") or "")
            try:
                client.lock_profile(profile_id, ttl_minutes=LOCK_TTL_MINUTES)
                client.start_profile(profile_id)
                self._live_server_profile_ids[name] = profile_id
                self._ensure_heartbeat_timer()
            except ServerClientError as exc:
                self._emit_message(f"Cannot lock/start server profile: {exc}")
                return
        proxy = self._proxy_for(acc)
        engine = str(acc.get("_browser_engine") or acc.get("browser_engine") or "camoufox")
        settings = self._settings_dict(acc.get("cloakbrowser_settings") if engine == "cloakbrowser" else acc.get("camoufox_settings"))
        browser = BrowserInterface(
            profile_name=name,
            proxy=proxy,
            keep_browser_open=True,
            browser_engine=engine,
            browser_settings=settings,
        )
        browser.add_close_callback(lambda: QTimer.singleShot(0, lambda: self._on_browser_closed(name, browser)))
        self._live_browsers[name] = browser
        self._emit_message(f"Starting browser for {name}")
        self.refresh()

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(browser.start())
            except Exception as exc:
                LOGGER.exception("Browser start failed for %s", name)
                QTimer.singleShot(0, lambda exc=exc: self._on_browser_failed(name, browser, exc))
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _proxy_for(self, acc: Dict[str, Any]) -> str:
        scheme = str(acc.get("proxy_scheme") or "socks5").strip() or "socks5"
        host = str(acc.get("proxy_host") or "")
        port = acc.get("proxy_port")
        user = str(acc.get("proxy_user") or "")
        pwd = str(acc.get("proxy_password") or "")
        if not (host and port):
            return ""
        if user and pwd:
            return f"{scheme}://{user}:{pwd}@{host}:{port}"
        return f"{scheme}://{host}:{port}"

    def _on_browser_failed(self, name: str, browser: BrowserInterface, exc: Exception) -> None:
        if self._live_browsers.get(name) is browser:
            self._live_browsers.pop(name, None)
        self._server_release_profile(name)
        self._emit_message(f"Cannot start {name}: {exc}")
        self.refresh()

    def _on_browser_closed(self, name: str, browser: BrowserInterface) -> None:
        if self._live_browsers.get(name) is browser:
            self._live_browsers.pop(name, None)
        self._server_release_profile(name)
        self._emit_message(f"Browser closed for {name}")
        self.refresh()

    def _server_release_profile(self, name: str) -> None:
        profile_id = self._live_server_profile_ids.pop(str(name or ""), "")
        self._ensure_heartbeat_timer()
        client = self._server_client()
        if not profile_id or not client:
            return
        try:
            client.stop_profile(profile_id)
            client.unlock_profile(profile_id)
        except Exception:
            LOGGER.exception("Cannot release server profile %s", profile_id)

    def _ensure_heartbeat_timer(self) -> None:
        if self._live_server_profile_ids:
            if not self._heartbeat_timer.isActive():
                self._heartbeat_timer.start()
        elif self._heartbeat_timer.isActive():
            self._heartbeat_timer.stop()

    def _heartbeat_server_profiles(self) -> None:
        if self._heartbeat_in_flight or not self._live_server_profile_ids:
            self._ensure_heartbeat_timer()
            return
        client = self._server_client()
        if not client:
            self._ensure_heartbeat_timer()
            return
        items = dict(self._live_server_profile_ids)
        self._heartbeat_in_flight = True

        def worker() -> None:
            failed: List[str] = []
            for name, profile_id in items.items():
                try:
                    client.heartbeat_profile_lock(profile_id, ttl_minutes=LOCK_TTL_MINUTES)
                except Exception:
                    LOGGER.exception("Profile heartbeat failed for %s", name)
                    failed.append(name)
            QTimer.singleShot(0, lambda: self._on_heartbeat_finished(failed))

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot(str)
    def runHealthCheck(self, name: str) -> None:  # noqa: N802
        name = str(name or "").strip()
        if not name or name in self._live_browsers:
            self._emit_message("Stop the browser before running a health check")
            return
        account = self._server_account(name) if server_enabled() and self._server_client() else next((item for item in db_get_accounts() if str(item.get("name") or "") == name), None)
        if not account:
            self._emit_message(f"Profile {name} not found")
            return
        self._emit_message(f"Running health check for {name}")

        def worker() -> None:
            browser = None
            try:
                engine = str(account.get("_browser_engine") or account.get("browser_engine") or "camoufox")
                settings = self._settings_dict(account.get("cloakbrowser_settings") if engine == "cloakbrowser" else account.get("camoufox_settings"))
                browser = BrowserInterface(profile_name=name, proxy=self._proxy_for(account), keep_browser_open=False, browser_engine=engine, browser_settings=settings)

                async def inspect() -> dict:
                    await browser.start()
                    try:
                        signals = await browser.page.evaluate("""() => ({
                            userAgent: navigator.userAgent,
                            language: navigator.language,
                            languages: navigator.languages,
                            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                            hardwareConcurrency: navigator.hardwareConcurrency,
                            platform: navigator.platform,
                            screen: { width: screen.width, height: screen.height, colorDepth: screen.colorDepth },
                            webgl: (() => { const c = document.createElement('canvas'); const gl = c.getContext('webgl'); return gl ? { vendor: gl.getParameter(gl.VENDOR), renderer: gl.getParameter(gl.RENDERER) } : null; })()
                        })""")
                        geo = browser._proxy_service.fetch_country() if browser.proxy else {}
                        return {"signals": signals, "geo": geo}
                    finally:
                        await browser.close(force=True)

                data = asyncio.run(inspect())
                signals = data.get("signals") if isinstance(data.get("signals"), dict) else {}
                geo = data.get("geo") if isinstance(data.get("geo"), dict) else {}
                previous = account.get("health_check")
                if not isinstance(previous, dict):
                    previous = (account.get("camoufox_settings") or account.get("cloakbrowser_settings") or {}).get("health_check", {})
                fingerprint = hashlib.sha256(json.dumps({
                    "userAgent": signals.get("userAgent"), "language": signals.get("language"), "timezone": signals.get("timezone"),
                    "hardwareConcurrency": signals.get("hardwareConcurrency"), "platform": signals.get("platform"), "screen": signals.get("screen"), "webgl": signals.get("webgl"),
                }, sort_keys=True).encode("utf-8")).hexdigest()
                warnings = []
                configured_locale = str(settings.get("locale") or "").lower()
                if configured_locale and not str(signals.get("language") or "").lower().startswith(configured_locale.split("-")[0]):
                    warnings.append("Configured locale does not match browser language")
                configured_timezone = str(settings.get("timezone") or "")
                if configured_timezone and configured_timezone != str(signals.get("timezone") or ""):
                    warnings.append("Configured timezone does not match browser timezone")
                if browser.proxy and not geo.get("country_code"):
                    warnings.append("Proxy geo lookup failed")
                if isinstance(previous, dict) and previous.get("fingerprint") and previous.get("fingerprint") != fingerprint:
                    warnings.append("Browser fingerprint changed since the last health check")
                geo_summary = {
                    "ip": str(geo.get("ip") or ""), "country": str(geo.get("country_code") or geo.get("country") or ""),
                    "city": str(geo.get("city") or ""), "asn": str((geo.get("connection") or {}).get("asn") if isinstance(geo.get("connection"), dict) else geo.get("asn") or ""),
                }
                report = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "status": "warning" if warnings else "ready", "warnings": warnings, "geo": geo_summary, "signals": signals, "fingerprint": fingerprint}
                if server_enabled() and self._server_client():
                    remote = self._server_account(name)
                    if remote:
                        remote_settings = dict(remote.get("camoufox_settings") or remote.get("cloakbrowser_settings") or {})
                        remote_settings["health_check"] = report
                        self._server_client().update_profile(str(remote.get("id") or ""), {"settings": remote_settings})
                else:
                    db_update_account(name, {"health_check": report})
                status = "ready" if not warnings else f"warning: {'; '.join(warnings)}"
                self._emit_message(f"Health check {name}: {status}")
            except Exception as exc:
                LOGGER.exception("Health check failed for %s", name)
                self._emit_message(f"Health check failed for {name}: {exc}")
            finally:
                QTimer.singleShot(0, self.refresh)

        threading.Thread(target=worker, daemon=True).start()

    def _on_heartbeat_finished(self, failed: List[str]) -> None:
        self._heartbeat_in_flight = False
        if failed:
            self._emit_message("Profile lock heartbeat failed: " + ", ".join(failed))
        self._ensure_heartbeat_timer()
        self.refresh()

    @pyqtSlot(str)
    def stopProfile(self, name: str) -> None:  # noqa: N802
        name = str(name or "").strip()
        browser = self._live_browsers.pop(name, None)
        if browser is None:
            self._server_release_profile(name)
            self.refresh()
            return

        def worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(browser.close(force=True))
            except Exception:
                LOGGER.exception("Browser stop failed for %s", name)
            finally:
                loop.close()
                QTimer.singleShot(0, self.refresh)

        threading.Thread(target=worker, daemon=True).start()
        self._emit_message(f"Stopping browser for {name}")
        self.refresh()

    @pyqtSlot(str)
    def forceUnlockProfile(self, name: str) -> None:  # noqa: N802
        if not self._ensure_allowed("manager"):
            return
        acc = self._server_account(str(name or "")) if server_enabled() and self._server_client() else None
        if not acc:
            self._emit_message("Server profile not found")
            return
        profile_id = str(acc.get("id") or "")
        if not profile_id:
            return
        try:
            ServerClient().unlock_profile(profile_id)
        except ServerClientError as exc:
            self._emit_message(f"Cannot unlock profile: {exc}")
            return
        self._live_server_profile_ids.pop(str(name or ""), None)
        self._ensure_heartbeat_timer()
        self._emit_message(f"Profile {name} unlocked")
        self.refresh()

    @pyqtSlot(str, str)
    def setStage(self, name: str, stage: str) -> None:  # noqa: N802
        if server_enabled() and not self._ensure_allowed("manager"):
            return
        client = self._server_client()
        if server_enabled() and client:
            acc = self._server_account(str(name))
            if not acc:
                return
            try:
                client.update_profile(str(acc.get("id") or ""), {"group_name": str(stage or "").strip() or "Default"})
                self.refresh()
            except Exception as exc:
                self._emit_message(f"Cannot update server profile: {exc}")
            return
        try:
            db_update_account(str(name), {"stage": str(stage or "")})
            self.refresh()
        except Exception as exc:
            self._emit_message(f"Cannot update profile: {exc}")
