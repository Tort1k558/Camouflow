"""Cloud token rotation stays single-flight and cannot undo logout/team changes."""

import json
import threading
from dataclasses import replace
from unittest.mock import Mock

import pytest

from app.services import server_client
from app.storage import db


@pytest.mark.parametrize("app_pair", [False, True])
def test_google_login_starts_in_browser_on_configured_origin(monkeypatch, app_pair):
    client = server_client.ServerClient(server_client.ServerSession(False, "https://cloud.example", "", "", "", ""))
    monkeypatch.setattr(client, "request", lambda *args, **kwargs: {"url": "https://accounts.google.com/o/oauth2/v2/auth?state=owned"})
    expected = "https://cloud.example/api/v1/auth/google/start" + ("?app=true" if app_pair else "")
    assert client.google_login_url(app_pair) == expected


@pytest.mark.parametrize("url", ["https://accounts.google.com.evil.example/", "https://evil.example/accounts.google.com",
                                 "https://accounts.google.com@evil.example/", "http://accounts.google.com/",
                                 "https://user:secret@accounts.google.com/"])
def test_google_login_rejects_spoofed_provider_urls(monkeypatch, url):
    client = server_client.ServerClient(server_client.ServerSession(False, "https://cloud.example", "", "", "", ""))
    monkeypatch.setattr(client, "request", lambda *args, **kwargs: {"url": url})
    with pytest.raises(server_client.ServerClientError):
        client.google_login_url()


@pytest.fixture
def session_store(monkeypatch):
    stored = [server_client.ServerSession(True, "http://example.invalid", "old-access", "old-refresh", "original-team", "qa@example.invalid")]
    monkeypatch.setattr(server_client, "get_server_session", lambda: replace(stored[0]))
    def save(**values):
        stored[0] = server_client.ServerSession(values["enabled"], values["url"], values["token"],
                                                values["refresh_token"], values["team_id"], values["email"])
    monkeypatch.setattr(server_client, "save_server_session", save)
    return stored


@pytest.mark.parametrize("same_client", [False, True])
def test_concurrent_401_refreshes_consume_one_token(session_store, same_client):
    first = server_client.ServerClient(replace(session_store[0]))
    second = first if same_client else server_client.ServerClient(replace(session_store[0]))
    entered, release = threading.Event(), threading.Event()
    calls, errors = [], []
    def request(method, path, payload, **options):
        calls.append(payload)
        entered.set()
        assert release.wait(3)
        return {"access_token": "new-access", "refresh_token": "new-refresh"}
    first.request = second.request = request
    def rotate(client):
        try:
            client.refresh_token(expected_token="old-access")
        except Exception as exc:
            errors.append(exc)
    workers = [threading.Thread(target=rotate, args=(client,)) for client in (first, second)]
    try:
        for worker in workers:
            worker.start()
        assert entered.wait(3)
        release.set()
        for worker in workers:
            worker.join(3)
        assert not any(worker.is_alive() for worker in workers)
        assert not errors
        assert calls == [{"refresh_token": "old-refresh"}]
        assert first.session.token == second.session.token == session_store[0].token == "new-access"
    finally:
        release.set()
        for worker in workers:
            worker.join(3)


@pytest.mark.parametrize("change", ["logout", "server", "account"])
def test_in_flight_refresh_cannot_resurrect_or_overwrite_session(session_store, change):
    client = server_client.ServerClient(replace(session_store[0]))
    def request(*args, **kwargs):
        if change == "logout":
            session_store[0] = replace(session_store[0], enabled=False, token="", refresh_token="")
        elif change == "server":
            session_store[0] = replace(session_store[0], url="http://other.invalid")
        else:
            session_store[0] = replace(session_store[0], email="other@example.invalid")
        return {"access_token": "new-access", "refresh_token": "new-refresh"}
    client.request = request
    with pytest.raises(server_client.ServerClientError, match="changed"):
        client.refresh_token()
    assert session_store[0].token != "new-access"
    assert client.session.token == "old-access"


def test_refresh_preserves_latest_selected_team(session_store):
    client = server_client.ServerClient(replace(session_store[0]))
    def request(*args, **kwargs):
        session_store[0] = replace(session_store[0], team_id="selected-during-refresh")
        return {"access_token": "new-access", "refresh_token": "new-refresh"}
    client.request = request
    client.refresh_token()
    assert session_store[0].team_id == "selected-during-refresh"
    assert client.session.team_id == "original-team"
    assert client.session.token == "new-access"


@pytest.mark.parametrize("payload", [{}, {"access_token": "new-access"}, {"refresh_token": "new-refresh"}])
def test_invalid_refresh_response_preserves_saved_token_pair(session_store, payload):
    client = server_client.ServerClient(replace(session_store[0]))
    client.request = Mock(return_value=payload)
    with pytest.raises(server_client.ServerClientError, match="complete token pair"):
        client.refresh_token()
    assert session_store[0].token == client.session.token == "old-access"
    assert session_store[0].refresh_token == "old-refresh"


def test_stale_401_adopts_already_rotated_tokens_without_another_request(session_store):
    client = server_client.ServerClient(replace(session_store[0]))
    session_store[0] = replace(session_store[0], token="new-access", refresh_token="new-refresh", team_id="other-team")
    client.request = Mock()
    client.refresh_token(expected_token="old-access")
    client.request.assert_not_called()
    assert client.session.token == "new-access"
    assert client.session.team_id == "original-team"


def test_session_save_is_one_atomic_write_and_preserves_other_settings(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"unrelated": "preserved"}), encoding="utf-8")
    monkeypatch.setattr(db, "SETTINGS_FILE", path)
    original = db._atomic_write_text
    writes = Mock(wraps=original)
    monkeypatch.setattr(db, "_atomic_write_text", writes)
    server_client.save_server_session(enabled=True, url="http://example.invalid", token="new-access",
                                      refresh_token="new-refresh", team_id="team", email="qa@example.invalid")
    writes.assert_called_once()
    assert json.loads(path.read_text(encoding="utf-8"))["unrelated"] == "preserved"
    assert server_client.get_server_session().refresh_token == "new-refresh"
    previous = path.read_bytes()
    monkeypatch.setattr(db, "_atomic_write_text", Mock(side_effect=OSError("synthetic disk full")))
    with pytest.raises(OSError):
        server_client.clear_server_session()
    assert path.read_bytes() == previous
