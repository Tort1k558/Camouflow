"""Profile rendering snapshots capabilities without per-row session reads."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.server_client import ServerSession
from app.ui.bridge import profiles
from app.ui.bridge.models import DictListModel


def make_bridge(entries):
    bridge = SimpleNamespace(
        _accounts_cache=entries, _accounts_index={account["name"]: account for account in entries},
        _accounts_session=ServerSession(False, "http://example.invalid", "", "", "", ""),
        _live_browsers={}, _pending_starts=set(), _browser_stops={}, _browser_resources={},
        _busy=False, _selected_stage="", _last_counts=None, _search_query="",
        _stages_model=DictListModel(["name"]), _model=DictListModel(["name", "status"]),
        modelChanged=Mock(), countsChanged=Mock(), canRun=True, canManage=True, canAdmin=True,
        _settings_dict=profiles.ProfilesBridge._settings_dict)
    bridge._cached_account = lambda name: profiles.ProfilesBridge._cached_account(bridge, name)
    bridge.actionState = lambda name: profiles.ProfilesBridge.actionState(bridge, name)
    bridge._action_state = lambda name, account, permissions: profiles.ProfilesBridge._action_state(bridge, name, account, permissions)
    bridge._proxy_label = lambda account: profiles.ProfilesBridge._proxy_label(bridge, account)
    bridge._apply_search = lambda: profiles.ProfilesBridge._apply_search(bridge)
    return bridge


def test_profile_render_reads_session_once_not_per_row(monkeypatch):
    bridge = make_bridge([{"name": f"profile{index}"} for index in range(100)])
    session = Mock(return_value=bridge._accounts_session)
    monkeypatch.setattr(profiles, "get_server_session", session)
    monkeypatch.setattr(profiles, "db_get_setting", lambda key: "[]")
    profiles.ProfilesBridge._render_accounts(bridge)
    assert session.call_count == 1
    assert bridge._model.rowCount() == 100
    assert all(row["status"] == "Available" and row["startAllowed"] for row in bridge._profile_rows)


@pytest.mark.parametrize("permissions", [(False, False, False), (True, False, False),
                                        (True, True, False), (True, True, True)])
def test_profile_render_matches_live_action_capabilities(monkeypatch, permissions):
    bridge = make_bridge([{"name": "profile1"}])
    bridge.canRun, bridge.canManage, bridge.canAdmin = permissions
    monkeypatch.setattr(profiles, "get_server_session", lambda: bridge._accounts_session)
    monkeypatch.setattr(profiles, "db_get_setting", lambda key: "[]")
    profiles.ProfilesBridge._render_accounts(bridge)
    row = bridge._profile_rows[0]
    assert {key: row[key] for key in bridge.actionState("profile1")} == bridge.actionState("profile1")
    assert row["startAllowed"] is permissions[0]
    assert row["editAllowed"] is permissions[1]
    assert row["deleteAllowed"] is permissions[2]


def test_stale_session_never_enables_cached_profile_actions(monkeypatch):
    bridge = make_bridge([{"name": "profile1"}])
    current = ServerSession(True, "http://other.example.invalid", "new-token", "new-refresh", "other-team", "other@example.invalid")
    monkeypatch.setattr(profiles, "get_server_session", lambda: current)
    monkeypatch.setattr(profiles, "db_get_setting", lambda key: "[]")
    profiles.ProfilesBridge._render_accounts(bridge)
    assert "startAllowed" not in bridge._profile_rows[0]
    assert bridge.actionState("profile1") == {}


@pytest.mark.parametrize("state,expected", [("starting", "Starting"), ("running", "Browser open"),
                                          ("stopping", "Stopping"), ("locked", "Locked"),
                                          ("reserved", "In use locally"), ("recording", "Recording")])
def test_profile_render_preserves_dynamic_occupancy(monkeypatch, state, expected):
    bridge = make_bridge([{"name": "profile1"}])
    if state in {"starting", "running", "stopping"}:
        bridge._live_browsers["profile1"] = SimpleNamespace(page=None if state == "starting" else object())
    if state == "stopping":
        from threading import Event
        stopped = Event()
        stopped.set()
        bridge._browser_stops["profile1"] = stopped
    if state == "locked":
        bridge._accounts_cache[0]["lock_user_id"] = "synthetic-lock-owner"
    if state in {"reserved", "recording"}:
        bridge.operations = SimpleNamespace(isReserved=lambda name: True, reservationLabel=lambda name: "In use locally")
    if state == "recording":
        bridge.recorder = SimpleNamespace(active=True, profileName="profile1")
    monkeypatch.setattr(profiles, "get_server_session", lambda: bridge._accounts_session)
    monkeypatch.setattr(profiles, "db_get_setting", lambda key: "[]")
    profiles.ProfilesBridge._render_accounts(bridge)
    row = bridge._profile_rows[0]
    assert row["status"] == expected
    assert not row["startAllowed"] and not row["editAllowed"] and not row["deleteAllowed"]


def test_empty_reservations_do_not_resolve_profile_paths(monkeypatch):
    from threading import RLock

    from app.ui.bridge.operations import OperationsBridge

    bridge = SimpleNamespace(_reservation_lock=RLock(), _reserved=set())
    path = Mock(side_effect=AssertionError("Unnecessary filesystem lookup"))
    monkeypatch.setattr(profiles, "profile_dir_for_email", path)
    from app.storage import db
    monkeypatch.setattr(db, "profile_dir_for_email", path)
    assert not OperationsBridge.isReserved(bridge, "profile1")
    path.assert_not_called()


def test_reservations_still_guard_different_names_sharing_a_storage_path(tmp_path, monkeypatch):
    from threading import RLock

    from app.storage import db
    from app.ui.bridge.operations import OperationsBridge

    monkeypatch.setattr(db, "PROFILES_DIR", tmp_path)
    bridge = SimpleNamespace(_reservation_lock=RLock(), _reserved={"profile:one"})
    assert OperationsBridge.isReserved(bridge, "profile?one")
    assert not OperationsBridge.isReserved(bridge, "different")
