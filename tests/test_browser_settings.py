"""Settings must survive persistence and reach the selected browser engine."""
import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.browser_interface import BrowserInterface
from app.core.browser_launchers import CamoufoxLaunchBuilder, CloakBrowserLaunchBuilder
from app.core.camoufox_profile_fingerprint import (
    load_or_create_profile_fingerprint_bundle,
)
from app.storage import db


def cloak_builder(path, settings):
    return CloakBrowserLaunchBuilder(path, db.CLOAKBROWSER_DEFAULTS, settings, None,
                                    lambda: "en-US", lambda: "America/New_York")


def test_cloak_window_and_screen_are_independent(tmp_path):
    options = cloak_builder(tmp_path, {"window_width": 1100, "window_height": 700,
        "screen_width": 1920, "screen_height": 1080}).build()
    assert options["viewport"] == {"width": 1100, "height": 700}
    assert "--window-size=1100,700" in options["args"]
    assert "--fingerprint-screen-width=1920" in options["args"]
    assert "--fingerprint-screen-height=1080" in options["args"]
    assert "viewport" not in cloak_builder(tmp_path, {}).build()


def test_camoufox_fixed_window_fingerprint_roundtrip_and_resize(tmp_path):
    first, overrides, gpu = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1100, 700))
    second, restored, restored_gpu = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1100, 700))
    assert asdict(first) == asdict(second)
    assert all(overrides[key] == value for key, value in restored.items())
    assert gpu == restored_gpu
    resized, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1000, 650))
    assert resized.navigator == first.navigator
    assert (resized.screen.outerWidth, resized.screen.outerHeight) == (1000, 650)
    third, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows", window=(1000, 650))
    assert asdict(resized) == asdict(third)


def test_camoufox_requested_os_change_is_not_ignored(tmp_path):
    first, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    second, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="linux")
    assert "Windows" in first.navigator.userAgent
    assert "Linux" in second.navigator.userAgent


def test_existing_camoufox_profile_gets_persistent_noise_seeds_without_identity_reset(tmp_path):
    first, _, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    path = tmp_path / "camoufox_fingerprint.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ("audio:seed",):
        payload["overrides"].pop(key)
    path.write_text(json.dumps(payload), encoding="utf-8")
    migrated, seeds, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    restored, later_seeds, _ = load_or_create_profile_fingerprint_bundle(tmp_path, os_payload="windows")
    assert asdict(first) == asdict(migrated) == asdict(restored)
    assert seeds["audio:seed"] == later_seeds["audio:seed"]


