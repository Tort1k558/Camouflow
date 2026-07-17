"""Dashboard bridge for QML."""

from __future__ import annotations

import json

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.storage.db import db_get_accounts, db_get_scenarios, db_get_setting
from app.services.server_client import ServerClient, ServerClientError, server_enabled
from app.ui.bridge.models import DictListModel
from app.ui.dashboard_data import build_dashboard_metrics


class DashboardBridge(QObject):
    changed = pyqtSignal()

    def __init__(self, profiles_bridge=None, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._profiles_bridge = profiles_bridge
        self._app_state = app_state
        self._activity = DictListModel(["type", "title", "desc", "time"], parent=self)
        self._running = DictListModel(["name", "browser", "proxy", "uptime", "color"], parent=self)
        self._operator = DictListModel(["type", "title", "desc", "meta", "accent"], parent=self)
        self._issues = DictListModel(["type", "title", "desc", "meta", "accent"], parent=self)
        self._metrics = {}
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)
            app_state.cloudChanged.connect(self.refresh)
        if profiles_bridge is not None:
            profiles_bridge.countsChanged.connect(self.refresh)
        self.refresh()

    @pyqtProperty(QObject, constant=True)
    def activityModel(self) -> QObject:  # noqa: N802
        return self._activity

    @pyqtProperty(QObject, constant=True)
    def runningModel(self) -> QObject:  # noqa: N802
        return self._running

    @pyqtProperty(QObject, constant=True)
    def operatorModel(self) -> QObject:  # noqa: N802
        return self._operator

    @pyqtProperty(QObject, constant=True)
    def issuesModel(self) -> QObject:  # noqa: N802
        return self._issues

    @pyqtProperty(int, notify=changed)
    def profiles(self) -> int:
        return int(self._metrics.get("profiles", 0))

    @pyqtProperty(int, notify=changed)
    def running(self) -> int:
        return int(self._metrics.get("running", 0))

    @pyqtProperty(int, notify=changed)
    def scenarios(self) -> int:
        return int(self._metrics.get("scenarios", 0))

    @pyqtProperty(int, notify=changed)
    def proxies(self) -> int:
        return int(self._metrics.get("proxy_total", 0))

    @pyqtProperty(int, notify=changed)
    def locked(self) -> int:
        return int(self._metrics.get("locked", 0))

    @pyqtProperty(int, notify=changed)
    def failedRuns(self) -> int:  # noqa: N802
        return int(self._metrics.get("failed_runs", 0))

    @pyqtProperty(int, notify=changed)
    def failedProxies(self) -> int:  # noqa: N802
        return int(self._metrics.get("failed_proxies", 0))

    @pyqtProperty(str, notify=changed)
    def operatorSummary(self) -> str:  # noqa: N802
        if self._app_state is not None and getattr(self._app_state, "cloudEnabled", False):
            team = getattr(self._app_state, "cloudTeamName", "") or "No team"
            role = getattr(self._app_state, "cloudRole", "") or "no role"
            return f"{team} / {role}"
        return "Local workspace"

    @pyqtSlot()
    def refresh(self) -> None:
        proxy_pools = {}
        try:
            proxy_pools = json.loads(db_get_setting("proxy_pools") or "{}")
        except Exception:
            proxy_pools = {}
        live = self._profiles_bridge.live_browsers() if self._profiles_bridge is not None else {}
        accounts = db_get_accounts()
        scenarios = db_get_scenarios()
        scenario_runs = []
        audit_rows = []
        if server_enabled():
            try:
                client = ServerClient()
                if client.configured:
                    accounts = self._profiles_bridge._server_accounts() if self._profiles_bridge is not None and hasattr(self._profiles_bridge, "_server_accounts") else []
                    scenarios = client.scenarios()
                    scenario_runs = client.scenario_runs(limit=30)
                    try:
                        audit_rows = client.audit_log(limit=20)
                    except ServerClientError:
                        audit_rows = []
                    proxy_pools = {}
                    for proxy in client.proxies():
                        group = str(proxy.get("group_name") or "Default")
                        proxy_pools.setdefault(group, {"proxies": []})["proxies"].append(proxy)
            except Exception:
                accounts = []
                scenarios = []
                scenario_runs = []
                audit_rows = []
                proxy_pools = {}
        self._metrics = build_dashboard_metrics(accounts, scenarios, proxy_pools, live)
        self._metrics.update(self._operator_metrics(accounts, proxy_pools, scenario_runs))
        self._activity.set_rows(self._activity_rows(audit_rows, scenario_runs))
        rows = []
        for name, browser in live.items():
            rows.append({"name": name, "browser": getattr(browser, "browser_engine", "Camoufox"), "proxy": getattr(browser, "proxy", "None") or "None", "uptime": "live", "color": "#06b6d4"})
        self._running.set_rows(rows)
        self._operator.set_rows(self._operator_rows(accounts, scenario_runs))
        self._issues.set_rows(self._issue_rows(accounts, proxy_pools, scenario_runs))
        self.changed.emit()

    @staticmethod
    def _operator_metrics(accounts, proxy_pools, scenario_runs) -> dict:
        locked = sum(1 for acc in accounts if acc.get("lock_user_email"))
        failed_runs = sum(1 for run in scenario_runs if str(run.get("status") or "").lower() == "failed")
        failed_proxies = 0
        for pool in proxy_pools.values():
            proxies = pool.get("proxies", []) if isinstance(pool, dict) else []
            for proxy in proxies:
                status = str(proxy.get("status") or "").lower() if isinstance(proxy, dict) else ""
                check = proxy.get("last_check") if isinstance(proxy, dict) else {}
                check_status = str(check.get("status") or "").lower() if isinstance(check, dict) else ""
                if status == "failed" or check_status in {"fail", "failed"}:
                    failed_proxies += 1
        return {"locked": locked, "failed_runs": failed_runs, "failed_proxies": failed_proxies}

    def _operator_rows(self, accounts, scenario_runs) -> list[dict]:
        rows = []
        for acc in accounts:
            if acc.get("lock_user_email"):
                rows.append({
                    "type": "lock",
                    "title": str(acc.get("name") or "Profile"),
                    "desc": "Locked by " + str(acc.get("lock_user_email") or "teammate"),
                    "meta": str(acc.get("lock_expires_at") or "")[:19].replace("T", " "),
                    "accent": "#f59e0b",
                })
        for run in scenario_runs[:8]:
            status = str(run.get("status") or "").lower()
            rows.append({
                "type": "run",
                "title": str(run.get("scenario_name") or "Scenario"),
                "desc": f"{status or 'running'} / {run.get('profile_name') or 'profile'}",
                "meta": self._duration(run),
                "accent": "#22c55e" if status == "success" else "#ef4444" if status == "failed" else "#f59e0b",
            })
        return rows[:14]

    def _issue_rows(self, accounts, proxy_pools, scenario_runs) -> list[dict]:
        rows = []
        for run in scenario_runs:
            if str(run.get("status") or "").lower() == "failed":
                rows.append({
                    "type": "scenario",
                    "title": str(run.get("scenario_name") or "Failed scenario"),
                    "desc": str(run.get("error") or "Scenario failed"),
                    "meta": str(run.get("profile_name") or ""),
                    "accent": "#ef4444",
                })
        for pool_name, pool in proxy_pools.items():
            for proxy in pool.get("proxies", []) if isinstance(pool, dict) else []:
                if not isinstance(proxy, dict):
                    continue
                status = str(proxy.get("status") or "").lower()
                check = proxy.get("last_check") if isinstance(proxy.get("last_check"), dict) else {}
                check_status = str(check.get("status") or "").lower()
                if status == "failed" or check_status in {"fail", "failed"}:
                    rows.append({
                        "type": "proxy",
                        "title": str(proxy.get("name") or proxy.get("value") or "Proxy"),
                        "desc": str(check.get("error") or "Proxy check failed"),
                        "meta": str(pool_name),
                        "accent": "#ef4444",
                    })
        if not rows:
            rows.append({"type": "ok", "title": "No critical issues", "desc": "Profiles, runs and proxies look stable", "meta": "now", "accent": "#22c55e"})
        return rows[:12]

    def _activity_rows(self, audit_rows, scenario_runs) -> list[dict]:
        rows = []
        for row in audit_rows[:10]:
            rows.append({
                "type": "info",
                "title": str(row.get("action") or "Activity"),
                "desc": " ".join(part for part in [str(row.get("entity_type") or ""), str(row.get("entity_id") or "")[:8]] if part),
                "time": str(row.get("created_at") or "")[:19].replace("T", " "),
            })
        if not rows:
            rows = [
                {"type": "success", "title": "System ready", "desc": "Operator dashboard online", "time": "now"},
                {"type": "info", "title": f"{self.profiles} profiles loaded", "desc": "Workspace synchronized", "time": "now"},
                {"type": "warning", "title": f"{self.failedRuns} failed runs", "desc": "Recent scenario failures", "time": "now"},
                {"type": "info", "title": f"{self.proxies} proxies", "desc": f"{self.failedProxies} failed checks", "time": "now"},
            ]
        return rows

    @staticmethod
    def _duration(run: dict) -> str:
        ms = int(run.get("duration_ms") or 0)
        if ms >= 1000:
            return f"{ms / 1000:.1f}s"
        if ms > 0:
            return f"{ms}ms"
        return "running"
