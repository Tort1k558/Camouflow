import asyncio
import copy
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.ai_agent.llm import LLMConfig
from app.services.scenario_definition import definition_hash
from app.services.scenario_engine import ScenarioExecutor
from app.storage import db
from app.ui.bridge.operations import OperationsBridge


@pytest.fixture
def engine(monkeypatch, tmp_path):
    values = {"ai_enabled": "true", "ai_selector_repair_enabled": "true"}
    monkeypatch.setattr("app.services.scenario_engine.db_get_setting", values.get)
    monkeypatch.setattr("app.services.ai_agent.llm.configured_llm_config", lambda **kwargs: LLMConfig("https://provider.test", "", "test"))
    proposal = AsyncMock(return_value={"verified": True, "replacement_selector": "#new"})
    monkeypatch.setattr("app.services.selector_repair.propose_selector_repair", proposal)
    runner = SimpleNamespace(account_payload={}, scenario=SimpleNamespace(name="QA"), _run_artifact_dir=tmp_path, _cancel_event=threading.Event(), logger=Mock())
    return runner, proposal, values, tmp_path


def invoke_engine(runner):
    return asyncio.run(ScenarioExecutor._maybe_propose_selector_repair(runner, [{"action": "click", "selector": "#old"}], "QA", 0))


def test_enabled_proposal_is_written_without_repeating_or_saving(engine):
    runner, proposal, _, path = engine
    invoke_engine(runner)
    proposal.assert_awaited_once()
    payload = json.loads((path / "selector-repair.json").read_text(encoding="utf-8"))
    assert payload["status"] == "awaiting_confirmation"
    assert payload["scenario"] == "QA"


@pytest.mark.parametrize("flag", ["ai_enabled", "ai_selector_repair_enabled"])
def test_either_disabled_flag_prevents_provider_calls(engine, flag):
    runner, proposal, values, path = engine
    values[flag] = "false"
    invoke_engine(runner)
    proposal.assert_not_awaited()
    assert not (path / "selector-repair.json").exists()


def test_cloud_and_nested_definitions_are_not_silently_repaired(engine):
    runner, proposal, _, _ = engine
    runner.account_payload["_storage_scope"] = {"team": "owned"}
    invoke_engine(runner)
    runner.account_payload.clear()
    runner.scenario.name = "different root"
    invoke_engine(runner)
    proposal.assert_not_awaited()


def test_provider_error_does_not_replace_the_original_failure(engine):
    runner, proposal, _, path = engine
    proposal.side_effect = RuntimeError("PRIVATE_PROVIDER_ERROR")
    invoke_engine(runner)
    payload = json.loads((path / "selector-repair.json").read_text(encoding="utf-8"))
    assert payload == {"status": "unavailable", "error_type": "RuntimeError"}


def test_cancellation_stops_proposal_and_does_not_save_it(engine):
    runner, proposal, _, path = engine
    stopped = []
    async def verify():
        started = asyncio.Event()
        async def delayed(*args):
            started.set()
            try:
                await asyncio.sleep(30)
            finally:
                stopped.append(True)
        proposal.side_effect = delayed
        task = asyncio.create_task(ScenarioExecutor._maybe_propose_selector_repair(runner, [{"action": "click"}], "QA", 0))
        await started.wait()
        runner._cancel_event.set()
        await asyncio.wait_for(task, 2)
    asyncio.run(verify())
    assert stopped == [True]
    assert not (path / "selector-repair.json").exists()