def test_camoufox_context_gpu_and_screen_defaults_survive_save(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SETTINGS_FILE", tmp_path / "settings.json")
    values = {"screen_width": 1920, "screen_height": 1080, "webgl_vendor": "vendor", "webgl_renderer": "renderer",
              "extra_http_headers": {"X-Audit": "global"}, "permissions": ["geolocation"], "java_script_enabled": False,
              "bypass_csp": True, "ignore_https_errors": True, "accept_downloads": False}
    db.db_set_camoufox_defaults(values)
    assert all(db.db_get_camoufox_defaults()[key] == value for key, value in values.items())


def test_camoufox_persistent_launch_applies_context_options(tmp_path):
    options = CamoufoxLaunchBuilder("test", tmp_path, {"locale": "en-US", "timezone": "America/New_York",
        "os": ["windows"], "java_script_enabled": False, "bypass_csp": True,
        "permissions": ["geolocation"], "screen_width": 1920, "screen_height": 1080,
        "extra_http_headers": {"X-Audit": "test"}}, db.CAMOUFOX_DEFAULTS, None, None,
        SimpleNamespace(detect_timezone=lambda: None), Mock(), Mock(), lambda: "en-US").build()
    assert options["java_script_enabled"] is False
    assert options["bypass_csp"] is True
    assert options["extra_http_headers"] == {"X-Audit": "test"}
    assert options["config"]["screen.width"] == 1920
    assert "window.history.length" not in options["config"]


@pytest.mark.parametrize("clear", [True, False])
def test_disabled_humanization_does_not_add_typing_delays(clear, monkeypatch):
    sleeper = AsyncMock()
    monkeypatch.setattr("app.core.browser_interface.asyncio.sleep", sleeper)
    browser = SimpleNamespace(_browser_settings={"humanize": False}, browser_engine="cloakbrowser")
    element = SimpleNamespace(fill=AsyncMock(), type=AsyncMock())
    asyncio.run(BrowserInterface._human_type(browser, element, "audit", clear=clear))
    (element.fill if clear else element.type).assert_awaited_once_with("audit")
    sleeper.assert_not_awaited()


@pytest.mark.parametrize("persistent", [True, False])
def test_cloak_context_uses_native_launcher_and_inherited_defaults(tmp_path, monkeypatch, persistent):
    import cloakbrowser

    monkeypatch.setattr("app.core.browser_interface.profile_dir_for_email", lambda name: tmp_path / name)
    monkeypatch.setattr("app.core.browser_interface.db_get_camoufox_defaults", lambda: dict(db.CAMOUFOX_DEFAULTS))
    monkeypatch.setattr("app.core.browser_interface.db_get_cloakbrowser_defaults", lambda: {
        **db.CLOAKBROWSER_DEFAULTS, "locale": "de-DE", "timezone": "Europe/Berlin",
        "humanize": False, "extra_http_headers": {"X-Audit": "global"}})
    context = SimpleNamespace(browser=Mock())
    launch = AsyncMock(return_value=context)
    monkeypatch.setattr(cloakbrowser, "launch_persistent_context_async" if persistent else "launch_context_async", launch)
    browser = BrowserInterface("test", browser_engine="cloakbrowser", browser_settings={"persistent_context": persistent})
    asyncio.run(browser._start_cloakbrowser())
    assert browser.context is context
    options = launch.call_args.kwargs
    assert options["locale"] == "de-DE"
    assert options["timezone"] == "Europe/Berlin"
    assert options["extra_http_headers"] == {"X-Audit": "global"}
    assert "timezone_id" not in options
    assert "viewport" not in options
    assert browser._browser_settings["humanize"] is False


@pytest.mark.parametrize("entry, expected", [
    ({}, False), ({"quarantine_until": ""}, False),
    ({"quarantine_until": "2000-01-01T00:00:00Z"}, False),
    ({"quarantine_until": "2099-01-01T00:00:00+03:00"}, True),
    ({"quarantine_until": "2099-01-01T00:00:00"}, True),
    ({"quarantine_until": "malformed"}, True),
    ({"status": "quarantined"}, True),
])
def test_quarantine_is_consistent_between_launch_policy_and_ui(entry, expected):
    from app.services.proxy_policy import is_proxy_quarantined
    from app.ui.bridge.proxies import ProxiesBridge

    assert is_proxy_quarantined(entry) is expected
    assert ProxiesBridge._is_quarantined(entry) is expected


def test_invalid_quarantine_skips_candidate_without_disabling_healthy_pool():
    import threading
    from app.services.proxy_policy import choose_proxy

    probe = Mock(return_value=(True, 1, "", {}))
    candidates = [{"value": "socks5://invalid:1080", "quarantine_until": "malformed"},
                  {"value": "socks5://healthy:1080"}]
    assert choose_proxy({}, "replace_failed", candidates, threading.Event(), probe) == "socks5://healthy:1080"
    probe.assert_called_once_with("socks5://healthy:1080", timeout_s=5.0)


@pytest.mark.parametrize("assigned", [True, False])
def test_cancel_during_proxy_probe_does_not_return_an_assignment(assigned):
    import threading
    from app.services.proxy_policy import choose_proxy

    cancel = threading.Event()
    def probe(value, timeout_s):
        cancel.set()
        return True, 1, "", {}
    account = {"proxy_host": "assigned", "proxy_port": "1080"} if assigned else {}
    with pytest.raises(ValueError, match="canceled"):
        choose_proxy(account, "replace_failed", [{"value": "socks5://replacement:1080"}], cancel, probe)


@pytest.mark.parametrize("check_all", [False, True])
@pytest.mark.parametrize("mutation", ["edit", "delete", "replace"])
def test_proxy_probe_completion_preserves_concurrent_pool_edits(monkeypatch, check_all, mutation):
    import copy
    import json
    import threading
    from app.ui.bridge import proxies

    state = {"QA": {"proxies": [{"value": "socks5://synthetic:1080", "name": "Before"}]}}
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    refreshes = [0]
    def save(data):
        state.clear()
        state.update(copy.deepcopy(data))
    def refresh():
        refreshes[0] += 1
        if refreshes[0] > 1:
            finished.set()
    def probe(value, timeout_s):
        entered.set()
        assert release.wait(3)
        return True, 1, "", {}
    monkeypatch.setattr(proxies, "server_enabled", lambda: False)
    monkeypatch.setattr(proxies, "db_get_setting", lambda key: json.dumps(state))
    monkeypatch.setattr(proxies, "db_set_setting", lambda key, value: save(json.loads(value)))
    monkeypatch.setattr("app.services.proxy_health.probe_proxy_endpoint", probe)
    bridge = SimpleNamespace(_ensure_allowed=lambda _: True, _server_client=lambda: None,
                             _load=lambda: copy.deepcopy(state), _save=save, refresh=refresh,
                             _record_check=proxies.ProxiesBridge._record_check,
                             _is_quarantined=proxies.ProxiesBridge._is_quarantined, _emit_message=Mock())
    bridge._store_local_check = lambda pool, value, result: proxies.ProxiesBridge._store_local_check(bridge, pool, value, result)
    try:
        if check_all:
            proxies.ProxiesBridge.checkAll(bridge)
        else:
            proxies.ProxiesBridge.checkProxy(bridge, "QA", 0)
        assert entered.wait(3)
        if mutation == "edit":
            state["QA"]["proxies"][0].update(name="Edited during check", assigned_to="Synthetic profile")
        elif mutation == "delete":
            state["QA"]["proxies"].clear()
        else:
            state["QA"]["proxies"][0].update(value="socks5://replacement:1080", last_check={"status": "unchecked"})
        state["QA"]["proxies"].append({"value": "socks5://new:1080", "name": "Added during check"})
        release.set()
        assert finished.wait(3)
        rows = state["QA"]["proxies"]
        assert rows[-1]["name"] == "Added during check"
        assert "last_check" not in rows[-1]
        if mutation == "edit":
            assert rows[0]["name"] == "Edited during check"
            assert rows[0]["assigned_to"] == "Synthetic profile"
            assert rows[0]["last_check"]["status"] == "ok"
        elif mutation == "delete":
            assert len(rows) == 1
        else:
            assert rows[0]["value"] == "socks5://replacement:1080"
            assert rows[0]["last_check"]["status"] == "unchecked"
    finally:
        release.set()


def test_local_proxy_result_is_discarded_after_cloud_switch(monkeypatch):
    from app.ui.bridge import proxies

    monkeypatch.setattr(proxies, "server_enabled", lambda: True)
    save = Mock()
    monkeypatch.setattr(proxies, "db_set_setting", save)
    bridge = SimpleNamespace(_record_check=proxies.ProxiesBridge._record_check)
    assert not proxies.ProxiesBridge._store_local_check(bridge, "QA", "socks5://synthetic:1080", {"status": "ok"})
    save.assert_not_called()


@pytest.mark.parametrize("value, expected", [
    ("", "None"), ("socks5://host:1080", "socks5://host:1080"),
    ("socks5://username:secret@host:1080", "socks5://host:1080"),
    ("http://host:8080:username:secret", "http://host:8080"),
    ("host:1080:username:secret", "socks5://host:1080"),
    ("username:secret@host:1080", "socks5://host:1080"),
    ("http://u:p%40ss@[::1]:8080", "http://[::1]:8080"),
    ("http://u:secret@host:invalid", "Invalid proxy"),
    ("malformed-secret", "Invalid proxy"),
])
def test_proxy_list_address_never_displays_credentials(value, expected):
    from app.core.proxy_utils import proxy_display_address

    assert proxy_display_address(value) == expected


def test_proxy_inventory_distinguishes_unchecked_tcp_and_internet_checks():
    from app.ui.bridge.models import DictListModel
    from app.ui.bridge.proxies import ProxiesBridge

    entries = [
        {"value": "http://synthetic-user:synthetic-secret@fresh:1080", "status": "unchecked"},
        {"value": "http://internet:1080", "last_check": {"status": "ok", "mode": "internet"}},
        {"value": "http://tcp:1080", "last_check": {"status": "ok", "mode": "tcp"}},
        {"value": "http://checking:1080", "last_check": {"status": "checking"}},
        {"value": "http://failed:1080", "last_check": {"status": "fail"}},
        {"value": "http://quarantined:1080", "quarantine_until": "malformed"},
    ]
    bridge = SimpleNamespace(_pools_cache={"QA": {"proxies": entries}}, _server_pools={}, _selected_pool="", _selected=set(), _proxy_query="", _proxy_status="",
                             _pools_model=DictListModel(["name"]), _model=DictListModel(["status", "address"]),
                             _is_quarantined=ProxiesBridge._is_quarantined, modelChanged=Mock(), statsChanged=Mock())
    ProxiesBridge._render_pools(bridge)
    rows = bridge._model.rows()
    assert [row["status"] for row in rows] == ["Unchecked", "Active", "Reachable", "Checking", "Failed", "Quarantined"]
    assert rows[0]["address"] == "http://fresh:1080"
    assert "synthetic-secret" in entries[0]["value"]
    assert (bridge._active, bridge._unchecked, bridge._checking, bridge._failed) == (2, 1, 1, 2)
    assert bridge._locations == 0


def test_cloud_proxy_check_scope_is_conservative_and_does_not_mutate_response(monkeypatch):
    import copy
    from app.ui.bridge import proxies

    rows = [
        {"value": "http://fresh:1080", "status": "active", "last_check": {}},
        {"value": "http://legacy:1080", "last_check": {"status": "ok", "ms": 1}},
        {"value": "http://full:1080", "last_check": {"status": "ok", "mode": "internet"}},
    ]
    original = copy.deepcopy(rows)
    monkeypatch.setattr(proxies, "ServerClient", lambda session: SimpleNamespace(proxies=lambda: rows))
    pools = proxies.ProxiesBridge._load(SimpleNamespace(), SimpleNamespace(enabled=True))
    checks = [row["last_check"] for row in pools["Default"]["proxies"]]
    assert checks[0]["status"] == "unchecked"
    assert checks[1]["mode"] == "tcp"
    assert checks[2]["mode"] == "internet"
    assert rows == original


def test_cloud_proxy_actions_resolve_displayed_snapshot_not_fresh_position(monkeypatch):
    from app.ui.bridge import proxies

    session = SimpleNamespace(enabled=True, url="https://synthetic.invalid", team_id="team", email="qa@synthetic.invalid")
    monkeypatch.setattr(proxies, "get_server_session", lambda: session)
    load = Mock(return_value={"QA": {"proxies": [{"id": "new-row"}, {"id": "shown-row"}]}})
    bridge = SimpleNamespace(_cache_session=session, _pools_cache={"QA": {"proxies": [{"id": "shown-row"}]}}, _load=load)
    assert proxies.ProxiesBridge._server_proxy_entry(bridge, "QA", 0)["id"] == "shown-row"
    load.assert_not_called()
    bridge._pools_cache["QA"]["proxies"].insert(0, {"id": "new-row"})
    assert proxies.ProxiesBridge._server_proxy_entry(bridge, "QA", 0, "shown-row")["id"] == "shown-row"
    assert proxies.ProxiesBridge._server_proxy_entry(bridge, "QA", 0, "removed-row") == {}
    monkeypatch.setattr(proxies, "get_server_session", lambda: SimpleNamespace(**{**vars(session), "team_id": "other-team"}))
    assert proxies.ProxiesBridge._server_proxy_entry(bridge, "QA", 0) == {}


def test_cloud_bulk_delete_uses_original_ids_after_each_server_reorder(monkeypatch):
    from app.ui.bridge import proxies

    session = SimpleNamespace(enabled=True, url="https://synthetic.invalid", team_id="team", email="qa@synthetic.invalid")
    monkeypatch.setattr(proxies, "get_server_session", lambda: session)
    monkeypatch.setattr(proxies, "server_enabled", lambda: True)
    server_rows = [{"id": "selected-A"}, {"id": "selected-B"}, {"id": "unselected-C"}]
    deleted = []
    def delete(identity):
        deleted.append(identity)
        server_rows[:] = [row for row in server_rows if row["id"] != identity]
    client = SimpleNamespace(delete_proxy=delete)
    bridge = SimpleNamespace(_cache_session=session, _pools_cache={"QA": {"proxies": list(server_rows)}},
                             _selected={("QA", 0), ("QA", 1)}, _server_client=lambda: client,
                             _ensure_allowed=lambda _: True, _emit_message=Mock(), refresh=Mock(),
                             _load=lambda: {"QA": {"proxies": list(server_rows)}})
    bridge._server_proxy_entry = lambda pool, index: proxies.ProxiesBridge._server_proxy_entry(bridge, pool, index)
    proxies.ProxiesBridge.removeSelected(bridge)
    assert set(deleted) == {"selected-A", "selected-B"}
    assert server_rows == [{"id": "unselected-C"}]


def test_cloud_refresh_clears_positional_selection_when_inventory_changes():
    from app.ui.bridge.proxies import ProxiesBridge

    session = SimpleNamespace(enabled=True)
    bridge = SimpleNamespace(_pools_cache={"QA": {"proxies": [{"id": "A"}]}},
                             _selected={("QA", 0)}, _render_pools=Mock())
    ProxiesBridge._apply_refresh(bridge, (session, {"QA": {"proxies": [{"id": "B"}, {"id": "A"}]}}, {}))
    assert not bridge._selected
    bridge._selected.add(("QA", 1))
    ProxiesBridge._apply_refresh(bridge, (session, {"QA": {"proxies": [{"id": "B", "name": "changed"}, {"id": "A"}]}}, {}))
    assert bridge._selected == {("QA", 1)}


@pytest.mark.parametrize("method", ["saveProxy", "deleteProxy"])
@pytest.mark.parametrize("enabled, identity", [(False, "cloud-id"), (True, "local")])
def test_proxy_dialog_action_rejects_local_cloud_switch(monkeypatch, method, enabled, identity):
    from app.ui.bridge import proxies

    monkeypatch.setattr(proxies, "server_enabled", lambda: enabled)
    bridge = SimpleNamespace(_ensure_allowed=lambda _: True, _emit_message=Mock())
    args = ("QA", 0, "Name", "http://synthetic:1080", identity) if method == "saveProxy" else ("QA", 0, identity)
    getattr(proxies.ProxiesBridge, method)(bridge, *args)
    bridge._emit_message.assert_called_once()


def test_proxy_filters_use_cached_metadata_preserve_indices_and_pool_stats():
    from app.ui.bridge.models import DictListModel
    from app.ui.bridge.proxies import ProxiesBridge

    bridge = SimpleNamespace(_pools_cache={"QA": {"proxies": [
        {"name": "Stra\u00dfe", "value": "http://username:secret@first:1080"},
        {"name": "Europe", "value": "http://second:1080", "last_check": {"status": "ok", "mode": "tcp", "country": "Synthetic"}},
    ]}}, _server_pools={}, _selected_pool="", _selected={("QA", 0)}, _proxy_query="", _proxy_status="",
        _pools_model=DictListModel(["name"]), _model=DictListModel(["status", "address"]),
        _is_quarantined=ProxiesBridge._is_quarantined, modelChanged=Mock(), statsChanged=Mock(), _load=Mock())
    bridge._render_pools = lambda: ProxiesBridge._render_pools(bridge)
    ProxiesBridge.setProxyFilters(bridge, " STRASSE ", "unchecked")
    assert [row["index"] for row in bridge._model.rows()] == [0]
    assert not bridge._selected
    assert (bridge._active, bridge._unchecked, bridge._locations) == (1, 1, 1)
    ProxiesBridge.setProxyFilters(bridge, "synthetic", "reachable")
    assert [row["index"] for row in bridge._model.rows()] == [1]
    ProxiesBridge.setProxyFilters(bridge, "secret", "")
    assert bridge._model.rowCount() == 0
    ProxiesBridge.setProxyFilters(bridge, "", "invalid")
    assert bridge._proxy_query == "secret"
    resets = bridge.modelChanged.call_count
    ProxiesBridge.setProxyFilters(bridge, "secret", "")
    assert bridge.modelChanged.call_count == resets
    ProxiesBridge.setProxyFilters(bridge, "", "")
    assert bridge._model.rowCount() == 2
    bridge._load.assert_not_called()
