"""Invalid persisted AI transcripts must not partially replace the current UI."""

import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.ui.bridge import ai


@pytest.fixture
def history_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "DATA_ROOT", tmp_path)
    session = SimpleNamespace(enabled=False)
    monkeypatch.setattr(ai, "get_server_session", lambda: session)
    state = SimpleNamespace(notify=Mock())
    bridge = ai.AIBridge(Mock(), Mock(), state)
    bridge._task, bridge._profile_name, bridge._outcome = "Previous task", "previous", "previous"
    bridge._session = session
    bridge._outputs = {"previous": "retained"}
    bridge._sources = {"previous": "https://example.invalid"}
    folder = tmp_path / "outputs" / "ai-runs" / "synthetic-history"
    folder.mkdir(parents=True)
    bridge._history = Mock()
    bridge._history.get.return_value = {
        "id": "synthetic-history", "workspace": bridge._history_workspace(),
        "profile": "synthetic", "artifacts": str(folder),
    }
    payload = {"task": "Restored task", "status": "success", "result": "Synthetic result",
               "steps": [{"action": "start"}], "outputs": {}, "output_sources": {}, "events": []}
    return bridge, payload, folder / "transcript.json"


def snapshot(bridge):
    return copy.deepcopy({key: getattr(bridge, key) for key in (
        "_task", "_profile_name", "_outcome", "_result_text", "_draft_steps", "_secrets",
        "_outputs", "_sources", "_usage", "_artifacts", "_rows", "_status",
    )})


@pytest.mark.parametrize("field,value", [
    ("task", None), ("status", None), ("result", {}), ("secrets", None),
    ("output_sources", []), ("events", [None]), ("events", [{"step": "invalid"}]),
    ("requests", "invalid"), ("prompt_tokens", -1), ("completion_tokens", True),
])
def test_invalid_transcript_preserves_current_state(history_restore, field, value):
    bridge, payload, path = history_restore
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = snapshot(bridge)
    previous_session = bridge._session
    bridge.loadRun("synthetic-history")
    assert snapshot(bridge) == before
    assert bridge._session is previous_session
    bridge.state.notify.assert_called_once()
    bridge._history.record.assert_not_called()


def test_valid_transcript_normalizes_history_event_roles(history_restore):
    bridge, payload, path = history_restore
    payload["events"] = [{"type": "action", "step": 1, "action": {"name": "goto"}}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    bridge.loadRun("synthetic-history")
    assert bridge._task == "Restored task" and bridge._outcome == "success"
    assert bridge._rows == [{"type": "action", "step": 1, "text": "", "action": "{'name': 'goto'}", "url": ""}]
    bridge.state.notify.assert_not_called()
    bridge._history.record.assert_not_called()
