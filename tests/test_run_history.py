"""Local run history tests; no browser required."""

import time

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
