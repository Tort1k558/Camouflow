"""Regression checks for bounded AI drafts and integration execution."""

import asyncio
import json

import pytest

from app.cli import definition_hash, validate_readonly
from app.services.ai_agent.actions import ActionError, execute_action, validate_action
from app.services.ai_agent.extraction import table_csv
from app.services.ai_agent.loop import AgentSession, save_transcript
from app.services.ai_agent.templates import template
from app.services.ai_agent.to_steps import compile_workflow
from test_ai_agent import FakeClient, FakePage, make_client, reply, run_session


@pytest.mark.parametrize(
    "url",
    [
        "file:///secret",
        "https://user:pass@example.com",
        "javascript:alert(1)",
        "https://other.test",
    ],
)
def test_url_policy(url):
    session = AgentSession(FakePage(), FakeClient([]), "task", allowed_host="shop.test")
    with pytest.raises(ActionError):
        session._check_url(url)


def test_file_access_is_explicit():
    session = AgentSession(FakePage(), FakeClient([]), "task", allow_local_files=True)
    session._check_url("file:///demo")


def test_zero_elements_and_non_boolean_submit_rejected():
    with pytest.raises(ActionError):
        validate_action({"name": "click", "index": 0}, element_count=0)
    with pytest.raises(ActionError):
        validate_action({"name": "type", "index": 0, "text": "x", "submit": "false"})
    assert validate_action({"name": "type", "index": 0, "text": " x "})["text"] == " x "


def test_click_failure_is_not_silently_successful():
    class Locator:
        async def click(self, **kwargs):
            raise RuntimeError("not actionable")

    class Page:
        url = "https://shop.test"

        def locator(self, selector):
            return Locator()

    with pytest.raises(RuntimeError, match="not actionable"):
        asyncio.run(
            execute_action(
                Page(), {"name": "click", "index": 0}, [{"selector": "button"}]
            )
        )


def test_cancel_preserves_completed_steps():
    async def run():
        entered = asyncio.Event()

        class Client(FakeClient):
            async def next_action(self, *args, **kwargs):
                if self.script:
                    return await super().next_action(*args, **kwargs)
                entered.set()
                await asyncio.sleep(60)

        session = AgentSession(
            FakePage(),
            Client([("type", {"name": "type", "index": 0, "text": "x"})]),
            "task",
        )
        task = asyncio.create_task(session.run())
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        return await task

    result = asyncio.run(run())
    assert result["status"] == "stopped"
    assert result["steps"][-1]["action"] == "type"


def test_pause_obeys_session_deadline():
    result, _ = run_session(
        FakePage(), FakeClient([]), pause_check=lambda: True, session_timeout_s=0.02
    )
    assert result["status"] == "timeout"


def test_approval_obeys_session_deadline():
    async def approval(*args):
        await asyncio.sleep(60)

    result, _ = run_session(
        FakePage(),
        FakeClient([("go", {"name": "click", "index": 1})]),
        before_action=approval,
        session_timeout_s=0.02,
    )
    assert result["status"] == "timeout"


def test_help_without_operator_ends_honestly():
    result, _ = run_session(
        FakePage(),
        FakeClient([("help", {"name": "ask_user", "question": "Which item?"})]),
    )
    assert result["status"] == "needs_help"


def test_password_in_thought_and_result_never_saved(tmp_path):
    secret = 'private"password'
    result, _ = run_session(
        FakePage(),
        FakeClient(
            [
                (secret, {"name": "type", "index": 2, "text": secret}),
                (secret, {"name": "done", "result": secret, "status": "success"}),
            ]
        ),
    )
    encoded = save_transcript(result, tmp_path).read_text(encoding="utf-8")
    assert secret not in encoded and "private" not in encoded
    assert "[redacted]" in json.loads(encoded)["result"]


def test_short_password_redaction_preserves_protocol(tmp_path):
    result, _ = run_session(FakePage(), FakeClient([
        ("a", {"name": "type", "index": 2, "text": "a"}),
        ("finished", {"name": "done", "status": "success"}),
    ]))
    saved = json.loads(save_transcript(result, tmp_path).read_text(encoding="utf-8"))
    assert saved["status"] == "success"
    assert saved["steps"][-1]["value"] == "{{recorded_secret_1}}"
    assert saved["events"][-1]["type"] == "end"


def test_compile_parameter_and_output_extensions():
    steps = [
        {"action": "goto", "value": "https://shop.test"},
        {"action": "extract_text", "selector": "table", "to_var": "rows"},
        {"action": "extract_text", "selector": "h1", "to_var": "title"},
    ]
    compiled = compile_workflow(
        steps,
        {"url": "https://shop.test"},
        {"rows": [{"Name": "A"}], "title": "Catalog"},
    )
    assert compiled[1]["value"] == "{{url}}"
    assert compiled[0]["_required_inputs"] == ["url"]
    assert compiled[-2]["filename"].endswith(".json")
    assert compiled[-1]["filename"].endswith(".txt")
    assert steps[0]["value"] == "https://shop.test"


def test_compile_rejects_unrecorded_input_and_output():
    with pytest.raises(ValueError, match="does not match"):
        compile_workflow([], {"unknown": "x"}, {})
    with pytest.raises(ValueError, match="reproducible"):
        compile_workflow([], {}, {"rows": "x"})


def test_csv_formula_protection():
    csv = table_csv([{"Name": "=HYPERLINK(1)", "Price": "12"}])
    assert "'=HYPERLINK(1)" in csv
    assert table_csv([{"=header": "value"}]).startswith("'=header")


@pytest.mark.parametrize("output", [[], [1], [{"A": "x"}, {"B": "y"}], 12])
def test_invalid_output_schema_rejected(output):
    with pytest.raises(ValueError, match="Outputs must"):
        compile_workflow([], {}, {"rows": output})


def test_reserved_and_conflicting_variables_rejected():
    with pytest.raises(ActionError, match="reserved"):
        validate_action({"name": "extract", "index": 0, "variable": "timestamp"})
    with pytest.raises(ValueError, match="conflicting"):
        compile_workflow(
            [{"action": "goto", "value": "x"}], {"rows": "x"}, {"rows": "y"}
        )


def test_templates_are_isolated_and_cli_restricts_actions():
    original = template("catalog")
    validate_readonly(original["steps"])
    original["steps"][0]["_required_inputs"].append("other")
    assert "other" not in template("catalog")["steps"][0]["_required_inputs"]
    with pytest.raises(ValueError, match="read-only"):
        validate_readonly(template("form")["steps"])
    assert definition_hash([{"action": "start"}]) != definition_hash(
        [{"action": "sleep"}]
    )


def test_malformed_optional_usage_does_not_break_reply():
    client = make_client([reply("done", {"name": "done"})])
    original = client._transport

    async def transport(*args):
        status, body = await original(*args)
        body["usage"] = {"prompt_tokens": "unknown", "completion_tokens": -1}
        return status, body

    client._transport = transport
    asyncio.run(client.next_action([]))
    assert (
        client.requests == 1 and client.prompt_tokens == client.completion_tokens == 0
    )
