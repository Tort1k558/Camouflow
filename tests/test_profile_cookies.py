"""Cookie drafts cannot clear storage before validation or fake cloud support."""

import asyncio
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.storage import db
from app.ui.bridge import profiles


@pytest.fixture
def cookie_bridge(monkeypatch):
    account = {"name": "safe", "_browser_engine": "camoufox"}
    context = SimpleNamespace(clear_cookies=AsyncMock(), add_cookies=AsyncMock(), cookies=AsyncMock(return_value=[]))
    browser = SimpleNamespace(start=AsyncMock(), close=AsyncMock(), context=context)
    factory = Mock(return_value=browser)
    monkeypatch.setattr(profiles, "BrowserInterface", factory)
    monkeypatch.setattr(profiles, "db_get_accounts", lambda: [account])
    monkeypatch.setattr(profiles, "server_enabled", lambda: False)
    monkeypatch.setattr(profiles.threading, "Thread", lambda target, **kwargs: SimpleNamespace(start=target))
    bridge = SimpleNamespace(_emit_message=Mock(), _settings_dict=lambda value: {}, _proxy_for=lambda account: "",
                             uiCall=Mock(side_effect=lambda callback: callback()), _live_browsers={},
                             _ensure_allowed=lambda role: True, _cached_account=lambda name: account)
    bridge._cookie_draft = lambda raw: profiles.ProfilesBridge._cookie_draft(raw)
    bridge._replace_cookie_jar = profiles.ProfilesBridge._replace_cookie_jar if hasattr(profiles.ProfilesBridge, "_replace_cookie_jar") else None

    def mutate(work, names):
        try:
            bridge._emit_message(work(None))
        except Exception as error:
            bridge._emit_message(str(error))
    bridge._mutate = Mock(side_effect=mutate)
    return bridge, factory, context


@pytest.mark.parametrize("draft", ["", " ", "not-json", "{}", "[null]", '[{"name":"n"}]',
                                  '[{"name":"n","domain":"example.invalid","value":"<encrypted>"}]',
                                  '[{"name":"n","domain":"example.invalid","value":1}]',
                                  '[{"name":"n","domain":"example.invalid","value":"v","sameSite":"bad"}]',
                                  '[{"name":"n","domain":"example.invalid","value":"v","secure":"true"}]'])
def test_invalid_cookie_draft_never_opens_or_clears_a_browser(cookie_bridge, draft):
    bridge, factory, context = cookie_bridge
    profiles.ProfilesBridge.saveProfileCookiesJson(bridge, "safe", draft)
    factory.assert_not_called()
    context.clear_cookies.assert_not_called()
    assert bridge._emit_message.call_count == 1


def test_cloud_cookie_save_is_explicitly_unsupported(cookie_bridge, monkeypatch):
    bridge, factory, _ = cookie_bridge
    monkeypatch.setattr(profiles, "server_enabled", lambda: True)
    profiles.ProfilesBridge.saveProfileCookiesJson(bridge, "safe", "[]")
    factory.assert_not_called()
    assert "local" in bridge._emit_message.call_args.args[0].lower()


