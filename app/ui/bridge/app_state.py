"""Shared QML application state."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot


class AppState(QObject):
    currentPageChanged = pyqtSignal()
    messageChanged = pyqtSignal()
    cloudChanged = pyqtSignal()
    refreshRequested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_page = "Dashboard"
        self._message = "Ready"
        self._cloud_enabled = False
        self._cloud_available = False
        self._cloud_email = ""
        self._cloud_team_id = ""
        self._cloud_team_name = ""
        self._cloud_role = ""
        self._cloud_status = "Local mode"

    @pyqtProperty(str, notify=currentPageChanged)
    def currentPage(self) -> str:  # noqa: N802
        return self._current_page

    @pyqtProperty(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @pyqtProperty(bool, notify=cloudChanged)
    def cloudEnabled(self) -> bool:  # noqa: N802
        return self._cloud_enabled

    @pyqtProperty(bool, notify=cloudChanged)
    def cloudAvailable(self) -> bool:  # noqa: N802
        return self._cloud_available

    @pyqtProperty(str, notify=cloudChanged)
    def cloudEmail(self) -> str:  # noqa: N802
        return self._cloud_email

    @pyqtProperty(str, notify=cloudChanged)
    def cloudTeamId(self) -> str:  # noqa: N802
        return self._cloud_team_id

    @pyqtProperty(str, notify=cloudChanged)
    def cloudTeamName(self) -> str:  # noqa: N802
        return self._cloud_team_name

    @pyqtProperty(str, notify=cloudChanged)
    def cloudRole(self) -> str:  # noqa: N802
        return self._cloud_role

    @pyqtProperty(str, notify=cloudChanged)
    def cloudStatus(self) -> str:  # noqa: N802
        return self._cloud_status

    @pyqtProperty(bool, notify=cloudChanged)
    def canViewCloud(self) -> bool:  # noqa: N802
        return self._role_allows("viewer")

    @pyqtProperty(bool, notify=cloudChanged)
    def canRunCloud(self) -> bool:  # noqa: N802
        return self._role_allows("operator")

    @pyqtProperty(bool, notify=cloudChanged)
    def canManageCloud(self) -> bool:  # noqa: N802
        return self._role_allows("manager")

    @pyqtProperty(bool, notify=cloudChanged)
    def canAdminCloud(self) -> bool:  # noqa: N802
        return self._role_allows("admin")

    def _role_allows(self, min_role: str) -> bool:
        if not self._cloud_enabled:
            return True
        if not self._cloud_available:
            return False
        ranks = {"viewer": 0, "operator": 1, "manager": 2, "admin": 3, "owner": 4}
        return ranks.get(self._cloud_role.lower(), -1) >= ranks.get(min_role.lower(), 999)

    @pyqtSlot(str)
    def setPage(self, page: str) -> None:  # noqa: N802
        page = str(page or "Dashboard")
        if page == self._current_page:
            return
        self._current_page = page
        self.currentPageChanged.emit()

    @pyqtSlot(str)
    def notify(self, message: str) -> None:
        self._message = str(message or "")
        self.messageChanged.emit()

    def set_cloud_context(
        self,
        *,
        enabled: bool,
        available: bool,
        email: str = "",
        team_id: str = "",
        team_name: str = "",
        role: str = "",
        status: str = "",
    ) -> None:
        self._cloud_enabled = bool(enabled)
        self._cloud_available = bool(available)
        self._cloud_email = str(email or "")
        self._cloud_team_id = str(team_id or "")
        self._cloud_team_name = str(team_name or "")
        self._cloud_role = str(role or "")
        self._cloud_status = str(status or ("Cloud" if enabled else "Local mode"))
        self.cloudChanged.emit()

    @pyqtSlot()
    def refreshAll(self) -> None:  # noqa: N802
        self.refreshRequested.emit()
