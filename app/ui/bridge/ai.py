"""QML bridge for AI agent sessions: lifecycle, live event stream, save-as-scenario."""

from __future__ import annotations

import asyncio
import copy
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QUrl, QObject, pyqtProperty, pyqtSignal, pyqtSlot

from PyQt6.QtGui import QDesktopServices

from app.core.browser_interface import BrowserInterface
from app.services.ai_agent.llm import LLMClient, LLMConfig
from app.services.ai_agent.loop import DOM_JS_PATH, AgentSession, check_navigation_url, save_transcript
from app.services.run_history import RunHistory
from app.services.ai_agent.to_steps import compile_workflow, scenario_description, session_to_scenario_steps, steps_summary
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
    resultReady = pyqtSignal(object, str)
    validationReady = pyqtSignal(str, str)
    demoPrepared = pyqtSignal(str, str, str)

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
        self._pause = threading.Event()
        self._decision = threading.Event()
        self._answer = ""
        self._question = ""
        self._waiting = False
        self._outputs = {}
        self._sources = {}
        self._usage = ""
        self._outcome = ""
        self._options = {"start_url": "", "stay_on_host": True, "allow_local_files": False, "confirm_actions": True}
        self._inputs = {}
        self._verified_signature = ""
        self._demo = None
        self._validation = False
        self._history = RunHistory(DATA_ROOT / "settings" / "ai-history.json", limit=100)
        self._history_model = None
        self.validationReady.connect(self._validation_finished)
        self.resultReady.connect(self._accept_result)
        self.eventFired.connect(self._append_event)
        self.finished.connect(self._finished)
        self.saveFinished.connect(self._save_finished)

    @staticmethod
    def _workspace(session):
        return (session.enabled, session.url, session.team_id, session.email) if session.enabled else (False,)

    @pyqtSlot()
    def refresh(self):
        if self._active and self._session is not None and self._workspace(self._session) != self._workspace(get_server_session()):
            self.stop()
        if self._history_model is not None:
            self._history_model.set_rows(self._history.list(self._history_workspace(), 100))
        self.changed.emit()

    def _history_workspace(self, session=None):
        session = session or get_server_session()
        return json.dumps(self._workspace(session))

    @pyqtProperty(QObject, constant=True)
    def historyModel(self):
        from app.ui.bridge.models import DictListModel
        if self._history_model is None:
            self._history_model = DictListModel(["id", "scenario", "profile", "status", "artifacts"], parent=self)
            self._history_model.set_rows(self._history.list(self._history_workspace(), 100))
        return self._history_model

    @pyqtProperty(bool, notify=changed)
    def paused(self):
        return self._pause.is_set()

    @pyqtProperty(bool, notify=changed)
    def waiting(self):
        return self._waiting

    @pyqtProperty(str, notify=changed)
    def question(self):
        return self._question

    @pyqtProperty(str, notify=changed)
    def usageText(self):
        return self._usage

    @pyqtProperty(str, notify=changed)
    def outputsJson(self):
        return json.dumps({"data": self._outputs, "sources": self._sources}, ensure_ascii=False, indent=2) if self._outputs else ""

    @pyqtProperty("QVariantList", notify=changed)
    def tableColumns(self):
        table = next((value for value in self._outputs.values() if isinstance(value, list) and value), [])
        return list(table[0]) if table else []

    @pyqtProperty("QVariantList", notify=changed)
    def tableCells(self):
        table = next((value for value in self._outputs.values() if isinstance(value, list) and value), [])
        return [str(row.get(key, "")) for row in table[:30] for key in self.tableColumns]

    @pyqtSlot(str)
    def exportWorkflow(self, destination):
        if self.busy or not self.hasDraft:
            return
        try:
            steps = compile_workflow(self._draft_steps, self._inputs, self._outputs)
            for step in steps:
                if step.get("action") in {"goto", "type", "select_option"} and "{{" not in str(step.get("value", "")):
                    raise ValueError("Parameterize navigation and typed values before sharing")
            path = Path(QUrl(destination).toLocalFile() if destination.startswith("file:") else destination)
            if path.suffix.lower() != ".json":
                raise ValueError("Choose a JSON file")
            path.write_text(json.dumps({"name": "Shared AI workflow", "description": "Review selectors before use", "steps": steps}, ensure_ascii=False, indent=2), encoding="utf-8")
            self.state.notify("Workflow exported without profiles or input values; review selectors before sharing")
        except Exception as exc:
            self.state.notify(f"Cannot share workflow: {exc}")

    @pyqtProperty(str, notify=changed)
    def inputsJson(self):
        return json.dumps(self._inputs, ensure_ascii=False, indent=2)

    @pyqtProperty(str, notify=changed)
    def workflowStatus(self):
        return "Replay checked for these inputs" if self._verified_signature else "Not replay-checked"

    @pyqtSlot(str, bool, bool, bool)
    def configureTask(self, url, stay_on_host, local_files, confirm_actions):
        if self.busy:
            return
        self._options = {"start_url": url.strip(), "stay_on_host": stay_on_host,
                         "allow_local_files": local_files, "confirm_actions": confirm_actions}

    @pyqtSlot(str)
    def setInputs(self, text):
        if self.busy:
            return
        try:
            inputs = json.loads(text)
            compile_workflow(self._draft_steps, inputs, self._outputs)
            self._inputs = inputs
            self._verified_signature = ""
            self.changed.emit()
        except (ValueError, TypeError) as exc:
            self.state.notify(f"Invalid inputs: {exc}")

    @pyqtSlot()
    def togglePause(self):
        if not self._active or self._waiting:
            return
        if self._pause.is_set():
            self._pause.clear()
            self._status = "Resuming; the next action will re-read the page"
        else:
            self._pause.set()
            self._status = "Pausing after the current action"
        self.changed.emit()

    @pyqtSlot(str)
    def respond(self, answer):
        if not self._waiting:
            return
        if len(answer) > 2000:
            self.state.notify("Response exceeds 2000 characters")
            return
        self._answer = answer
        self._decision.set()

    async def _before_action(self, action, elements):
        while self._pause.is_set() and not self._stop.is_set():
            await asyncio.sleep(0.1)
        ask = action["name"] == "ask_user"
        mutating = action["name"] in {"click", "type", "press", "set_checked", "select_option"}
        if not ask and not (mutating and self._options["confirm_actions"]):
            return ""
        from app.services.ai_agent.actions import describe_action
        question = action["question"] if ask else "Approve this browser action? " + describe_action(action, elements)
        self._decision.clear()
        self._answer = ""
        self.eventFired.emit({"type": "approval", "text": question})
        while not self._decision.is_set() and not self._stop.is_set():
            await asyncio.sleep(0.1)
        self.eventFired.emit({"type": "resumed", "text": "Resuming"})
        return self._answer

    @pyqtSlot(object, str)
    def _accept_result(self, result, artifacts, record_history=True):
        self._outcome = result["status"]
        self._result_text = f"{result['status']}: {result.get('result', '')}"
        self._draft_steps = session_to_scenario_steps(result["steps"])
        self._secrets = dict(result.get("secrets", {}))
        self._outputs = result.get("outputs", {})
        self._sources = result.get("output_sources", {})
        self._usage = f"{result.get('requests', 0)} requests / {result.get('prompt_tokens', 0)} input tokens / {result.get('completion_tokens', 0)} output tokens"
        self._artifacts = artifacts
        if artifacts and record_history:
            try:
                self._history.record({"id": Path(artifacts).name, "workspace": self._history_workspace(self._session),
                                      "scenario": self._task[:120], "profile": self._profile_name,
                                      "status": self._outcome, "finished": time.time(), "artifacts": artifacts})
            except Exception as exc:
                self.state.notify(f"Could not save AI history: {exc}")
        self.refresh()

    @pyqtSlot()
    def openArtifacts(self):
        if self._artifacts and not QDesktopServices.openUrl(QUrl.fromLocalFile(self._artifacts)):
            self.state.notify("Could not open artifacts")

    @pyqtSlot(str)
    def loadRun(self, run_id):
        if self.busy or self.hasDraft:
            self.state.notify("Save or discard the current draft first")
            return
        row = self._history.get(run_id)
        if not row or row.get("workspace") != self._history_workspace():
            self.state.notify("Run is not in this workspace")
            return
        try:
            path = (Path(row["artifacts"]) / "transcript.json").resolve()
            if not path.is_relative_to((DATA_ROOT / "outputs" / "ai-runs").resolve()) or path.stat().st_size > 4 * 1024 * 1024:
                raise ValueError("Invalid transcript path or size")
            result = json.loads(path.read_text(encoding="utf-8-sig"))
            if (not isinstance(result, dict) or not isinstance(result.get("steps"), list)
                    or any(not isinstance(step, dict) for step in result["steps"])
                    or not isinstance(result.get("outputs", {}), dict)
                    or not isinstance(result.get("events", []), list)):
                raise ValueError("Invalid transcript structure")
            compile_workflow(result["steps"], {}, result.get("outputs", {}))
            self._session = copy.deepcopy(get_server_session())
            self._task = result["task"]
            self._profile_name = row["profile"]
            self._accept_result(result, str(path.parent), record_history=False)
            self._rows = result.get("events", [])[-MAX_EVENT_ROWS:]
            if self._events_model is not None:
                self._events_model.set_rows(self._rows)
            self._status = "Loaded previous AI run; review before replay"
            self.changed.emit()
        except Exception as exc:
            self.state.notify(f"Cannot load run: {exc}")

    @pyqtSlot(str)
    def exportResults(self, destination):
        if self.busy or not self._outputs:
            return
        try:
            path = Path(QUrl(destination).toLocalFile() if destination.startswith("file:") else destination)
            if path.suffix.lower() == ".csv":
                from app.services.ai_agent.extraction import table_csv
                tables = [value for value in self._outputs.values() if isinstance(value, list)]
                if len(tables) != 1:
                    raise ValueError("CSV export needs exactly one extracted table; use JSON otherwise")
                content = table_csv(tables[0])
            elif path.suffix.lower() == ".json":
                content = self.outputsJson
            else:
                raise ValueError("Choose a .json or .csv file")
            path.write_text(content, encoding="utf-8")
            self.state.notify("Results exported")
        except Exception as exc:
            self.state.notify(f"Cannot export results: {exc}")

    @pyqtSlot()
    def prepareDemo(self):
        if self.busy or self.hasDraft:
            self.state.notify("Save or discard the current draft first")
            return
        if get_server_session().enabled:
            self.state.notify("Switch to local mode for the isolated demo")
            return
        try:
            from app.services.ai_agent.templates import DemoServer
            if self._demo is None:
                self._demo = DemoServer()
            existing = {account["name"] for account in db.db_get_accounts()}
            name = "AI demo"
            serial = 1
            while name in existing:
                serial += 1
                name = f"AI demo {serial}"
            db.db_add_account({"name": name, "browser_engine": "camoufox"})
            self.operations.profiles.refresh()
            self.demoPrepared.emit(name, self._demo.url, "Extract the catalog table into the catalog variable using table format. Report the number of rows. Do not change the page.")
            self.state.notify("Isolated demo prepared. Start explicitly; the selected provider may charge for API requests.")
        except Exception as exc:
            self.state.notify(f"Cannot prepare demo: {exc}")

    @pyqtSlot(str)
    def installTemplate(self, key):
        if self.busy or self.hasDraft or get_server_session().enabled:
            self.state.notify("Use an idle local workspace to install starters")
            return
        try:
            from app.services.ai_agent.templates import template
            item = template(key)
            with db._STORAGE_LOCK:
                if db.db_get_scenario(item["name"]) is not None:
                    raise ValueError("Template already exists; open it in the editor")
                db.db_save_scenario(item["name"], item["steps"], item["description"])
            self.scenarios.refresh()
            self.scenarios._set_selected(db.Scenario(item["name"], item["steps"], item["description"]))
            self.state.setPage("Scenarios")
            self.state.notify(item["description"])
        except Exception as exc:
            self.state.notify(f"Cannot install template: {exc}")

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
            issue = self.sessionIssue(profile)
            if issue:
                raise ValueError(issue)
            session = get_server_session()
            if session.enabled and not self.scenarios._ensure_allowed("operator"):
                return
            if self._options["stay_on_host"] and not urlparse(self._options["start_url"]).hostname:
                raise ValueError("Enter a starting HTTP(S) URL or disable the starting-host restriction")
            if self._options["start_url"]:
                check_navigation_url(self._options["start_url"], self._options["allow_local_files"])
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
        self._config = ai_config()
        self._pause.clear()
        self._waiting = False
        self._question = ""
        self._outputs, self._sources, self._inputs = {}, {}, {}
        self._verified_signature = ""
        self._usage = self._outcome = ""
        self._session = session
        self._task = task
        self._profile_name = account["name"]
        self._result_text = ""
        self._artifacts = ""
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
            if self._validation:
                asyncio.run(self._run_validation(account))
            else:
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

    @pyqtSlot()
    def verifyDraft(self):
        if self.busy or not self.hasDraft:
            return
        if self._session is None or self._workspace(self._session) != self._workspace(get_server_session()):
            self.state.notify("Return to the original workspace before replaying")
            return
        try:
            session = copy.deepcopy(get_server_session())
            if session.enabled and not self.scenarios._ensure_allowed("operator"):
                return
            account = self.operations.profiles._cached_account(self._profile_name)
            if not account or not self.operations.profiles.actionState(self._profile_name).get("startAllowed"):
                raise ValueError("Original profile is unavailable")
            steps = compile_workflow(self._draft_steps, self._inputs, self._outputs)
            if not self._outputs:
                raise ValueError("Extract an output before checking a repeatable workflow")
            allowed = {"start", "goto", "extract_text", "sleep", "wait_element", "wait_for_load_state", "write_file"}
            if any(step.get("action") not in allowed for step in steps):
                raise ValueError("Automatic replay check is read-only. Review interactive drafts in the editor and use Runs explicitly.")
            self.operations._reserve([account["name"]])
        except Exception as exc:
            self.state.notify(str(exc))
            return
        self._validation_steps = steps
        self._validation = True
        self._active = True
        self._verified_signature = ""
        self._stop.clear()
        self._status = "Checking replay and output schemas..."
        self.changed.emit()
        self._thread = threading.Thread(target=self._worker, args=(copy.deepcopy(account), "", 0, session), daemon=True, name="ai-replay")
        self._thread.start()

    async def _run_validation(self, account):
        from app.services.scenario_engine import ScenarioExecutor
        self._loop = asyncio.get_running_loop()
        self._task_handle = asyncio.current_task()
        engine = str(account.get("_browser_engine") or account.get("browser_engine") or db.db_get_browser_engine())
        settings = account.get(f"{engine}_settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        account.update(_browser_engine=engine, _browser_settings={**settings, "headless": False})
        extra = account.get("extra_fields")
        account["extra_fields"] = {**(extra if isinstance(extra, dict) else {}), **self._inputs}
        executor = ScenarioExecutor(account, account_proxy(account), db.Scenario("AI replay check", copy.deepcopy(self._validation_steps)),
                                    keep_browser_open=False, cancel_event=self._stop)
        error = ""
        signature = ""
        try:
            await executor.start()
            ok = await executor.run()
            if not ok or self._stop.is_set():
                raise ValueError("Replay did not finish successfully")
            for name, expected in self._outputs.items():
                value = executor.variables.get(name, "")
                if isinstance(expected, list):
                    actual = json.loads(value)
                    if not actual or not isinstance(actual, list) or any(not isinstance(row, dict) or set(row) != set(expected[0]) for row in actual):
                        raise ValueError(f"Output schema changed: {name}")
                elif not value.strip():
                    raise ValueError(f"Output is empty: {name}")
            signature = json.dumps(self._validation_steps, sort_keys=True)
        except asyncio.CancelledError:
            error = "Replay check stopped"
        except Exception as exc:
            error = str(exc)
        finally:
            try:
                await executor.close(force=True)
            except Exception as exc:
                error = error or f"Could not close replay browser: {exc}"
                signature = ""
        self.validationReady.emit(signature, error)

    @pyqtSlot(str, str)
    def _validation_finished(self, signature, error):
        self._verified_signature = signature
        self._status = "Replay check failed: " + error if error else "Replay checked: required outputs match their schemas"
        self.state.notify(self._status)
        self.changed.emit()

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
                LLMClient(self._config),
                task,
                max_steps=max_steps,
                on_event=lambda event: self.eventFired.emit(dict(event)),
                stop_check=self._stop.is_set,
                dom_js=DOM_JS_PATH.read_text(encoding="utf-8"),
                start_url=self._options["start_url"],
                allow_local_files=self._options["allow_local_files"],
                allowed_host=(urlparse(self._options["start_url"]).hostname or "") if self._options["stay_on_host"] else "",
                before_action=self._before_action,
                pause_check=self._pause.is_set,
            )
            result = await session.run()
            try:
                save_transcript(result, artifacts)
                artifact_path = str(artifacts)
            except Exception as exc:
                self.eventFired.emit({"type": "error", "text": f"Could not save transcript: {exc}"})
                artifact_path = ""
            self.resultReady.emit(result, artifact_path)
        finally:
            try:
                await browser.close(force=True)
            except Exception:
                pass

    @pyqtSlot(object)
    def _append_event(self, event):
        if event.get("type") == "approval":
            self._waiting = True
            self._question = event["text"]
        elif event.get("type") == "resumed":
            self._waiting = False
            self._question = ""
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
        was_validation = self._validation
        self._validation = False
        self._active = False
        self._waiting = False
        self._question = ""
        self._pause.clear()
        if error:
            self._status = f"Session failed: {error}"
        elif was_validation:
            pass
        elif self._draft_steps:
            self._status = f"{self._outcome or 'Session finished'} / {steps_summary(self._draft_steps)}"
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
        self._outputs, self._sources, self._inputs = {}, {}, {}
        self._verified_signature = ""
        self._usage = self._outcome = ""
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
        if self._session is not None and self._workspace(session) != self._workspace(self._session):
            self.state.notify("Switch back to the workspace where this AI task started before saving")
            return
        if session.enabled and not self.scenarios._ensure_allowed("manager"):
            return
        name = str(name or "").strip()
        if not name or len(name) > 100:
            self.state.notify("Enter a scenario name (1-100 characters)")
            return
        try:
            steps = compile_workflow(self._draft_steps, self._inputs, self._outputs)
        except ValueError as exc:
            self.state.notify(str(exc))
            return
        steps[0]["_ai_replay_checked"] = bool(self._verified_signature and self._verified_signature == json.dumps(steps, sort_keys=True))
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
        if self._workspace(session) != self._workspace(get_server_session()):
            self.state.notify("AI scenario saved in its original workspace")
            return
        self.scenarios.refresh()
        if scenario_id:
            self.scenarios._server_scenario_ids[scenario.name] = scenario_id
        self.scenarios._set_selected(scenario)
        self.state.setPage("Scenarios")
        notice = f"AI draft saved: {scenario.name}. Set required inputs in profile variables; replay in Runs to verify outputs."
        if secrets:
            notice += f". Fill the profile variable(s) {', '.join(sorted(secrets))} before replay"
        self.state.notify(notice)

    @pyqtSlot()
    def shutdown(self):
        if self._demo is not None:
            self._demo.close()
            self._demo = None
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
