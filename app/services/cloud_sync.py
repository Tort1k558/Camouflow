from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from app.services.server_client import ServerClient, ServerClientError
from app.storage.db import (
    db_add_account,
    db_delete_account,
    db_delete_scenario,
    db_get_accounts,
    db_get_scenario,
    db_get_scenarios,
    db_get_setting,
    db_save_scenario,
    db_set_setting,
    db_update_account,
)

SYNC_STATE_KEY = "cloud_sync_state_v1"
SYNC_CONFLICTS_KEY = "cloud_sync_conflicts_v1"

SYNC_WORKSPACE_KEY = "cloud_sync_workspace_v2"
_SYNC_LOCK = Lock()


def _sync_operation(func):
    @wraps(func)
    def guarded(self, *args, **kwargs):
        if not _SYNC_LOCK.acquire(blocking=False):
            raise ServerClientError("Another synchronization is already running")
        try:
            if not self.client.configured:
                raise ServerClientError("Select a cloud team first")
            owner = db_get_setting(SYNC_WORKSPACE_KEY)
            if owner and owner != self.workspace_id:
                raise ServerClientError("Local data is linked to another server/team. Switch back to that team to synchronize; no data was transferred.")
            if not owner:
                legacy = json.loads(db_get_setting(SYNC_STATE_KEY) or "{}")
                if legacy.get("team_id") and legacy["team_id"] != self.team_id:
                    raise ServerClientError("Local data was synchronized with another team. Switch back before synchronizing.")
                db_set_setting(SYNC_WORKSPACE_KEY, self.workspace_id)
            self.state = self._load_state()
            return func(self, *args, **kwargs)
        finally:
            _SYNC_LOCK.release()
    return guarded


@dataclass
class CloudSyncResult:
    uploaded: int = 0
    downloaded: int = 0
    conflicts: list[str] = field(default_factory=list)
    conflict_items: list[dict] = field(default_factory=list)


