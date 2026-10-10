import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.ai_agent.llm import LLMClient, LLMConfig, LLMError
from app.services.scenario_definition import definition_hash
from app.services.selector_repair import apply_selector_repair, propose_selector_repair


def fixture():
    steps = [{"action": "start"}, {"action": "type", "selector": "#old", "value": "PRIVATE_VALUE", "field_label": "Company", "frame_selector": ["#outer"]}]
    locator = SimpleNamespace(count=AsyncMock(return_value=1), is_visible=AsyncMock(return_value=True), evaluate=AsyncMock(return_value={"tag": "input", "type": "text", "editable": False, "disabled": False}))
    frame = SimpleNamespace(url="https://example.test/form?token=PRIVATE_TOKEN", locator=Mock(return_value=locator), evaluate=AsyncMock(return_value={"text": "PRIVATE_TEXT", "elements": [{"tag": "input", "type": "text", "text": "Company", "selector": "#company", "value": "PRIVATE_INPUT", "href": "PRIVATE_LINK"}]}))
    executor = SimpleNamespace(page=SimpleNamespace(url=frame.url), _resolve_frame=AsyncMock(return_value=frame), _build_locator=Mock(return_value=SimpleNamespace(count=AsyncMock(return_value=0))))
    calls = []
    async def transport(method, url, headers, payload):
        calls.append(payload)
        return 200, {"choices": [{"message": {"content": json.dumps({"action": {"name": "click", "index": 0}})}}]}
    client = LLMClient(LLMConfig("https://provider.test", "PRIVATE_KEY", "test"), transport=transport)
    return steps, executor, client, calls, frame, locator


def test_proposal_is_readonly_private_bounded_and_frame_scoped():
    steps, executor, client, calls, frame, locator = fixture()
    proposal = asyncio.run(propose_selector_repair(executor, steps, 1, client))
    assert proposal["replacement_selector"] == "#company"
    assert proposal["applied"] is False
    assert proposal["requests_sent"] == 1
    assert proposal["verified_page"] == "https://example.test/form"
    assert calls[0]["max_tokens"] == 512
    assert "PRIVATE" not in json.dumps(calls)
    assert "PRIVATE_TOKEN" not in json.dumps(proposal)
    executor._resolve_frame.assert_awaited_once_with({**steps[1], "frame_timeout_ms": 3000})
    frame.locator.assert_called_once_with("#company")
    assert steps[1]["selector"] == "#old"


def test_confirmed_patch_changes_only_locator_fields():
    steps, executor, client, _, _, _ = fixture()
    proposal = asyncio.run(propose_selector_repair(executor, steps, 1, client))
    steps[1]["selector_index"] = 7
    proposal["definition_hash"] = definition_hash(steps)
    patched = apply_selector_repair(steps, proposal, confirmed=True)
    expected = copy.deepcopy(steps)
    expected[1].update(selector="#company", selector_type="css", selector_index=0)
    assert patched == expected
    assert steps[1]["selector"] == "#old"


def test_apply_requires_confirmation_and_unchanged_definition():
    steps, executor, client, _, _, _ = fixture()
    proposal = asyncio.run(propose_selector_repair(executor, steps, 1, client))
    with pytest.raises(ValueError, match="Confirm"):
        apply_selector_repair(steps, proposal)
    steps[1]["value"] = "changed"
    with pytest.raises(ValueError, match="scenario changed"):
        apply_selector_repair(steps, proposal, confirmed=True)


@pytest.mark.parametrize("count", [0, 2])
def test_ambiguous_or_missing_replacement_is_rejected(count):
    steps, executor, client, _, _, locator = fixture()
    locator.count.return_value = count
    with pytest.raises(ValueError, match="uniquely"):
        asyncio.run(propose_selector_repair(executor, steps, 1, client))


def test_matching_original_selector_does_not_call_provider():
    steps, executor, client, calls, _, _ = fixture()
    executor._build_locator.return_value.count.return_value = 1
    with pytest.raises(ValueError, match="original selector still matches"):
        asyncio.run(propose_selector_repair(executor, steps, 1, client))
    assert calls == []


def test_invalid_model_replies_stop_after_existing_validation_retry():
    steps, executor, client, calls, _, _ = fixture()
    async def invalid_transport(method, url, headers, payload):
        calls.append(payload)
        return 200, {"choices": [{"message": {"content": "invalid json"}}]}
    client._transport = invalid_transport
    with pytest.raises(LLMError, match="invalid actions"):
        asyncio.run(propose_selector_repair(executor, steps, 1, client))
    assert len(calls) == 2


def test_navigation_during_request_invalidates_proposal():
    steps, executor, client, _, frame, _ = fixture()
    original = client._transport
    async def navigate(method, url, headers, payload):
        response = await original(method, url, headers, payload)
        frame.url = "https://example.test/changed"
        return response
    client._transport = navigate
    with pytest.raises(ValueError, match="page navigated"):
        asyncio.run(propose_selector_repair(executor, steps, 1, client))


def test_negative_assertion_is_not_repaired():
    steps, executor, client, calls, _, _ = fixture()
    steps[1].update(action="wait_element", state="hidden")
    with pytest.raises(ValueError, match="Negative"):
        asyncio.run(propose_selector_repair(executor, steps, 1, client))
    assert calls == []


def test_password_cannot_be_redirected_to_plain_text_field():
    steps, executor, client, calls, _, _ = fixture()
    steps[1]["required_variable"] = "password"
    with pytest.raises(ValueError, match="No compatible"):
        asyncio.run(propose_selector_repair(executor, steps, 1, client))
    assert calls == []


def test_changed_label_after_model_reply_invalidates_proposal():
    steps, executor, client, _, frame, _ = fixture()
    snapshot = frame.evaluate.return_value
    changed = copy.deepcopy(snapshot)
    changed["elements"][0]["text"] = "Different company field"
    frame.evaluate.side_effect = [snapshot, changed]
    with pytest.raises(ValueError, match="target changed"):
        asyncio.run(propose_selector_repair(executor, steps, 1, client))
