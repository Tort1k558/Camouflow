"""Persistent, bounded desktop job queue. Execution is supplied by the UI bridge."""

from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from app.storage.db import _atomic_write_text

TERMINAL = {"success", "failed", "canceled", "interrupted"}


class RunQueue:
    def __init__(self, path: Path, runner: Callable, changed: Callable = lambda: None):
        self.path = path
        self.runner = runner
        self.changed = changed
        self._lock = threading.RLock()
        self._active: dict[str, threading.Event] = {}
        self.paused = True
        self.parallelism = 1
        self.jobs: list[dict] = []
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8-sig"))
            if saved.get("version") != 1 or not isinstance(saved.get("jobs"), list):
                raise ValueError("Unsupported or invalid queue file")
            self.jobs = saved["jobs"]
            self.parallelism = max(1, min(8, int(saved.get("parallelism", 1))))
            for job in self.jobs:
                if job["status"] == "running":
                    job.update(status="interrupted", error="Application stopped during execution; review results before retrying.", finished=time.time())
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(self.path, json.dumps({"version": 1, "parallelism": self.parallelism, "jobs": self.jobs}, ensure_ascii=False, indent=2))

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self.jobs)

    def enqueue(self, specs: list[dict], due: float):
        if not specs or not isinstance(due, (int, float)) or not 0 <= due < 32503680000:
            raise ValueError("Select profiles and a valid execution time")
        with self._lock:
            pending = sum(j["status"] not in TERMINAL for j in self.jobs)
            if pending + len(specs) > 500:
                raise ValueError("Queue safety limit: 500 unfinished jobs")
            if len(json.dumps([*self.jobs, *specs]).encode("utf-8")) > 32 * 1024 * 1024:
                raise ValueError("Queue storage exceeds 32 MiB. Remove finished jobs before adding more.")
            for spec in specs:
                self.jobs.append({**copy.deepcopy(spec), "id": uuid.uuid4().hex, "status": "queued", "due": due,
                                  "created": time.time(), "started": 0, "finished": 0, "error": "", "artifacts": ""})
            self._save()
        self.changed()

    def clear_finished(self, workspace=None):
        with self._lock:
            self.jobs = [j for j in self.jobs if j["status"] not in TERMINAL or (workspace is not None and j.get("workspace") != workspace)]
            self._save()
        self.changed()

    def configure(self, parallelism: int, paused: bool):
        if not 1 <= parallelism <= 8:
            raise ValueError("Parallelism must be between 1 and 8")
        with self._lock:
            self.parallelism, self.paused = parallelism, paused
            self._save()
        self.changed()

    def cancel(self, job_id: str = "", workspace=None):
        with self._lock:
            for job in self.jobs:
                if workspace is not None and job.get("workspace") != workspace:
                    continue
                if job_id and job["id"] != job_id:
                    continue
                if job["id"] in self._active:
                    self._active[job["id"]].set()
                elif job["status"] == "queued":
                    job.update(status="canceled", finished=time.time())
            self._save()
        self.changed()

    def tick(self, workspace=None):
        launched = False
        with self._lock:
            if self.paused:
                return
            busy_profiles = {j["profile"] for j in self.jobs if j["id"] in self._active}
            for job in self.jobs:
                if workspace is not None and job.get("workspace") != workspace:
                    continue
                if len(self._active) >= self.parallelism:
                    break
                if job["status"] != "queued" or job["due"] > time.time() or job["profile"] in busy_profiles:
                    continue
                event = threading.Event()
                self._active[job["id"]] = event
                busy_profiles.add(job["profile"])
                job.update(status="running", started=time.time())
                self._save()
                threading.Thread(target=self._execute, args=(job, event), daemon=True, name="camouflow-queue").start()
                launched = True
        if launched:
            self.changed()

    def _execute(self, job, event):
        try:
            result = self.runner(copy.deepcopy(job), event)
            result = dict(result or {})
            result["status"] = "canceled" if event.is_set() else result.get("status", "failed")
            if result["status"] not in TERMINAL:
                raise ValueError("Invalid job result")
        except Exception as exc:
            result = {"status": "canceled" if event.is_set() else "failed", "error": str(exc)}
        with self._lock:
            job.update({key: result[key] for key in ("status", "error", "artifacts", "step") if key in result}, finished=time.time())
            self._active.pop(job["id"], None)
            self._save()
        self.changed()

    def shutdown(self):
        with self._lock:
            self.paused = True
            for event in self._active.values():
                event.set()
