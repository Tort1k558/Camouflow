"""Profile operations must not target workspace roots or another identity."""

from unittest.mock import Mock

import pytest

from app.core.browser_interface import BrowserInterface
from app.storage import db


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    monkeypatch.setattr(db, "PROFILES_DIR", profiles)
    monkeypatch.setattr(db, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    monkeypatch.setattr(db, "SETTINGS_FILE", tmp_path / "settings.json")
    db.ACCOUNTS_FILE.write_text("[]", encoding="utf-8")
    db.SETTINGS_FILE.write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("name", [".", "..", "CON", "con.txt", "NUL", "COM1", "LPT9", "name."])
def test_new_accounts_reject_unsafe_storage_names(workspace, name):
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError):
        db.db_add_account({"name": name})
    assert db.ACCOUNTS_FILE.read_bytes() == before


@pytest.mark.parametrize("name", [".", ".."])
@pytest.mark.parametrize("operation", [db.clear_profile_cookies, db.delete_profile_for_account])
def test_root_directory_cannot_be_deleted_as_a_profile(workspace, monkeypatch, name, operation):
    remove = Mock()
    monkeypatch.setattr(db.shutil, "rmtree", remove)
    with pytest.raises(ValueError):
        operation(name)
    remove.assert_not_called()


@pytest.mark.parametrize("name", [".", ".."])
@pytest.mark.parametrize("engine", ["camoufox", "cloakbrowser"])
def test_browser_rejects_workspace_root_before_creating_profile_files(workspace, name, engine):
    before = sorted(str(path.relative_to(workspace)) for path in workspace.rglob("*"))
    with pytest.raises(ValueError):
        BrowserInterface(name, browser_engine=engine)
    assert sorted(str(path.relative_to(workspace)) for path in workspace.rglob("*")) == before


def test_new_account_cannot_alias_an_existing_profile_directory(workspace):
    db.db_add_account({"name": "profile:one"})
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError, match="browser directory"):
        db.db_add_account({"name": "profile?one"})
    assert db.ACCOUNTS_FILE.read_bytes() == before


def test_rename_cannot_alias_another_profile_directory(workspace):
    db.db_add_account({"name": "profile:one"})
    db.db_add_account({"name": "other"})
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError, match="browser directory"):
        db.db_update_account("other", {"name": "profile?one"})
    assert db.ACCOUNTS_FILE.read_bytes() == before


@pytest.mark.parametrize("operation", [db.clear_profile_cookies, db.delete_profile_for_account])
def test_legacy_ambiguous_names_cannot_delete_a_shared_directory(workspace, monkeypatch, operation):
    db._save_accounts_raw([{"name": "profile:one"}, {"name": "profile?one"}])
    target = db.profile_dir_for_email("profile:one")
    target.mkdir()
    remove = Mock()
    monkeypatch.setattr(db.shutil, "rmtree", remove)
    with pytest.raises(ValueError, match="browser directory"):
        operation("profile:one")
    remove.assert_not_called()


def test_unreadable_accounts_cannot_allow_a_destructive_reset(workspace, monkeypatch):
    target = db.profile_dir_for_email("profile1")
    target.mkdir()
    db.ACCOUNTS_FILE.write_text('{"unfinished":', encoding="utf-8")
    remove = Mock()
    monkeypatch.setattr(db.shutil, "rmtree", remove)
    with pytest.raises(RuntimeError):
        db.clear_profile_cookies("profile1")
    remove.assert_not_called()


def test_rename_does_not_adopt_existing_unmanaged_browser_data(workspace):
    db.db_add_account({"name": "original"})
    old = db.profile_dir_for_email("original")
    old.mkdir()
    (old / "session.dat").write_bytes(b"original session")
    destination = db.profile_dir_for_email("new")
    destination.mkdir()
    (destination / "session.dat").write_bytes(b"unrelated session")
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        db.db_update_account("original", {"name": "new"})
    assert db.ACCOUNTS_FILE.read_bytes() == before
    assert (old / "session.dat").read_bytes() == b"original session"
    assert (destination / "session.dat").read_bytes() == b"unrelated session"


def test_failed_directory_rename_preserves_account_metadata(workspace, monkeypatch):
    db.db_add_account({"name": "original"})
    old = db.profile_dir_for_email("original")
    old.mkdir()
    before = db.ACCOUNTS_FILE.read_bytes()
    monkeypatch.setattr(type(old), "rename", Mock(side_effect=OSError("Synthetic rename failure")))
    with pytest.raises(OSError, match="Synthetic rename failure"):
        db.db_update_account("original", {"name": "new"})
    assert db.ACCOUNTS_FILE.read_bytes() == before
    assert old.exists()


def test_failed_metadata_save_rolls_back_a_directory_rename(workspace, monkeypatch):
    db.db_add_account({"name": "original"})
    old = db.profile_dir_for_email("original")
    old.mkdir()
    (old / "session.dat").write_bytes(b"original session")
    before = db.ACCOUNTS_FILE.read_bytes()
    monkeypatch.setattr(db, "_save_accounts_raw", Mock(side_effect=OSError("Synthetic save failure")))
    with pytest.raises(OSError, match="Synthetic save failure"):
        db.db_update_account("original", {"name": "new"})
    assert db.ACCOUNTS_FILE.read_bytes() == before
    assert (old / "session.dat").read_bytes() == b"original session"
    assert not db.profile_dir_for_email("new").exists()


