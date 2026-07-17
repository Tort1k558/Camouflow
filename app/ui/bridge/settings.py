"""Settings bridge for QML."""

from __future__ import annotations

import json

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.services.server_client import get_server_session, save_server_session
from app.storage.db import DATA_ROOT, db_get_setting, db_set_setting
from app.ui.bridge.models import DictListModel

ONBOARDING_COMPLETED_KEY = "onboarding_completed"


class SettingsBridge(QObject):
    changed = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._vars_model = DictListModel(["key", "type", "value"], parent=self)
        self._stages_model = DictListModel(["name"], parent=self)
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)
        self.refresh()

    @pyqtProperty(str, notify=changed)
    def dataRoot(self) -> str:  # noqa: N802
        return str(DATA_ROOT)

    @pyqtProperty(QObject, constant=True)
    def variablesModel(self) -> QObject:  # noqa: N802
        return self._vars_model

    @pyqtProperty(QObject, constant=True)
    def stagesModel(self) -> QObject:  # noqa: N802
        return self._stages_model

    @pyqtProperty(bool, notify=changed)
    def serverEnabled(self) -> bool:  # noqa: N802
        session = get_server_session()
        return bool(session.enabled and session.url and session.token)

    @pyqtProperty(bool, notify=changed)
    def onboardingRequired(self) -> bool:  # noqa: N802
        if (db_get_setting(ONBOARDING_COMPLETED_KEY) or "").strip().lower() in {"1", "true", "yes", "on"}:
            return False
        session = get_server_session()
        return not (session.enabled and session.url and session.token)

    @pyqtProperty(str, notify=changed)
    def modeSummary(self) -> str:  # noqa: N802
        session = get_server_session()
        if session.enabled and session.url and session.token:
            if not session.team_id:
                return "Cloud mode: accept an invite in User to join a team."
            return "Cloud mode: shared team data, locks, roles, audit and backups are available."
        return "Local mode: profiles, proxies and scenarios are stored only on this computer."

    @pyqtProperty(str, constant=True)
    def localModeLimitations(self) -> str:  # noqa: N802
        return (
            "No shared profiles/proxies/scenarios\n"
            "No roles or access control\n"
            "No profile locks between teammates\n"
            "No audit log or cloud backup\n"
            "No license/team policy enforcement"
        )

    def _emit_message(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    def _load_vars(self) -> dict:
        try:
            data = json.loads(db_get_setting("shared_variables") or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_stages(self) -> list:
        try:
            data = json.loads(db_get_setting("stages_json") or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @pyqtSlot()
    def refresh(self) -> None:
        rows = []
        for key, payload in sorted(self._load_vars().items()):
            if isinstance(payload, dict):
                typ = str(payload.get("type") or "string")
                val = payload.get("value")
            else:
                typ = "string"
                val = payload
            if isinstance(val, list):
                val = ", ".join(map(str, val))
            rows.append({"key": str(key), "type": typ, "value": str(val or "")})
        self._vars_model.set_rows(rows)
        self._stages_model.set_rows([{"name": str(name)} for name in sorted(map(str, self._load_stages()))])
        self.changed.emit()

    @pyqtSlot(str, str, str)
    def saveVariable(self, key: str, typ: str, value: str) -> None:  # noqa: N802
        key = str(key or "").strip()
        if not key:
            self._emit_message("Variable key is empty")
            return
        typ = str(typ or "string")
        data = self._load_vars()
        val = [line.strip() for line in str(value or "").splitlines() if line.strip()] if typ == "list" else str(value or "")
        data[key] = {"type": typ, "value": val}
        db_set_setting("shared_variables", json.dumps(data, ensure_ascii=False))
        self._emit_message(f"Variable {key} saved")
        self.refresh()

    @pyqtSlot(str)
    def deleteVariable(self, key: str) -> None:  # noqa: N802
        data = self._load_vars()
        data.pop(str(key or ""), None)
        db_set_setting("shared_variables", json.dumps(data, ensure_ascii=False))
        self.refresh()

    @pyqtSlot(str, result="QVariant")
    def getVariable(self, key: str) -> dict:  # noqa: N802
        payload = self._load_vars().get(str(key or ""))
        if isinstance(payload, dict):
            value = payload.get("value", "")
            if isinstance(value, list):
                value = "\n".join(map(str, value))
            return {"key": str(key or ""), "type": str(payload.get("type") or "string"), "value": str(value or "")}
        if payload is None:
            return {}
        return {"key": str(key or ""), "type": "string", "value": str(payload)}

    @pyqtSlot(str)
    def addStage(self, name: str) -> None:  # noqa: N802
        name = str(name or "").strip()
        if not name:
            return
        stages = self._load_stages()
        if name not in stages:
            stages.append(name)
            db_set_setting("stages_json", json.dumps(stages, ensure_ascii=False))
        self.refresh()

    @pyqtSlot(str)
    def deleteStage(self, name: str) -> None:  # noqa: N802
        stages = [item for item in self._load_stages() if str(item) != str(name)]
        db_set_setting("stages_json", json.dumps(stages, ensure_ascii=False))
        self.refresh()

    @pyqtSlot()
    def startLocalMode(self) -> None:  # noqa: N802
        session = get_server_session()
        save_server_session(
            enabled=False,
            url=session.url,
            token=session.token,
            refresh_token=session.refresh_token,
            team_id=session.team_id,
            email=session.email,
        )
        db_set_setting(ONBOARDING_COMPLETED_KEY, "true")
        self._emit_message("Local mode enabled. You can connect Cloud later in User.")
        self.refresh()
        if self._app_state is not None:
            self._app_state.refreshAll()

    @pyqtSlot()
    def openUserLogin(self) -> None:  # noqa: N802
        db_set_setting(ONBOARDING_COMPLETED_KEY, "true")
        self.refresh()
        if self._app_state is not None:
            self._app_state.setPage("User")

    @pyqtSlot()
    def resetOnboarding(self) -> None:  # noqa: N802
        db_set_setting(ONBOARDING_COMPLETED_KEY, "false")
        self.refresh()
