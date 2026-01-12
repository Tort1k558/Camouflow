"""Scenario execution helpers."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Callable, Dict, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox
from app.core.browser_interface import BrowserInterface
from app.services.scenario_engine import run_scenario
from app.services.scenario_debug import ScenarioDebugSession
from app.storage.db import db_get_accounts, db_get_scenario, db_get_scenario_path, db_get_setting
from app.ui.scenario_debugger_window import ScenarioDebuggerWindow

LOGGER = logging.LoggerAdapter(logging.getLogger(__name__), {"profile": "ui"})


class _UiInvoker(QObject):
    """Helper that executes callables on the main Qt thread."""

    _request = pyqtSignal(object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._request.connect(self._run)

    def invoke(self, func: Callable[[], None]) -> None:
        self._request.emit(func)

    def _run(self, func: object) -> None:
        if callable(func):
            try:
                func()
            except Exception:
                # Swallow exceptions during UI dispatch to avoid crashes.
                LOGGER.exception("UI dispatch failed")


class ScenarioRunnerMixin:
    def _general_debug_mode_enabled(self) -> bool:
        try:
            raw = (db_get_setting("general_debug_mode") or "").strip().lower()
        except Exception:
            LOGGER.exception("Failed to read general_debug_mode setting")
            raw = ""
        return raw in {"1", "true", "yes", "on"}

    def _build_runtime_shared(self) -> Dict[str, object]:
        runtime_shared: Dict[str, object] = {}
        for key, payload in self.shared_variables.items():
            if isinstance(payload, dict):
                typ = payload.get("type", "string")
                val = payload.get("value")
                if typ == "list" and isinstance(val, list):
                    runtime_shared[key] = list(map(str, val))
                else:
                    runtime_shared[key] = str(val)
            else:
                runtime_shared[key] = str(payload)
        return runtime_shared

    def _apply_shared_back(self, runtime_shared: Dict[str, object]) -> None:
        for key, val in runtime_shared.items():
            if key in self.shared_variables and isinstance(self.shared_variables[key], dict):
                typ = self.shared_variables[key].get("type", "string")
                if typ == "list" and isinstance(val, str):
                    self.shared_variables[key]["value"] = [ln for ln in val.splitlines() if ln]
                elif typ == "list" and isinstance(val, list):
                    self.shared_variables[key]["value"] = val
                else:
                    self.shared_variables[key]["value"] = val
            else:
                self.shared_variables[key] = {"type": "string", "value": val}
        self._save_shared_vars()

    def _ensure_ui_invoker(self) -> None:
        if getattr(self, "_ui_invoker", None) is None:
            parent = self if isinstance(self, QObject) else None
            self._ui_invoker = _UiInvoker(parent)

    def _invoke_on_ui_thread(self, func: Callable[[], None]) -> None:
        if not callable(func):
            return
        invoker = getattr(self, "_ui_invoker", None)
        if invoker is None:
            func()
            return
        invoker.invoke(func)

    def _run_scenario_async(self, accounts: List[Dict], scenario: Scenario, label: str) -> None:
        if not accounts:
            return
        runtime_shared = self._build_runtime_shared()
        limit = self.count_spin.value()
        prepared_accounts = [self._prepare_account_payload(acc) for acc in accounts]
        scenario_path = db_get_scenario_path(scenario.name)

        debug_session: Optional[ScenarioDebugSession] = None
        debug_window: Optional[ScenarioDebuggerWindow] = None
        if self._general_debug_mode_enabled():
            try:
                existing_session = getattr(self, "_scenario_debug_session", None)
                if existing_session:
                    existing_session.request_stop()
            except Exception:
                LOGGER.exception("Failed to stop existing debug session")
            try:
                existing_window = getattr(self, "_scenario_debug_window", None)
                if existing_window:
                    existing_window.close()
            except Exception:
                LOGGER.exception("Failed to close existing debug window")

            window_ref: Dict[str, object] = {"window": None}

            def _on_browser_closed():
                wnd = window_ref.get("window")
                if wnd is not None:
                    try:
                        wnd.close()
                    except Exception:
                        LOGGER.exception("Failed to close debug window on browser close")
                window_ref["window"] = None
                try:
                    self._scenario_debug_window = None
                    self._scenario_debug_session = None
                except Exception:
                    LOGGER.exception("Failed to clear debug session references")

            def _on_finished(ok: bool, reason: Optional[str] = None) -> None:
                wnd = window_ref.get("window")
                if wnd is not None:
                    try:
                        wnd.mark_finished(stopped=not ok)
                    except Exception:
                        LOGGER.exception("Failed to mark debug window finished")

            def _on_update(update):
                wnd = window_ref.get("window")
                if wnd is not None:
                    try:
                        wnd.apply_update(update)
                    except Exception:
                        LOGGER.exception("Failed to apply debugger update")

            debug_session = ScenarioDebugSession(
                ui_invoke=self._invoke_on_ui_thread,
                on_update=_on_update,
                on_browser_closed=_on_browser_closed,
                on_finished=_on_finished,
            )
            debug_session.pause()
            # No parent => independent window (does not minimize/restore with the main window).
            debug_window = ScenarioDebuggerWindow(debug_session, scenario_path=scenario_path, parent=None)
            window_ref["window"] = debug_window
            debug_window.show()
            try:
                debug_window.raise_()
                debug_window.activateWindow()
            except Exception:
                LOGGER.exception("Failed to raise or activate debug window")
            self._scenario_debug_session = debug_session
            self._scenario_debug_window = debug_window
            try:
                self.log("Scenario debugger window opened (General debug mode).")
            except Exception:
                LOGGER.exception("Failed to write debug mode log entry")

        def worker():
            processed = run_scenario(
                prepared_accounts,
                scenario,
                max_accounts=limit,
                shared_vars=runtime_shared,
                debug_session=debug_session,
                scenario_path=scenario_path,
            )
            def finish():
                self._apply_shared_back(runtime_shared)
                self.refresh_accounts_list()
                # In debug mode the runner may stay alive until the browser closes;
                # completion is handled via the debugger window callbacks.
                self.log(f"Done: {len(processed)} accounts finished scenario {scenario.name} ({label})")
            self._invoke_on_ui_thread(finish)

        threading.Thread(target=worker, daemon=True).start()

    def open_browser_for_account(self, account_name: str) -> None:
        target_name = str(account_name or "").strip()
        acc = next((a for a in db_get_accounts() if str(a.get("name") or "") == target_name), None)
        if not acc:
            QMessageBox.warning(self, "Error", f"Account {account_name} not found")
            return
        profile_name = str(acc.get("name") or target_name)
        if profile_name in self.live_browsers:
            QMessageBox.information(self, "Browser already running", f"Browser already started for {profile_name}")
            return
        if hasattr(self, "_set_account_action_button_state"):
            try:
                self._set_account_action_button_state(profile_name, "launching")
            except Exception:
                LOGGER.exception("Failed to set action button state to launching")

        proxy = self._proxy_string_for(acc)
        browser = BrowserInterface(
            profile_name=profile_name,
            proxy=proxy,
            keep_browser_open=True,
            camoufox_settings=self._camoufox_settings_for_account(acc),
        )

        browser.add_close_callback(
            lambda: self._invoke_on_ui_thread(lambda: self._handle_browser_closed(profile_name, browser))
        )

        async def runner():
            await browser.start()

        browser.add_ready_callback(
            lambda: self._invoke_on_ui_thread(
                lambda: self._mark_browser_running(profile_name, acc, browser, source="ready")
            )
        )

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _run_and_keep_alive() -> None:
                try:
                    await runner()
                except Exception as exc:
                    LOGGER.exception("Browser start failed for %s", profile_name)
                    self._invoke_on_ui_thread(
                        lambda exc=exc: self._handle_browser_failure(profile_name, exc)
                    )
                    return

                self._invoke_on_ui_thread(
                    lambda: self._mark_browser_running(profile_name, acc, browser, source="fallback")
                )

                ping_counter = 0
                while not getattr(browser, "_closed_notified", False):
                    await asyncio.sleep(0.5)
                    ping_counter += 1
                    if ping_counter < 6:
                        continue
                    ping_counter = 0
                    page = getattr(browser, "page", None)
                    if page is None:
                        browser._notify_browser_closed()
                        break
                    try:
                        if getattr(page, "is_closed", None) and page.is_closed():
                            browser._notify_browser_closed()
                            break
                        await page.evaluate("1")
                    except Exception:
                        LOGGER.exception("Browser keep-alive ping failed for %s", profile_name)
                        browser._notify_browser_closed()
                        break

                try:
                    await browser.close(force=True)
                except Exception:
                    LOGGER.exception("Failed to close browser for %s", profile_name)

            try:
                loop.run_until_complete(_run_and_keep_alive())
            finally:
                try:
                    pending = asyncio.all_tasks(loop)
                except Exception:
                    LOGGER.exception("Failed to enumerate pending asyncio tasks")
                    pending = set()
                for task in pending:
                    try:
                        task.cancel()
                    except Exception:
                        LOGGER.exception("Failed to cancel pending task")
                if pending:
                    try:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        LOGGER.exception("Failed to wait on pending tasks")
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    LOGGER.exception("Failed to shutdown async generators")
                try:
                    shutdown_default = getattr(loop, "shutdown_default_executor", None)
                    if callable(shutdown_default):
                        loop.run_until_complete(shutdown_default())
                except Exception:
                    LOGGER.exception("Failed to shutdown loop executor")
                loop.close()
                try:
                    asyncio.set_event_loop(None)
                except Exception:
                    LOGGER.exception("Failed to clear event loop")

        threading.Thread(target=worker, daemon=True).start()

    def _mark_browser_running(self, profile_name: str, acc: Dict, browser: BrowserInterface, source: str = "") -> None:
        existing = self.live_browsers.get(profile_name)
        if existing is browser:
            return
        if existing is not None:
            if hasattr(self, "_set_account_action_button_state"):
                try:
                    self._set_account_action_button_state(profile_name, "running")
                except Exception:
                    LOGGER.exception("Failed to set action button state to running")
            return
        self.live_browsers[profile_name] = browser
        if hasattr(self, "_set_account_action_button_state"):
            try:
                self._set_account_action_button_state(profile_name, "running")
            except Exception:
                LOGGER.exception("Failed to set action button state to running")
        try:
            browser.add_close_callback(
                lambda: self._invoke_on_ui_thread(
                    lambda: self._handle_browser_closed(profile_name, browser)
                )
            )
        except Exception:
            LOGGER.exception("Failed to attach browser close callback")
        proxy_label = acc.get("proxy_host") or "-"
        self.log(f"Browser opened for {profile_name} (proxy {proxy_label})")

    def _handle_browser_failure(self, account_name: str, error: Exception) -> None:
        if hasattr(self, "_set_account_action_button_state"):
            try:
                self._set_account_action_button_state(account_name, "idle")
            except Exception:
                LOGGER.exception("Failed to set action button state to idle")
        QMessageBox.warning(self, "Error", f"Cannot open browser for {account_name}: {error}")

    def _handle_browser_closed(self, account_name: str, browser: BrowserInterface) -> None:
        existing = self.live_browsers.get(account_name)
        if existing is browser:
            self.live_browsers.pop(account_name, None)
        if hasattr(self, "_set_account_action_button_state"):
            try:
                self._set_account_action_button_state(account_name, "idle")
            except Exception:
                LOGGER.exception("Failed to set action button state to idle")
        self.log(f"Browser closed for {account_name}")

    def open_browser_for_selected_account(self) -> None:
        selected = self._get_selected_names()
        if not selected:
            QMessageBox.warning(self, "Error", "Select an account first")
            return
        self.open_browser_for_account(selected[0])

    def start_selected_scenario(self) -> None:
        scenario_name = self.scenario_run_combo.currentText().strip()
        if not scenario_name:
            QMessageBox.warning(self, "Error", "Select a scenario to run")
            return
        scenario = db_get_scenario(scenario_name)
        if not scenario:
            # try reloading scenarios from disk
            self._reload_scenarios()
            scenario = db_get_scenario(scenario_name)
            if not scenario:
                QMessageBox.warning(self, "Error", f"Scenario {scenario_name} not found")
                return
        accounts_all = db_get_accounts()
        selected_names = self._get_selected_names()
        if selected_names:
            accounts = [
                a for a in accounts_all if str(a.get("name") or "") in selected_names
            ][: self.count_spin.value()]
        else:
            accounts = [a for a in accounts_all if (a.get("stage") or "") == scenario_name][: self.count_spin.value()]
        if not accounts:
            QMessageBox.warning(self, "Error", "No accounts to run (select them or assign the scenario)")
            return

        self.log(f"[{scenario_name}] start for {len(accounts)} accounts (limit {self.count_spin.value()})")
        self._run_scenario_async(accounts, scenario, "selection")

    def run_scenario_for_stage(self) -> None:
        stage_name = self.run_stage_combo.currentText().strip()
        scenario_name = self.scenario_run_combo.currentText().strip()
        if not stage_name:
            QMessageBox.warning(self, "Error", "Select a tag to run")
            return
        if not scenario_name:
            QMessageBox.warning(self, "Error", "Select a scenario to run")
            return
        scenario = db_get_scenario(scenario_name)
        if not scenario:
            self._reload_scenarios()
            scenario = db_get_scenario(scenario_name)
            if not scenario:
                QMessageBox.warning(self, "Error", f"Scenario {scenario_name} not found")
                return
        accounts = [
            a for a in db_get_accounts() if str(a.get("stage") or "") == stage_name
        ][: self.count_spin.value()]
        if not accounts:
            QMessageBox.warning(self, "Error", f"No accounts with tag {stage_name}")
            return

        self.log(f"[{scenario_name}] start for tag {stage_name} ({len(accounts)} accounts, limit {self.count_spin.value()})")
        self._run_scenario_async(accounts, scenario, f"tag {stage_name}")

    def _camoufox_settings_for_account(self, acc: Dict) -> Dict[str, object]:
        defaults = dict(getattr(self, "camoufox_defaults", {}) or {})
        override = acc.get("camoufox_settings")
        data: Dict[str, object] = {}
        if isinstance(override, dict):
            data = override
        elif isinstance(override, str):
            try:
                parsed = json.loads(override)
                if isinstance(parsed, dict):
                    data = parsed
            except Exception:
                LOGGER.exception("Failed to parse camoufox_settings JSON")
                data = {}
        defaults.update(data or {})
        return defaults

    def _prepare_account_payload(self, acc: Dict) -> Dict:
        payload = dict(acc)
        payload["_camoufox_settings"] = self._camoufox_settings_for_account(acc)
        return payload
