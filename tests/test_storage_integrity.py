"""Mutations must not replace unreadable storage with an empty document."""

import json

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
