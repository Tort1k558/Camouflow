"""Mutations must not replace unreadable storage with an empty document."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.storage import db


@pytest.fixture
def storage_files(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(db, "ACCOUNTS_FILE", accounts)
    monkeypatch.setattr(db, "SETTINGS_FILE", settings)
    return accounts, settings


ACCOUNT_WRITES = [
    lambda: db.db_add_account({"name": "new-profile"}),
    lambda: db.db_delete_account("profile1"),
    lambda: db.db_update_stage("profile1", "done"),
    lambda: db.db_update_account("profile1", {"stage": "done"}),
]
SETTINGS_WRITES = [
    lambda: db.db_set_setting("theme", "dark"),
    lambda: db.db_set_settings({"theme": "dark"}),
    lambda: db.db_set_selector_index("#item", 2),
    lambda: db.db_set_selector_indices({"#item": 2}),
    lambda: db.db_delete_selector_index("#item"),
]


@pytest.mark.parametrize("write", ACCOUNT_WRITES)
@pytest.mark.parametrize("content", [b'{"unfinished":', b'{}', b'[null]'])
def test_account_writes_preserve_invalid_file(storage_files, write, content):
    accounts, _ = storage_files
    accounts.write_bytes(content)
    with pytest.raises((RuntimeError, ValueError)):
        write()
    assert accounts.read_bytes() == content


@pytest.mark.parametrize("write", SETTINGS_WRITES)
@pytest.mark.parametrize("content", [b'{"unfinished":', b'[]'])
def test_setting_writes_preserve_invalid_file(storage_files, write, content):
    _, settings = storage_files
    settings.write_bytes(content)
    with pytest.raises(RuntimeError):
        write()
    assert settings.read_bytes() == content


def test_bom_documents_remain_readable_and_rewrite_as_utf8(storage_files):
    accounts, settings = storage_files
    accounts.write_text('[{"name":"profile1","stage":"original"}]', encoding="utf-8-sig")
    settings.write_text('{"existing":"keep"}', encoding="utf-8-sig")
    db.db_update_stage("profile1", "done")
    db.db_set_setting("theme", "dark")
    assert json.loads(accounts.read_text(encoding="utf-8"))[0]["stage"] == "done"
    assert json.loads(settings.read_text(encoding="utf-8")) == {"existing": "keep", "theme": "dark"}
    assert not accounts.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not settings.read_bytes().startswith(b"\xef\xbb\xbf")


def test_new_storage_can_be_created(storage_files):
    accounts, settings = storage_files
    db.db_add_account({"name": "profile1"})
    db.db_set_setting("theme", "dark")
    assert json.loads(accounts.read_text(encoding="utf-8"))[0]["name"] == "profile1"
    assert json.loads(settings.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_unreadable_settings_are_not_overwritten(storage_files, monkeypatch):
    _, settings = storage_files
    settings.write_text('{"existing":"keep"}', encoding="utf-8")
    original_read = type(settings).read_text

    def read(path, *args, **kwargs):
        if path == settings:
            raise PermissionError("Synthetic unreadable storage")
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(type(settings), "read_text", read)
    with pytest.raises(RuntimeError):
        db.db_set_setting("theme", "dark")
    assert settings.read_bytes() == b'{"existing":"keep"}'


@pytest.mark.parametrize("write", SETTINGS_WRITES)
def test_valid_setting_mutations_preserve_unrelated_fields(storage_files, write):
    _, settings = storage_files
    settings.write_text('{"existing":"keep","selector_indices":{"#other":1}}', encoding="utf-8")
    write()
    result = json.loads(settings.read_text(encoding="utf-8"))
    assert result["existing"] == "keep"


@pytest.mark.parametrize("write", ACCOUNT_WRITES)
def test_valid_account_mutations_preserve_other_profiles(storage_files, write):
    accounts, _ = storage_files
    accounts.write_text('[{"name":"profile1"},{"name":"other","custom":"keep"}]', encoding="utf-8")
    write()
    result = json.loads(accounts.read_text(encoding="utf-8"))
    assert next(entry for entry in result if entry["name"] == "other")["custom"] == "keep"


@pytest.mark.parametrize("method,args", [
    ("saveVariable", ("key", "string", "value")),
    ("deleteVariable", ("key",)),
    ("addStage", ("new",)),
    ("deleteStage", ("old",)),
    ("startLocalMode", ()),
    ("openUserLogin", ()),
    ("resetOnboarding", ()),
    ("saveAiSettings", (True, "https://example.invalid", "synthetic-key", "model", "25")),
])
def test_settings_slots_report_failed_writes(storage_files, method, args):
    from app.ui.bridge.settings import SettingsBridge

    _, settings = storage_files
    settings.write_bytes(b'{"unfinished":')
    bridge = SimpleNamespace(_emit_message=Mock(), refresh=Mock(), _app_state=Mock(),
                             _load_vars=lambda: {}, _load_stages=lambda: ["old"])
    bridge._persist = lambda values: SettingsBridge._persist(bridge, values)
    getattr(SettingsBridge, method)(bridge, *args)
    assert bridge._emit_message.call_count == 1
    assert "Cannot save" in bridge._emit_message.call_args.args[0]
    assert settings.read_bytes() == b'{"unfinished":'
    bridge.refresh.assert_not_called()
    bridge._app_state.refreshAll.assert_not_called()
    bridge._app_state.setPage.assert_not_called()


def test_ai_settings_are_one_atomic_write(storage_files, monkeypatch):
    from app.ui.bridge import settings as settings_module

    _, settings = storage_files
    settings.write_text('{"existing":"keep"}', encoding="utf-8")
    persist = Mock(wraps=db.db_set_settings)
    monkeypatch.setattr(settings_module, "db_set_settings", persist)
    bridge = SimpleNamespace(_emit_message=Mock(), refresh=Mock())
    bridge._persist = lambda values: settings_module.SettingsBridge._persist(bridge, values)
    settings_module.SettingsBridge.saveAiSettings(bridge, True, "https://example.invalid/", "synthetic-key", "model", "30")
    assert persist.call_count == 1
    result = json.loads(settings.read_text(encoding="utf-8"))
    assert result["existing"] == "keep"
    assert result["ai_enabled"] == "true" and result["ai_max_steps"] == "30"
    assert result["ai_base_url"] == "https://example.invalid"
    bridge.refresh.assert_called_once()


@pytest.mark.parametrize("method,args", [("setAutoSyncEnabled", (True,)), ("logout", ())])
def test_user_slots_report_failed_local_writes(storage_files, monkeypatch, method, args):
    from app.ui.bridge import user

    _, settings = storage_files
    settings.write_bytes(b'{"unfinished":')
    monkeypatch.setattr(user, "ServerClient", lambda: SimpleNamespace(configured=False))
    bridge = SimpleNamespace(_notify=Mock(), changed=Mock(), refresh=Mock(), _app_state=Mock())
    getattr(user.UserBridge, method)(bridge, *args)
    assert bridge._notify.call_count == 1
    assert "Cannot" in bridge._notify.call_args.args[0]
    assert settings.read_bytes() == b'{"unfinished":'
    bridge.changed.emit.assert_not_called()
    bridge.refresh.assert_not_called()
