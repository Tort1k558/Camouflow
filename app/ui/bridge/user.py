"""User/account bridge for QML."""

from __future__ import annotations

import json
import threading

from PyQt6.QtCore import QUrl, QObject, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication

from app.services.cloud_sync import CloudWorkspaceSync
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
    cloudRefreshFinished = pyqtSignal(object, str)
    cloudSyncFinished = pyqtSignal(object, str)
    uiCall = pyqtSignal(object)  # run a callable on the UI thread

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
        self._members_model = DictListModel(["id", "email", "full_name", "role", "last_seen", "is_superadmin"], parent=self)
        self._sent_invites_model = DictListModel(["id", "email", "role", "expires_at", "status"], parent=self)
        self._audit_model = DictListModel(["time", "action", "entity", "details"], parent=self)
        self._conflicts_model = DictListModel(["resource", "key", "remote_id"], parent=self)
        self._email = ""
        self._name = ""
        self._is_superadmin = False
        self._server_role = ""
        self._status = "Local mode"
        self._last_invite_link = ""
        self.cloudRefreshFinished.connect(self._apply_cloud_refresh)
        self.cloudSyncFinished.connect(self._apply_cloud_sync)
        self.uiCall.connect(lambda fn: fn())
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

    @pyqtProperty(QObject, constant=True)
    def conflictModel(self) -> QObject:  # noqa: N802
        return self._conflicts_model

    @pyqtProperty(QObject, constant=True)
    def sentInvitesModel(self) -> QObject:  # noqa: N802
        return self._sent_invites_model

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
    def lastInviteLink(self) -> str:  # noqa: N802
        return self._last_invite_link

    @pyqtProperty(bool, notify=changed)
    def autoSyncEnabled(self) -> bool:  # noqa: N802
        return (db_get_setting("cloud_autosync") or "").strip().lower() in {"1", "true", "yes", "on"}

    @pyqtProperty(int, notify=changed)
    def conflictCount(self) -> int:  # noqa: N802
        return len(self._pending_conflicts())

    @pyqtProperty(str, notify=changed)
    def localLimitations(self) -> str:  # noqa: N802
        return (
            "No team list or invitations\n"
            "No shared profiles, proxies or scenarios\n"
            "No role-based access control\n"
            "No profile locks between teammates\n"
            "No audit log or cloud backup"
        )

    def _async(self, work, then=None, fail=None):
        """Run a cloud call off the UI thread; deliver results on the UI thread.

        Without this, any slow request (or a 20s timeout) freezes the whole
        QML interface while the slot blocks the event loop."""
        def runner() -> None:
            try:
                result = work()
            except ServerClientError as exc:
                if fail is not None:
                    self.uiCall.emit(lambda: fail(exc))
                return
            except Exception as exc:  # defensive: never hang the worker
                if fail is not None:
                    self.uiCall.emit(lambda: fail(exc))
                return
            if then is not None:
                self.uiCall.emit(lambda: then(result))

        threading.Thread(target=runner, daemon=True, name="camouflow-user-async").start()

    def _notify(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    def _pending_conflicts(self) -> list:
        try:
            items = json.loads(db_get_setting("cloud_sync_conflicts_v1") or "[]")
        except Exception:
            items = []
        return items if isinstance(items, list) else []

    @pyqtSlot(str)
    def copyToClipboard(self, text: str) -> None:  # noqa: N802
        clipboard = QApplication.clipboard()
        if clipboard is not None and text:
            clipboard.setText(str(text))
            self._notify("Copied to clipboard")

    @pyqtSlot(bool)
    def setAutoSyncEnabled(self, enabled: bool) -> None:  # noqa: N802
        db_set_setting("cloud_autosync", "true" if enabled else "false")
        self.changed.emit()

    @pyqtSlot()
    def maybeAutoSync(self) -> None:  # noqa: N802
        if self.autoSyncEnabled and get_server_session().enabled:
            self.syncCloudWorkspace()

    @pyqtSlot(str)
    def resolveConflict(self, spec: str) -> None:  # noqa: N802
        """spec = 'resource|key|local' or 'resource|key|remote'."""
        parts = str(spec or "").split("|")
        if len(parts) != 3:
            return
        resource, key, choice = parts
        client = ServerClient()
        if not client.configured:
            self._notify("Not connected to cloud")
            return

        def worker() -> None:
            try:
                error = CloudWorkspaceSync(client).resolve(resource, key, choice)
                self.cloudSyncFinished.emit({"resolved": 1, "error_text": error}, "")
            except ServerClientError as exc:
                self.cloudSyncFinished.emit({}, str(exc))

        threading.Thread(target=worker, daemon=True, name="camouflow-conflict-resolve").start()

    def _reload_conflicts(self) -> None:
        self._conflicts_model.set_rows(self._pending_conflicts())

    @pyqtSlot()
    def refresh(self) -> None:
        self._reload_conflicts()
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
            self._sent_invites_model.set_rows([])
            self._sync_app_state(False)
            self.changed.emit()
            return
        self._status = f"Connecting to {session.url}…"
        self.changed.emit()

        def worker() -> None:
            try:
                client = ServerClient(session)
                context = client.request_async("GET", "/api/v1/auth/context").result()
                members = client.request_async("GET", f"/api/v1/teams/{client.session.team_id}/members").result() if client.configured else []
                audit_rows = client.request_async("GET", f"/api/v1/teams/{client.session.team_id}/audit-log?limit=80").result() if client.configured else []
                try:
                    sent_invites = client.request_async("GET", f"/api/v1/teams/{client.session.team_id}/invites").result() if client.configured else []
                except ServerClientError:
                    sent_invites = []
                self.cloudRefreshFinished.emit({"context": context, "members": members, "audit": audit_rows, "sent_invites": sent_invites}, "")
            except ServerClientError as exc:
                self.cloudRefreshFinished.emit({}, str(exc))

        threading.Thread(target=worker, daemon=True, name="camouflow-cloud-refresh").start()

    @pyqtSlot(object, str)
    def _apply_cloud_refresh(self, payload: object, error: str) -> None:
        session = get_server_session()
        if error:
            self._status = f"Server unavailable: {error}"
            self._server_role = ""
            self._teams_model.set_rows([])
            self._invites_model.set_rows([])
            self._members_model.set_rows([])
            self._audit_model.set_rows([])
            self._sent_invites_model.set_rows([])
            self._sync_app_state(False)
            self.changed.emit()
            return
        data = payload if isinstance(payload, dict) else {}
        context = data.get("context") if isinstance(data.get("context"), dict) else {}
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
        members = data.get("members") if isinstance(data.get("members"), list) else []
        sent_invites = data.get("sent_invites") if isinstance(data.get("sent_invites"), list) else []
        self._sent_invites_model.set_rows([
            {
                "id": str(row.get("id") or ""),
                "email": str(row.get("email") or ""),
                "role": str(row.get("role") or ""),
                "expires_at": str(row.get("expires_at") or "")[:16].replace("T", " "),
                "status": str(row.get("status") or "active"),
            }
            for row in sent_invites if isinstance(row, dict)
        ])
        self._members_model.set_rows([
            {
                "id": str(member.get("id") or ""),
                "email": str(member.get("email") or ""),
                "full_name": str(member.get("full_name") or ""),
                "role": str(member.get("role") or ""),
                "last_seen": str(member.get("last_seen") or "")[:16].replace("T", " "),
                "is_superadmin": bool(member.get("is_superadmin")),
            }
            for member in members if isinstance(member, dict)
        ])
        audit_rows = data.get("audit") if isinstance(data.get("audit"), list) else []
        self._audit_model.set_rows([
            {
                "time": str(row.get("created_at") or "")[:19].replace("T", " "),
                "action": str(row.get("action") or ""),
                "entity": " ".join(part for part in [str(row.get("entity_type") or ""), str(row.get("entity_id") or "")[:8]] if part),
                "details": json.dumps(row.get("payload") or {}, ensure_ascii=False),
            }
            for row in audit_rows if isinstance(row, dict)
        ])
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
        def work():
            return ServerClient().accept_invite(str(invite_id or ""))

        def done(result) -> None:
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

        self._async(work, then=done, fail=lambda exc: self._notify(f"Cannot accept invite: {exc}"))
    @pyqtSlot()
    def leaveTeam(self) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            self._notify("Not connected to cloud")
            return

        def work():
            client.request("POST", f"/api/v1/teams/{client.session.team_id}/leave", None)

        def done(_result) -> None:
            self._notify("You left the team")
            self.refresh()
            if self._app_state is not None:
                self._app_state.refreshAll()

        self._async(work, then=done, fail=lambda exc: self._notify(f"Leave failed: {exc}"))

    @pyqtSlot(str)
    def revokeInvite(self, invite_id: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            return

        def work():
            client.request("DELETE", f"/api/v1/teams/{client.session.team_id}/invites/{invite_id}", None)

        def done(_result) -> None:
            self._notify("Invite revoked")
            self.refresh()

        self._async(work, then=done, fail=lambda exc: self._notify(f"Revoke failed: {exc}"))

    @pyqtSlot(str, str)
    def createInvite(self, email: str, role: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            self._notify("Select a team first")
            return

        def work():
            return client.create_invite({"email": str(email or "").strip(), "role": str(role or "operator").strip().lower()})

        def done(invite) -> None:
            token = str(invite.get("token") or "")
            self._last_invite_link = f"{get_server_session().url}/invite?token={token}" if token else ""
            self._notify("Invite link created (see the link field below)")
            self.refresh()

        self._async(work, then=done, fail=lambda exc: self._notify(f"Cannot create invite: {exc}"))

    @pyqtSlot(str, str)
    def updateMemberRole(self, member_id: str, role: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            return

        def work():
            client.update_member(str(member_id or ""), str(role or "viewer").strip().lower())

        def done(_result) -> None:
            self._notify("Member role updated")
            self.refresh()

        self._async(work, then=done, fail=lambda exc: self._notify(f"Cannot update member: {exc}"))

    @pyqtSlot(str)
    def deleteMember(self, member_id: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            return

        def work():
            client.delete_member(str(member_id or ""))

        def done(_result) -> None:
            self._notify("Member removed")
            self.refresh()

        self._async(work, then=done, fail=lambda exc: self._notify(f"Cannot remove member: {exc}"))

    @pyqtSlot(str)
    def createPasswordReset(self, member_id: str) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            return

        def work():
            return client.create_password_reset(str(member_id or ""))

        def done(reset) -> None:
            self._notify(f"Password reset token for {reset.get('email')}: {reset.get('token')}")

        self._async(work, then=done, fail=lambda exc: self._notify(f"Cannot create reset token: {exc}"))

    @pyqtSlot()
    def uploadLocalWorkspace(self) -> None:  # noqa: N802
        self.syncCloudWorkspace()

    @pyqtSlot()
    @pyqtSlot(bool)
    def syncCloudWorkspace(self, upload_cookies: bool = False) -> None:  # noqa: N802
        client = ServerClient()
        if not client.configured:
            self._notify("Select a cloud team first")
            return
        if not self.canManageCloud:
            self._notify("Cloud role 'manager' or higher required")
            return
        self._notify("Cloud sync started")

        def worker() -> None:
            try:
                result = CloudWorkspaceSync(client).sync(upload_cookies=bool(upload_cookies))
                self.cloudSyncFinished.emit({"uploaded": result.uploaded, "downloaded": result.downloaded, "conflicts": result.conflicts, "conflict_items": result.conflict_items}, "")
            except ServerClientError as exc:
                self.cloudSyncFinished.emit({}, str(exc))

        threading.Thread(target=worker, daemon=True, name="camouflow-cloud-sync").start()

    @pyqtSlot(object, str)
    def _apply_cloud_sync(self, payload: object, error: str) -> None:
        if error:
            self._notify(f"Cloud sync failed: {error}")
            return
        result = payload if isinstance(payload, dict) else {}
        if result.get("resolved"):
            if result.get("error_text"):
                self._notify(str(result["error_text"]))
            else:
                self._notify("Conflict resolved")
            self.changed.emit()
            if self._app_state is not None:
                self._app_state.refreshAll()
            return
        uploaded = int(result.get("uploaded") or 0)
        downloaded = int(result.get("downloaded") or 0)
        conflicts = result.get("conflicts") if isinstance(result.get("conflicts"), list) else []
        message = f"Cloud sync finished: {uploaded} uploaded, {downloaded} downloaded"
        if conflicts:
            message += f". Conflicts: {len(conflicts)} (open Conflict center to resolve)"
        self._notify(message)
        self._reload_conflicts()
        self.changed.emit()
        if self._app_state is not None:
            self._app_state.refreshAll()

    @pyqtSlot(str, str)
    def login(self, email: str, password: str) -> None:
        self._notify("Signing in…")

        def work():
            return ServerClient().login(get_server_session().url, str(email or "").strip(), str(password or ""))

        self._async(work, then=self._after_login, fail=lambda exc: self._notify(f"Login failed: {exc}"))

    @pyqtSlot()
    def googleLogin(self) -> None:  # noqa: N802
        self._notify("Opening Google sign-in…")

        def work():
            return ServerClient().google_login_url(app_pair=True)

        def done(url: str) -> None:
            QDesktopServices.openUrl(QUrl(url))
            self._notify("Browser opened — finish Google sign-in and paste the pairing code here")

        self._async(work, then=done, fail=lambda exc: self._notify(f"Google sign-in unavailable: {exc}"))

    @pyqtSlot(str)
    def loginWithPairCode(self, code: str) -> None:  # noqa: N802
        code = str(code or "").strip()
        if not code:
            self._notify("Paste the pairing code from the browser first")
            return
        try:
            result = ServerClient().login_with_pair_code(code)
        except ServerClientError as exc:
            self._notify(f"Pairing failed: {exc}")
            return
        self._after_login(result)

    def _after_login(self, result: dict) -> None:
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
