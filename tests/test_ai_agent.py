"""Unit tests for the built-in AI agent core (no browser, no network)."""

import asyncio
import json

import pytest

from app.services.ai_agent.actions import ActionError, describe_action, validate_action
from app.services.ai_agent.llm import LLMClient, LLMConfig, LLMError
from app.services.ai_agent.loop import AgentSession
from app.services.ai_agent.to_steps import scenario_description, session_to_scenario_steps, steps_summary


# --- action validation ---------------------------------------------------------


def test_validate_action_ok():
    assert validate_action({"name": "goto", "url": "https://example.com"}) == {"name": "goto", "url": "https://example.com"}
    assert validate_action({"name": "click", "index": 3})["index"] == 3
    typed = validate_action({"name": "type", "index": 1, "text": "hi", "submit": True})
    assert typed == {"name": "type", "index": 1, "text": "hi", "submit": True}
    assert validate_action({"name": "done", "result": "ok"})["result"] == "ok"
    assert validate_action({"name": "done"}) == {"name": "done", "result": ""}


@pytest.mark.parametrize("payload", [
    {"name": "hack", "index": 0},
    {"name": "click", "index": -1},
    {"name": "click", "index": True},
    {"name": "click", "index": 999},
    {"name": "click", "index": 0, "extra": 1},
    {"name": "goto", "url": "javascript:alert(1)"},
    {"name": "goto", "url": ""},
    {"name": "goto"},
    {"name": "type", "index": 0, "text": ""},
    {"name": "press", "key": "Ctrl+W"},
    {"name": "set_checked", "index": 0, "checked": "yes"},
    {"name": "scroll", "direction": "sideways"},
    {"name": "wait", "seconds": 60},
    {"name": "done", "result": 42},
    "not-a-dict",
])
def test_validate_action_rejects(payload):
    with pytest.raises(ActionError):
        validate_action(payload, element_count=10)


def test_describe_action():
    elements = [{"text": "Log in", "selector": 'button[id="login"]'}]
    assert "Log in" in describe_action({"name": "click", "index": 0}, elements)
    assert "goto" in describe_action({"name": "goto", "url": "https://x.test"})


# --- LLM parsing ----------------------------------------------------------------


def make_client(replies):
    queue = list(replies)

    async def transport(method, url, headers, payload):
        return 200, {"choices": [{"message": {"content": queue.pop(0)}}]}

    return LLMClient(LLMConfig(base_url="https://llm.test/v1", api_key="k", model="m"), transport=transport)


def reply(thought, action):
    return json.dumps({"thought": thought, "action": action})


def test_llm_parses_plain_and_fenced_json():
    client = make_client(['{"thought": "go", "action": {"name": "goto", "url": "https://a.test"}}',
                          '```json\n{"thought": "go2", "action": {"name": "done", "result": "fin"}}\n```'])
    thought, action = asyncio.run(client.next_action([]))
    assert (thought, action["name"], action["url"]) == ("go", "goto", "https://a.test")
    thought, action = asyncio.run(client.next_action([]))
    assert action["name"] == "done"


def test_llm_retries_once_on_invalid_action():
    client = make_client([
        "I think clicking is nice",  # no JSON
        '{"thought": "retry", "action": {"name": "click", "index": 2}}',
    ])
    thought, action = asyncio.run(client.next_action([], element_count=5))
    assert (thought, action) == ("retry", {"name": "click", "index": 2})


def test_llm_gives_up_after_two_bad_replies():
    client = make_client(["garbage", "still garbage"])
    with pytest.raises(LLMError):
        asyncio.run(client.next_action([]))


def test_llm_surfaces_http_errors():
    async def transport(method, url, headers, payload):
        return 401, {"error": "bad key"}

    client = LLMClient(LLMConfig(base_url="https://llm.test/v1", api_key="k", model="m"), transport=transport)
    with pytest.raises(LLMError, match="401"):
        asyncio.run(client.next_action([]))


# --- agent loop with fakes --------------------------------------------------------


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    async def click(self, timeout=None):
        self.page.performed.append(("click", self.selector))

    async def fill(self, text, timeout=None):
        self.page.performed.append(("fill", self.selector, text))

    async def press(self, key, timeout=None):
        self.page.performed.append(("press", self.selector, key))

    async def select_option(self, value, timeout=None):
        self.page.performed.append(("select", self.selector, value))

    async def set_checked(self, checked, timeout=None):
        self.page.performed.append(("check", self.selector, checked))


class FakeKeyboard:
    async def press(self, key):
        self.page.performed.append(("key", key))

    def __init__(self, page):
        self.page = page


class FakePage:
    url = "https://shop.test/catalog"

    def __init__(self, snapshot=None):
        self.snapshot = snapshot or _catalog_snapshot()
        self.performed = []
        self.keyboard = FakeKeyboard(self)
        self.goto_calls = []

    def locator(self, selector):
        return FakeLocator(self, selector)

    async def evaluate(self, script, *args):
        return self.snapshot

    async def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append(url)
        self.url = url

    async def wait_for_load_state(self, state=None, timeout=None):
        self.performed.append(("load_state", state))


