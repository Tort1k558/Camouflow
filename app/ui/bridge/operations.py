"""Desktop execution queue, result inspection and local workspace operations."""

from __future__ import annotations

import asyncio
import copy
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, QObject, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices

from app.services.cloud_sync import CloudWorkspaceSync
from app.services.profile_backup import export_profile, restore_profile
from app.services.proxy_policy import account_proxy, choose_proxy
from app.services.run_queue import RunQueue, TERMINAL
from app.services.scenario_engine import ScenarioExecutor
from app.services.scenario_debug import ScenarioDebugSession
from app.ui.scenario_debugger_window import ScenarioDebuggerWindow
from app.services.server_client import ServerClient, get_server_session, role_allows
from app.storage import db
from app.ui.bridge.models import DictListModel


class OperationsBridge(QObject):
    changed = pyqtSignal()
    message = pyqtSignal(str)
    uiCall = pyqtSignal(object)

    def __init__(self, profiles, scenarios, state, parent=None):
        super().__init__(parent)
        self.profiles, self.scenarios, self.state = profiles, scenarios, state
        self._model = DictListModel(["id", "scenario", "profile", "status", "due", "error", "artifacts", "duration"], parent=self)
        self._debug_windows = {}
        self._debug_enabled = str(db.db_get_setting("general_debug_mode") or "").lower() in {"true", "1"}
        self._busy = False
        self._preview = ""
        self._plan = None
        self._selected = ""
        self._details = ""
        self._selection_workspace = self._workspace()
        self._selection = []
        self._reserved = set()
        self._reservation_labels = {}
        self._reservation_lock = threading.RLock()
        self._proxy_lock = threading.Lock()
        self.uiCall.connect(self._invoke)
        state.cloudChanged.connect(self._check_selection_workspace)
        self.queue = RunQueue(db.SETTINGS_DIR / "run-queue.json", self._run_job, lambda: self.uiCall.emit(self.refresh))
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(lambda: self.queue.tick(workspace=self._workspace()))
        self.timer.start()
        self.refresh()

    def _check_selection_workspace(self):
        workspace = self._workspace()
        if workspace != self._selection_workspace:
            self._selection_workspace = workspace
            self.clearSelection()
            self._selected = ""
            self._details = ""
            self.queue.configure(self.queue.parallelism, True)
            self.refresh()

    @pyqtSlot(object)
    def _invoke(self, callback):
        callback()

    @pyqtProperty(bool, notify=changed)
    def debugEnabled(self):
        return self._debug_enabled

    @pyqtSlot(bool)
    def setDebugEnabled(self, enabled):
        self._debug_enabled = enabled
        self.changed.emit()

    def _show_debugger(self, job, session):
        if session.stop_requested():
            return
        snapshots = {name: row["steps"] for name, row in job.get("library", {}).items()}
        snapshots[job["scenario"]] = job["steps"]
        window = ScenarioDebuggerWindow(session, snapshots=snapshots)
        self._debug_windows[job["id"]] = window
        window.destroyed.connect(lambda: self._debug_windows.pop(job["id"], None))
        window.show()
        window.raise_()

    def _debug_update(self, job_id, update):
        window = self._debug_windows.get(job_id)
        if window:
            window.apply_update(update)

    def _debug_finished(self, job_id):
        window = self._debug_windows.get(job_id)
        if window:
            window.mark_finished()

    @pyqtProperty(QObject, constant=True)
    def jobsModel(self):
        return self._model

    @pyqtProperty(int, notify=changed)
    def parallelism(self):
        return self.queue.parallelism

    @pyqtProperty(bool, notify=changed)
    def paused(self):
        return self.queue.paused

    @pyqtProperty(bool, notify=changed)
    def busy(self):
        return self._busy

    @pyqtProperty(str, notify=changed)
    def preview(self):
        return self._preview

    @pyqtProperty(str, notify=changed)
    def details(self):
        return self._details

    @pyqtProperty(str, notify=changed)
    def selectedProfiles(self):
        return "\n".join(self._selection)

    @pyqtSlot(str)
    def prepareRun(self, names):
        self._selection = self._names(names)
        self.changed.emit()
        self.state.setPage("ScenarioRuns")

    @pyqtSlot(str, bool)
    def selectProfile(self, name, selected):
        if selected and name not in self._selection:
            self._selection.append(name)
        elif not selected and name in self._selection:
            self._selection.remove(name)
        self.changed.emit()

    @pyqtSlot()
    def clearSelection(self):
        self._selection = []
        self.changed.emit()

    def _notify(self, message):
        self.message.emit(message)
        self.state.notify(message)

    @pyqtSlot()
    def refresh(self):
        rows = []
        for job in reversed(self.queue.snapshot()):
            if job.get("workspace") != self._workspace():
                continue
            rows.append({**job, "due": datetime.fromtimestamp(job["due"]).strftime("%Y-%m-%d %H:%M"),
                         "duration": f"{max(0, (job.get('finished') or time.time()) - job['started']):.1f}s" if job["started"] else "—"})
        self._model.set_rows(rows)
        if self._selected:
            self.selectJob(self._selected)
        self.changed.emit()

    @staticmethod
    def _workspace():
        session = get_server_session()
        return f"{session.url}|{session.team_id}" if session.enabled else "local"

    @staticmethod
    def _names(text):
        return list(dict.fromkeys(n.strip() for n in text.splitlines() if n.strip()))

    def _accounts(self):
        if get_server_session().enabled and QThread.currentThread() == self.thread():
            return self.profiles._accounts_cache if self.profiles._accounts_session == get_server_session() else []
        return self.profiles._server_accounts() if get_server_session().enabled else db.db_get_accounts()

    @pyqtSlot(str, str, str, str, str)
    def enqueue(self, names, scenario_name, when, policy, pool):
        try:
            if not self.scenarios._ensure_allowed("operator"):
                return
            scenario = self.scenarios._get_scenario(scenario_name.strip())
            if scenario is None:
                raise ValueError("Scenario not found")
            error = self.scenarios._validate_scenario(scenario)
            if error:
                raise ValueError(error)
            selected = self._names(names)
            accounts = {a["name"]: a for a in self._accounts()}
            if not selected or any(n not in accounts for n in selected):
                raise ValueError("Select existing profiles")
            due = datetime.strptime(when.strip(), "%Y-%m-%d %H:%M").timestamp() if when.strip() else time.time()
            if when.strip() and due < time.time() - 60:
                raise ValueError("Scheduled time is in the past")
            if policy not in {"unchanged", "check", "replace_failed"}:
                raise ValueError("Invalid proxy policy")
            if policy == "replace_failed" and not pool.strip():
                raise ValueError("Select a proxy pool for replacement")
            library = {s.name: {"steps": s.steps, "description": s.description or ""} for s in self.scenarios._list_scenarios()}
            self.queue.enqueue([{"profile": n, "scenario": scenario.name, "workspace": self._workspace(),
                                 "profile_id": str(accounts[n].get("id") or ""),
                                 "steps": copy.deepcopy(scenario.steps), "description": scenario.description or "",
                                 "policy": policy, "pool": pool.strip(), "library": library, "debug": self._debug_enabled} for n in selected], due)
            self._notify(f"Queued {len(selected)} profile(s). Resume the queue when ready; keep the application open.")
        except Exception as exc:
            self._notify(str(exc))

    @pyqtSlot(int, bool)
    def configure(self, parallelism, paused):
        try:
            self.queue.configure(parallelism, paused)
        except Exception as exc:
            self._notify(str(exc))

    @pyqtSlot(str)
    def cancel(self, job_id):
        self.queue.cancel(job_id, workspace=self._workspace())

    @pyqtSlot()
    def clearFinished(self):
        self.queue.clear_finished(workspace=self._workspace())
        self._selected = ""
        self._details = ""
        self.changed.emit()

    def isReserved(self, name):
        with self._reservation_lock:
            return db.profile_dir_for_email(name).resolve() in {db.profile_dir_for_email(n).resolve() for n in self._reserved}

    def reservationLabel(self, name):
        with self._reservation_lock:
            return self._reservation_labels.get(name, "In use locally")

    def _reserve(self, names, reason="In use locally"):
        with self._reservation_lock:
            targets = {db.profile_dir_for_email(n).resolve() for n in names}
            occupied = {db.profile_dir_for_email(n).resolve() for n in self._reserved | set(self.profiles._live_browsers)}
            if targets & occupied:
                raise ValueError("Stop running profiles before this operation")
            if self.scenarios._run_cancel_event is not None:
                raise ValueError("Wait for the current scenario run to finish")
            self._reserved.update(names)
            self._reservation_labels.update({name: reason for name in names})
        self.uiCall.emit(self.profiles._render_accounts)

    def _release(self, names):
        with self._reservation_lock:
            self._reserved.difference_update(names)
            for name in names:
                self._reservation_labels.pop(name, None)
        self.uiCall.emit(self.profiles.refresh)

    def _run_job(self, job, cancel):
        if job["workspace"] != self._workspace():
            raise ValueError("Workspace changed. Switch back and explicitly retry this job.")
        name = job["profile"]
        self._reserve([name], reason="Scenario running")
        client = ServerClient() if get_server_session().enabled else None
        locked = False
        heartbeat_stop = threading.Event()
        heartbeat_errors = []
        run_id = ""
        started = time.monotonic()
        try:
            if client:
                context = client.request("GET", "/api/v1/auth/context")
                memberships = context.get("teams", [])
                member = next((t for t in memberships if str(t.get("id")) == client.session.team_id), {})
                if not context.get("user", {}).get("is_superadmin") and not role_allows(member.get("role", ""), "operator"):
                    raise ValueError("Cloud operator permission required")
                rows = client.profiles()
                row = next((r for r in rows if str(r.get("id")) == job["profile_id"]), None)
                if row is None or row["name"] != name:
                    raise ValueError("Queued cloud profile was removed or renamed")
                proxies = client.proxies()
                proxy = next((p for p in proxies if p["id"] == row.get("proxy_id")), {})
                account = CloudWorkspaceSync._profile_from_remote(row, proxy.get("value", ""))
                account["id"] = row["id"]
                client.lock_profile(row["id"])
                locked = True
                def renew():
                    while not heartbeat_stop.wait(40):
                        try:
                            client.heartbeat_profile_lock(row["id"])
                        except Exception as exc:
                            heartbeat_errors.append(str(exc))
                            cancel.set()
                            return
                threading.Thread(target=renew, daemon=True, name="queue-lock-heartbeat").start()
            else:
                account = next((a for a in db.db_get_accounts() if a["name"] == name), None)
                if account is None:
                    raise ValueError("Queued local profile was removed")
            with self._proxy_lock:
                if client:
                    candidates = [{**p, "assigned_to": p.get("assigned_profile_id")} for p in client.proxies() if p.get("group_name") == job["pool"]]
                    used = {r.get("proxy_id") for r in client.profiles() if r["id"] != account["id"]}
                    candidates = [p for p in candidates if p["id"] not in used]
                else:
                    pools = json.loads(db.db_get_setting("proxy_pools") or "{}")
                    candidates = pools.get(job["pool"], {}).get("proxies", [])
                    assignments = {account_proxy(a): a["name"] for a in db.db_get_accounts() if account_proxy(a) and a["name"] != name}
                    candidates = [p for p in candidates if p.get("value") not in assignments]
                value = choose_proxy(account, job["policy"], candidates, cancel)
                if value != account_proxy(account):
                    if client:
                        if not role_allows(member.get("role", ""), "manager") and not context.get("user", {}).get("is_superadmin"):
                            raise ValueError("Replacing cloud proxies requires manager permission")
                        chosen = next(p for p in candidates if p["value"] == value)
                        client.update_profile(account["id"], {"proxy_id": chosen["id"]})
                        client.update_proxy(chosen["id"], {"assigned_profile_id": account["id"]})
                    else:
                        with db._STORAGE_LOCK:
                            fresh = json.loads(db.db_get_setting("proxy_pools") or "{}")
                            entries = fresh.get(job["pool"], {}).get("proxies", [])
                            chosen = next((p for p in entries if p.get("value") == value and p.get("assigned_to") in {None, "", name}), None)
                            occupied = any(account_proxy(a) == value and a["name"] != name for a in db.db_get_accounts())
                            if chosen is None or occupied:
                                raise ValueError("Proxy assignment changed during health check. Launch stopped.")
                            chosen["assigned_to"] = name
                            db.db_set_setting("proxy_pools", json.dumps(fresh, ensure_ascii=False))
                            db.db_update_account(name, CloudWorkspaceSync._proxy_fields(value))
                    account.update(CloudWorkspaceSync._proxy_fields(value))
            if cancel.is_set():
                return {"status": "canceled", "error": "Canceled before browser launch"}
            scenario = db.Scenario(job["scenario"], job["steps"], job["description"])
            if client:
                record = client.create_scenario_run({"profile_id": account["id"], "profile_name": name, "scenario_name": scenario.name, "logs": {"source": "desktop-queue", "queue_id": job["id"]}})
                run_id = str(record["id"])
            debug_session = None
            if job.get("debug"):
                debug_session = ScenarioDebugSession(
                    ui_invoke=self.uiCall.emit, cancel_event=cancel,
                    on_update=lambda update: self._debug_update(job["id"], update))
                debug_session.pause()
                self.uiCall.emit(lambda: self._show_debugger(job, debug_session))
            async def execute():
                engine = account.get("_browser_engine") or account.get("browser_engine") or "camoufox"
                account["_browser_engine"] = engine
                account["_browser_settings"] = account.get("cloakbrowser_settings" if engine == "cloakbrowser" else "camoufox_settings", {})
                runner = ScenarioExecutor(account, account_proxy(account), scenario, keep_browser_open=False, cancel_event=cancel, debug_session=debug_session)
                if debug_session:
                    runner.add_process_exit_callback(debug_session.notify_browser_closed)
                runner._scenario_library = {name: db.Scenario(name, row["steps"], row.get("description")) for name, row in job.get("library", {}).items()}
                if client:
                    runner._tag_updater = lambda tag: client.update_profile(account["id"], {"group_name": tag})
                try:
                    await runner.start()
                    await runner.start_run_capture()
                    ok, reason = await runner._execute_steps(scenario.steps, scenario.name, scenario_path=None)
                    return {"status": "success" if ok else "failed", "error": reason or "", "artifacts": str(runner._run_artifact_dir or "")}
                except Exception as exc:
                    return {"status": "failed", "error": str(exc), "artifacts": str(runner._run_artifact_dir or "")}
                finally:
                    try:
                        await runner.stop_run_capture()
                    finally:
                        await runner.close(force=True)
            try:
                result = asyncio.run(execute())
            finally:
                if debug_session:
                    debug_session.request_stop()
                    self.uiCall.emit(lambda: self._debug_finished(job["id"]))
            if heartbeat_errors:
                result.update(status="failed", error="Cloud profile lock lost: " + heartbeat_errors[0])
            if client and run_id:
                client.update_scenario_run(run_id, {"status": "canceled" if cancel.is_set() else result["status"], "error": result["error"], "duration_ms": int((time.monotonic() - started) * 1000)})
            return result
        except Exception as exc:
            if client and run_id:
                try:
                    client.update_scenario_run(run_id, {"status": "failed", "error": str(exc), "duration_ms": int((time.monotonic() - started) * 1000)})
                except Exception:
                    pass
            raise
        finally:
            heartbeat_stop.set()
            if client and locked:
                try:
                    client.unlock_profile(job["profile_id"])
                except Exception as exc:
                    self.uiCall.emit(lambda error=str(exc): self._notify("Could not release cloud lock: " + error))
            self._release([name])

    @pyqtSlot(str)
    def selectJob(self, job_id):
        self._selected = job_id
        job = next((j for j in self.queue.snapshot() if j["id"] == job_id), None)
        self._details = json.dumps({k: v for k, v in job.items() if k not in {"steps", "library"}}, ensure_ascii=False, indent=2) if job else ""
        if job and job.get("artifacts"):
            path = Path(job["artifacts"]) / "error.json"
            if path.is_file() and path.resolve().is_relative_to(db.OUTPUTS_DIR.resolve()):
                self._details += "\n\nFailure details:\n" + path.read_text(encoding="utf-8")
        self.changed.emit()

    @pyqtSlot(str, str)
    def openResultFile(self, job_id, kind):
        job = next((j for j in self.queue.snapshot() if j["id"] == job_id), {})
        directory = Path(job.get("artifacts") or "").resolve()
        if not job.get("artifacts") or not directory.is_relative_to(db.OUTPUTS_DIR.resolve()):
            self._notify("No artifacts available")
            return
        choices = {"screenshot": ("page.png", "viewport.png"), "trace": ("trace.zip",)}
        path = next((directory / n for n in choices.get(kind, ()) if (directory / n).is_file()), None)
        if path is None:
            self._notify("Requested artifact was not captured")
        elif kind == "screenshot":
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                self._notify("Could not open screenshot")
        else:
            import subprocess
            import sys
            command = [sys.executable, "--show-trace", str(path)] if getattr(sys, "frozen", False) else [sys.executable, "-m", "playwright", "show-trace", str(path)]
            def viewer():
                log = directory / "trace-viewer.log"
                try:
                    with log.open("w", encoding="utf-8") as output:
                        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                        code = process.wait()
                    if code:
                        self.uiCall.emit(lambda: self._notify(f"Trace viewer exited with an error. Check {log}; the Playwright viewer requires its Chromium browser installation."))
                except OSError as exc:
                    self.uiCall.emit(lambda error=str(exc): self._notify("Cannot launch trace viewer: " + error))
            threading.Thread(target=viewer, daemon=True, name="trace-viewer").start()

    @pyqtSlot(str)
    def retry(self, job_id):
        job = next((j for j in self.queue.snapshot() if j["id"] == job_id), None)
        if not job or job["status"] not in TERMINAL:
            self._notify("Select a finished job")
            return
        if job["workspace"] != self._workspace() or not self.scenarios._ensure_allowed("operator"):
            self._notify("Switch to the original workspace before retrying")
            return
        try:
            self.queue.enqueue([{k: job[k] for k in ("profile", "profile_id", "scenario", "workspace", "steps", "description", "policy", "pool", "library") if k in job}], time.time())
        except Exception as exc:
            self._notify(str(exc))

    @pyqtSlot(str)
    def openArtifacts(self, job_id):
        job = next((j for j in self.queue.snapshot() if j["id"] == job_id), {})
        path = Path(job.get("artifacts") or "").resolve()
        if not job.get("artifacts") or not path.is_dir() or not path.is_relative_to(db.OUTPUTS_DIR.resolve()):
            self._notify("No artifacts available")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self._notify("Could not open artifact directory")

    def _background(self, names, work):
        if self._busy:
            self._notify("Wait for the current workspace operation")
            return
        try:
            self._reserve(names)
        except Exception as exc:
            self._notify(str(exc))
            return
        self._busy = True
        self.changed.emit()
        def worker():
            try:
                result = work()
            except Exception as exc:
                result = str(exc)
            finally:
                self._release(names)
            def done():
                self._busy = False
                self._notify(str(result))
                self.state.refreshAll()
                self.changed.emit()
            self.uiCall.emit(done)
        threading.Thread(target=worker, daemon=True, name="workspace-operation").start()

    @pyqtSlot(str, str, str)
    def previewBulk(self, names, action, value):
        self._plan = None
        try:
            if get_server_session().enabled:
                raise ValueError("Bulk local edits require local mode; cloud profiles are not modified")
            selected = self._names(names)
            accounts = {a["name"]: a for a in db.db_get_accounts()}
            if not selected or any(n not in accounts for n in selected):
                raise ValueError("Select existing local profiles")
            if action == "tag":
                updates = {"stage": value.strip()}
            elif action == "proxy":
                updates = CloudWorkspaceSync._proxy_fields(value.strip())
                if not updates:
                    raise ValueError("Enter a valid proxy URL, including scheme and port")
            elif action == "settings":
                payload = json.loads(value)
                if set(payload) != {"engine", "settings"} or payload["engine"] not in {"camoufox", "cloakbrowser"} or not isinstance(payload["settings"], dict):
                    raise ValueError('Expected {"engine":"camoufox","settings":{...}}')
                updates = {"_browser_engine": payload["engine"], payload["engine"] + "_settings": payload["settings"]}
            else:
                raise ValueError("Unknown bulk action")
            self._plan = {"names": selected, "before": {n: accounts[n] for n in selected}, "updates": updates}
            self._preview = json.dumps({"profiles": selected, "changes": updates}, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._preview = str(exc)
        self.changed.emit()

    @pyqtSlot()
    def applyBulk(self):
        plan = copy.deepcopy(self._plan)
        if not plan or get_server_session().enabled:
            self._notify("Create a local changes preview first")
            return
        def apply():
            with db._STORAGE_LOCK:
                accounts = db._load_accounts_raw()
                current = {a["name"]: a for a in db.db_get_accounts()}
                if any(current.get(n) != plan["before"][n] for n in plan["names"]):
                    raise ValueError("Profiles changed after preview. Review a new preview.")
                changed = [db._normalize_account({**a, **plan["updates"]}) if a["name"] in plan["names"] else a for a in accounts]
                db._save_accounts_raw(changed)
            return f"Updated {len(plan['names'])} profile(s)"
        self._plan = None
        self._background(plan["names"], apply)

    @pyqtSlot(str, str, bool, bool)
    def exportBackup(self, name, destination, sessions, secrets):
        if get_server_session().enabled:
            self._notify("Switch to local mode to export local browser files")
            return
        path = QUrl(destination).toLocalFile() if destination.startswith("file:") else destination
        self._background([name], lambda: (export_profile(name, Path(path), sessions, secrets), "Archive saved and checksummed")[1])

    @pyqtSlot(str, str)
    def exportSelected(self, names, destination):
        if get_server_session().enabled:
            self._notify("Switch to local mode to export local profiles")
            return
        selected = self._names(names)
        if not selected:
            self._notify("Select profiles first")
            return
        folder = Path(QUrl(destination).toLocalFile())
        def work():
            import uuid
            if not folder.is_dir():
                raise ValueError("Select an existing output directory")
            completed = []
            for name in selected:
                path = folder / f"{db._safe_profile_name(name)[:80]}-{uuid.uuid4().hex[:8]}.zip"
                try:
                    export_profile(name, path, False, False)
                except Exception as exc:
                    return f"Exported {len(completed)}/{len(selected)} profiles; stopped at {name}: {exc}. Existing exports were retained."
                completed.append(path)
            return f"Exported {len(completed)} metadata archives without secrets or sessions"
        self._background(selected, work)

    @pyqtSlot(str, str, bool)
    def restoreBackup(self, source, new_name, import_scenarios):
        if get_server_session().enabled:
            self._notify("Switch to local mode to restore a local profile")
            return
        path = QUrl(source).toLocalFile() if source.startswith("file:") else source
        self._background([new_name], lambda: f"Restored to {restore_profile(Path(path), new_name, import_scenarios)}")

    def shutdown(self):
        self.timer.stop()
        for window in list(self._debug_windows.values()):
            window.close()
        self.queue.shutdown()
