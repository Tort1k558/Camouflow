from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.storage.db import db_get_setting, db_set_setting


SERVER_ENABLED_KEY = "server_enabled"
SERVER_URL_KEY = "server_url"
SERVER_TOKEN_KEY = "server_token"
SERVER_REFRESH_TOKEN_KEY = "server_refresh_token"
SERVER_TEAM_ID_KEY = "server_team_id"
SERVER_EMAIL_KEY = "server_email"
DEFAULT_SERVER_URL = "http://localhost"
_REQUEST_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="camouflow-cloud")


class ServerClientError(RuntimeError):
    pass


def normalize_server_url(value: str) -> str:
    url = str(value or "").strip().rstrip("/")
    if not url:
        raise ServerClientError("Server URL is empty")

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ServerClientError("Server URL must be a full http(s) URL")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ServerClientError("Server URL must not include credentials, a path, or query parameters")
    return url


@dataclass
class ServerSession:
    enabled: bool
    url: str
    token: str
    refresh_token: str
    team_id: str
    email: str


def server_enabled() -> bool:
    return (db_get_setting(SERVER_ENABLED_KEY) or "").strip().lower() in {"1", "true", "yes", "on"}


def get_server_session() -> ServerSession:
    stored_url = (db_get_setting(SERVER_URL_KEY) or "").strip()
    return ServerSession(
        enabled=server_enabled(),
        url=stored_url.rstrip("/") or DEFAULT_SERVER_URL,
        token=(db_get_setting(SERVER_TOKEN_KEY) or "").strip(),
        refresh_token=(db_get_setting(SERVER_REFRESH_TOKEN_KEY) or "").strip(),
        team_id=(db_get_setting(SERVER_TEAM_ID_KEY) or "").strip(),
        email=(db_get_setting(SERVER_EMAIL_KEY) or "").strip(),
    )


def save_server_session(*, enabled: bool, url: str, token: str = "", refresh_token: str = "", team_id: str = "", email: str = "") -> None:
    normalized_url = normalize_server_url(url) if enabled else (str(url or "").strip().rstrip("/") or DEFAULT_SERVER_URL)
    db_set_setting(SERVER_ENABLED_KEY, "true" if enabled else "false")
    db_set_setting(SERVER_URL_KEY, normalized_url)
    if token or not enabled:
        db_set_setting(SERVER_TOKEN_KEY, str(token or "").strip())
    if refresh_token or not enabled:
        db_set_setting(SERVER_REFRESH_TOKEN_KEY, str(refresh_token or "").strip())
    if team_id or not enabled:
        db_set_setting(SERVER_TEAM_ID_KEY, str(team_id or "").strip())
    if email or not enabled:
        db_set_setting(SERVER_EMAIL_KEY, str(email or "").strip())


def clear_server_session() -> None:
    save_server_session(enabled=False, url="", token="", refresh_token="", team_id="", email="")


