"""User/account bridge for QML."""

from __future__ import annotations

import json

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.services.server_client import (
    ServerClient,
    ServerClientError,
    clear_server_session,
    get_server_session,
    role_allows,
    save_server_session,
)
from app.storage.db import db_get_accounts, db_get_scenarios, db_get_setting, db_set_setting
from app.ui.bridge.models import DictListModel

ONBOARDING_COMPLETED_KEY = "onboarding_completed"


class UserBridge(QObject):
    changed = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._teams_model = DictListModel([
            "id", "name", "slug", "role", "plan", "license_status", "invited_by",
            "invited_by_email", "selected", "profiles", "proxies", "scenarios",
        ], parent=self)
        self._invites_model = DictListModel([
            "id", "team_id", "team_name", "team_slug", "role", "invited_by_email", "expires_at",
        ], parent=self)
        self._members_model = DictListModel(["id", "email", "full_name", "role"], parent=self)
        self._audit_model = DictListModel(["time", "action", "entity", "details"], parent=self)
        self._email = ""
        self._name = ""
        self._is_superadmin = False
        self._server_role = ""
        self._status = "Local mode"
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)
        self.refresh()

    @pyqtProperty(QObject, constant=True)
    def teamsModel(self) -> QObject:  # noqa: N802
        return self._teams_model

    @pyqtProperty(QObject, constant=True)
    def invitesModel(self) -> QObject:  # noqa: N802
        return self._invites_model

    @pyqtProperty(QObject, constant=True)
    def membersModel(self) -> QObject:  # noqa: N802
        return self._members_model

    @pyqtProperty(QObject, constant=True)
    def auditModel(self) -> QObject:  # noqa: N802
        return self._audit_model

    @pyqtProperty(bool, notify=changed)
    def serverEnabled(self) -> bool:  # noqa: N802
        return get_server_session().enabled

    @pyqtProperty(str, notify=changed)
    def serverUrl(self) -> str:  # noqa: N802
        return get_server_session().url

    @pyqtProperty(str, notify=changed)
    def email(self) -> str:
        return self._email

    @pyqtProperty(str, notify=changed)
    def fullName(self) -> str:  # noqa: N802
        return self._name

    @pyqtProperty(bool, notify=changed)
    def isSuperadmin(self) -> bool:  # noqa: N802
        return self._is_superadmin

    @pyqtProperty(str, notify=changed)
    def status(self) -> str:
        return self._status

    @pyqtProperty(str, notify=changed)
    def selectedTeamId(self) -> str:  # noqa: N802
        return get_server_session().team_id

    @pyqtProperty(str, notify=changed)
    def serverRole(self) -> str:  # noqa: N802
        return self._server_role

    @pyqtProperty(bool, notify=changed)
    def canManageTeam(self) -> bool:  # noqa: N802
        return role_allows(self._server_role, "admin") or self._is_superadmin

    @pyqtProperty(bool, notify=changed)
    def canViewCloud(self) -> bool:  # noqa: N802
        return role_allows(self._server_role, "viewer")

    @pyqtProperty(bool, notify=changed)
    def canRunCloud(self) -> bool:  # noqa: N802
        return role_allows(self._server_role, "operator")

    @pyqtProperty(bool, notify=changed)
    def canManageCloud(self) -> bool:  # noqa: N802
        return role_allows(self._server_role, "manager")

    @pyqtProperty(bool, notify=changed)
    def canAdminCloud(self) -> bool:  # noqa: N802
        return role_allows(self._server_role, "admin")

    @pyqtProperty(str, notify=changed)
    def serverEmail(self) -> str:  # noqa: N802
        return get_server_session().email

    @pyqtProperty(str, notify=changed)
    def localLimitations(self) -> str:  # noqa: N802
        return (
            "No team list or invitations\n"
            "No shared profiles, proxies or scenarios\n"
            "No role-based access control\n"
            "No profile locks between teammates\n"
            "No audit log or cloud backup"
        )

    def _notify(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    @pyqtSlot()
    def refresh(self) -> None:
        session = get_server_session()
        self._email = session.email
        self._name = ""
        self._is_superadmin = False
        if not (session.enabled and session.url and session.token):
            self._status = "Local mode: this computer only"
            self._server_role = ""
            self._teams_model.set_rows([])
            self._invites_model.set_rows([])
            self._members_model.set_rows([])
            self._audit_model.set_rows([])
            self._sync_app_state(False)
            self.changed.emit()
            return
        try:
            context = ServerClient(session).context()
        except ServerClientError as exc:
            self._status = f"Server unavailable: {exc}"
            self._server_role = ""
            self._teams_model.set_rows([])
            self._invites_model.set_rows([])
            self._members_model.set_rows([])
            self._audit_model.set_rows([])
            self._sync_app_state(False)
            self.changed.emit()
            return
        user = context.get("user") or {}
        self._email = str(user.get("email") or session.email)
        self._name = str(user.get("full_name") or "")
        self._is_superadmin = bool(user.get("is_superadmin"))
        teams = list(context.get("teams") or [])
        selected = session.team_id
        self._status = f"Connected to {session.url}"
        self._server_role = "owner" if self._is_superadmin else ""
        selected_team_name = ""
        for team in teams:
            if str(team.get("id") or "") == selected:
                self._server_role = str(team.get("role") or "")
                selected_team_name = str(team.get("name") or "")
                break
        if not selected and teams:
            selected = str(teams[0].get("id") or "")
            if selected:
                save_server_session(
                    enabled=session.enabled,
                    url=session.url,
                    token=session.token,
                    refresh_token=session.refresh_token,
                    team_id=selected,
                    email=session.email,
                )
                session = get_server_session()
                selected_team_name = str(teams[0].get("name") or "")
                self._server_role = str(teams[0].get("role") or self._server_role)
        self._teams_model.set_rows([
            {
                "id": str(team.get("id") or ""),
                "name": str(team.get("name") or ""),
                "slug": str(team.get("slug") or ""),
                "role": str(team.get("role") or ""),
                "plan": str(team.get("plan") or ""),
                "license_status": str(team.get("license_status") or ""),
                "invited_by": str(team.get("invited_by") or ""),
                "invited_by_email": str(team.get("invited_by_email") or ""),
                "selected": str(team.get("id") or "") == selected,
                "profiles": int(team.get("profiles") or 0),
                "proxies": int(team.get("proxies") or 0),
                "scenarios": int(team.get("scenarios") or 0),
            }
            for team in teams
        ])
        self._invites_model.set_rows([
            {
                "id": str(invite.get("id") or ""),
                "team_id": str(invite.get("team_id") or ""),
                "team_name": str(invite.get("team_name") or ""),
                "team_slug": str(invite.get("team_slug") or ""),
                "role": str(invite.get("role") or ""),
                "invited_by_email": str(invite.get("invited_by_email") or ""),
                "expires_at": str(invite.get("expires_at") or "")[:19].replace("T", " "),
            }
            for invite in list(context.get("pending_invites") or [])
        ])
        self._refresh_members()
        self._refresh_audit()
        self._sync_app_state(bool(selected and self._server_role))
        self.changed.emit()

    def _sync_app_state(self, available: bool) -> None:
        if self._app_state is None:
            return
        session = get_server_session()
        team_name = ""
        try:
            for index in range(self._teams_model.rowCount()):
                item = self._teams_model.get(index)
                if str(item.get("id") or "") == session.team_id:
                    team_name = str(item.get("name") or "")
                    break
        except Exception:
            team_name = ""
        self._app_state.set_cloud_context(
            enabled=session.enabled,
            available=bool(available),
            email=self._email,
            team_id=session.team_id,
            team_name=team_name,
            role=self._server_role,
            status=self._status,
        )

    def _refresh_members(self) -> None:
        client = ServerClient()
        if not client.configured:
            self._members_model.set_rows([])
            return
        try:
            members = client.team_members()
        except ServerClientError:
            self._members_model.set_rows([])
            return
        self._members_model.set_rows([
            {
                "id": str(member.get("id") or ""),
                "email": str(member.get("email") or ""),
                "full_name": str(member.get("full_name") or ""),
                "role": str(member.get("role") or ""),
            }
            for member in members
        ])

    def _refresh_audit(self) -> None:
        client = ServerClient()
        if not client.configured:
            self._audit_model.set_rows([])
            return
        try:
            audit_rows = client.audit_log(limit=80)
        except ServerClientError:
            self._audit_model.set_rows([])
            return
        self._audit_model.set_rows([
            {
                "time": str(row.get("created_at") or "")[:19].replace("T", " "),
                "action": str(row.get("action") or ""),
                "entity": " ".join(part for part in [str(row.get("entity_type") or ""), str(row.get("entity_id") or "")[:8]] if part),
                "details": json.dumps(row.get("payload") or {}, ensure_ascii=False),
            }
            for row in audit_rows
        ])

    @pyqtSlot(str)
    def selectTeam(self, team_id: str) -> None:  # noqa: N802
        session = get_server_session()
        save_server_session(
            enabled=session.enabled,
            url=session.url,
            token=session.token,
            refresh_token=session.refresh_token,
            team_id=str(team_id or ""),
            email=session.email,
        )
        self._notify("Active team changed")
        self.refresh()
        if self._app_state is not None:
            self._app_state.refreshAll()

    @pyqtSlot(str)
    def acceptInvite(self, invite_id: str) -> None:  # noqa: N802
        try:
            result = ServerClient().accept_invite(str(invite_id or ""))
        except ServerClientError as exc:
            self._notify(f"Cannot accept invite: {exc}")
            return
        team_id = str(result.get("team_id") or "")
        session = get_server_session()
        if team_id and not session.team_id:
            save_server_session(
                enabled=session.enabled,
                url=session.url,
                token=session.token,
                refresh_token=session.refresh_token,
                team_id=team_id,
                email=session.email,
            )
        self._notify("Invite accepted")
        self.refresh()
        if self._app_state is not None:
            self._app_state.refreshAll()
    @pyqtSlot(str, str)
    def createInvite(self, email: str, role: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            self._notify("Select a team first")
            return
        try:
            invite = client.create_invite({"email": str(email or "").strip(), "role": str(role or "operator").strip().lower()})
        except ServerClientError as exc:
            self._notify(f"Cannot create invite: {exc}")
            return
        self._notify(f"Invite created. Token for external delivery: {invite.get('token')}")
        self.refresh()

    @pyqtSlot(str, str)
    def updateMemberRole(self, member_id: str, role: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            return
        try:
            client.update_member(str(member_id or ""), str(role or "viewer").strip().lower())
        except ServerClientError as exc:
            self._notify(f"Cannot update member: {exc}")
            return
        self._notify("Member role updated")
        self.refresh()

    @pyqtSlot(str)
    def deleteMember(self, member_id: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            return
        try:
            client.delete_member(str(member_id or ""))
        except ServerClientError as exc:
            self._notify(f"Cannot remove member: {exc}")
            return
        self._notify("Member removed")
        self.refresh()

    @pyqtSlot(str)
    def createPasswordReset(self, member_id: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            return
        try:
            reset = client.create_password_reset(str(member_id or ""))
        except ServerClientError as exc:
            self._notify(f"Cannot create reset token: {exc}")
            return
        self._notify(f"Password reset token for {reset.get('email')}: {reset.get('token')}")

    @pyqtSlot()
    def uploadLocalWorkspace(self) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            self._notify("Select a cloud team first")
            return
        if not self.canManageCloud:
            self._notify("Cloud role 'manager' or higher required")
            return
        try:
            proxies = self._upload_local_proxies(client)
            profiles = self._upload_local_profiles(client)
            scenarios = self._upload_local_scenarios(client)
        except ServerClientError as exc:
            self._notify(f"Cloud upload failed: {exc}")
            return
        self._notify(f"Cloud upload finished: {profiles} profile(s), {proxies} proxy(s), {scenarios} scenario(s)")
        if self._app_state is not None:
            self._app_state.refreshAll()

    def _upload_local_proxies(self, client: ServerClient) -> int:
        existing = {str(item.get("value") or ""): item for item in client.proxies()}
        uploaded = 0
        try:
            pools = json.loads(db_get_setting("proxy_pools") or "{}")
        except Exception:
            pools = {}
        if not isinstance(pools, dict):
            return 0
        for pool_name, pool in pools.items():
            entries = pool.get("proxies", []) if isinstance(pool, dict) else []
            for entry in entries:
                value = str((entry if isinstance(entry, dict) else {}).get("value") or "").strip()
                if not value or value in existing:
                    continue
                created = client.create_proxy({"value": value, "group_name": str(pool_name or "Default")})
                existing[value] = created
                uploaded += 1
        return uploaded

    def _upload_local_profiles(self, client: ServerClient) -> int:
        existing = {str(item.get("name") or ""): item for item in client.profiles()}
        proxies = {str(item.get("value") or ""): str(item.get("id") or "") for item in client.proxies()}
        uploaded = 0
        for account in db_get_accounts():
            name = str(account.get("name") or "").strip()
            if not name:
                continue
            proxy_value = self._proxy_value(account)
            proxy_id = proxies.get(proxy_value, "") if proxy_value else ""
            if proxy_value and not proxy_id:
                created = client.create_proxy({"value": proxy_value, "group_name": str(account.get("proxy_pool") or account.get("stage") or "Default")})
                proxy_id = str(created.get("id") or "")
                proxies[proxy_value] = proxy_id
            settings = {}
            engine = str(account.get("_browser_engine") or account.get("browser_engine") or "camoufox").lower()
            raw_settings = account.get("cloakbrowser_settings") if engine == "cloakbrowser" else account.get("camoufox_settings")
            if isinstance(raw_settings, dict):
                settings.update(raw_settings)
            extra = account.get("extra_fields")
            if isinstance(extra, dict):
                settings["variables"] = extra
            payload = {
                "name": name,
                "group_name": str(account.get("stage") or "Default"),
                "browser_engine": engine,
                "proxy_id": proxy_id or None,
                "settings": settings,
            }
            current = existing.get(name)
            if current:
                client.update_profile(str(current.get("id") or ""), payload)
            else:
                client.create_profile(payload)
            uploaded += 1
        return uploaded

    def _upload_local_scenarios(self, client: ServerClient) -> int:
        existing = {str(item.get("name") or ""): item for item in client.scenarios()}
        uploaded = 0
        for scenario in db_get_scenarios():
            payload = {
                "name": scenario.name,
                "description": scenario.description or "",
                "definition": {"steps": scenario.steps or []},
            }
            current = existing.get(scenario.name)
            if current:
                client.update_scenario(str(current.get("id") or ""), payload)
            else:
                client.create_scenario(payload)
            uploaded += 1
        return uploaded

    @staticmethod
    def _proxy_value(account: dict) -> str:
        host = str(account.get("proxy_host") or "").strip()
        port = str(account.get("proxy_port") or "").strip()
        if not host or not port:
            return ""
        scheme = str(account.get("proxy_scheme") or "socks5").strip() or "socks5"
        user = str(account.get("proxy_user") or "").strip()
        password = str(account.get("proxy_password") or "").strip()
        auth = f"{user}:{password}@" if user and password else ""
        return f"{scheme}://{auth}{host}:{port}"

    @pyqtSlot(str, str, str)
    def login(self, url: str, email: str, password: str) -> None:
        try:
            result = ServerClient().login(str(url or "").strip(), str(email or "").strip(), str(password or ""))
        except ServerClientError as exc:
            self._notify(f"Login failed: {exc}")
            return
        db_set_setting(ONBOARDING_COMPLETED_KEY, "true")
        team_id = str(result.get("team_id") or "")
        self._notify(f"Cloud connected, team {team_id[:8]}" if team_id else "Cloud connected. Accept an invite below.")
        self.refresh()
        if self._app_state is not None:
            self._app_state.refreshAll()

    @pyqtSlot()
    def logout(self) -> None:
        try:
            client = ServerClient()
            if client.configured:
                client.logout()
        except Exception:
            pass
        clear_server_session()
        self._notify("Logged out")
        self.refresh()
        if self._app_state is not None:
            self._app_state.refreshAll()
