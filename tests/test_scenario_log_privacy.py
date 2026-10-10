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
    response = SimpleNamespace(status=200, headers={}, text=AsyncMock(return_value="OK"), json=AsyncMock(return_value={}))
    runner.context = SimpleNamespace(request=SimpleNamespace(fetch=AsyncMock(return_value=response)))
    result = asyncio.run(runner._action_http_request({"url": url}))
    assert result.status == "next" and runner.variables["http_url"] == url
    assert runner.context.request.fetch.call_args.args == (url,)
    assert_private_logs(runner)


def test_explicit_log_action_keeps_user_requested_output(runner):
    result = asyncio.run(runner._action_log({"value": SECRET}))
    assert result.status == "next"
    runner.logger.info.assert_called_once_with("SCENARIO LOG: %s", SECRET)