class CloudWorkspaceSync:
    """Merge local workspace data with a team without destructive writes."""

    def __init__(self, client: ServerClient) -> None:
        self.client = client
        self.team_id = client.session.team_id
        self.workspace_id = f"{client.session.url.rstrip('/')}|{self.team_id}"
        self.state_key = f"{SYNC_STATE_KEY}:{self.workspace_id}"
        self.conflicts_key = f"{SYNC_CONFLICTS_KEY}:{self.workspace_id}"
        self.state = self._load_state()

    @_sync_operation
    def sync(self, upload_cookies: bool = False) -> CloudSyncResult:
        result = CloudSyncResult(conflict_items=self.pending_conflicts())
        self._upload_cookies = bool(upload_cookies)
        self._sync_proxies(result)
        self._sync_profiles(result)
        self._sync_scenarios(result)
        self._save_state()
        db_set_setting(self.conflicts_key, json.dumps(result.conflict_items, ensure_ascii=False))
        return result

    # --- conflict resolution -------------------------------------------------

    def pending_conflicts(self) -> list[dict]:
        try:
            raw = db_get_setting(self.conflicts_key)
            if raw is None:
                legacy = json.loads(db_get_setting(SYNC_STATE_KEY) or "{}")
                if legacy.get("team_id") == self.team_id:
                    raw = db_get_setting(SYNC_CONFLICTS_KEY)
            items = json.loads(raw or "[]")
        except Exception:
            items = []
        return items if isinstance(items, list) else []

    @_sync_operation
    def resolve(self, resource: str, key: str, choice: str) -> str:
        """Resolve a sync conflict: 'local' pushes the local version to the
        server, 'remote' applies the server version locally."""
        if choice not in {"local", "remote"}:
            return "Invalid conflict choice"
        conflicts = self.pending_conflicts()
        item = next((c for c in conflicts if c.get("resource") == resource and str(c.get("key")) == str(key)), None)
        if not item:
            return "Conflict not found"
        try:
            if item.get("reason") == "remote_deleted":
                if choice == "local":
                    self._resolve_keep_local(resource, key, "")
                else:
                    self._delete_local(resource, key)
                    self._resource_state(resource).pop(key, None)
                    self._save_state()
            elif item.get("reason") == "local_deleted":
                if choice == "local":
                    getattr(self.client, {"profiles": "delete_profile", "proxies": "delete_proxy", "scenarios": "delete_scenario"}[resource])(item["remote_id"])
                    self._resource_state(resource).pop(key, None)
                    self._save_state()
                else:
                    self._resolve_keep_remote(resource, key, item["remote_id"])
            elif choice == "local":
                self._resolve_keep_local(resource, key, str(item.get("remote_id") or ""))
            else:
                self._resolve_keep_remote(resource, key, str(item.get("remote_id") or ""))
        except ServerClientError as exc:
            return f"Resolve failed: {exc}"
        remaining = [c for c in conflicts if c is not item]
        db_set_setting(self.conflicts_key, json.dumps(remaining, ensure_ascii=False))
        return ""

    def _local_proxy_group(self, value: str) -> str:
        try:
            pools = json.loads(db_get_setting("proxy_pools") or "{}")
        except Exception:
            return ""
        for group, pool in pools.items():
            for entry in (pool.get("proxies", []) if isinstance(pool, dict) else []):
                if isinstance(entry, dict) and str(entry.get("value") or "") == value:
                    return str(group)
        return ""

    def _resolve_keep_local(self, resource: str, key: str, remote_id: str) -> None:
        if resource == "proxies":
            payload = {"value": key, "group_name": self._local_proxy_group(key) or "Default"}
            update = self.client.update_proxy if remote_id else None
            create = self.client.create_proxy
        elif resource == "profiles":
            account = next((a for a in db_get_accounts() if str(a.get("name") or "") == key), None)
            if account is None:
                raise ServerClientError("Local profile not found")
            proxy_ids = {str(row.get("value") or ""): row["id"] for row in self.client.proxies()}
            payload = self._profile_payload(account, proxy_ids.get(self._proxy_value(account)))
            update = self.client.update_profile if remote_id else None
            create = self.client.create_profile
        elif resource == "scenarios":
            scenario = db_get_scenario(key)
            if scenario is None:
                raise ServerClientError("Local scenario not found")
            payload = {"name": key, "description": scenario.description or "", "definition": {"steps": scenario.steps or []}}
            update = self.client.update_scenario if remote_id else None
            create = self.client.create_scenario
        else:
            raise ServerClientError(f"Unknown resource {resource}")
        if resource == "profiles" and remote_id:
            row = next((r for r in self.client.profiles() if str(r.get("id")) == remote_id), None)
            self._preserve_cookie_snapshot(payload, row)
        if update is not None:
            updated = update(remote_id, payload)
        else:
            updated = create(payload)
        records = self._resource_state(resource)
        records[key] = {"remote_id": remote_id or str(updated.get("id") or ""), "local_hash": self._fingerprint(payload), "remote_hash": self._fingerprint(self._remote_payload(resource, updated)), "normalized": True}
        self._save_state()

    def _resolve_keep_remote(self, resource: str, key: str, remote_id: str) -> None:
        if resource == "proxies":
            row = next((r for r in self.client.proxies() if str(r.get("id")) == remote_id), None)
            if row is None:
                raise ServerClientError("Remote proxy not found")
            try:
                pools = json.loads(db_get_setting("proxy_pools") or "{}")
            except Exception:
                pools = {}
            group = str(row.get("group_name") or "Default")
            for existing_pool in pools.values():
                existing_pool["proxies"] = [e for e in existing_pool.get("proxies", []) if not isinstance(e, dict) or e.get("value") != key]
            pool = pools.setdefault(group, {"proxies": []})
            entries = pool.setdefault("proxies", [])
            if not any(isinstance(e, dict) and str(e.get("value")) == str(row.get("value")) for e in entries):
                entries.append({"value": str(row.get("value")), "status": "unchecked"})
            db_set_setting("proxy_pools", json.dumps(pools, ensure_ascii=False))
            payload = {"value": str(row.get("value")), "group_name": group}
        elif resource == "profiles":
            row = next((r for r in self.client.profiles() if str(r.get("id")) == remote_id), None)
            if row is None:
                raise ServerClientError("Remote profile not found")
            values = {str(r.get("id") or ""): str(r.get("value") or "") for r in self.client.proxies()}
            account = self._profile_from_remote(row, values.get(str(row.get("proxy_id") or ""), ""))
            account["name"] = key
            if any(a.get("name") == key for a in db_get_accounts()):
                db_update_account(key, account)
            else:
                db_add_account(account)
            payload = self._profile_payload(account, row.get("proxy_id"))
        elif resource == "scenarios":
            row = next((r for r in self.client.scenarios() if str(r.get("id")) == remote_id), None)
            if row is None:
                raise ServerClientError("Remote scenario not found")
            definition = row.get("definition") if isinstance(row.get("definition"), dict) else {}
            steps = definition.get("steps") if isinstance(definition.get("steps"), list) else []
            db_save_scenario(key, steps, str(row.get("description") or ""))
            payload = {"name": key, "description": str(row.get("description") or ""), "definition": {"steps": steps}}
        else:
            raise ServerClientError(f"Unknown resource {resource}")
        records = self._resource_state(resource)
        records[key] = {"remote_id": remote_id, "local_hash": self._fingerprint(payload), "remote_hash": self._fingerprint(self._remote_payload(resource, row)), "normalized": True}
        self._save_state()

    def _cookie_snapshot(self, profile_name: str) -> str:
        """Read the profile cookie jar as JSON (opt-in upload)."""
        try:
            from app.ui.bridge.profiles import (
                ProfilesBridge,  # local import avoids a cycle
            )
            rows = ProfilesBridge._read_cookie_rows(profile_name)
            return json.dumps(rows, ensure_ascii=False) if rows else ""
        except Exception:
            return ""

    def _load_state(self) -> dict[str, Any]:
        try:
            raw = json.loads(db_get_setting(self.state_key) or db_get_setting(SYNC_STATE_KEY) or "{}")
        except Exception:
            raw = {}
        if not isinstance(raw, dict) or raw.get("team_id") != self.team_id:
            return {"team_id": self.team_id, "resources": {}}
        raw.setdefault("resources", {})
        return raw

    def _save_state(self) -> None:
        db_set_setting(self.state_key, json.dumps(self.state, ensure_ascii=False, sort_keys=True))

    def _resource_state(self, resource: str) -> dict[str, Any]:
        resources = self.state.setdefault("resources", {})
        return resources.setdefault(resource, {})

    @staticmethod
    def _fingerprint(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _profile_payload(account: dict[str, Any], proxy_id: str | None) -> dict[str, Any]:
        engine = str(account.get("_browser_engine") or account.get("browser_engine") or "camoufox").lower()
        settings = account.get("cloakbrowser_settings") if engine == "cloakbrowser" else account.get("camoufox_settings")
        settings = dict(settings) if isinstance(settings, dict) else {}
        if isinstance(account.get("extra_fields"), dict):
            settings["variables"] = account["extra_fields"]
        return {
            "name": str(account.get("name") or "").strip(),
            "group_name": str(account.get("stage") or "Default"),
            "browser_engine": engine,
            "proxy_id": proxy_id,
            "settings": settings,
        }

    @staticmethod
    def _profile_from_remote(row: dict[str, Any], proxy_value: str) -> dict[str, Any]:
        settings = dict(row.get("settings") or {})
        variables = settings.pop("variables", {})
        account: dict[str, Any] = {
            "name": str(row.get("name") or "").strip(),
            "stage": str(row.get("group_name") or "Default"),
            "_browser_engine": str(row.get("browser_engine") or "camoufox"),
            "extra_fields": variables if isinstance(variables, dict) else {},
        }
        if account["_browser_engine"] == "cloakbrowser":
            account["cloakbrowser_settings"] = settings
        else:
            account["camoufox_settings"] = settings
        account.update({"proxy_scheme": "", "proxy_host": "", "proxy_port": "", "proxy_user": "", "proxy_password": ""})
        account.update(CloudWorkspaceSync._proxy_fields(proxy_value))
        return account

    @staticmethod
    def _proxy_fields(value: str) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = urlsplit(value if "://" in value else f"socks5://{value}")
            if not parsed.hostname or not parsed.port:
                return {}
            return {
                "proxy_scheme": parsed.scheme or "socks5",
                "proxy_host": parsed.hostname,
                "proxy_port": parsed.port,
                "proxy_user": unquote(parsed.username or ""),
                "proxy_password": unquote(parsed.password or ""),
            }
        except ValueError:
            return {}

    @staticmethod
    def _proxy_value(account: dict[str, Any]) -> str:
        host = str(account.get("proxy_host") or "").strip()
        port = str(account.get("proxy_port") or "").strip()
        if not host or not port:
            return ""
        scheme = str(account.get("proxy_scheme") or "socks5").strip() or "socks5"
        user = str(account.get("proxy_user") or "").strip()
        password = str(account.get("proxy_password") or "").strip()
        return f"{scheme}://{user}:{password}@{host}:{port}" if user and password else f"{scheme}://{host}:{port}"

    @staticmethod
    def _preserve_cookie_snapshot(payload: dict, remote: dict | None) -> None:
        if remote and "cookies_snapshot" not in payload.get("settings", {}):
            snapshot = (remote.get("settings") or {}).get("cookies_snapshot")
            if snapshot:
                payload.setdefault("settings", {})["cookies_snapshot"] = snapshot

    @staticmethod
    def _remote_payload(resource: str, row: dict) -> dict:
        keys = {
            "profiles": ("name", "group_name", "browser_engine", "proxy_id", "settings"),
            "proxies": ("value", "group_name"),
            "scenarios": ("name", "description", "definition"),
        }[resource]
        return {key: row.get(key) for key in keys}

    def _delete_local(self, resource: str, key: str) -> None:
        if resource == "profiles":
            db_delete_account(key)  # Browser files are deliberately retained.
        elif resource == "scenarios":
            db_delete_scenario(key)
        elif resource == "proxies":
            pools = json.loads(db_get_setting("proxy_pools") or "{}")
            for pool in pools.values():
                pool["proxies"] = [e for e in pool.get("proxies", []) if not isinstance(e, dict) or e.get("value") != key]
            db_set_setting("proxy_pools", json.dumps(pools, ensure_ascii=False))

    def _conflict(self, result: CloudSyncResult, resource: str, key: str, remote_id: str, reason: str = "changed") -> None:
        result.conflicts.append(f"{resource}: {key} ({reason})")
        item = {"resource": resource, "key": key, "remote_id": remote_id, "reason": reason}
        result.conflict_items[:] = [c for c in result.conflict_items if (c.get("resource"), c.get("key")) != (resource, key)]
        result.conflict_items.append(item)

    def _merge(self, resource: str, local_key: str, local_payload: dict,
               remote_rows: dict, create_remote: Callable, update_remote: Callable,
               result: CloudSyncResult) -> dict | None:
        records = self._resource_state(resource)
        record = records.get(local_key, {})
        remote_id = str(record.get("remote_id") or "")
        remote = remote_rows.get(remote_id)
        local_hash = self._fingerprint(local_payload)
        if remote is None and remote_id:
            self._conflict(result, resource, local_key, remote_id, "remote_deleted")
            return None
        if remote is None:
            remote = next((r for r in remote_rows.values() if str(r.get("name") or r.get("value") or "") == local_key), None)
        if remote is None:
            remote = create_remote(local_payload)
            result.uploaded += 1
        else:
            remote_id = str(remote["id"])
            canonical = self._remote_payload(resource, remote)
            remote_hash = self._fingerprint(canonical)
            if any(c.get("resource") == resource and c.get("key") == local_key for c in result.conflict_items):
                return remote
            if local_hash != remote_hash:
                previous_local = record.get("local_hash")
                previous_remote = record.get("remote_hash")
                comparison = remote_hash if record.get("normalized") else self._fingerprint(remote)
                local_changed = local_hash != previous_local
                remote_changed = comparison != previous_remote
                if not previous_local or (local_changed and remote_changed):
                    self._conflict(result, resource, local_key, remote_id)
                    return remote
                if remote_changed:
                    self._resolve_keep_remote(resource, local_key, remote_id)
                    result.downloaded += 1
                    return remote
                if local_changed:
                    if resource == "profiles":
                        self._preserve_cookie_snapshot(local_payload, remote)
                    remote = update_remote(remote_id, local_payload)
                    result.uploaded += 1
        records[local_key] = {"remote_id": str(remote["id"]), "local_hash": local_hash,
                              "remote_hash": self._fingerprint(self._remote_payload(resource, remote)), "normalized": True}
        return remote

    def _skip_download(self, resource: str, row: dict, local_keys: set[str], result: CloudSyncResult) -> bool:
        for key, record in self._resource_state(resource).items():
            if record.get("remote_id") == str(row["id"]):
                if key not in local_keys:
                    self._conflict(result, resource, key, str(row["id"]), "local_deleted")
                return True
        return False

    def _sync_proxies(self, result: CloudSyncResult) -> None:
        try:
            pools = json.loads(db_get_setting("proxy_pools") or "{}")
        except Exception:
            pools = {}
        if not isinstance(pools, dict):
            pools = {}
        remote = {str(row.get("id") or ""): row for row in self.client.proxies()}
        local_values: set[str] = set()
        for group, pool in pools.items():
            for entry in (pool.get("proxies", []) if isinstance(pool, dict) else []):
                payload = entry if isinstance(entry, dict) else {}
                value = str(payload.get("value") or "").strip()
                if not value:
                    continue
                local_values.add(value)
                self._merge("proxies", value, {"value": value, "group_name": str(group or "Default")}, remote, self.client.create_proxy, self.client.update_proxy, result)
        pools = json.loads(db_get_setting("proxy_pools") or "{}")
        records = self._resource_state("proxies")
        for row in remote.values():
            value = str(row.get("value") or "").strip()
            if not value or value in local_values:
                continue
            if self._skip_download("proxies", row, local_values, result):
                continue
            group = str(row.get("group_name") or "Default")
            pool = pools.setdefault(group, {"proxies": []})
            pool.setdefault("proxies", []).append({"value": value, "status": str(row.get("status") or "unchecked")})
            records[value] = {"remote_id": str(row.get("id") or ""), "local_hash": self._fingerprint({"value": value, "group_name": group}), "remote_hash": self._fingerprint(row)}
            result.downloaded += 1
        db_set_setting("proxy_pools", json.dumps(pools, ensure_ascii=False))

    def _sync_profiles(self, result: CloudSyncResult) -> None:
        remote = {str(row.get("id") or ""): row for row in self.client.profiles()}
        proxy_ids = {str(row.get("value") or ""): str(row.get("id") or "") for row in self.client.proxies()}
        local_names: set[str] = set()
        for account in db_get_accounts():
            name = str(account.get("name") or "").strip()
            if not name:
                continue
            local_names.add(name)
            payload = self._profile_payload(account, proxy_ids.get(self._proxy_value(account)) or None)
            if getattr(self, "_upload_cookies", False):
                snapshot = self._cookie_snapshot(name)
                if snapshot:
                    payload.setdefault("settings", {})["cookies_snapshot"] = snapshot
            self._merge("profiles", name, payload, remote, self.client.create_profile, self.client.update_profile, result)
        records = self._resource_state("profiles")
        proxy_values = {str(row.get("id") or ""): str(row.get("value") or "") for row in self.client.proxies()}
        for row in remote.values():
            name = str(row.get("name") or "").strip()
            if not name or name in local_names:
                continue
            if self._skip_download("profiles", row, local_names, result):
                continue
            db_add_account(self._profile_from_remote(row, proxy_values.get(str(row.get("proxy_id") or ""), "")))
            records[name] = {"remote_id": str(row.get("id") or ""), "local_hash": self._fingerprint(self._profile_payload(self._profile_from_remote(row, proxy_values.get(str(row.get("proxy_id") or ""), "")), row.get("proxy_id"))), "remote_hash": self._fingerprint(row)}
            result.downloaded += 1

    def _sync_scenarios(self, result: CloudSyncResult) -> None:
        remote = {str(row.get("id") or ""): row for row in self.client.scenarios()}
        local_names: set[str] = set()
        for scenario in db_get_scenarios():
            name = str(scenario.name or "").strip()
            if not name:
                continue
            local_names.add(name)
            payload = {"name": name, "description": scenario.description or "", "definition": {"steps": scenario.steps or []}}
            self._merge("scenarios", name, payload, remote, self.client.create_scenario, self.client.update_scenario, result)
        records = self._resource_state("scenarios")
        for row in remote.values():
            name = str(row.get("name") or "").strip()
            if not name or name in local_names:
                continue
            if self._skip_download("scenarios", row, local_names, result):
                continue
            definition = row.get("definition") if isinstance(row.get("definition"), dict) else {}
            steps = definition.get("steps") if isinstance(definition.get("steps"), list) else []
            db_save_scenario(name, steps, str(row.get("description") or ""))
            local_payload = {"name": name, "description": str(row.get("description") or ""), "definition": {"steps": steps}}
            records[name] = {"remote_id": str(row.get("id") or ""), "local_hash": self._fingerprint(local_payload), "remote_hash": self._fingerprint(row)}
            result.downloaded += 1
