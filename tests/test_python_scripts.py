"""Contract tests; no browser or user profile data required."""

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from app.services.python_script import DEFAULT_CODE, execute_script, script_bundle, validate_script


def step(code=DEFAULT_CODE, **kwargs):
    return {"action": "python", "script_api_version": 1, "code": code, **kwargs}


@pytest.mark.parametrize("payload", [
    step("def main(ctx):\n    return 1"), step("async def main():\n    return 1"),
    step("async def main(ctx):\n    return ("), step(script_api_version=2),
    step(inputs=[]), step(timeout_ms=0), step(timeout_ms=True),
])
def test_invalid_script_contract(payload):
    with pytest.raises((ValueError, SyntaxError)):
        validate_script(payload)


def test_nested_script_digest_changes_on_edits():
    steps = [{"action": "run_scenario", "scenario": "child"}]
    library = {"child": {"steps": [step()]}}
    digest, preview = script_bundle(steps, library)
    assert digest and "async def main" in preview
    library["child"]["steps"][0]["code"] += "\n# edit"
    assert script_bundle(steps, library)[0] != digest


def test_dynamic_nested_calls_include_library_and_cycles_terminate():
    steps = [{"action": "run_scenario", "scenario": "{{target}}"}]
    library = {"child": {"steps": [step(), {"action": "run_scenario", "scenario": "child"}]}}
    assert script_bundle(steps, library)[0]


def test_plain_scenario_requires_no_approval():
    assert script_bundle([{"action": "start"}], {}) == ("", "")


@pytest.mark.parametrize("key", ["scenario", "scenario_name", "name", "value"])
def test_nested_reference_aliases(key):
    assert script_bundle([{"action": "run_scenario", key: " child "}],
                         {"child": {"steps": [step()]}})[0]


def runner(tmp_path):
    async def persist():
        pass
    events = []
    return SimpleNamespace(_python_worker=True, _run_artifact_dir=tmp_path,
                           variables={"existing": "retained"}, _cancel_event=threading.Event(),
                           logger=__import__("logging").getLogger(__name__),
                           _apply_template_recursive=lambda value: value,
                           _persist_profile_vars=persist, _worker_emit=events.append)


def test_result_and_inputs_are_separate_from_code(tmp_path):
    engine = runner(tmp_path)
    payload = step('async def main(ctx):\n    return {"text": ctx.inputs["text"]}',
                   inputs={"text": "quotes '\" {braces}\n"}, result_variable="output")
    result = asyncio.run(execute_script(engine, payload))
    assert result.status == "next"
    assert __import__("json").loads(engine.variables["output"]) == payload["inputs"]
    assert engine.variables["existing"] == "retained"


@pytest.mark.parametrize("code", [
    "async def main(ctx):\n    return object()", "async def main(ctx):\n    return float('nan')",
    "async def main(ctx):\n    raise ValueError('failure')",
    "async def main(ctx):\n    return 'x' * 1048577",
])
def test_failure_does_not_overwrite_result(tmp_path, code):
    engine = runner(tmp_path)
    with pytest.raises(RuntimeError):
        asyncio.run(execute_script(engine, step(code, result_variable="existing")))
    assert engine.variables["existing"] == "retained"


def test_legacy_execution_cannot_bypass_supervisor(tmp_path):
    engine = runner(tmp_path)
    engine._python_worker = False
    with pytest.raises(RuntimeError, match="supervised"):
        asyncio.run(execute_script(engine, step()))


def test_missing_input_is_explicit(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        asyncio.run(execute_script(runner(tmp_path), step(inputs={"url": "{{missing}}"})))


def test_debugger_runs_to_target_without_skipping_actions():
    from app.services.scenario_debug import ScenarioDebugSession
    session = ScenarioDebugSession()
    session.pause()
    completed = []
    observed = []
    session._on_update = lambda update: observed.append(update.step_index)

    def execute():
        for index in range(4):
            decision = session.before_step(scenario_name="test", account_name="profile", step_index=index,
                                           total_steps=4, action="python", description="", tag="")
            if decision.stop:
                break
            completed.append(index)

    def wait_for(predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            time.sleep(.01)
        assert predicate()

    thread = threading.Thread(target=execute)
    thread.start()
    try:
        wait_for(lambda: observed == [0])
        session.run_until("test", 2)
        wait_for(lambda: observed == [0, 1, 2])
        assert completed == [0, 1]
        assert session.paused
        session.step_once()
        wait_for(lambda: observed == [0, 1, 2, 3])
        assert completed == [0, 1, 2]
    finally:
        session.request_stop()
        thread.join(3)
    assert not thread.is_alive()


def test_shared_pool_pop_is_atomic_between_jobs():
    from concurrent.futures import ThreadPoolExecutor
    from app.core.shared_vars import SharedVarsManager
    manager = SharedVarsManager()
    manager.set("pool", "\n".join(str(i) for i in range(100)))
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: manager.pop_first("pool")[0], range(100)))
    assert len(set(values)) == 100
    assert manager.get("pool") == ""