def test_successful_rename_preserves_browser_files(workspace):
    db.db_add_account({"name": "original"})
    old = db.profile_dir_for_email("original")
    old.mkdir()
    (old / "session.dat").write_bytes(b"original session")
    db.db_update_account("original", {"name": "new"})
    assert not old.exists()
    assert db.profile_dir_for_email("new").joinpath("session.dat").read_bytes() == b"original session"
    assert db.db_get_accounts()[0]["name"] == "new"


def test_duplicate_legacy_case_identifiers_are_not_dedicated_storage(workspace, monkeypatch):
    db._save_accounts_raw([{"name": "Profile1"}, {"name": "profile1"}])
    remove = Mock()
    monkeypatch.setattr(db.shutil, "rmtree", remove)
    with pytest.raises(ValueError, match="browser directory"):
        db.clear_profile_cookies("Profile1")
    remove.assert_not_called()


@pytest.mark.parametrize("link_method", ["is_symlink", "is_junction"])
def test_new_account_rejects_linked_profile_storage(workspace, monkeypatch, link_method):
    target = db.profile_dir_for_email("linked")
    monkeypatch.setattr(type(target), link_method, lambda path: path == target)
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError, match="filesystem link"):
        db.db_add_account({"name": "linked"})
    assert db.ACCOUNTS_FILE.read_bytes() == before


def test_cloakbrowser_rejects_linked_engine_subdirectory_before_mkdir(workspace, monkeypatch):
    child = db.profile_dir_for_email("safe") / "cloakbrowser"
    monkeypatch.setattr(type(child), "is_junction", lambda path: path == child)
    with pytest.raises(ValueError, match="dedicated profile storage"):
        BrowserInterface("safe", browser_engine="cloakbrowser")
    assert not db.profile_dir_for_email("safe").exists()


@pytest.mark.parametrize("engine", ["camoufox", "cloakbrowser"])
def test_profile_preflight_rejects_root_identities(workspace, engine):
    from app.ui.bridge.profiles import ProfilesBridge

    with pytest.raises(ValueError):
        ProfilesBridge._profile_storage_issue("..", engine=engine)


def test_cookie_read_rejects_linked_files_before_database_access(workspace, monkeypatch):
    import sqlite3

    from app.ui.bridge.profiles import ProfilesBridge

    db.db_add_account({"name": "safe"})
    profile = db.profile_dir_for_email("safe")
    profile.mkdir()
    cookie = profile / "cookies.sqlite"
    monkeypatch.setattr(type(cookie), "is_symlink", lambda path: path == cookie)
    connect = Mock()
    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(ValueError, match="Cookie storage"):
        ProfilesBridge._read_cookie_rows("safe")
    connect.assert_not_called()


def test_constructor_validation_error_uses_existing_gui_cleanup(monkeypatch):
    from types import SimpleNamespace

    from app.ui.bridge import profiles

    failure = ValueError("Synthetic constructor validation failure")
    monkeypatch.setattr(profiles, "BrowserInterface", Mock(side_effect=failure))
    bridge = SimpleNamespace(_proxy_for=lambda account: "", _settings_dict=lambda value: {},
                             _browser_stops={}, _live_browsers={}, _browser_resources={},
                             _server_release_profile=Mock(), _emit_message=Mock(), refresh=Mock())
    bridge._on_browser_failed = lambda name, browser, error: profiles.ProfilesBridge._on_browser_failed(bridge, name, browser, error)
    profiles.ProfilesBridge._start_prepared(bridge, "safe", {})
    bridge._server_release_profile.assert_called_once_with("safe")
    assert "Synthetic constructor validation failure" in bridge._emit_message.call_args.args[0]
    bridge.refresh.assert_called_once()


def test_restore_rejects_directory_alias_before_opening_archive(workspace):
    from app.services.profile_backup import restore_profile

    db.db_add_account({"name": "profile:one"})
    source = workspace / "not-an-archive.zip"
    source.write_bytes(b"synthetic invalid archive")
    before = db.ACCOUNTS_FILE.read_bytes()
    with pytest.raises(ValueError, match="browser directory"):
        restore_profile(source, "profile?one")
    assert db.ACCOUNTS_FILE.read_bytes() == before
    assert not list(db.PROFILES_DIR.glob(".restore-*"))


def test_restore_rejects_linked_destination_before_opening_archive(workspace, monkeypatch):
    from app.services.profile_backup import restore_profile

    target = db.profile_dir_for_email("linked")
    monkeypatch.setattr(type(target), "is_symlink", lambda path: path == target)
    with pytest.raises(ValueError, match="filesystem link"):
        restore_profile(workspace / "missing.zip", "linked")
    assert not list(db.PROFILES_DIR.glob(".restore-*"))
