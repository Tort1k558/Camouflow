"""Recorder keeps frame identity and secrets scoped to the captured document."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

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


@pytest.mark.parametrize("engine", ["camoufox", "native"])
def test_supported_engine_is_available_to_recorder_ui(engine):
    profiles = SimpleNamespace(_cached_account=Mock(return_value={"name": "QA", "browser_engine": engine}), actionState=Mock(return_value={"startAllowed": True}))
    bridge = SimpleNamespace(operations=SimpleNamespace(profiles=profiles))
    assert RecorderBridge.recordingIssue(bridge, "QA") == ""


@pytest.mark.parametrize("engine", ["cloakbrowser", "unknown"])
def test_unsupported_recorder_engine_is_explicit(engine):
    profiles = SimpleNamespace(_cached_account=Mock(return_value={"name": "QA", "browser_engine": engine}))
    bridge = SimpleNamespace(operations=SimpleNamespace(profiles=profiles))
    assert "does not support recording" in RecorderBridge.recordingIssue(bridge, "QA")


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


def test_script_rebinds_cleared_document_listeners_without_duplicate_events_or_losing_flush():
    from pathlib import Path
    import subprocess
    import sys

    import playwright
    from app.services.scenario_recorder import RECORDER_SCRIPT

    node = Path(playwright.__file__).parent / "driver" / ("node.exe" if sys.platform == "win32" else "node")
    model = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const script = require('node:fs').readFileSync(0, 'utf8');
const button = {
  tagName: 'BUTTON',
  getAttribute: name => name === 'id' ? 'probe' : null,
  closest: selector => selector === 'label' ? null : button,
  matches: () => false,
};
function documentModel() {
  return {
    listeners: new Map(), querySelectorAll: () => [button],
    addEventListener(name, listener, options) {
      assert.equal(options.capture, true);
      assert(options.signal instanceof AbortSignal);
      if (!this.listeners.has(name)) this.listeners.set(name, new Set());
      this.listeners.get(name).add(listener);
      options.signal.addEventListener('abort', () => this.listeners.get(name)?.delete(listener), {once: true});
    },
  };
}
const window = {};
const resolvers = [];
window.__camouflowRecord = payload => {
  assert.equal(payload.action, 'click');
  return new Promise(resolve => resolvers.push(resolve));
};
const environment = {window, document: documentModel(), AbortController, Set, performance: {now: () => 0}};
const inject = () => vm.runInNewContext(script, environment);
const click = () => {
  for (const listener of environment.document.listeners.get('click') || [])
    listener({isTrusted: true, button: 0, detail: 1, target: button});
};
const drain = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  inject();
  click();
  const pending = window.__camouflowRecorderState.pending;
  assert.equal(pending.size, 1);
  inject();
  assert.equal(window.__camouflowRecorderState.pending, pending);
  assert.equal(environment.document.listeners.get('click').size, 1);
  let stopped = false;
  const stop = window.__camouflowStopRecording().then(value => {stopped = true; assert.equal(value, false);});
  await drain();
  assert.equal(stopped, false, 'reinjection must retain the in-flight flush');
  resolvers.shift()();
  await stop;
  assert.equal(pending.size, 0);
  environment.document.listeners.clear(); // document.open clears listeners, not document identity.
  inject();
  assert.equal(environment.document.listeners.size, 4);
  click();
  assert.equal(resolvers.length, 1, 'one click must produce exactly one binding call');
  resolvers.shift()();
  await drain();
  const oldDocument = environment.document;
  environment.document = documentModel();
  inject();
  assert.notEqual(window.__camouflowRecorderState.pending, pending);
  assert([...oldDocument.listeners.values()].every(listeners => listeners.size === 0));
  assert.equal(await window.__camouflowStopRecording(), false);
  click();
  assert.equal(resolvers.length, 0, 'stopped recording must ignore clicks');
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    subprocess.run([str(node), "-e", model], input=RECORDER_SCRIPT, text=True, capture_output=True, check=True, timeout=15)


def test_document_open_repair_does_not_admit_failing_bfcache_binding_flush():
    import hashlib
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    folder = root / "native/drafts/environment"
    record = json.loads((folder / "recorder-document-open70-observations.json").read_bytes())
    source = (root / "app/services/scenario_recorder.py").read_text(encoding="utf-8-sig").encode("utf-8")
    assert hashlib.sha256(source).hexdigest() == record["source_after_normalized_utf8_lf_sha256"]
    assert hashlib.sha256((folder / record["patch"]).read_bytes()).hexdigest() == record["patch_sha256"]
    fixed, old, history = (record["controls"][key] for key in ("fixed_no_bfcache", "original_no_bfcache", "fixed_with_bfcache"))
    assert fixed["passed"] and fixed["measurement_complete"] and fixed["postguards_passed"]
    assert fixed["attached_before_initial_navigation"] and fixed["recorded_clicks"] == 6
    assert fixed["warnings"] == [] and fixed["replay_passed"]
    assert fixed["replay_click_counts"] == {role: 1 for role in ("main", "same", "cross", "srcdoc", "about-blank", "nested-return")}
    assert old["passed"] is False and old["recorded_clicks"] == 5 and old["postguards_passed"]
    assert history["passed"] is False and history["history_navigation_type"] == "BackForwardCacheRestore"
    assert history["recorded_clicks"] == 9 and history["warnings"] and history["replay_passed"] is False
    assert history["pending_counts"] == {role: int(role == "main") for role in fixed["replay_click_counts"]}
    full = record["full_runtime_regression"]
    assert full["passed"] and full["measurement_complete"] and full["source_unchanged"] and full["core_unchanged"]
    assert len(full["checks"]) == 18 and "existing-recorder-capture-and-replay" in full["checks"]
    assert all(record[name] is False for name in ("history_recorded_draft_replay_verified", "manager_bfcache_default_changed", "production_admitted", "privacy_admitted"))