@pytest.fixture
def approval(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr("app.ui.bridge.operations.get_server_session", lambda: SimpleNamespace(enabled=False))
    steps = [{"action": "start", "tag": "Start"}, {"action": "click", "selector": "#old", "tag": "Click"}]
    current = db.Scenario("QA", copy.deepcopy(steps), "Description")
    saves = []
    monkeypatch.setattr(db, "db_get_scenario", lambda name: current if name == "QA" else None)
    monkeypatch.setattr(db, "db_save_scenario", lambda *args: saves.append(args))
    proposal = {"schema_version": 1, "status": "awaiting_confirmation", "scenario": "QA", "step_index": 1, "original_selector": "#old", "replacement_selector": "#new", "verified_page": "https://example.test/", "definition_hash": definition_hash(steps), "verified": True}
    (tmp_path / "selector-repair.json").write_text(json.dumps(proposal), encoding="utf-8")
    job = {"id": "owned", "status": "failed", "scenario": "QA", "workspace": "local", "artifacts": str(tmp_path)}
    scenarios = SimpleNamespace(_ensure_allowed=Mock(return_value=True), _run_cancel_event=None, selectedName="QA", _current_steps=copy.deepcopy(steps), _set_selected=Mock(), scenarioSaved=Mock(), refresh=Mock())
    bridge = SimpleNamespace(scenarios=scenarios, queue=SimpleNamespace(snapshot=lambda: []), _pending_selector_repair=None, _selector_repair=proposal, _editor_drafts_present=False, _workspace=lambda: "local", _find_run=lambda ident: job if ident == "owned" else None, _notify=Mock(), selectorRepairApprovalRequested=Mock(), changed=Mock())
    bridge._artifact_directory = OperationsBridge._artifact_directory
    bridge._read_selector_repair = lambda row: OperationsBridge._read_selector_repair(bridge, row)
    return bridge, current, saves, tmp_path


def test_rejecting_confirmation_does_not_save(approval):
    bridge, _, saves, _ = approval
    OperationsBridge.requestSelectorRepair(bridge, "owned")
    bridge.selectorRepairApprovalRequested.emit.assert_called_once()
    OperationsBridge.approveSelectorRepair(bridge, False)
    assert saves == []
    assert bridge._pending_selector_repair is None


def test_confirmation_saves_only_patch_and_marks_receipt(approval):
    bridge, current, saves, path = approval
    OperationsBridge.requestSelectorRepair(bridge, "owned")
    OperationsBridge.approveSelectorRepair(bridge, True)
    assert len(saves) == 1
    assert saves[0][0] == "QA"
    assert saves[0][1][1]["selector"] == "#new"
    assert current.steps[1]["selector"] == "#old"
    assert json.loads((path / "selector-repair.json").read_text())["status"] == "saved"
    assert bridge._read_selector_repair(bridge._find_run("owned")) is None


@pytest.mark.parametrize("change", ["workspace", "definition", "unsaved", "active", "editor_fields"])
def test_state_changes_between_review_and_approval_prevent_saving(approval, change):
    bridge, current, saves, _ = approval
    OperationsBridge.requestSelectorRepair(bridge, "owned")
    if change == "workspace": bridge._workspace = lambda: "different"
    elif change == "definition": current.steps[1]["selector"] = "#edited"
    elif change == "unsaved": bridge.scenarios._current_steps[1]["selector"] = "#draft"
    elif change == "editor_fields": bridge._editor_drafts_present = True
    else: bridge.scenarios._run_cancel_event = threading.Event()
    OperationsBridge.approveSelectorRepair(bridge, True)
    assert saves == []
    bridge._notify.assert_called()


def test_malformed_artifact_does_not_open_confirmation(approval):
    bridge, _, saves, path = approval
    (path / "selector-repair.json").write_text('[]', encoding="utf-8")
    OperationsBridge.requestSelectorRepair(bridge, "owned")
    bridge.selectorRepairApprovalRequested.emit.assert_not_called()
    assert saves == []


def test_stale_proposal_is_rejected_before_review(approval):
    bridge, current, saves, _ = approval
    current.steps[1]["selector"] = "#new-version"
    OperationsBridge.requestSelectorRepair(bridge, "owned")
    bridge.selectorRepairApprovalRequested.emit.assert_not_called()
    assert saves == []


def test_unsaved_editor_fields_block_review(approval):
    bridge, _, saves, _ = approval
    OperationsBridge.setEditorDraftsPresent(bridge, True)
    OperationsBridge.requestSelectorRepair(bridge, "owned")
    bridge.selectorRepairApprovalRequested.emit.assert_not_called()
    assert saves == []
