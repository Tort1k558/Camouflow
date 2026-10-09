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
