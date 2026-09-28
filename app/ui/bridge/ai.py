"""QML bridge for AI agent sessions: lifecycle, live event stream, save-as-scenario."""

from __future__ import annotations

import asyncio
import copy
import json
import threading
import time
import uuid
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.core.browser_interface import BrowserInterface
from app.services.ai_agent.llm import LLMClient, LLMConfig
from app.services.ai_agent.loop import DOM_JS_PATH, AgentSession, save_transcript
from app.services.ai_agent.to_steps import scenario_description, session_to_scenario_steps, steps_summary
from app.services.proxy_policy import account_proxy
from app.services.server_client import ServerClient, get_server_session
from app.storage import db
from app.storage.db import DATA_ROOT

EVENT_ROLES = ["type", "step", "text", "action", "url"]
MAX_EVENT_ROWS = 500


def _ai_setting(key: str, default: str = "") -> str:
    return str(db.db_get_setting(key) or default)


def ai_config() -> LLMConfig:
    return LLMConfig(
        base_url=_ai_setting("ai_base_url"),
        api_key=_ai_setting("ai_api_key"),
        model=_ai_setting("ai_model"),
    )


def ai_configured() -> bool:
    config = ai_config()
    return bool(config.base_url.strip() and config.model.strip())


def ai_enabled() -> bool:
    return _ai_setting("ai_enabled").strip().lower() in {"1", "true", "yes", "on"} and ai_configured()