class ServerClient:
    def __init__(self, session: Optional[ServerSession] = None) -> None:
        self.session = session or get_server_session()

    @property
    def configured(self) -> bool:
        return bool(self.session.enabled and self.session.url and self.session.token and self.session.team_id)

    def _url(self, path: str) -> str:
        if not self.session.url:
            raise ServerClientError("Server URL is empty")
        path = "/" + str(path or "").lstrip("/")
        return f"{self.session.url}{path}"

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        auth: bool = True,
        retry_refresh: bool = True,
    ) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth and self.session.token:
            headers["Authorization"] = f"Bearer {self.session.token}"
        method = method.upper()
        attempts = 2 if method == "GET" else 1
        for attempt in range(attempts):
            req = urllib.request.Request(self._url(path), data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    raw = resp.read()
                    if not raw:
                        return None
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 401 and auth and retry_refresh and self.session.refresh_token:
                    self.refresh_token()
                    return self.request(method, path, payload, auth=auth, retry_refresh=False)
                detail = exc.read().decode("utf-8", errors="ignore")
                try:
                    parsed = json.loads(detail)
                    detail = str(parsed.get("detail") or detail)
                except Exception:
                    pass
                raise ServerClientError(f"{exc.code}: {detail}") from exc
            except Exception as exc:
                if attempt + 1 < attempts:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise ServerClientError(str(exc)) from exc
        raise ServerClientError("Cloud request failed")

    def request_async(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        auth: bool = True,
    ) -> Future:
        """Run a Cloud request off the QML thread with retries only for idempotent GET requests."""
        return _REQUEST_EXECUTOR.submit(self._request_async_safe, method, path, payload, auth)

    def _request_async_safe(self, method: str, path: str, payload: Optional[Dict[str, Any]], auth: bool) -> Any:
        attempts = 2 if str(method).upper() == "GET" else 0
        for attempt in range(attempts + 1):
            try:
                return self.request(method, path, payload, auth=auth)
            except ServerClientError:
                if attempt >= attempts:
                    raise
                time.sleep(0.5 * (2 ** attempt))
        return None

    def login(self, url: str, email: str, password: str) -> Dict[str, Any]:
        self.session = ServerSession(enabled=True, url=normalize_server_url(url), token="", refresh_token="", team_id="", email=email)
        auth_payload = self.request(
            "POST",
            "/api/v1/auth/login",
            {"email": email, "password": password},
            auth=False,
        )
        token = str(auth_payload.get("access_token") or "")
        refresh_token = str(auth_payload.get("refresh_token") or "")
        if not token:
            raise ServerClientError("Server did not return access token")
        self.session.token = token
        self.session.refresh_token = refresh_token
        teams = self.request("GET", "/api/v1/teams")
        team_id = str(teams[0].get("id") or "") if teams else ""
        self.session.team_id = team_id
        save_server_session(enabled=True, url=self.session.url, token=token, refresh_token=refresh_token, team_id=team_id, email=email)
        return {"token": token, "teams": teams, "team_id": team_id}

    def refresh_token(self) -> None:
        if not self.session.refresh_token:
            raise ServerClientError("Refresh token is empty")
        payload = self.request("POST", "/api/v1/auth/refresh", {"refresh_token": self.session.refresh_token}, auth=False, retry_refresh=False)
        self.session.token = str(payload.get("access_token") or "")
        self.session.refresh_token = str(payload.get("refresh_token") or "")
        save_server_session(
            enabled=True,
            url=self.session.url,
            token=self.session.token,
            refresh_token=self.session.refresh_token,
            team_id=self.session.team_id,
            email=self.session.email,
        )

    def logout(self) -> None:
        if self.session.refresh_token:
            self.request("POST", "/api/v1/auth/logout", {"refresh_token": self.session.refresh_token}, retry_refresh=False)

    def teams(self) -> List[Dict[str, Any]]:
        return list(self.request("GET", "/api/v1/teams") or [])

    def me(self) -> Dict[str, Any]:
        return dict(self.request("GET", "/api/v1/auth/me") or {})

    def context(self) -> Dict[str, Any]:
        return dict(self.request("GET", "/api/v1/auth/context") or {})

    def team_members(self) -> List[Dict[str, Any]]:
        return list(self.request("GET", f"/api/v1/teams/{self.session.team_id}/members") or [])

    def current_role(self) -> str:
        me = self.me()
        user_id = str(me.get("id") or "")
        for member in self.team_members():
            if str(member.get("user_id") or "") == user_id:
                return str(member.get("role") or "")
        return "owner" if me.get("is_superadmin") else ""

    def add_member(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/members", payload) or {})

    def create_invite(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/invites", payload) or {})

    def accept_invite(self, invite_id: str) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/auth/invites/{invite_id}/accept", {}) or {})

    def update_member(self, member_id: str, role: str) -> Dict[str, Any]:
        return dict(self.request("PATCH", f"/api/v1/teams/{self.session.team_id}/members/{member_id}", {"role": role}) or {})

    def delete_member(self, member_id: str) -> None:
        self.request("DELETE", f"/api/v1/teams/{self.session.team_id}/members/{member_id}")

    def create_password_reset(self, member_id: str) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/members/{member_id}/password-reset", {}) or {})

    def profiles(self) -> List[Dict[str, Any]]:
        return list(self.request("GET", f"/api/v1/teams/{self.session.team_id}/profiles") or [])

    def create_profile(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/profiles", payload) or {})

    def update_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("PATCH", f"/api/v1/teams/{self.session.team_id}/profiles/{profile_id}", payload) or {})

    def delete_profile(self, profile_id: str) -> None:
        self.request("DELETE", f"/api/v1/teams/{self.session.team_id}/profiles/{profile_id}")

    def lock_profile(self, profile_id: str, *, force: bool = False, ttl_minutes: int = 3) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/profiles/{profile_id}/lock", {"force": force, "ttl_minutes": int(ttl_minutes)}) or {})

    def heartbeat_profile_lock(self, profile_id: str, *, ttl_minutes: int = 3) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/profiles/{profile_id}/heartbeat", {"ttl_minutes": int(ttl_minutes)}) or {})

    def unlock_profile(self, profile_id: str) -> None:
        self.request("POST", f"/api/v1/teams/{self.session.team_id}/profiles/{profile_id}/unlock", {})

    def start_profile(self, profile_id: str) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/profiles/{profile_id}/start", {}) or {})

    def stop_profile(self, profile_id: str) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/profiles/{profile_id}/stop", {}) or {})

    def proxies(self) -> List[Dict[str, Any]]:
        return list(self.request("GET", f"/api/v1/teams/{self.session.team_id}/proxies") or [])

    def create_proxy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/proxies", payload) or {})

    def update_proxy(self, proxy_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("PATCH", f"/api/v1/teams/{self.session.team_id}/proxies/{proxy_id}", payload) or {})

    def delete_proxy(self, proxy_id: str) -> None:
        self.request("DELETE", f"/api/v1/teams/{self.session.team_id}/proxies/{proxy_id}")

    def check_proxy(self, proxy_id: str) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/proxies/{proxy_id}/check", {}) or {})

    def scenarios(self) -> List[Dict[str, Any]]:
        return list(self.request("GET", f"/api/v1/teams/{self.session.team_id}/scenarios") or [])

    def create_scenario(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/scenarios", payload) or {})

    def update_scenario(self, scenario_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("PATCH", f"/api/v1/teams/{self.session.team_id}/scenarios/{scenario_id}", payload) or {})

    def delete_scenario(self, scenario_id: str) -> None:
        self.request("DELETE", f"/api/v1/teams/{self.session.team_id}/scenarios/{scenario_id}")

    def market_scenarios(self, query: str = "", category: str = "", sort: str = "popular") -> List[Dict[str, Any]]:
        params = urllib.parse.urlencode({
            "query": str(query or ""),
            "category": str(category or ""),
            "sort": str(sort or "popular"),
        })
        return list(self.request("GET", f"/api/v1/market/scenarios?{params}", auth=False) or [])

    def market_scenario(self, scenario_id: str) -> Dict[str, Any]:
        return dict(self.request("GET", f"/api/v1/market/scenarios/{scenario_id}", auth=False) or {})

    def download_market_scenario(self, scenario_id: str) -> Dict[str, Any]:
        return dict(self.request(
            "POST",
            f"/api/v1/market/scenarios/{scenario_id}/download",
            {},
            auth=bool(self.session.token),
        ) or {})

    def publish_market_scenario(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/market/scenarios", payload) or {})

    def scenario_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self.request("GET", f"/api/v1/teams/{self.session.team_id}/scenario-runs?limit={int(limit)}") or [])

    def create_scenario_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("POST", f"/api/v1/teams/{self.session.team_id}/scenario-runs", payload) or {})

    def update_scenario_run(self, run_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self.request("PATCH", f"/api/v1/teams/{self.session.team_id}/scenario-runs/{run_id}", payload) or {})

    def audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(self.request("GET", f"/api/v1/teams/{self.session.team_id}/audit-log?limit={int(limit)}") or [])

    def license(self) -> Dict[str, Any]:
        return dict(self.request("GET", f"/api/v1/teams/{self.session.team_id}/license") or {})

    def export_backup(self) -> Dict[str, Any]:
        return dict(self.request("GET", "/api/v1/backups/export") or {})


ROLE_RANK = {"viewer": 0, "operator": 1, "manager": 2, "admin": 3, "owner": 4}


def role_allows(role: str, min_role: str) -> bool:
    return ROLE_RANK.get(str(role or "").lower(), -1) >= ROLE_RANK.get(str(min_role or "").lower(), 999)
