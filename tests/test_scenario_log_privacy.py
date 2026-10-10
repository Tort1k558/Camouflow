"""Implicit progress logs must not copy scenario values or credential pools."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.scenario_engine import ScenarioExecutor

SECRET = "synthetic-private-value-123"


@pytest.fixture
def runner():
    executor = ScenarioExecutor.__new__(ScenarioExecutor)
    executor.variables = {}
    executor.logger = Mock()
    executor._persist_profile_vars = AsyncMock()
    executor.shared_manager = Mock()
    executor.shared_manager.all.return_value = {}
    return executor


def assert_private_logs(runner):
    assert runner.logger.info.called
    for call in runner.logger.info.call_args_list:
        assert SECRET not in str(call)


@pytest.mark.parametrize("scope", ["profile", "shared", "both"])
def test_set_var_preserves_value_without_logging_it(runner, scope):
    result = asyncio.run(runner._action_set_var({"name": "password", "value": SECRET, "scope": scope}))
    assert result.status == "next" and runner.variables["password"] == SECRET
    if scope != "profile":
        runner.shared_manager.set.assert_called_once_with("password", SECRET)
    assert_private_logs(runner)


def test_extract_preserves_content_without_logging_it(runner):
    runner._locate_element = AsyncMock(return_value=SimpleNamespace(text_content=AsyncMock(return_value=SECRET)))
    result = asyncio.run(runner._action_extract({"to_var": "private_content"}))
    assert result.status == "next" and runner.variables["private_content"] == SECRET
    assert_private_logs(runner)


def test_shared_pool_pop_updates_account_without_logging_credentials(runner):
    runner.shared_manager.get.return_value = SECRET
    runner.shared_manager.pop_first.return_value = (SECRET, "")
    runner._persist_shared_setting = Mock()
    runner._account_updater = Mock()
    runner.account_payload = {}
    result = asyncio.run(runner._action_pop_shared({"value": "credentials", "pattern": "{{password}}"}))
    assert result.status == "next" and runner.variables["password"] == SECRET
    runner._account_updater.assert_called_once_with({"password": SECRET})
    assert_private_logs(runner)


def test_http_progress_does_not_log_url_credentials_or_query(runner):
    url = f"https://user:{SECRET}@example.invalid/path?token={SECRET}"
    response = SimpleNamespace(status=200, headers={}, text=AsyncMock(return_value="OK"), json=AsyncMock(return_value={}), dispose=AsyncMock())
    runner.context = SimpleNamespace(request=SimpleNamespace(fetch=AsyncMock(return_value=response)))
    result = asyncio.run(runner._action_http_request({"url": url}))
    assert result.status == "next" and runner.variables["http_url"] == url
    assert runner.context.request.fetch.call_args.args == (url,)
    assert_private_logs(runner)
    response.dispose.assert_awaited_once()


def test_explicit_log_action_keeps_user_requested_output(runner):
    result = asyncio.run(runner._action_log({"value": SECRET}))
    assert result.status == "next"
    runner.logger.info.assert_called_once_with("SCENARIO LOG: %s", SECRET)


@pytest.mark.parametrize("timeout_ms", [None, 0, 1500, "30000", 1.5])
def test_http_request_preserves_playwright_millisecond_timeout(runner, timeout_ms):
    response = SimpleNamespace(status=200, headers={}, text=AsyncMock(return_value="OK"), json=AsyncMock(return_value={}), dispose=AsyncMock())
    runner.context = SimpleNamespace(request=SimpleNamespace(fetch=AsyncMock(return_value=response)))

    result = asyncio.run(runner._action_http_request({"url": "https://example.invalid/", "timeout_ms": timeout_ms}))

    assert result.status == "next"
    expected = None if timeout_ms is None else float(timeout_ms)
    assert runner.context.request.fetch.call_args.kwargs["timeout"] == expected
    response.dispose.assert_awaited_once()


@pytest.mark.parametrize("timeout_ms", [True, False, -1, "invalid", "", [], float("nan"), float("inf")])
def test_http_request_rejects_invalid_timeout_before_network_io(runner, timeout_ms):
    runner.context = SimpleNamespace(request=SimpleNamespace(fetch=AsyncMock()))

    result = asyncio.run(runner._action_http_request({"url": "https://example.invalid/", "timeout_ms": timeout_ms}))

    assert result.status == "stop" and "timeout_ms" in result.stop_reason
    runner.context.request.fetch.assert_not_awaited()


@pytest.mark.parametrize("status", [200, 503])
def test_http_request_releases_response_after_non_json_body(runner, status):
    response = SimpleNamespace(status=status, headers={}, text=AsyncMock(return_value="Synthetic non-JSON body"),
                               json=AsyncMock(side_effect=ValueError("Not JSON")), dispose=AsyncMock())
    runner.context = SimpleNamespace(request=SimpleNamespace(fetch=AsyncMock(return_value=response)))

    result = asyncio.run(runner._action_http_request({"url": "https://example.invalid/", "require_success": True}))

    assert result.status == ("next" if status == 200 else "stop")
    assert runner.variables["http_body"] == "Synthetic non-JSON body"
    response.dispose.assert_awaited_once()


def test_http_request_releases_response_when_result_processing_fails(runner):
    response = SimpleNamespace(status="invalid", dispose=AsyncMock())
    runner.context = SimpleNamespace(request=SimpleNamespace(fetch=AsyncMock(return_value=response)))

    with pytest.raises(ValueError):
        asyncio.run(runner._action_http_request({"url": "https://example.invalid/"}))

    response.dispose.assert_awaited_once()