def _catalog_snapshot():
    return {
        "url": "https://shop.test/catalog",
        "title": "Catalog",
        "elements": [
            {"index": 0, "tag": "input", "selector": 'input[id="search"]', "type": "text", "text": "Search"},
            {"index": 1, "tag": "button", "selector": 'button[id="search-go"]', "text": "Go"},
            {"index": 2, "tag": "input", "selector": 'input[id="pass"]', "type": "password", "text": "Password"},
        ],
    }


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.seen_element_counts = []

    async def next_action(self, messages, element_count=250):
        self.seen_element_counts.append(element_count)
        thought, action = self.script.pop(0)
        return thought, validate_action(action, element_count)


def run_session(page, client, **kwargs):
    events = []
    session = AgentSession(page, client, "find the price", on_event=events.append, **kwargs)
    result = asyncio.run(session.run())
    return result, events


def test_loop_executes_script_and_finishes():
    page = FakePage()
    client = FakeClient([
        ("search", {"name": "type", "index": 0, "text": "coffee", "submit": False}),
        ("go", {"name": "click", "index": 1}),
        ("done", {"name": "done", "result": "price is 42"}),
    ])
    result, events = run_session(page, client)
    assert result["status"] == "done"
    assert result["result"] == "price is 42"
    assert ("fill", 'input[id="search"]', "coffee") in page.performed
    assert ("click", 'button[id="search-go"]') in page.performed
    actions = [e["action"] for e in events if e["type"] == "action"]
    assert actions == ["type", "click", "done"]
    # steps: start, type, click (+ load_state settle), no press
    step_actions = [s["action"] for s in result["steps"]]
    assert step_actions[0] == "start"
    assert "type" in step_actions and "click" in step_actions
    assert [s["tag"] for s in result["steps"]] == ["Start"] + [f"Step{i}" for i in range(1, len(result["steps"]))]
    assert client.seen_element_counts[0] == 3  # element_count passed through


def test_loop_masks_password_typing_as_secret():
    page = FakePage()
    client = FakeClient([
        ("login", {"name": "type", "index": 2, "text": "hunter2"}),
        ("done", {"name": "done", "result": "ok"}),
    ])
    result, _ = run_session(page, client)
    assert ("fill", 'input[id="pass"]', "hunter2") in page.performed
    assert result["secrets"] == {"recorded_secret_1": "hunter2"}
    type_step = next(s for s in result["steps"] if s["action"] == "type")
    assert type_step["value"] == "{{recorded_secret_1}}"
    assert type_step["required_variable"] == "recorded_secret_1"
    # secrets never leak into events
    assert "hunter2" not in json.dumps(result["events"])


def test_loop_recovers_from_action_error_then_stops_after_streak():
    class ExplodingPage(FakePage):
        async def evaluate(self, script, *args):
            raise RuntimeError("page gone")

    page = ExplodingPage()
    client = FakeClient([("hmm", {"name": "done", "result": "x"})])
    result, events = run_session(page, client)
    assert result["status"] == "error"
    assert any(e["type"] == "error" for e in events)


def test_loop_respects_max_steps():
    page = FakePage()
    client = FakeClient([("more", {"name": "scroll", "direction": "down", "amount": 600})] * 10)
    result, _ = run_session(page, client, max_steps=3)
    assert result["status"] == "max_steps"


def test_loop_stop_event():
    page = FakePage()

    async def scenario():
        stop = asyncio.Event()
        client = FakeClient([("wait", {"name": "wait", "seconds": 5})] * 20)
        session = AgentSession(page, client, "task", on_event=lambda e: None, stop_event=stop, session_timeout_s=60)
        run = asyncio.create_task(session.run())
        await asyncio.sleep(0.05)
        stop.set()
        return await run

    result = asyncio.run(scenario())
    assert result["status"] == "stopped"


# --- to_steps ----------------------------------------------------------------------


def test_session_to_scenario_steps_merges_typing_and_tags():
    raw = [
        {"action": "start", "tag": "Start"},
        {"action": "goto", "url": "https://a.test", "value": "https://a.test", "tag": "Step1"},
        {"action": "type", "selector": 'input[id="q"]', "value": "ab", "clear": True, "tag": "Step2"},
        {"action": "type", "selector": 'input[id="q"]', "value": "abcd", "clear": True, "tag": "Step3"},
        {"action": "click", "selector": 'button[id="go"]', "tag": "Step4"},
    ]
    steps = session_to_scenario_steps(raw)
    assert [s["action"] for s in steps] == ["start", "goto", "type", "click"]
    assert steps[2]["value"] == "abcd"
    assert [s["tag"] for s in steps] == ["Start", "Step1", "Step2", "Step3"]


def test_summary_and_description():
    steps = [{"action": "start"}] + [{"action": a} for a in ("goto", "click", "type")]
    assert steps_summary(steps).startswith("3 steps")
    assert scenario_description("  find   the price ").startswith("AI draft: find the price")
