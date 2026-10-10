"""Explicit import pools never silently create a direct-connection profile."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.server_client import ServerClientError
from app.ui.bridge import profiles


@pytest.mark.parametrize("blocked", [
    {"quarantine_until": "malformed"},
    {"quarantine_until": "2099-01-01T00:00:00"},
    {"quarantine_until": "2099-01-01T00:00:00Z"},
    {"status": "quarantined"},
    {"assigned_to": "occupied"},
])
def test_local_pool_import_skips_unavailable_connections(monkeypatch, blocked):
    data = {"QA": {"proxies": [{"value": "http://blocked:8080", **blocked},
                               {"value": "http://available:8080"}]}}
    monkeypatch.setattr(profiles, "db_get_setting", lambda key: json.dumps(data))
    save = Mock()
    monkeypatch.setattr(profiles, "db_set_setting", save)
    bridge = SimpleNamespace(_parse_proxy_value=profiles.ProfilesBridge._parse_proxy_value)
    result = profiles.ProfilesBridge._take_proxy_from_pool(bridge, "QA", "profile1")
    assert result["proxy_host"] == "available"
    stored = json.loads(save.call_args.args[1])["QA"]["proxies"]
    assert stored[0] == data["QA"]["proxies"][0]
    assert stored[1]["assigned_to"] == "profile1"


@pytest.mark.parametrize("entries", [[], [{"value": "invalid"}], [{"value": "http://occupied:8080", "assigned_to": "other"}]])
def test_exhausted_local_import_pool_fails_without_a_write(monkeypatch, entries):
    monkeypatch.setattr(profiles, "db_get_setting", lambda key: json.dumps({"QA": {"proxies": entries}}))
    save = Mock()
    monkeypatch.setattr(profiles, "db_set_setting", save)
    bridge = SimpleNamespace(_parse_proxy_value=profiles.ProfilesBridge._parse_proxy_value)
    with pytest.raises(ValueError, match="available proxy"):
        profiles.ProfilesBridge._take_proxy_from_pool(bridge, "QA", "profile1")
    save.assert_not_called()


@pytest.mark.parametrize("blocked", [{"status": "quarantined"}, {"assigned_profile_id": "occupied"}])
def test_cloud_pool_import_skips_unavailable_connections(blocked):
    client = SimpleNamespace(proxies=lambda: [{"id": "blocked", "group_name": "QA", **blocked},
                                             {"id": "available", "group_name": "QA"}])
    assert profiles.ProfilesBridge._take_server_proxy_from_pool(None, client, "QA") == "available"


def test_cloud_pool_read_failure_is_not_a_direct_connection_fallback():
    client = SimpleNamespace(proxies=Mock(side_effect=ServerClientError("Synthetic unavailable API")))
    with pytest.raises(ServerClientError):
        profiles.ProfilesBridge._take_server_proxy_from_pool(None, client, "QA")


def test_exhausted_cloud_import_pool_fails():
    client = SimpleNamespace(proxies=lambda: [])
    with pytest.raises(ValueError, match="available proxy"):
        profiles.ProfilesBridge._take_server_proxy_from_pool(None, client, "QA")


@pytest.mark.parametrize("cloud", [False, True])
def test_failed_pool_import_creates_no_profile_and_does_not_log_credentials(monkeypatch, caplog, cloud):
    client = SimpleNamespace(proxies=lambda: [], create_profile=Mock())
    monkeypatch.setattr(profiles, "server_enabled", lambda: cloud)
    monkeypatch.setattr(profiles, "db_get_setting", lambda key: "{}")
    create_local = Mock()
    monkeypatch.setattr(profiles, "db_add_account", create_local)
    bridge = SimpleNamespace(_ensure_allowed=lambda role: True, _server_client=lambda: client,
                             _emit_message=Mock(), refresh=Mock(), profilesImportFinished=Mock(),
                             _parse_proxy_value=profiles.ProfilesBridge._parse_proxy_value)
    bridge._take_proxy_from_pool = lambda pool, name: profiles.ProfilesBridge._take_proxy_from_pool(bridge, pool, name)
    bridge._take_server_proxy_from_pool = lambda client, pool: profiles.ProfilesBridge._take_server_proxy_from_pool(bridge, client, pool)
    profiles.ProfilesBridge.importProfiles(bridge, "profile1;synthetic-import-secret", "{name};{password}", "", "QA")
    create_local.assert_not_called()
    client.create_profile.assert_not_called()
    assert "synthetic-import-secret" not in caplog.text
    assert bridge._emit_message.call_args.args[0] == "Imported 0 profile(s), 1 failed"
    bridge.profilesImportFinished.emit.assert_called_once_with("profile1;synthetic-import-secret")


@pytest.mark.parametrize("content", ['[{"name":"profile1"}]', '{"unfinished":'])
def test_failed_local_account_write_restores_pool_assignment(tmp_path, monkeypatch, content):
    from app.storage import db

    accounts, settings = tmp_path / "accounts.json", tmp_path / "settings.json"
    monkeypatch.setattr(db, "ACCOUNTS_FILE", accounts)
    monkeypatch.setattr(db, "SETTINGS_FILE", settings)
    accounts.write_text(content, encoding="utf-8")
    initial = {"QA": {"proxies": [{"value": "http://available:8080"}]}}
    settings.write_text(json.dumps({"proxy_pools": json.dumps(initial), "unrelated": "keep"}), encoding="utf-8")
    monkeypatch.setattr(profiles, "server_enabled", lambda: False)
    bridge = SimpleNamespace(_ensure_allowed=lambda role: True, _emit_message=Mock(), refresh=Mock(), profilesImportFinished=Mock(),
                             _parse_proxy_value=profiles.ProfilesBridge._parse_proxy_value)
    bridge._take_proxy_from_pool = lambda pool, name: profiles.ProfilesBridge._take_proxy_from_pool(bridge, pool, name)
    profiles.ProfilesBridge.importProfiles(bridge, "profile1;synthetic-password", "{name};{password}", "", "QA")
    assert accounts.read_text(encoding="utf-8") == content
    assert json.loads(db.db_get_setting("proxy_pools")) == initial
    assert db.db_get_setting("unrelated") == "keep"
    assert bridge._emit_message.call_args.args[0] == "Imported 0 profile(s), 1 failed"


def test_explicit_no_pool_import_preserves_direct_profile_intent(monkeypatch):
    monkeypatch.setattr(profiles, "server_enabled", lambda: False)
    create = Mock()
    monkeypatch.setattr(profiles, "db_add_account", create)
    bridge = SimpleNamespace(_ensure_allowed=lambda role: True, _emit_message=Mock(), refresh=Mock(), profilesImportFinished=Mock())
    bridge._take_proxy_from_pool = lambda pool, name: profiles.ProfilesBridge._take_proxy_from_pool(bridge, pool, name)
    profiles.ProfilesBridge.importProfiles(bridge, "profile1;synthetic-password", "{name};{password}", "", "")
    create.assert_called_once()
    assert "proxy_host" not in create.call_args.args[0]
    assert bridge._emit_message.call_args.args[0] == "Imported 1 profile(s)"
    bridge.profilesImportFinished.emit.assert_called_once_with("")


def test_incomplete_cloud_session_does_not_import_locally(monkeypatch):
    monkeypatch.setattr(profiles, "server_enabled", lambda: True)
    create = Mock()
    monkeypatch.setattr(profiles, "db_add_account", create)
    bridge = SimpleNamespace(_ensure_allowed=lambda role: True, _server_client=lambda: None,
                             _emit_message=Mock(), refresh=Mock(), profilesImportFinished=Mock())
    profiles.ProfilesBridge.importProfiles(bridge, "profile1", "{name}", "", "")
    create.assert_not_called()
    assert "Cloud session is not configured" in bridge._emit_message.call_args.args[0]


@pytest.mark.parametrize("host,user,password,value", [
    ("proxy.example.invalid", "user@name", "p:a/s#s", "socks5://user%40name:p%3Aa%2Fs%23s@proxy.example.invalid:1080"),
    ("::1", "user", "password", "socks5://user:password@[::1]:1080"),
    ("proxy.example.invalid", "user", "", "socks5://user:@proxy.example.invalid:1080"),
])
@pytest.mark.parametrize("existing", [False, True])
def test_cloud_profile_proxy_fields_use_canonical_connection_strings(host, user, password, value, existing):
    rows = [{"id": "existing", "value": value}] if existing else []
    client = SimpleNamespace(proxies=lambda: rows, create_proxy=Mock(return_value={"id": "new"}))
    identity = profiles.ProfilesBridge._server_proxy_id_from_fields(
        None, client, stage="QA", proxy_host=host, proxy_port="1080", proxy_user=user, proxy_password=password)
    assert identity == ("existing" if existing else "new")
    if existing:
        client.create_proxy.assert_not_called()
    else:
        client.create_proxy.assert_called_once_with({"value": value, "group_name": "QA"})
