"""Local run history tests; no browser required."""

import time

import pytest

from app.services.run_history import RunHistory
from app.services.run_queue import RunQueue


def test_run_history_records_bounded_public_rows(tmp_path):
    history = RunHistory(tmp_path / "history.json", limit=2)
    history.record({
        "id": "1",
        "workspace": "local",
        "scenario": "old",
        "profile": "p1",
        "status": "success",
        "finished": 1,
        "steps": [{"secret": "not stored"}],
        "library": {"x": {}},
    })
    history.record({"id": "2", "workspace": "other", "scenario": "skip", "profile": "p2", "status": "failed", "finished": 2})
    history.record({"id": "3", "workspace": "local", "scenario": "new", "profile": "p3", "status": "failed", "finished": 3})

    reloaded = RunHistory(tmp_path / "history.json", limit=2)
    rows = reloaded.list("local")
    assert [row["id"] for row in rows] == ["3"]
    assert "steps" not in rows[0]
    assert reloaded.get("3")["scenario"] == "new"


def test_queue_persists_finished_job_to_history(tmp_path):
    history = RunHistory(tmp_path / "history.json")

    def runner(job, cancel):
        assert not cancel.is_set()
        return {"status": "success", "error": "", "artifacts": str(tmp_path / "artifacts")}

    queue = RunQueue(tmp_path / "queue.json", runner, finished=history.record)
    queue.configure(1, False)
    queue.enqueue([{"workspace": "local", "profile": "p1", "scenario": "s1"}], time.time() - 1)
    queue.tick("local")

    deadline = time.monotonic() + 3
    while not history.list("local") and time.monotonic() < deadline:
        time.sleep(0.01)

    rows = history.list("local")
    assert len(rows) == 1
    assert rows[0]["status"] == "success"
    assert rows[0]["artifacts"].endswith("artifacts")


def test_queue_records_interrupted_running_job_on_load(tmp_path):
    recorded = []
    path = tmp_path / "queue.json"
    queue = RunQueue(path, lambda job, cancel: {"status": "success"})
    queue.enqueue([{"workspace": "local", "profile": "p1", "scenario": "s1"}], time.time() - 1)
    queue.jobs[0].update(status="running", started=time.time())
    queue._save()

    RunQueue(path, lambda job, cancel: {"status": "success"}, finished=recorded.append)

    assert recorded
    assert recorded[0]["status"] == "interrupted"
    assert isinstance(recorded[0]["finished"], float)


@pytest.mark.parametrize("cancel_all", [False, True])
def test_pending_cancellation_survives_queue_cleanup(tmp_path, cancel_all):
    history = RunHistory(tmp_path / "history.json")
    recorded = []

    def record(job):
        recorded.append(job)
        history.record(job)

    queue = RunQueue(tmp_path / "queue.json", lambda job, cancel: {}, finished=record)
    for workspace in ("local", "other"):
        queue.enqueue([{"workspace": workspace, "profile": "p1", "scenario": "s1"}], time.time())
    job_id = queue.snapshot()[0]["id"]
    queue.cancel("" if cancel_all else job_id, workspace="local")
    queue.cancel("" if cancel_all else job_id, workspace="local")
    queue.clear_finished("local")

    assert len(recorded) == 1
    assert recorded[0]["status"] == "canceled"
    assert recorded[0]["started"] == 0
    assert recorded[0]["finished"] > 0
    assert recorded[0]["id"] == job_id
    assert [job["workspace"] for job in queue.snapshot()] == ["other"]
    assert queue.snapshot()[0]["status"] == "queued"
    rows = RunHistory(history.path).list("local")
    assert len(rows) == 1
    assert rows[0]["id"] == job_id
    assert rows[0]["status"] == "canceled"


def test_running_cancellation_records_only_after_worker_finishes(tmp_path):
    import threading

    started = threading.Event()
    release = threading.Event()
    recorded = []
    finished = threading.Event()

    def runner(job, cancel):
        started.set()
        assert release.wait(3)
        assert cancel.is_set()
        return {"status": "success"}

    def record(job):
        recorded.append(job)
        finished.set()

    queue = RunQueue(tmp_path / "queue.json", runner, finished=record)
    queue.enqueue([{"workspace": "local", "profile": "p1", "scenario": "s1"}], time.time())
    queue.configure(1, False)
    queue.tick("local")
    try:
        assert started.wait(3)
        queue.cancel(workspace="local")
        assert not recorded
        assert queue.snapshot()[0]["status"] == "running"
        release.set()
        assert finished.wait(3)
        assert len(recorded) == 1
        assert recorded[0]["status"] == "canceled"
    finally:
        release.set()
        queue.shutdown()


def test_failed_start_save_does_not_reserve_a_profile(tmp_path, monkeypatch):
    from unittest.mock import Mock

    runner = Mock()
    queue = RunQueue(tmp_path / "queue.json", runner)
    queue.enqueue([{"workspace": "local", "profile": "p1", "scenario": "s1"}], time.time())
    queue.configure(1, False)
    original_jobs = queue.snapshot()
    original_file = queue.path.read_bytes()
    monkeypatch.setattr(queue, "_save", Mock(side_effect=OSError("synthetic disk full")))

    with pytest.raises(OSError):
        queue.tick("local")

    assert queue.paused
    assert queue.snapshot() == original_jobs
    assert queue.path.read_bytes() == original_file
    assert not queue._active
    assert not queue._workers
    runner.assert_not_called()


