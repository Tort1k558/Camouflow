"""Recorder keeps frame identity and secrets scoped to the captured document."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.services.scenario_recorder import ScenarioRecorder
from app.ui.bridge.recorder import RecorderBridge


def recording():
    recorder = ScenarioRecorder()
    recorder.active = True
    recorder.page = SimpleNamespace(main_frame=object())
    return recorder


def test_same_selector_in_different_frames_is_not_coalesced():
    recorder = recording()
    source = {"page": recorder.page, "frame": object()}
    payload = {"action": "type", "selector": "#field", "value": "first"}
    recorder.receive(source, payload, frame_selectors=['iframe[id="first"]'])
    recorder.receive(source, {**payload, "value": "second"}, frame_selectors=['iframe[id="second"]'])
    recorder.receive(source, {**payload, "value": "edited"}, frame_selectors=['iframe[id="second"]'])
    assert len(recorder.steps) == 3
    assert recorder.steps[1]["value"] == "first"
    assert recorder.steps[2]["value"] == "edited"
    assert recorder.steps[1]["frame_selector"] != recorder.steps[2]["frame_selector"]


def test_sensitive_variables_are_distinct_in_different_frames():
    recorder = recording()
    source = {"page": recorder.page, "frame": object()}
    payload = {"action": "type", "selector": "#code", "value": "NEVER_STORE", "sensitive": True}
    recorder.receive(source, payload, frame_selectors=["#first"])
    recorder.receive(source, payload, frame_selectors=["#second"])
    assert recorder.steps[1]["required_variable"] != recorder.steps[2]["required_variable"]
    assert "NEVER_STORE" not in str(recorder.snapshot())


def test_nested_frame_binding_derives_scope_from_browser_not_payload():
    recorder = recording()
    outer = SimpleNamespace(parent_frame=recorder.page.main_frame, frame_element=AsyncMock(return_value=SimpleNamespace(evaluate=AsyncMock(return_value="#outer"))))
    inner = SimpleNamespace(parent_frame=outer, frame_element=AsyncMock(return_value=SimpleNamespace(evaluate=AsyncMock(return_value="#inner"))))
    asyncio.run(recorder._receive_event({"page": recorder.page, "frame": inner}, {"action": "click", "selector": "#button", "frame_selector": ["#forged"]}))
    assert recorder.steps[1]["frame_selector"] == ["#outer", "#inner"]


def test_unidentifiable_frame_action_is_skipped_with_warning():
    recorder = recording()
    frame = SimpleNamespace(parent_frame=recorder.page.main_frame, frame_element=AsyncMock(return_value=SimpleNamespace(evaluate=AsyncMock(return_value=""))))
    asyncio.run(recorder._receive_event({"page": recorder.page, "frame": frame}, {"action": "click", "selector": "#button"}))
    assert len(recorder.steps) == 1
    assert "unique stable" in recorder.warnings[0]


def test_detached_frame_does_not_record_action_in_parent_document():
    recorder = recording()
    frame = SimpleNamespace(frame_element=AsyncMock(side_effect=RuntimeError("detached")))
    asyncio.run(recorder._receive_event({"page": recorder.page, "frame": frame}, {"action": "click", "selector": "#button"}))
    assert len(recorder.steps) == 1
    assert "detached" in recorder.warnings[0]


def test_camoufox_is_available_to_recorder_ui():
    profiles = SimpleNamespace(_cached_account=Mock(return_value={"name": "QA", "browser_engine": "camoufox"}), actionState=Mock(return_value={"startAllowed": True}))
    bridge = SimpleNamespace(operations=SimpleNamespace(profiles=profiles))
    assert RecorderBridge.recordingIssue(bridge, "QA") == ""


def test_recorder_still_requires_profile_start_permission():
    profiles = SimpleNamespace(_cached_account=Mock(return_value={"name": "QA", "browser_engine": "camoufox"}), actionState=Mock(return_value={"startAllowed": False}))
    bridge = SimpleNamespace(operations=SimpleNamespace(profiles=profiles))
    assert "permission" in RecorderBridge.recordingIssue(bridge, "QA")


def test_navigated_child_document_is_instrumented():
    recorder = recording()
    frame = SimpleNamespace(evaluate=AsyncMock())
    asyncio.run(recorder._frame_navigated(frame))
    frame.evaluate.assert_awaited_once()
    assert recorder.steps == [{"action": "start", "tag": "Start"}]


def test_failed_frame_instrumentation_is_visible():
    recorder = recording()
    frame = SimpleNamespace(evaluate=AsyncMock(side_effect=RuntimeError("detached")))
    asyncio.run(recorder._frame_navigated(frame))
    assert "could not be instrumented" in recorder.warnings[0]


def test_frame_lookup_does_not_reorder_browser_events():
    recorder = recording()
    async def verify():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def frame_element():
            entered.set()
            await release.wait()
            return SimpleNamespace(evaluate=AsyncMock(return_value="#frame"))
        frame = SimpleNamespace(parent_frame=recorder.page.main_frame, frame_element=frame_element)
        first = asyncio.create_task(recorder._receive_event({"page": recorder.page, "frame": frame}, {"action": "type", "selector": "#field", "value": "first"}))
        await entered.wait()
        second = asyncio.create_task(recorder._receive_event({"page": recorder.page, "frame": recorder.page.main_frame}, {"action": "click", "selector": "#save"}))
        release.set()
        await asyncio.gather(first, second)
    asyncio.run(verify())
    assert [step["action"] for step in recorder.steps] == ["start", "type", "click"]
