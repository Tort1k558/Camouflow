"""QML application bootstrap for CamouFlow."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Dict

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtQml import QQmlApplicationEngine

from app.ui.bridge.app_state import AppState
from app.ui.bridge.billing import BillingBridge
from app.ui.bridge.browser_settings import BrowserSettingsBridge
from app.ui.bridge.dashboard import DashboardBridge
from app.ui.bridge.logs import LogsBridge
from app.ui.bridge.profiles import ProfilesBridge
from app.ui.bridge.proxies import ProxiesBridge
from app.ui.bridge.scenarios import ScenariosBridge
from app.ui.bridge.settings import SettingsBridge
from app.ui.bridge.user import UserBridge

LOGGER = logging.getLogger(__name__)


def _install_qt_logging_rules() -> None:
    rule = "qt.qpa.mime.warning=false"
    current = os.environ.get("QT_LOGGING_RULES", "")
    if rule not in current:
        os.environ["QT_LOGGING_RULES"] = f"{current};{rule}" if current else rule


class QmlApplication:
    """Owns the Qt/QML engine and long-lived bridge objects."""

    def __init__(self, argv: list[str]) -> None:
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
        _install_qt_logging_rules()
        self.app = QGuiApplication(argv)
        self.engine = QQmlApplicationEngine()
        self.root_dir = self._resource_path("app/qml")
        self.state = AppState()
        self.profiles = ProfilesBridge(self.state)
        self.scenarios = ScenariosBridge(self.profiles, self.state)
        self.proxies = ProxiesBridge(self.state)
        self.browser_settings = BrowserSettingsBridge(self.state)
        self.logs = LogsBridge(self.state)
        self.settings = SettingsBridge(self.state)
        self.user = UserBridge(self.state)
        self.dashboard = DashboardBridge(self.profiles, self.state)
        self.billing = BillingBridge(self.state)
        self._connect_messages()
        self._install_context()
        self._install_icon()

    def _resource_path(self, relative: str) -> Path:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(getattr(sys, "_MEIPASS")).resolve() / relative
        return Path(__file__).resolve().parents[2] / relative

    def _install_icon(self) -> None:
        icon_path = self._resource_path("logo.ico")
        if icon_path.exists():
            self.app.setWindowIcon(QIcon(str(icon_path)))

    def _connect_messages(self) -> None:
        for bridge in (
            self.profiles,
            self.scenarios,
            self.proxies,
            self.browser_settings,
            self.settings,
            self.user,
            self.billing,
        ):
            bridge.message.connect(self.logs.append)

    def _install_context(self) -> None:
        context = self.engine.rootContext()
        context.setContextProperty("AppState", self.state)
        context.setContextProperty("appState", self.state)
        context.setContextProperty("DashboardBridge", self.dashboard)
        context.setContextProperty("dashboardBridge", self.dashboard)
        context.setContextProperty("ProfilesBridge", self.profiles)
        context.setContextProperty("profilesBridge", self.profiles)
        context.setContextProperty("ScenariosBridge", self.scenarios)
        context.setContextProperty("scenariosBridge", self.scenarios)
        context.setContextProperty("ProxiesBridge", self.proxies)
        context.setContextProperty("proxiesBridge", self.proxies)
        context.setContextProperty("BrowserSettingsBridge", self.browser_settings)
        context.setContextProperty("browserSettingsBridge", self.browser_settings)
        context.setContextProperty("LogsBridge", self.logs)
        context.setContextProperty("logsBridge", self.logs)
        context.setContextProperty("SettingsBridge", self.settings)
        context.setContextProperty("settingsBridge", self.settings)
        context.setContextProperty("UserBridge", self.user)
        context.setContextProperty("userBridge", self.user)
        context.setContextProperty("BillingBridge", self.billing)
        context.setContextProperty("billingBridge", self.billing)
        context.setContextProperty("AppRoot", str(self._resource_path(".")))
        self.engine.addImportPath(str(self.root_dir))

    def exec(self) -> int:
        qml_file = self.root_dir / "Main.qml"
        self.engine.load(QUrl.fromLocalFile(str(qml_file)))
        if not self.engine.rootObjects():
            LOGGER.error("Failed to load QML root: %s", qml_file)
            return 1
        return self.app.exec()


def run_qml_app(argv: list[str] | None = None) -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    _install_qt_logging_rules()
    app = QmlApplication(list(argv if argv is not None else sys.argv))
    return app.exec()
