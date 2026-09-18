from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from app.services.server_client import ServerClient
from app.storage.db import (
    db_add_account,
    db_get_accounts,
    db_get_scenarios,
    db_get_setting,
    db_save_scenario,
    db_set_setting,
    db_update_account,
)


SYNC_STATE_KEY = "cloud_sync_state_v1"
SYNC_CONFLICTS_KEY = "cloud_sync_conflicts_v1"


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
        self.state = self._load_state()

    def sync(self, upload_cookies: bool = False) -> CloudSyncResult:
        result = CloudSyncResult()
        self._upload_cookies = bool(upload_cookies)
        self._sync_proxies(result)
        self._sync_profiles(result)
        self._sync_scenarios(result)
        self._save_state()
        db_set_setting(SYNC_CONFLICTS_KEY, json.dumps(result.conflict_items, ensure_ascii=False))
        return result

    # --- conflict resolution -------------------------------------------------

    def pending_conflicts(self) -> list[dict]:
        try:
            items = json.loads(db_get_setting(SYNC_CONFLICTS_KEY) or "[]")
        except Exception:
            items = []
        return items if isinstance(items, list) else []

    def resolve(self, resource: str, key: str, choice: str) -> str:
        """Resolve a sync conflict: 'local' pushes the local version to the
        server, 'remote' applies the server version locally."""
        conflicts = self.pending_conflicts()
        item = next((c for c in conflicts if c.get("resource") == resource and str(c.get("key")) == str(key)), None)
        if not item:
            return "Conflict not found"
        try:
            if choice == "local":
                self._resolve_keep_local(resource, key, str(item.get("remote_id") or ""))
            else:
                self._resolve_keep_remote(resource, key, str(item.get("remote_id") or ""))
        except ServerClientError as exc:
            return f"Resolve failed: {exc}"
        remaining = [c for c in conflicts if c is not item]
        db_set_setting(SYNC_CONFLICTS_KEY, json.dumps(remaining, ensure_ascii=False))
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
            payload = self._profile_payload(account, None)
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
        if update is not None:
            updated = update(remote_id, payload)
        else:
            updated = create(payload)
        records = self._resource_state(resource)
        records[key] = {"remote_id": remote_id or str(updated.get("id") or ""), "local_hash": self._fingerprint(payload), "remote_hash": self._fingerprint(updated)}
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
            db_update_account(key, account)
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
        records[key] = {"remote_id": remote_id, "local_hash": self._fingerprint(payload), "remote_hash": self._fingerprint(payload)}
        self._save_state()

    def _cookie_snapshot(self, profile_name: str) -> str:
        """Read the profile cookie jar as JSON (opt-in upload)."""
        try:
            from app.ui.bridge.profiles import ProfilesBridge  # local import avoids a cycle
            rows = ProfilesBridge._read_cookie_rows(profile_name)
            return json.dumps(rows, ensure_ascii=False) if rows else ""
        except Exception:
            return ""

    def _load_state(self) -> dict[str, Any]:
        try:
            raw = json.loads(db_get_setting(SYNC_STATE_KEY) or "{}")
        except Exception:
            raw = {}
        if not isinstance(raw, dict) or raw.get("team_id") != self.team_id:
            return {"team_id": self.team_id, "resources": {}}
        raw.setdefault("resources", {})
        return raw

    def _save_state(self) -> None:
        db_set_setting(SYNC_STATE_KEY, json.dumps(self.state, ensure_ascii=False, sort_keys=True))

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

    def _merge(
        self,
        resource: str,
        local_key: str,
        local_payload: dict[str, Any],
        remote_rows: dict[str, dict[str, Any]],
        create_remote: Callable[[dict[str, Any]], dict[str, Any]],
        update_remote: Callable[[str, dict[str, Any]], dict[str, Any]],
        result: CloudSyncResult,
    ) -> dict[str, Any] | None:
        records = self._resource_state(resource)
        record = records.get(local_key, {})
        remote_id = str(record.get("remote_id") or "")
        remote = remote_rows.get(remote_id)
        local_hash = self._fingerprint(local_payload)

        if remote is None and not remote_id:
            remote = next((row for row in remote_rows.values() if str(row.get("name") or row.get("value") or "") == local_key), None)
            if remote:
                remote_id = str(remote.get("id") or "")
        if remote is None:
            created = create_remote(local_payload)
            records[local_key] = {"remote_id": str(created.get("id") or ""), "local_hash": local_hash, "remote_hash": self._fingerprint(created)}
            result.uploaded += 1
            return created

        remote_hash = self._fingerprint(remote)
        previous_local = str(record.get("local_hash") or "")
        previous_remote = str(record.get("remote_hash") or "")
        if not previous_local and local_hash != remote_hash:
            result.conflicts.append(f"{resource}: {local_key}")
            result.conflict_items.append({"resource": resource, "key": local_key, "remote_id": remote_id})
            records[local_key] = {"remote_id": remote_id, "local_hash": local_hash, "remote_hash": remote_hash}
            return remote
        if previous_local and local_hash != previous_local and remote_hash != previous_remote:
            result.conflicts.append(f"{resource}: {local_key}")
            result.conflict_items.append({"resource": resource, "key": local_key, "remote_id": remote_id})
            return remote
        if local_hash != remote_hash and local_hash != previous_local:
            remote = update_remote(remote_id, local_payload)
            remote_hash = self._fingerprint(remote)
            result.uploaded += 1
        records[local_key] = {"remote_id": remote_id, "local_hash": local_hash, "remote_hash": remote_hash}
        return remote

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
        records = self._resource_state("proxies")
        for row in remote.values():
            value = str(row.get("value") or "").strip()
            if not value or value in local_values:
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
            definition = row.get("definition") if isinstance(row.get("definition"), dict) else {}
            steps = definition.get("steps") if isinstance(definition.get("steps"), list) else []
            db_save_scenario(name, steps, str(row.get("description") or ""))
            local_payload = {"name": name, "description": str(row.get("description") or ""), "definition": {"steps": steps}}
            records[name] = {"remote_id": str(row.get("id") or ""), "local_hash": self._fingerprint(local_payload), "remote_hash": self._fingerprint(row)}
            result.downloaded += 1
