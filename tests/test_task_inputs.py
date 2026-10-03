"""Task forms preserve scenario definitions and require explicit run inputs."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.scenario_engine import ScenarioExecutor
from app.services.task_inputs import (
    input_fields,
    prepare_recording,
    recording_candidates,
    validate_inputs,
)
from app.ui.bridge.operations import OperationsBridge


def recording():
    return [{"action": "start", "tag": "Start"},
            {"action": "goto", "url": "https://example.test", "value": "https://example.test", "tag": "Step1"},
            {"action": "type", "selector": "#period", "value": "October", "field_label": "Period", "tag": "Step2"},
            {"action": "type", "selector": "#password", "value": "{{password}}", "required_variable": "password", "tag": "Step3"}]


def test_recording_becomes_a_task_without_changing_the_draft():
    steps = recording()
    original = copy.deepcopy(steps)
    result = prepare_recording(steps, [{"name": "period", "label": "Период отчёта", "value": "October"}])
    assert steps == original
    assert result[2]["value"] == "{{period}}"
    assert result[3] == original[3]
    assert input_fields(result) == [{"name": "period", "label": "Период отчёта", "value": ""}]
    assert [field["value"] for field in recording_candidates(steps)] == ["https://example.test", "October"]
    assert validate_inputs(result, {"period": "November"}) == {"period": "November"}


@pytest.mark.parametrize("fields", [
    [{"name": "name", "label": "Name", "value": "October"}],
    [{"name": "bad-name", "label": "Period", "value": "October"}],
    [{"name": "period", "label": "", "value": "October"}],
    [{"name": "period", "label": "Period", "value": "Not recorded"}],
    [{"name": "password", "label": "Secret", "value": "{{password}}"}],
    [{"name": "period", "label": "Period", "value": "October"}] * 2,
])
def test_invalid_recorded_inputs_are_rejected(fields):
    with pytest.raises(ValueError):
        prepare_recording(recording(), fields)


@pytest.mark.parametrize("values", [{}, {"period": ""}, {"period": " "}, {"period": 3},
                                  {"period": "x" * 10001}, {"period": "November", "extra": "x"}])
def test_run_inputs_must_exactly_match_the_form(values):
    steps = prepare_recording(recording(), [{"name": "period", "label": "Period", "value": "October"}])
    with pytest.raises(ValueError):
        validate_inputs(steps, values)


@pytest.mark.parametrize("names", [["timestamp"], ["input", "input"], [None], "period", ["bad-name"]])
def test_invalid_imported_forms_are_rejected(names):
    with pytest.raises(ValueError):
        input_fields([{"action": "start", "_required_inputs": names}])


def test_inputs_are_queued_without_mutating_scenarios_or_profiles():
    from app.storage.db import Scenario

    steps = prepare_recording(recording(), [{"name": "period", "label": "Period", "value": "October"}])
    scenario = Scenario("Monthly report", steps, "")
    scenarios = SimpleNamespace(_ensure_allowed=lambda role: True, _get_scenario=lambda name: scenario,
                                _validate_scenario=lambda item: "", _list_scenarios=lambda: [scenario])
    account = {"name": "Company"}
    bridge = SimpleNamespace(scenarios=scenarios, _names=OperationsBridge._names, _accounts=lambda: [account],
                             _workspace=lambda: "local", _debug_enabled=False, queue=Mock(), _notify=Mock())
    assert OperationsBridge._enqueue(bridge, "Company", scenario.name, "", "unchanged", "", {"period": "November"})
    specs, _ = bridge.queue.enqueue.call_args.args
    assert specs[0]["inputs"] == {"period": "November"}
    assert scenario.steps[2]["value"] == "{{period}}"
    assert account == {"name": "Company"}
    bridge.queue.enqueue.reset_mock()
    assert not OperationsBridge._enqueue(bridge, "Company", scenario.name, "", "unchanged", "", {})
    bridge.queue.enqueue.assert_not_called()


def test_run_inputs_are_not_persisted_as_profile_defaults(tmp_path):
    runner = SimpleNamespace(_profile_vars_path=tmp_path / "variables.json", variables={"period": "November", "other": "keep"},
                             _transient_inputs={"period": "November"}, logger=Mock())
    asyncio.run(ScenarioExecutor._persist_profile_vars(runner))
    assert json.loads(runner._profile_vars_path.read_text(encoding="utf-8")) == {"other": "keep"}


def test_unrecorded_frames_produce_a_warning_even_without_delivered_events():
    from app.services.scenario_recorder import ScenarioRecorder

    recorder = ScenarioRecorder()
    recorder.active = True
    recorder.page = SimpleNamespace(main_frame=object())
    recorder.navigated(object())
    recorder.navigated(object())
    assert len(recorder.warnings) == 1
    assert "frame" in recorder.warnings[0]
    assert len(recorder.steps) == 1


def test_cloakbrowser_humanized_typing_requires_an_explicit_viewport():
    from app.core.browser_interface import BrowserInterface

    browser = SimpleNamespace(_browser_settings={"humanize": True}, browser_engine="cloakbrowser",
                              page=SimpleNamespace(viewport_size=None))
    element = Mock()
    with pytest.raises(RuntimeError, match="Set both window width and height"):
        asyncio.run(BrowserInterface._human_type(browser, element, "November"))
    element.fill.assert_not_called()
