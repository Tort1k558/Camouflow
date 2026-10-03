import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.run_history import RunHistory
from app.services.scenario_engine import ScenarioExecutor
from app.services.steps.data import DataSteps
from app.services.task_inputs import configure_task_run, csv_rows, csv_template
from app.storage.db import Scenario
from app.ui.bridge.operations import OperationsBridge

STEPS = [{"action": "start", "_required_inputs": ["period", "url"]}]


def test_csv_import_preserves_bom_unicode_quotes_and_duplicate_identity():
    rows = csv_rows(STEPS, '\ufeffurl;period\r\nhttps://a;"Oct;Nov"\r\nhttps://a;"Oct;Nov"\r\nhttps://b;December\r\n'.encode("utf-8"), ";")
    assert [row["duplicate_of"] for row in rows] == [0, 1, 0]
    assert rows[0]["inputs"] == {"url": "https://a", "period": "Oct;Nov"}
    assert csv_template(STEPS) == "period,url\r\n"


@pytest.mark.parametrize("payload", [b"period,url\n", b"url,url\na,b\n", b"period,url\na\n",
                                    b"period,url\na,b,c\n", b"period,url\n ,b\n", b"period,url\na,\xff\n",
                                    b'period,url\n"unterminated,b', b"x" * (1024 * 1024 + 1),
                                    b"period,url\n" + b"a,b\n" * 201],
                         ids=["empty", "headers", "short", "wide", "blank", "encoding", "quotes", "size", "rows"])
def test_csv_errors_reject_the_entire_import(payload):
    with pytest.raises(ValueError):
        csv_rows(STEPS, payload)


def test_batch_queue_snapshots_rows_and_rejects_partial_invalid_imports():
    scenario = Scenario("Report", STEPS, "")
    bridge = SimpleNamespace(scenarios=SimpleNamespace(_ensure_allowed=lambda role: True,
        _get_scenario=lambda name: scenario, _validate_scenario=lambda item: "", _list_scenarios=lambda: [scenario]),
        _names=OperationsBridge._names, _accounts=lambda: [{"name": "Company"}], _workspace=lambda: "local",
        _debug_enabled=False, queue=Mock(), _notify=Mock())
    rows = csv_rows(STEPS, b"period,url\na,b\nc,d\n")
    assert OperationsBridge._enqueue(bridge, "Company", "Report", "", "unchanged", "", batch_rows=rows)
    specs, _ = bridge.queue.enqueue.call_args.args
    assert len(specs) == 2
    assert specs[0]["batch_id"] == specs[1]["batch_id"]
    assert [spec["batch_row"] for spec in specs] == [1, 2]
    assert specs[0]["steps"] is not scenario.steps
    bridge.queue.enqueue.reset_mock()
    rows[1]["inputs"] = {}
    assert not OperationsBridge._enqueue(bridge, "Company", "Report", "", "unchanged", "", batch_rows=rows)
    bridge.queue.enqueue.assert_not_called()


def test_retry_keeps_task_inputs_and_batch_metadata():
    job = {"id": "original", "status": "failed", "workspace": "local", "profile": "Company",
           "scenario": "Report", "steps": STEPS, "inputs": {"period": "November", "url": "https://a"},
           "debug": False, "batch_id": "a" * 32, "batch_row": 2, "batch_size": 3}
    bridge = SimpleNamespace(queue=Mock(), _workspace=lambda: "local", _notify=Mock(),
                             scenarios=SimpleNamespace(_ensure_allowed=lambda role: True))
    bridge.queue.snapshot.return_value = [job]
    OperationsBridge.retry(bridge, "original")
    retry = bridge.queue.enqueue.call_args.args[0][0]
    assert retry["inputs"] == job["inputs"]
    assert retry["batch_row"] == 2
    assert "id" not in retry


def test_task_inputs_do_not_erase_existing_profile_defaults(tmp_path):
    import json

    path = tmp_path / "variables.json"
    path.write_text('{"period": "October"}', encoding="utf-8")
    runner = SimpleNamespace(_profile_vars_path=path, variables={"period": "November", "result": "new"},
                             _transient_inputs={"period": "November"}, logger=Mock())
    asyncio.run(ScenarioExecutor._persist_profile_vars(runner))
    assert json.loads(path.read_text(encoding="utf-8")) == {"period": "October", "result": "new"}


def test_batch_outputs_are_isolated_including_retries_and_history(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.steps.data.OUTPUTS_DIR", tmp_path)
    for identity, value in (("b" * 32, "November"), ("c" * 32, "December")):
        job = {"id": identity, "batch_id": "a" * 32, "batch_row": 1, "batch_size": 2,
               "steps": STEPS, "inputs": {"period": value, "url": "https://a"}}
        runner = SimpleNamespace(variables={}, _apply_template=lambda text: text)
        configure_task_run(runner, job, tmp_path)
        result = asyncio.run(DataSteps._action_write_file(runner, {"filename": "report.txt", "value": value}))
        assert result.status == "next"
        assert (runner._output_directory / "report.txt").read_text(encoding="utf-8").strip() == value
        escape = asyncio.run(DataSteps._action_write_file(runner, {"filename": "../other.txt", "value": value}))
        assert escape.status == "stop"
        history = RunHistory._public_row(job)
        assert history["batch_id"] == job["batch_id"]
        assert "inputs" not in history
    assert len(list(tmp_path.rglob("report.txt"))) == 2