@pytest.mark.parametrize("operation", ["enqueue", "configure", "clear_finished"])
def test_failed_queue_write_restores_in_memory_state(tmp_path, monkeypatch, operation):
    from unittest.mock import Mock

    queue = RunQueue(tmp_path / "queue.json", lambda job, cancel: {})
    spec = {"workspace": "local", "profile": "p1", "scenario": "s1"}
    queue.enqueue([spec], time.time())
    queue.cancel(workspace="local")
    original_jobs = queue.snapshot()
    original_file = queue.path.read_bytes()
    monkeypatch.setattr(queue, "_save", Mock(side_effect=OSError("synthetic disk full")))

    with pytest.raises(OSError):
        if operation == "enqueue":
            queue.enqueue([spec], time.time())
        elif operation == "configure":
            queue.configure(8, False)
        else:
            queue.clear_finished("local")

    assert queue.snapshot() == original_jobs
    assert queue.path.read_bytes() == original_file
    assert queue.parallelism == 1
    assert queue.paused


def test_failed_completion_save_still_records_history(tmp_path, monkeypatch, caplog):
    from unittest.mock import Mock

    history = RunHistory(tmp_path / "history.json")
    queue = RunQueue(tmp_path / "queue.json", lambda job, event: {"status": "success"}, finished=history.record)
    queue.enqueue([{"workspace": "local", "profile": "p1", "scenario": "s1"}], time.time())
    queue.configure(1, False)
    queue.jobs[0]["status"] = "running"
    import threading
    event = threading.Event()
    queue._active[queue.jobs[0]["id"]] = event
    monkeypatch.setattr(queue, "_save", Mock(side_effect=OSError("synthetic sensitive payload")))

    queue._execute(queue.jobs[0], event)

    assert queue.paused
    assert not queue._active
    assert history.list("local")[0]["status"] == "success"
    assert "completed run state could not be saved (OSError)" in caplog.text
    assert "synthetic sensitive payload" not in caplog.text


def test_failed_cancel_save_keeps_pending_jobs_and_history(tmp_path, monkeypatch):
    from unittest.mock import Mock

    history = RunHistory(tmp_path / "history.json")
    queue = RunQueue(tmp_path / "queue.json", lambda job, event: {}, finished=history.record)
    queue.enqueue([{"workspace": "local", "profile": "p1", "scenario": "s1"}], time.time())
    original_jobs = queue.snapshot()
    monkeypatch.setattr(queue, "_save", Mock(side_effect=OSError("synthetic disk full")))
    with pytest.raises(OSError):
        queue.cancel(workspace="local")
    assert queue.snapshot() == original_jobs
    assert history.list("local") == []


@pytest.mark.parametrize("operation", ["record", "clear"])
def test_failed_history_write_restores_rows(tmp_path, monkeypatch, operation):
    from unittest.mock import Mock

    history = RunHistory(tmp_path / "history.json", limit=1)
    history.record({"id": "original", "workspace": "local", "status": "success"})
    original_rows = history.list()
    original_file = history.path.read_bytes()
    monkeypatch.setattr(history, "_save", Mock(side_effect=OSError("synthetic disk full")))
    with pytest.raises(OSError):
        if operation == "record":
            history.record({"id": "new", "workspace": "local", "status": "success"})
        else:
            history.clear("local")
    assert history.list() == original_rows
    assert history.path.read_bytes() == original_file


def test_queue_timer_reports_write_error_without_escaping(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.ui.bridge.operations import OperationsBridge

    queue = SimpleNamespace(paused=False, tick=Mock(side_effect=OSError("synthetic sensitive payload")))
    bridge = SimpleNamespace(queue=queue, _workspace=lambda: "local", _notify=Mock(), refresh=Mock())
    OperationsBridge._tick_queue(bridge)
    assert queue.paused
    queue.tick.assert_called_once_with(workspace="local")
    bridge.refresh.assert_called_once()
    message = bridge._notify.call_args.args[0]
    assert "OSError" in message
    assert "synthetic sensitive payload" not in message


def test_run_filters_search_all_retained_rows_without_mutating_jobs(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.ui.bridge.models import DictListModel
    from app.ui.bridge.operations import OperationsBridge

    history = RunHistory(tmp_path / "history.json")
    for index in range(130):
        history.record({"id": str(index), "workspace": "local", "scenario": "Report", "profile": "Research",
                        "status": "success", "finished": index + 1, "error": "old special failure" if index == 0 else ""})
    history.record({"id": "other", "workspace": "other", "scenario": "Report", "status": "success", "finished": 500})
    job = {"id": "queue", "workspace": "local", "scenario": "Straße", "profile": "Research", "status": "queued", "due": 1, "started": 0}
    bridge = SimpleNamespace(_run_query="", _run_status="", queue=SimpleNamespace(snapshot=lambda: [job]), history=history,
                             _workspace=lambda: "local", _model=DictListModel(["id"]), _history_model=DictListModel(["id"]),
                             _selected="", _history_row=OperationsBridge._history_row, changed=Mock())
    bridge._matches_run = lambda row: OperationsBridge._matches_run(bridge, row)
    bridge.refresh = lambda: OperationsBridge.refresh(bridge)
    bridge.refresh()
    assert len(bridge._history_model.rows()) == 120
    reset = Mock()
    bridge._model.modelReset.connect(reset)
    bridge.refresh()
    reset.assert_not_called()
    OperationsBridge.setRunFilters(bridge, " STRASSE ", "queued")
    assert [row["id"] for row in bridge._model.rows()] == ["queue"]
    assert bridge._history_model.rows() == []
    OperationsBridge.setRunFilters(bridge, "special", "success")
    assert [row["id"] for row in bridge._history_model.rows()] == ["0"]
    assert bridge._model.rows() == []
    OperationsBridge.setRunFilters(bridge, "other", "invalid")
    assert bridge._run_query == "special"
    assert job["status"] == "queued"
