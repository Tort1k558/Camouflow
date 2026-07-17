"""Billing/plan bridge for QML.

Surfaces the team's current plan, subscription status, usage vs limits and the
plan catalog from the server, plus checkout/portal actions. No-ops gracefully
when Cloud is not connected.
"""

from __future__ import annotations

from PyQt6.QtCore import QUrl, QObject, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices

from app.services.server_client import ServerClient, ServerClientError, server_enabled
from app.ui.bridge.models import DictListModel

_OK_LICENSE = {"active", "trialing"}


def _fmt_price(plan: dict) -> str:
    cents = int(plan.get("price_cents") or 0)
    if cents <= 0:
        return "Free"
    currency = str(plan.get("currency") or "usd").upper()
    return f"${cents / 100:.2f} {currency}"


class BillingBridge(QObject):
    changed = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._plans_model = DictListModel(
            ["planId", "name", "price", "currency", "maxUsers", "maxProfiles", "maxProxies", "maxScenarios", "maxPools", "current"],
            parent=self,
        )
        self._plan = ""
        self._subscription_status = ""
        self._upgrade_available = False
        self._portal_url = ""
        self._error = ""
        self._usage_users = 0
        self._usage_profiles = 0
        self._usage_proxies = 0
        self._usage_scenarios = 0
        self._max_users = 0
        self._max_profiles = 0
        self._max_proxies = 0
        self._max_scenarios = 0
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)

    # --- models / properties ------------------------------------------------
    @pyqtProperty(QObject, constant=True)
    def plansModel(self) -> QObject:  # noqa: N802
        return self._plans_model

    @pyqtProperty(str, notify=changed)
    def plan(self) -> str:  # noqa: N802
        return self._plan

    @pyqtProperty(str, notify=changed)
    def subscriptionStatus(self) -> str:  # noqa: N802
        return self._subscription_status

    @pyqtProperty(bool, notify=changed)
    def licenseActive(self) -> bool:  # noqa: N802
        return (self._subscription_status or "").strip().lower() in _OK_LICENSE

    @pyqtProperty(bool, notify=changed)
    def upgradeAvailable(self) -> bool:  # noqa: N802
        return self._upgrade_available

    @pyqtProperty(str, notify=changed)
    def portalUrl(self) -> str:  # noqa: N802
        return self._portal_url

    @pyqtProperty(str, notify=changed)
    def billingError(self) -> str:  # noqa: N802
        return self._error

    @pyqtProperty(int, notify=changed)
    def usageUsers(self) -> int:  # noqa: N802
        return self._usage_users

    @pyqtProperty(int, notify=changed)
    def usageProfiles(self) -> int:  # noqa: N802
        return self._usage_profiles

    @pyqtProperty(int, notify=changed)
    def usageProxies(self) -> int:  # noqa: N802
        return self._usage_proxies

    @pyqtProperty(int, notify=changed)
    def usageScenarios(self) -> int:  # noqa: N802
        return self._usage_scenarios

    @pyqtProperty(int, notify=changed)
    def maxUsers(self) -> int:  # noqa: N802
        return self._max_users

    @pyqtProperty(int, notify=changed)
    def maxProfiles(self) -> int:  # noqa: N802
        return self._max_profiles

    @pyqtProperty(int, notify=changed)
    def maxProxies(self) -> int:  # noqa: N802
        return self._max_proxies

    @pyqtProperty(int, notify=changed)
    def maxScenarios(self) -> int:  # noqa: N802
        return self._max_scenarios

    # --- actions ------------------------------------------------------------
    @pyqtSlot()
    def refresh(self) -> None:  # noqa: N802
        if not server_enabled():
            self._error = ""
            self.changed.emit()
            return
        try:
            client = ServerClient()
            data = client.billing() or {}
        except ServerClientError as exc:
            self._error = str(exc)
            self.message.emit(f"Billing error: {exc}")
            self.changed.emit()
            return
        team = data.get("team") or {}
        usage = data.get("usage") or {}
        self._plan = str(data.get("plan") or team.get("plan") or "")
        self._subscription_status = str(data.get("subscription_status") or team.get("license_status") or "")
        self._upgrade_available = bool(data.get("upgrade_available"))
        self._portal_url = str(data.get("portal_url") or "")
        self._usage_users = int(usage.get("users") or 0)
        self._usage_profiles = int(usage.get("profiles") or 0)
        self._usage_proxies = int(usage.get("proxies") or 0)
        self._usage_scenarios = int(usage.get("scenarios") or 0)
        self._max_users = int(team.get("max_users") or 0)
        self._max_profiles = int(team.get("max_profiles") or 0)
        self._max_proxies = int(team.get("max_proxies") or 0)
        self._max_scenarios = int(team.get("max_scenarios") or 0)
        plans = []
        for p in data.get("plans") or []:
            plans.append({
                "planId": str(p.get("id") or ""),
                "name": str(p.get("name") or ""),
                "price": _fmt_price(p),
                "currency": str(p.get("currency") or "usd"),
                "maxUsers": int(p.get("max_users") or 0),
                "maxProfiles": int(p.get("max_profiles") or 0),
                "maxProxies": int(p.get("max_proxies") or 0),
                "maxScenarios": int(p.get("max_scenarios") or 0),
                "maxPools": int(p.get("max_pools") or 0),
                "current": str(p.get("id") or "") == self._plan,
            })
        self._plans_model.set_rows(plans)
        self._error = ""
        self.changed.emit()

    @pyqtSlot(str)
    def checkout(self, plan_id: str) -> None:  # noqa: N802
        if not server_enabled():
            self.message.emit("Connect to Cloud first to upgrade.")
            return
        try:
            result = ServerClient().create_checkout(str(plan_id or "")) or {}
        except ServerClientError as exc:
            self._error = str(exc)
            self.message.emit(f"Checkout failed: {exc}")
            self.changed.emit()
            return
        url = str(result.get("checkout_url") or "")
        if url:
            QDesktopServices.openUrl(QUrl(url))
            self.message.emit(f"Opening checkout for plan '{plan_id}'...")
        else:
            self.message.emit("Checkout request sent. An admin will confirm your plan.")
        self.refresh()

    @pyqtSlot()
    def openPortal(self) -> None:  # noqa: N802
        if not server_enabled():
            return
        if not self._portal_url:
            self.message.emit("Self-service portal is not available on this plan.")
            return
        QDesktopServices.openUrl(QUrl(self._portal_url))