def test_cloak_cookie_reader_uses_its_engine_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(db, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    db._save_accounts_raw([{"name": "safe", "_browser_engine": "cloakbrowser"}])
    cookie_file = db.profile_dir_for_email("safe") / "cloakbrowser" / "Default" / "Network" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    with sqlite3.connect(cookie_file) as connection:
        connection.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB, path TEXT, expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER)")
        connection.execute("INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("example.invalid", "synthetic", "synthetic-value", b"", "/", 0, 0, 1))
    rows = profiles.ProfilesBridge._read_cookie_rows("safe")
    assert len(rows) == 1 and rows[0]["value"] == "synthetic-value" and rows[0]["httpOnly"]


def test_legacy_cookie_getter_reports_path_errors_without_escaping_qt_slot(monkeypatch):
    monkeypatch.setattr(profiles, "server_enabled", lambda: False)
    bridge = SimpleNamespace(_read_cookie_rows=Mock(side_effect=ValueError("Synthetic unsafe directory")),
                             _emit_message=Mock(), _cached_account=lambda name: {"_browser_engine": "camoufox"})
    assert profiles.ProfilesBridge.getProfileCookiesJson(bridge, "..") == ""
    assert "Synthetic unsafe directory" in bridge._emit_message.call_args.args[0]


@pytest.mark.parametrize("replacement", [[], [{"name": "n", "value": "v", "domain": "example.invalid", "path": "/"}]])
def test_valid_cookie_drafts_use_reserved_mutation_worker(cookie_bridge, replacement):
    bridge, factory, context = cookie_bridge
    profiles.ProfilesBridge.saveProfileCookiesJson(bridge, "safe", json.dumps(replacement))
    bridge._mutate.assert_called_once()
    assert bridge._mutate.call_args.args[1] == ["safe"]
    factory.assert_called_once()
    context.clear_cookies.assert_awaited_once()
    if replacement:
        context.add_cookies.assert_awaited_once_with(replacement)


def test_failed_cookie_add_attempts_to_restore_original_jar():
    original = [{"name": "original", "domain": "example.invalid", "value": "synthetic-original", "path": "/"}]
    context = SimpleNamespace(cookies=AsyncMock(return_value=original), clear_cookies=AsyncMock(),
                             add_cookies=AsyncMock(side_effect=[ValueError("Synthetic add failure"), None]))
    with pytest.raises(ValueError, match="Synthetic add failure"):
        asyncio.run(profiles.ProfilesBridge._replace_cookie_jar(context, [{"name": "new"}]))
    assert context.add_cookies.await_args_list[-1].args[0] == original
    assert context.clear_cookies.await_count == 2


def test_snapshot_failure_does_not_clear_cookies():
    context = SimpleNamespace(cookies=AsyncMock(side_effect=OSError("Synthetic snapshot failure")),
                             clear_cookies=AsyncMock())
    with pytest.raises(OSError, match="Synthetic snapshot failure"):
        asyncio.run(profiles.ProfilesBridge._replace_cookie_jar(context, []))
    context.clear_cookies.assert_not_called()


def test_failed_restore_is_reported_without_fake_success():
    context = SimpleNamespace(cookies=AsyncMock(return_value=[{"name": "original"}]), clear_cookies=AsyncMock(),
                             add_cookies=AsyncMock(side_effect=OSError("Synthetic add/restore failure")))
    with pytest.raises(RuntimeError, match="could not be restored"):
        asyncio.run(profiles.ProfilesBridge._replace_cookie_jar(context, [{"name": "new"}]))


def test_pending_browser_start_blocks_cookie_mutation(cookie_bridge):
    bridge, factory, _ = cookie_bridge
    bridge._pending_starts = {"safe": object()}
    profiles.ProfilesBridge.saveProfileCookiesJson(bridge, "safe", "[]")
    bridge._mutate.assert_not_called()
    factory.assert_not_called()


@pytest.mark.parametrize("cloud,manage,expected", [(False, True, True), (False, False, False),
                                                 (True, True, False), (True, False, False)])
def test_cookie_editing_capability_is_local_only(monkeypatch, cloud, manage, expected):
    monkeypatch.setattr(profiles, "server_enabled", lambda: cloud)
    assert profiles.ProfilesBridge.canEditCookies.fget(SimpleNamespace(canManage=manage)) is expected


def test_cloud_cookie_read_does_not_fall_back_to_local_storage(monkeypatch):
    monkeypatch.setattr(profiles, "get_server_session", lambda: SimpleNamespace(enabled=True))
    read = Mock()
    bridge = SimpleNamespace(_cookie_request_id=0, cookiesLoaded=Mock(), _read_cookie_rows=read)
    profiles.ProfilesBridge.loadCookies(bridge, "same-human-name")
    read.assert_not_called()
    assert "local" in bridge.cookiesLoaded.emit.call_args.args[2]


@pytest.mark.parametrize("extra", [{"path": "relative"}, {"expires": True}, {"expires": -2},
                                   {"expires": float("nan")}, {"expires": float("inf")}, {"sameSite": []}])
def test_optional_cookie_fields_reject_invalid_types_without_values_in_error(extra):
    cookie = {"name": "synthetic-name", "domain": "example.invalid", "value": "synthetic-private-value", **extra}
    with pytest.raises(ValueError) as error:
        profiles.ProfilesBridge._cookie_draft(json.dumps([cookie]))
    assert "synthetic-private-value" not in str(error.value)


def test_corrupted_cookie_database_is_an_error_not_an_empty_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(db, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    db._save_accounts_raw([{"name": "safe", "_browser_engine": "camoufox"}])
    profile = db.profile_dir_for_email("safe")
    profile.mkdir(parents=True)
    (profile / "cookies.sqlite").write_bytes(b"synthetic malformed database")
    with pytest.raises(RuntimeError, match="Cannot read cookie storage"):
        profiles.ProfilesBridge._read_cookie_rows("safe")


def test_firefox_preview_does_not_mix_chromium_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(db, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    db._save_accounts_raw([{"name": "safe", "_browser_engine": "camoufox"}])
    profile = db.profile_dir_for_email("safe")
    profile.mkdir(parents=True)
    with sqlite3.connect(profile / "cookies.sqlite") as connection:
        connection.execute("PRAGMA user_version=15")
        connection.execute("CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT, path TEXT, expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER)")
        connection.execute("INSERT INTO moz_cookies VALUES ('example.invalid','synthetic','synthetic-value','/',1,0,0)")
    (profile / "Cookies").write_bytes(b"unrelated Chromium storage")
    assert len(profiles.ProfilesBridge._read_cookie_rows("safe")) == 1


def test_chromium_expiration_uses_unix_seconds(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(db, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    db._save_accounts_raw([{"name": "safe", "_browser_engine": "cloakbrowser"}])
    cookie_file = db.profile_dir_for_email("safe") / "cloakbrowser" / "Default" / "Network" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    expected = 1900000000
    with sqlite3.connect(cookie_file) as connection:
        connection.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT, encrypted_value BLOB, path TEXT, expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER)")
        connection.execute("INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("example.invalid", "synthetic", "value", b"", "/", (expected + 11644473600) * 1000000, 0, 0))
    assert profiles.ProfilesBridge._read_cookie_rows("safe")[0]["expires"] == expected


@pytest.mark.parametrize("version", [15, 16, 17])
def test_firefox_expiration_follows_declared_schema_not_numeric_heuristics(tmp_path, monkeypatch, version):
    monkeypatch.setattr(db, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(db, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    db._save_accounts_raw([{"name": "safe", "_browser_engine": "camoufox"}])
    profile = db.profile_dir_for_email("safe")
    profile.mkdir(parents=True)
    expected = 1900000000
    stored = expected * 1000 if version >= 16 else expected
    with sqlite3.connect(profile / "cookies.sqlite") as connection:
        connection.execute(f"PRAGMA user_version={version}")
        connection.execute("CREATE TABLE moz_cookies (host TEXT,name TEXT,value TEXT,path TEXT,expiry INTEGER,isSecure INTEGER,isHttpOnly INTEGER)")
        connection.execute("INSERT INTO moz_cookies VALUES ('example.invalid','synthetic','value','/',?,0,0)", (stored,))
    assert profiles.ProfilesBridge._read_cookie_rows("safe")[0]["expires"] == expected


@pytest.mark.parametrize("version", [0, 18])
def test_unknown_firefox_schema_does_not_guess_expiration_units(tmp_path, monkeypatch, version):
    monkeypatch.setattr(db, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(db, "ACCOUNTS_FILE", tmp_path / "accounts.json")
    db._save_accounts_raw([{"name": "safe", "_browser_engine": "camoufox"}])
    profile = db.profile_dir_for_email("safe")
    profile.mkdir(parents=True)
    with sqlite3.connect(profile / "cookies.sqlite") as connection:
        connection.execute(f"PRAGMA user_version={version}")
        connection.execute("CREATE TABLE moz_cookies (host TEXT,name TEXT,value TEXT,path TEXT,expiry INTEGER,isSecure INTEGER,isHttpOnly INTEGER)")
    with pytest.raises(RuntimeError, match="Unsupported Firefox cookie schema"):
        profiles.ProfilesBridge._read_cookie_rows("safe")
