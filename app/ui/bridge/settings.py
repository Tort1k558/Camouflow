"""Settings bridge for QML."""

from __future__ import annotations

import asyncio
import json
import threading

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.services.server_client import get_server_session, normalize_server_url, save_server_session
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

    @pyqtProperty(str, notify=changed)
    def serverUrl(self) -> str:  # noqa: N802
        return get_server_session().url

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
            "No audit log or cloud backup"
        )

    def _emit_message(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    @pyqtSlot(str)
    def saveServerUrl(self, value: str) -> None:  # noqa: N802
        try:
            url = normalize_server_url(str(value or ""))
        except Exception as exc:
            self._emit_message(f"Server URL is invalid: {exc}")
            return
        session = get_server_session()
        if session.enabled and url != session.url:
            save_server_session(enabled=False, url=url, token="", refresh_token="", team_id="", email=session.email)
            self._emit_message("Server URL saved. Sign in again to connect the new server.")
        else:
            save_server_session(
                enabled=session.enabled,
                url=url,
                token=session.token,
                refresh_token=session.refresh_token,
                team_id=session.team_id,
                email=session.email,
            )
            self._emit_message("Server URL saved")
        self.refresh()
        if self._app_state is not None:
            self._app_state.refreshAll()

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

    # --- AI agent provider ---------------------------------------------------------

    @pyqtProperty(bool, notify=changed)
    def aiEnabled(self) -> bool:  # noqa: N802
        return (db_get_setting("ai_enabled") or "").strip().lower() in {"1", "true", "yes", "on"}

    @pyqtProperty(str, notify=changed)
    def aiBaseUrl(self) -> str:  # noqa: N802
        return db_get_setting("ai_base_url") or ""

    @pyqtProperty(str, notify=changed)
    def aiApiKey(self) -> str:  # noqa: N802
        return db_get_setting("ai_api_key") or ""

    @pyqtProperty(str, notify=changed)
    def aiModel(self) -> str:  # noqa: N802
        return db_get_setting("ai_model") or ""

    @pyqtProperty(str, notify=changed)
    def aiMaxSteps(self) -> str:  # noqa: N802
        return db_get_setting("ai_max_steps") or "25"

    @pyqtSlot(bool, str, str, str, str)
    def saveAiSettings(self, enabled, base_url, api_key, model, max_steps):  # noqa: N802
        base_url = str(base_url or "").strip().rstrip("/")
        model = str(model or "").strip()
        try:
            steps = int(str(max_steps or "25").strip() or 25)
        except ValueError:
            self._emit_message("Max steps must be a number")
            return
        steps = max(5, min(100, steps))
        if enabled and (not base_url or not model):
            self._emit_message("AI provider needs a base URL and a model")
            return
        if base_url and not base_url.startswith(("http://", "https://")):
            self._emit_message("AI base URL must start with http:// or https://")
            return
        db_set_setting("ai_enabled", "true" if enabled else "false")
        db_set_setting("ai_base_url", base_url)
        db_set_setting("ai_api_key", str(api_key or "").strip())
        db_set_setting("ai_model", model)
        db_set_setting("ai_max_steps", str(steps))
        self._emit_message("AI settings saved" + ("" if enabled else " (disabled)"))
        self.refresh()

    @pyqtSlot()
    def testAiProvider(self):  # noqa: N802
        from app.ui.bridge.ai import ai_config, ai_configured

        if not ai_configured():
            self._emit_message("Configure the AI provider first")
            return
        threading.Thread(target=self._test_ai_worker, daemon=True, name="ai-test").start()

    def _test_ai_worker(self):
        from app.services.ai_agent.llm import LLMClient, LLMError
        from app.services.ai_agent.loop import SYSTEM_PROMPT
        from app.ui.bridge.ai import ai_config

        try:
            client = LLMClient(ai_config())
            thought, action = asyncio.run(client.next_action([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Connection test. Reply with the done action and result 'connection ok'."},
            ]))
            self.message.emit(f"AI provider works: {action['name']} ({thought[:60]})")
        except LLMError as exc:
            self.message.emit(f"AI provider test failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.message.emit(f"AI provider test failed: {exc}")
