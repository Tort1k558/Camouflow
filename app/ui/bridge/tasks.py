"""Saved scenarios presented as tasks, using the existing execution queue."""

import copy
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices

from app.services.task_inputs import csv_rows, csv_template, input_fields
from app.storage import db
from app.ui.bridge.models import DictListModel


class TasksBridge(QObject):
    changed = pyqtSignal()

    def __init__(self, operations, scenarios, state, parent=None):
        super().__init__(parent)
        self.operations, self.scenarios, self.state = operations, scenarios, state
        self._model = DictListModel(["name", "description", "steps", "status", "profile", "job"], parent=self)
        self._selected = ""
        self._steps = []
        self._fields = []
        self._problem = ""
        self._latest = {}
        self._csv_rows, self._csv_name, self._batch_runs = [], "", []
        self._workspace = operations._workspace()
        scenarios.modelChanged.connect(self.refresh)
        operations.changed.connect(self.refresh)
        state.cloudChanged.connect(self.refresh)
        self.refresh()

    @pyqtProperty(QObject, constant=True)
    def model(self):
        return self._model

    @pyqtProperty(str, notify=changed)
    def selectedName(self):
        return self._selected

    @pyqtProperty("QVariantList", notify=changed)
    def inputFields(self):
        return copy.deepcopy(self._fields)

    @pyqtProperty(str, notify=changed)
    def problem(self):
        return self._problem

    @pyqtProperty("QVariantList", notify=changed)
    def csvRows(self):
        return [{"row": row["row"], "summary": " | ".join(row["inputs"].values()),
                 "duplicate": row["duplicate_of"]} for row in self._csv_rows]

    @pyqtProperty(str, notify=changed)
    def csvName(self):
        return self._csv_name

    @pyqtProperty("QVariantList", notify=changed)
    def batchRuns(self):
        return [{key: row.get(key, "") for key in ("id", "batch_row", "status", "error")}
                for row in self._batch_runs]

    @pyqtProperty("QVariantMap", notify=changed)
    def lastRun(self):
        job = self._latest.get(self._selected, {})
        return {key: job.get(key, "") for key in ("id", "status", "profile", "error")}

    @pyqtProperty(str, notify=changed)
    def review(self):
        warnings = self._steps[0].get("_recording_warnings", []) if self._steps else []
        notes = [str(warning) for warning in warnings] if isinstance(warnings, list) else ["Invalid recording warnings"]
        notes.append("This task may change website data. Review its steps before running. Inputs are stored in the local queue; do not enter credentials.")
        return "\n".join(notes)

    @pyqtSlot()
    def refresh(self):
        workspace = self.operations._workspace()
        if workspace != self._workspace:
            self._workspace = workspace
            self._selected, self._steps, self._fields, self._problem = "", [], [], ""
            self._csv_rows, self._csv_name = [], ""
        jobs = {job["id"]: job for job in self.operations.history.list(workspace, limit=500)}
        jobs.update({job["id"]: job for job in self.operations.queue.snapshot() if job.get("workspace") == workspace})
        batches = [job for job in jobs.values() if job.get("batch_id") and job.get("scenario") == self._selected]
        batch_id = max(batches, key=lambda job: job.get("created", 0)).get("batch_id") if batches else ""
        self._batch_runs = sorted([job for job in batches if job["batch_id"] == batch_id],
                                  key=lambda job: (job["batch_row"], job.get("created", 0)))
        latest = {}
        for job in reversed(self.operations.queue.snapshot()):
            if job.get("workspace") == workspace:
                latest.setdefault(job["scenario"], job)
        for job in self.operations.history.list(workspace, limit=500):
            latest.setdefault(job["scenario"], job)
        self._latest = latest
        scenarios = self.scenarios._list_scenarios()
        self._model.set_rows([
            {"name": scenario.name, "description": scenario.description or "",
             "steps": max(0, len(scenario.steps) - 1),
             "status": latest.get(scenario.name, {}).get("status", "Not run yet"),
             "profile": latest.get(scenario.name, {}).get("profile", ""),
             "job": latest.get(scenario.name, {}).get("id", "")}
            for scenario in scenarios
        ])
        if self._selected and not any(scenario.name == self._selected for scenario in scenarios):
            self._selected, self._steps, self._fields = "", [], []
            self._csv_rows, self._csv_name = [], ""
        if self._csv_rows:
            scenario = self.scenarios._get_scenario(self._selected)
            if scenario is None or scenario.steps != self._steps:
                self._csv_rows, self._csv_name = [], ""
        self.changed.emit()

    @pyqtSlot(str)
    def select(self, name):
        scenario = self.scenarios._get_scenario(name)
        if scenario is None:
            self.state.notify("Task no longer exists; refresh the task list")
            return
        self._selected, self._steps = scenario.name, copy.deepcopy(scenario.steps)
        self._csv_rows, self._csv_name = [], ""
        try:
            self._fields = input_fields(self._steps)
            self._problem = self.scenarios._validate_scenario(scenario)
        except ValueError as exc:
            self._fields, self._problem = [], str(exc)
        self.refresh()

    @pyqtSlot(str, "QVariantMap", result=bool)
    def run(self, profile, inputs):
        if not self._ready():
            return False
        return self.operations.enqueueTask(profile, self._selected, inputs)

    def _ready(self):
        if self._problem or not self._selected or self._workspace != self.operations._workspace():
            return False
        scenario = self.scenarios._get_scenario(self._selected)
        if scenario is None or scenario.steps != self._steps:
            self.state.notify("Task changed. Select it again and review the updated inputs before running.")
            return False
        return True

    @pyqtSlot(str, str, result=bool)
    def importCsv(self, source, delimiter):
        self._csv_rows, self._csv_name = [], ""
        try:
            if not self._ready():
                return False
            path = Path(QUrl(source).toLocalFile() if source.startswith("file:") else source)
            with path.open("rb") as stream:
                self._csv_rows = csv_rows(self._steps, stream.read(1024 * 1024 + 1), delimiter)
            self._csv_name = path.name
            return True
        except (OSError, ValueError) as exc:
            self.state.notify(str(exc))
            return False
        finally:
            self.changed.emit()

    @pyqtSlot(str, str)
    def exportCsvTemplate(self, destination, delimiter):
        try:
            if not self._ready():
                return
            path = Path(QUrl(destination).toLocalFile() if destination.startswith("file:") else destination)
            if path.suffix.lower() != ".csv":
                raise ValueError("Choose a CSV file")
            path.write_text(csv_template(self._steps, delimiter), encoding="utf-8", newline="")
        except (OSError, ValueError) as exc:
            self.state.notify(str(exc))

    @pyqtSlot(str, bool, result=bool)
    def runBatch(self, profile, skip_duplicates):
        if not self._ready() or not self._csv_rows:
            return False
        rows = [row for row in self._csv_rows if not skip_duplicates or not row["duplicate_of"]]
        if not self.operations.enqueue_batch(profile, self._selected, rows):
            return False
        self._csv_rows, self._csv_name = [], ""
        self.changed.emit()
        return True

    @pyqtSlot(str)
    def inspectBatchRun(self, job_id):
        if any(job["id"] == job_id for job in self._batch_runs):
            self.operations.selectJob(job_id)
            self.state.setPage("ScenarioRuns")

    @pyqtSlot()
    def openBatchOutputs(self):
        if not self._batch_runs:
            return
        path = (db.OUTPUTS_DIR / "batches" / self._batch_runs[0]["batch_id"]).resolve()
        if not path.is_relative_to(db.OUTPUTS_DIR.resolve()) or not path.is_dir():
            self.state.notify("No Write file results yet. Browser artifacts are in run details.")
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.state.notify("Could not open batch results")

    @pyqtSlot()
    def edit(self):
        if self._selected:
            self.scenarios.selectScenario(self._selected)
            self.state.setPage("Scenarios")

    @pyqtSlot()
    def inspect(self):
        job = self._latest.get(self._selected)
        if job:
            self.operations.selectJob(job["id"])
            self.state.setPage("ScenarioRuns")
