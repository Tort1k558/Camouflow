"""QML recording controls, using the existing profile reservation and editor."""

from __future__ import annotations

import asyncio
import copy
import json
import threading
from urllib.parse import urlsplit

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.core.browser_interface import BrowserInterface
from app.services.proxy_policy import account_proxy
from app.services.scenario_recorder import ScenarioRecorder
from app.services.server_client import ServerClient, get_server_session, role_allows
from app.storage import db


class RecorderBridge(QObject):
    changed = pyqtSignal()
    updated = pyqtSignal(object, object)
    finished = pyqtSignal(str)
    saveFinished = pyqtSignal(object, str)

    def __init__(self, operations, scenarios, state, parent=None):
        super().__init__(parent)
        self.operations, self.scenarios, self.state = operations, scenarios, state
        self._session = None
        self._saving = False
        self._active = False
        self._steps = []
        self._warnings = []
        self._status = "Ready to record"
        self._profile_name = ""
        self._start_url = ""
        self._stop = threading.Event()
        self._thread = None
        self._loop = None
        self._task = None
        self._ready = False
        self.updated.connect(self._updated)
        self.finished.connect(self._finished)
        self.saveFinished.connect(self._save_finished)

    @staticmethod
    def _workspace(session):
        return (session.enabled, session.url, session.team_id, session.email) if session.enabled else (False,)

    @pyqtProperty(bool, notify=changed)
    def saving(self):
        return self._saving

    @pyqtProperty(bool, notify=changed)
    def active(self):
        return self._active

    @pyqtProperty(str, notify=changed)
    def status(self):
        return self._status

    @pyqtProperty(str, notify=changed)
    def profileName(self):  # noqa: N802
        return self._profile_name

    @pyqtProperty(str, notify=changed)
    def startUrl(self):  # noqa: N802
        return self._start_url

    @pyqtProperty(str, notify=changed)
    def preview(self):
        return json.dumps(self._steps, ensure_ascii=False, indent=2)

    @pyqtProperty(str, notify=changed)
    def warnings(self):
        return "\n".join(self._warnings)

    @pyqtProperty(bool, notify=changed)
    def hasDraft(self):  # noqa: N802
        return len(self._steps) > 1

    @pyqtSlot(object, object)
    def _updated(self, steps, warnings):
        self._steps, self._warnings = steps, warnings
        self._status = f"Recording: {max(0, len(steps) - 1)} steps"
        self.changed.emit()

    @pyqtSlot(str)
    def _finished(self, error):
        self._active = False
        self._status = error or "Recording stopped. Review and save your draft."
        self.changed.emit()

    @pyqtSlot(str, result=str)
    def recordingIssue(self, profile):
        account = self.operations.profiles._cached_account(profile)
        if not account:
            return "Choose a loaded profile"
        engine = account.get("_browser_engine") or account.get("browser_engine") or db.db_get_browser_engine()
        if engine != "camoufox":
            return "This profile uses CloakBrowser; recording requires a Camoufox profile"
        if not self.operations.profiles.actionState(profile).get("startAllowed"):
            return "Profile is unavailable or you do not have permission to start it"
        return ""

    @pyqtSlot(str, str)
    def start(self, profile, url):
        if self._active or self._saving or self.hasDraft:
            self.state.notify("Save or discard the current recording first")
            return
        try:
            session = get_server_session()
            if session.enabled and not self.scenarios._ensure_allowed("operator"):
                return
            parsed = urlsplit(url.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Enter an HTTP(S) start URL without credentials")
            account = (self.operations.profiles._cached_account(profile.strip()) if session.enabled else
                       next((a for a in db.db_get_accounts() if a["name"] == profile.strip()), None))
            if account is None:
                raise ValueError("Select an existing profile; wait for the profile list to load")
            engine = str(account.get("_browser_engine") or account.get("browser_engine") or db.db_get_browser_engine())
            if engine != "camoufox":
                raise ValueError("Recording supports Camoufox only. Select Camoufox in Browser engine first.")
            account["browser_engine"] = engine
            self.operations._reserve([account["name"]])
        except Exception as exc:
            self.state.notify(str(exc))
            return
        self._session = session
        self._steps, self._warnings = [], []
        self._profile_name = account["name"]
        self._start_url = url.strip()
        self._active = True
        self._ready = False
        self._status = "Starting recording browser..."
        self._stop.clear()
        self.changed.emit()
        self._thread = threading.Thread(target=self._worker, args=(copy.deepcopy(account), url.strip(), copy.deepcopy(session)), name="scenario-recorder", daemon=True)
        self._thread.start()

    def _worker(self, account, url, session):
        error = ""
        client = ServerClient(session) if session.enabled else None
        profile_id = str(account.get("id") or "")
        locked = False
        heartbeat_stop = threading.Event()
        heartbeat_thread = None
        heartbeat_errors = []
        try:
            if client:
                context = client.request("GET", "/api/v1/auth/context")
                member = next((t for t in context.get("teams", []) if str(t.get("id")) == session.team_id), {})
                if not context.get("user", {}).get("is_superadmin") and not role_allows(member.get("role", ""), "operator"):
                    raise ValueError("Cloud operator permission required")
                fresh = next((a for a in self.operations.profiles._server_accounts(client)
                              if str(a.get("id")) == profile_id), None)
                if fresh is None or fresh["name"] != account["name"]:
                    raise ValueError("Cloud profile was removed or renamed; refresh the profile list")
                account = fresh
                if (account.get("_browser_engine") or account.get("browser_engine") or "camoufox") != "camoufox":
                    raise ValueError("Recording supports Camoufox only")
                if self._stop.is_set():
                    return
                client.lock_profile(profile_id)
                locked = True
                def renew():
                    while not heartbeat_stop.wait(40):
                        try:
                            client.heartbeat_profile_lock(profile_id)
                        except Exception:
                            heartbeat_errors.append("Recording stopped: cloud profile lock could not be renewed")
                            self._stop.set()
                            loop, task = self._loop, self._task
                            if not self._ready and loop is not None and task is not None and not loop.is_closed():
                                loop.call_soon_threadsafe(task.cancel)
                            return
                heartbeat_thread = threading.Thread(target=renew, daemon=True, name="recording-lock-heartbeat")
                heartbeat_thread.start()
            asyncio.run(self._record(account, url))
        except asyncio.CancelledError:
            pass
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = "Recording failed. Check cloud access, the browser and connection; captured steps are retained."
        finally:
            self._loop = self._task = None
            heartbeat_stop.set()
            if heartbeat_thread:
                heartbeat_thread.join()
            if client and locked:
                try:
                    client.unlock_profile(profile_id)
                except Exception:
                    error = "Recording stopped, but cloud unlock failed. The lock will expire; captured steps are retained."
            self.operations._release([account["name"]])
            self.finished.emit(error or (heartbeat_errors[0] if heartbeat_errors else ""))

    async def _record(self, account, url):
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.current_task()
        if self._stop.is_set():
            return
        engine = str(account.get("_browser_engine") or account.get("browser_engine") or db.db_get_browser_engine())
        settings = account.get(f"{engine}_settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        browser = BrowserInterface(account["name"], proxy=account_proxy(account), browser_engine=engine,
                                   browser_settings={**settings, "headless": False}, keep_browser_open=False)
        recorder = ScenarioRecorder()
        recorder._on_change = lambda: self.updated.emit(*recorder.snapshot())
        try:
            await browser.start()
            if self._stop.is_set():
                return
            await recorder.attach(browser.page)
            await browser.page.goto(url, wait_until="domcontentloaded")
            self._ready = True
            while not self._stop.is_set() and not browser.page.is_closed() and recorder.active:
                await asyncio.sleep(0.1)
        finally:
            try:
                await recorder.stop()
            finally:
                self.updated.emit(*recorder.snapshot())
                await browser.close(force=True)

    @pyqtSlot()
    def stop(self):
        if self._stop.is_set():
            return
        self._stop.set()
        loop, task = self._loop, self._task
        if not self._ready and loop is not None and task is not None and not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)
        if self._active:
            self._status = "Stopping recording..."
            self.changed.emit()

    @pyqtSlot()
    def discard(self):
        if self._active or self._saving:
            return
        self._session = None
        self._steps, self._warnings = [], []
        self._status = "Ready to record"
        self.changed.emit()

    @pyqtSlot(str)
    def save(self, name):
        if self._active or self._saving or not self.hasDraft:
            return
        session = get_server_session()
        if self._session is not None and self._workspace(session) != self._workspace(self._session):
            self.state.notify("Switch back to the workspace where this recording was started to save it")
            return
        if session.enabled and not self.scenarios._ensure_allowed("manager"):
            return
        name = name.strip()
        if not name or len(name) > 100:
            self.state.notify("Enter a scenario name (1-100 characters)")
            return
        steps = copy.deepcopy(self._steps)
        self._saving = True
        self._status = "Saving recording..."
        self.changed.emit()
        def worker():
            try:
                scenario_id = ""
                description = "Recorded browser actions. Review before replay."
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
                self.saveFinished.emit((session, db.Scenario(name, steps, description), scenario_id), "")
            except Exception as exc:
                self.saveFinished.emit(None, str(exc))
        self._thread = threading.Thread(target=worker, daemon=True, name="recording-save")
        self._thread.start()

    @pyqtSlot(object, str)
    def _save_finished(self, result, error):
        self._saving = False
        if error:
            self._status = "Save failed. Your draft is retained."
            self.changed.emit()
            self.state.notify(f"Cannot save recording: {error}")
            return
        session, scenario, scenario_id = result
        self.discard()
        if self._workspace(session) == self._workspace(get_server_session()):
            self.scenarios.refresh()
            if scenario_id:
                self.scenarios._server_scenario_ids[scenario.name] = scenario_id
            self.scenarios._set_selected(scenario)
            self.state.setPage("Scenarios")
        self.state.notify(f"Recording saved: {scenario.name}")

    @pyqtSlot()
    def shutdown(self):
        already_stopping = self._stop.is_set()
        self._stop.set()
        loop, task = self._loop, self._task
        if not already_stopping and loop is not None and task is not None and not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)
        if self._thread is not None:
            self._thread.join(timeout=10)
