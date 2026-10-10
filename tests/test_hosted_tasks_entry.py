from types import SimpleNamespace
from unittest.mock import Mock

from app.ui.bridge import tasks


def test_team_center_entry_opens_configured_server(monkeypatch):
    monkeypatch.setattr(tasks, "get_server_session", lambda: SimpleNamespace(url="https://camouflow.site/", token="private"))
    opened = []
    monkeypatch.setattr(tasks.QDesktopServices, "openUrl", lambda value: opened.append(value.toString()) or True)
    bridge = SimpleNamespace(state=SimpleNamespace(notify=Mock()))
    bridge._open_console = lambda path, label: tasks.TasksBridge._open_console(bridge, path, label)
    tasks.TasksBridge.openTeamCenter(bridge)
    assert opened == ["https://camouflow.site/console/team-center"]
    bridge.state.notify.assert_not_called()


def test_hosted_entry_opens_console_without_credentials(monkeypatch):
    monkeypatch.setattr(tasks, "get_server_session", lambda: SimpleNamespace(url="https://camouflow.site/", token="private", team_id="team"))
    opened = []
    monkeypatch.setattr(tasks.QDesktopServices, "openUrl", lambda value: opened.append(value.toString()) or True)
    bridge = SimpleNamespace(state=SimpleNamespace(notify=Mock()))
    bridge._open_console = lambda path, label: tasks.TasksBridge._open_console(bridge, path, label)
    tasks.TasksBridge.openHostedTasks(bridge)
    assert opened == ["https://camouflow.site/console/hosted"]
    bridge.state.notify.assert_not_called()


def test_hosted_entry_rejects_credential_url(monkeypatch):
    monkeypatch.setattr(tasks, "get_server_session", lambda: SimpleNamespace(url="https://user:password@camouflow.site"))
    opened = Mock()
    monkeypatch.setattr(tasks.QDesktopServices, "openUrl", opened)
    bridge = SimpleNamespace(state=SimpleNamespace(notify=Mock()))
    bridge._open_console = lambda path, label: tasks.TasksBridge._open_console(bridge, path, label)
    tasks.TasksBridge.openHostedTasks(bridge)
    opened.assert_not_called()
    bridge.state.notify.assert_called_once()


def test_hosted_entry_reports_browser_failure(monkeypatch):
    monkeypatch.setattr(tasks, "get_server_session", lambda: SimpleNamespace(url="https://camouflow.site"))
    monkeypatch.setattr(tasks.QDesktopServices, "openUrl", lambda value: False)
    bridge = SimpleNamespace(state=SimpleNamespace(notify=Mock()))
    bridge._open_console = lambda path, label: tasks.TasksBridge._open_console(bridge, path, label)
    tasks.TasksBridge.openHostedTasks(bridge)
    bridge.state.notify.assert_called_once_with("Could not open hosted tasks in your browser")
