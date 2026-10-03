"""Local scenario run history stored separately from the execution queue."""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path
from typing import Any

from app.storage.db import _atomic_write_text


HISTORY_VERSION = 1
MAX_HISTORY_ROWS = 500


class RunHistory:
    def __init__(self, path: Path, limit: int = MAX_HISTORY_ROWS):
        self.path = path
        self.limit = max(1, int(limit))
        self._lock = threading.RLock()
        self.rows: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        if payload.get("version") != HISTORY_VERSION or not isinstance(payload.get("runs"), list):
            raise ValueError("Unsupported or invalid run history file")
        self.rows = [dict(row) for row in payload["runs"] if isinstance(row, dict)][-self.limit :]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": HISTORY_VERSION, "updated": time.time(), "runs": self.rows[-self.limit :]}
        _atomic_write_text(self.path, json.dumps(payload, ensure_ascii=False, indent=2))

    @staticmethod
    def _public_row(job: dict[str, Any]) -> dict[str, Any]:
        row = {
            key: copy.deepcopy(job.get(key))
            for key in (
                "id",
                "workspace",
                "scenario",
                "profile",
                "status",
                "created",
                "due",
                "started",
                "finished",
                "error",
                "artifacts",
                "step",
                "batch_id",
                "batch_row",
                "batch_size",
            )
            if key in job
        }
        row.setdefault("recorded", time.time())
        return row

    def record(self, job: dict[str, Any]) -> None:
        row = self._public_row(job)
        if not row.get("id"):
            return
        with self._lock:
            self.rows = [existing for existing in self.rows if existing.get("id") != row["id"]]
            self.rows.append(row)
            self.rows = self.rows[-self.limit :]
            self._save()

    def list(self, workspace: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = [copy.deepcopy(row) for row in self.rows if workspace is None or row.get("workspace") == workspace]
        rows.sort(key=lambda row: float(row.get("finished") or row.get("started") or row.get("created") or 0), reverse=True)
        return rows[:limit] if limit else rows

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = next((row for row in self.rows if row.get("id") == run_id), None)
            return copy.deepcopy(row) if row else None

    def clear(self, workspace: str | None = None) -> None:
        with self._lock:
            if workspace is None:
                self.rows = []
            else:
                self.rows = [row for row in self.rows if row.get("workspace") != workspace]
            self._save()