class AIBridge(QObject):
    changed = pyqtSignal()
    message = pyqtSignal(str)
    eventFired = pyqtSignal(object)
    finished = pyqtSignal(str)
    saveFinished = pyqtSignal(object, str)

    def __init__(self, operations, scenarios, state, parent=None):
        super().__init__(parent)
        self.operations, self.scenarios, self.state = operations, scenarios, state
        self._events_model = None  # built lazily; needs models import context
        self._rows = []
        self._session = None
        self._active = False
        self._status = "Ready"
        self._profile_name = ""
        self._task = ""
        self._result_text = ""
        self._draft_steps = []
        self._secrets = {}
        self._artifacts = ""
        self._stop = threading.Event()
        self._thread = None
        self._loop = None
        self._task_handle = None
        self._saving = False
        self.eventFired.connect(self._append_event)
        self.finished.connect(self._finished)
        self.saveFinished.connect(self._save_finished)

    # --- properties -------------------------------------------------------------

    @pyqtProperty(QObject, constant=True)
    def eventsModel(self):  # noqa: N802
        from app.ui.bridge.models import DictListModel

        if self._events_model is None:
            self._events_model = DictListModel(EVENT_ROLES, parent=self)
            self._events_model.set_rows(self._rows)
        return self._events_model

    @pyqtProperty(bool, notify=changed)
    def active(self):
        return self._active

    @pyqtProperty(bool, notify=changed)
    def busy(self):
        return self._active or self._saving

    @pyqtProperty(bool, notify=changed)
    def configured(self):
        return ai_enabled()

    @pyqtProperty(bool, notify=changed)
    def hasDraft(self):  # noqa: N802
        return len(self._draft_steps) > 1

    @pyqtProperty(str, notify=changed)
    def status(self):
        return self._status

    @pyqtProperty(str, notify=changed)
    def profileName(self):  # noqa: N802
        return self._profile_name

    @pyqtProperty(str, notify=changed)
    def task(self):
        return self._task

    @pyqtProperty(str, notify=changed)
    def resultText(self):  # noqa: N802
        return self._result_text

    @pyqtProperty(str, notify=changed)
    def artifactsDir(self):  # noqa: N802
        return self._artifacts

    @pyqtProperty(int, notify=changed)
    def defaultMaxSteps(self):  # noqa: N802
        try:
            return max(5, min(100, int(_ai_setting("ai_max_steps", "25"))))
        except ValueError:
            return 25

    # --- session validation -------------------------------------------------------

    @pyqtSlot(str, result=str)
    def sessionIssue(self, profile):  # noqa: N802
        if self._active or self._saving:
            return "A session is already running"
        if self.hasDraft:
            return "Save or discard the current AI draft first"
        if not ai_configured():
            return "Configure the AI provider in Settings first"
        if not ai_enabled():
            return "Enable the AI assistant in Settings first"
        account = self.operations.profiles._cached_account(profile)
        if not account:
            return "Choose a loaded profile"
        if not self.operations.profiles.actionState(profile).get("startAllowed"):
            return "Profile is unavailable or you do not have permission to start it"
        return ""

    # --- session lifecycle ----------------------------------------------------------

    @pyqtSlot(str, str, int)
    def start(self, profile, task, max_steps):
        if self._active or self._saving or self.hasDraft:
            self.state.notify("Save or discard the current AI draft first")
            return
        try:
            session = get_server_session()
            if session.enabled and not self.scenarios._ensure_allowed("operator"):
                return
            task = str(task or "").strip()
            if not task or len(task) > 4000:
                raise ValueError("Describe the task (1-4000 characters)")
            account = (self.operations.profiles._cached_account(profile.strip()) if session.enabled else
                       next((a for a in db.db_get_accounts() if a["name"] == profile.strip()), None))
            if account is None:
                raise ValueError("Select an existing profile; wait for the profile list to load")
            self.operations._reserve([account["name"]])
        except Exception as exc:
            self.state.notify(str(exc))
            return
        self._session = session
        self._task = task
        self._profile_name = account["name"]
        self._result_text = ""
        self._draft_steps, self._secrets = [], {}
        self._rows = []
        if self._events_model is not None:
            self._events_model.set_rows([])
        self._active = True
        self._status = "Starting AI session..."
        self._stop.clear()
        self.changed.emit()
        self._thread = threading.Thread(
            target=self._worker,
            args=(copy.deepcopy(account), task, int(max_steps or 25), copy.deepcopy(session)),
            name="ai-agent", daemon=True,
        )
        self._thread.start()

    def _worker(self, account, task, max_steps, session):
        error = ""
        client = ServerClient(session) if session.enabled else None
        profile_id = str(account.get("id") or "")
        locked = False
        heartbeat_stop = threading.Event()
        heartbeat_thread = None
        try:
            if client:
                client.lock_profile(profile_id)
                locked = True

                def renew():
                    while not heartbeat_stop.wait(40):
                        try:
                            client.heartbeat_profile_lock(profile_id)
                        except Exception:
                            self._stop.set()
                            return

                heartbeat_thread = threading.Thread(target=renew, daemon=True, name="ai-lock-heartbeat")
                heartbeat_thread.start()
            asyncio.run(self._run(account, task, max_steps))
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            error = str(exc) or "AI session failed"
        finally:
            self._loop = self._task_handle = None
            heartbeat_stop.set()
            if heartbeat_thread:
                heartbeat_thread.join()
            if client and locked:
                try:
                    client.unlock_profile(profile_id)
                except Exception:
                    error = error or "Session stopped, but the cloud lock release failed; it will expire"
            self.operations._release([account["name"]])
            self.finished.emit(error)

    async def _run(self, account, task, max_steps):
        self._loop = asyncio.get_running_loop()
        self._task_handle = asyncio.current_task()
        if self._stop.is_set():
            return
        engine = str(account.get("_browser_engine") or account.get("browser_engine") or db.db_get_browser_engine())
        settings = account.get(f"{engine}_settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        browser = BrowserInterface(account["name"], proxy=account_proxy(account), browser_engine=engine,
                                   browser_settings={**settings, "headless": False}, keep_browser_open=False)
        artifacts = DATA_ROOT / "outputs" / "ai-runs" / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
        try:
            await browser.start()
            if self._stop.is_set():
                return
            session = AgentSession(
                browser.page,
                LLMClient(ai_config()),
                task,
                max_steps=max_steps,
                on_event=lambda event: self.eventFired.emit(dict(event)),
                stop_check=self._stop.is_set,
                dom_js=DOM_JS_PATH.read_text(encoding="utf-8"),
            )
            result = await session.run()
            self._result_text = f"{result['status']}: {result['result']}" if result["result"] else f"{result['status']}"
            self._draft_steps = session_to_scenario_steps(result["steps"])
            self._secrets = dict(result["secrets"])
            try:
                save_transcript(result, artifacts)
                self._artifacts = str(artifacts)
            except Exception:
                self._artifacts = ""
        finally:
            try:
                await browser.close(force=True)
            except Exception:
                pass

    @pyqtSlot(object)
    def _append_event(self, event):
        row = {role: str(event.get(role, "")) for role in EVENT_ROLES}
        row["step"] = int(event.get("step") or 0)
        self._rows.append(row)
        if len(self._rows) > MAX_EVENT_ROWS:
            self._rows = self._rows[-MAX_EVENT_ROWS:]
        if self._events_model is not None:
            self._events_model.set_rows(list(self._rows))
        self._status = _event_status(event, self._rows)
        self.changed.emit()

    @pyqtSlot(str)
    def _finished(self, error):
        self._active = False
        if error:
            self._status = f"Session failed: {error}"
        elif self._draft_steps:
            self._status = f"Session finished · {steps_summary(self._draft_steps)}"
        else:
            self._status = "Session finished"
        self.changed.emit()

    @pyqtSlot()
    def stop(self):
        if self._stop.is_set():
            return
        self._stop.set()
        loop, task = self._loop, self._task_handle
        if loop is not None and task is not None and not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)
        if self._active:
            self._status = "Stopping AI session..."
            self.changed.emit()

    @pyqtSlot()
    def discard(self):
        if self._active or self._saving:
            return
        self._session = None
        self._task = ""
        self._result_text = ""
        self._draft_steps, self._secrets = [], {}
        self._artifacts = ""
        self._rows = []
        if self._events_model is not None:
            self._events_model.set_rows([])
        self._status = "Ready"
        self.changed.emit()

    # --- save as scenario ----------------------------------------------------------

    @pyqtSlot(str)
    def save(self, name):
        if self._active or self._saving or not self.hasDraft:
            return
        session = get_server_session()
        if session.enabled and not self.scenarios._ensure_allowed("manager"):
            return
        name = str(name or "").strip()
        if not name or len(name) > 100:
            self.state.notify("Enter a scenario name (1-100 characters)")
            return
        steps = copy.deepcopy(self._draft_steps)
        description = scenario_description(self._task)
        self._saving = True
        self._status = "Saving AI draft..."
        self.changed.emit()

        def worker():
            try:
                scenario_id = ""
                if session.enabled:
                    client = ServerClient(session)
                    if any(str(row.get("name") or "").casefold() == name.casefold() for row in client.scenarios()):
                        raise ValueError("That scenario already exists. Choose a new name.")
                    created = client.create_scenario({"name": name, "description": description, "definition": {"steps": steps}})
                    scenario_id = str(created["id"])
                else:
                    with db._STORAGE_LOCK:
                        if db.db_get_scenario(name) is not None:
                            raise ValueError("That scenario already exists. Choose a new name.")
                        db.db_save_scenario(name, steps, description)
                self.saveFinished.emit((session, db.Scenario(name, steps, description), scenario_id, self._secrets), "")
            except Exception as exc:
                self.saveFinished.emit(None, str(exc))

        self._thread = threading.Thread(target=worker, daemon=True, name="ai-save")
        self._thread.start()

    @pyqtSlot(object, str)
    def _save_finished(self, result, error):
        self._saving = False
        if error:
            self._status = "Save failed. Your draft is retained."
            self.changed.emit()
            self.state.notify(f"Cannot save AI draft: {error}")
            return
        session, scenario, scenario_id, secrets = result
        self.discard()
        self.scenarios.refresh()
        if scenario_id:
            self.scenarios._server_scenario_ids[scenario.name] = scenario_id
        self.scenarios._set_selected(scenario)
        self.state.setPage("Scenarios")
        notice = f"AI draft saved: {scenario.name}"
        if secrets:
            notice += f". Fill the profile variable(s) {', '.join(sorted(secrets))} before replay"
        self.state.notify(notice)

    @pyqtSlot()
    def shutdown(self):
        self._stop.set()
        loop, task = self._loop, self._task_handle
        if loop is not None and task is not None and not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)
        if self._thread is not None:
            self._thread.join(timeout=10)


def _event_status(event, rows):
    kind = event.get("type", "")
    step = event.get("step") or 0
    if kind == "thought":
        return f"Step {step}: thinking"
    if kind == "action":
        return f"Step {step}: {event.get('text', event.get('action', ''))}"
    if kind == "error":
        return f"Step {step}: {event.get('text', 'error')}"
    if kind == "done":
        return "Finished"
    return f"Events: {len(rows)}"
