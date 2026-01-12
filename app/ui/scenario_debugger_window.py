"""Scenario debugger window (pause/stop/jump + hot reload status)."""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QFileSystemWatcher, Qt, QTimer
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.scenario_debug import ScenarioDebugSession, ScenarioDebugUpdate


def _fmt_ts(ts: Optional[float]) -> str:
    if not ts:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
    except Exception:
        return "-"


class ScenarioDebuggerWindow(QWidget):
    def __init__(
        self,
        session: ScenarioDebugSession,
        *,
        scenario_path: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._scenario_path = scenario_path
        self._scenario_name: str = ""
        self._last_update: Optional[ScenarioDebugUpdate] = None
        self._watcher: Optional[QFileSystemWatcher] = None
        self._reload_timer: Optional[QTimer] = None
        self._steps_loaded_at: Optional[float] = None
        self.setWindowTitle("Scenario debugger")
        # Separate, non-modal top-level window (independent from the main window).
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QLabel("General debug mode is enabled for this run.")
        header.setWordWrap(True)
        root.addWidget(header)

        info = QFrame(self)
        info.setFrameShape(QFrame.Shape.StyledPanel)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(8)

        self._scenario_label = QLabel("Scenario: -", info)
        self._account_label = QLabel("Account: -", info)
        self._step_label = QLabel("Step: -", info)
        self._desc_label = QLabel("Description: -", info)
        self._desc_label.setWordWrap(True)
        self._reload_label = QLabel("Hot reload: -", info)
        self._steps_label = QLabel("Steps: -", info)
        info_layout.addWidget(self._scenario_label)
        info_layout.addWidget(self._account_label)
        info_layout.addWidget(self._step_label)
        info_layout.addWidget(self._desc_label)
        info_layout.addWidget(self._reload_label)
        info_layout.addWidget(self._steps_label)
        root.addWidget(info)

        controls = QFrame(self)
        controls.setFrameShape(QFrame.Shape.NoFrame)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self._pause_btn = QPushButton("Pause", controls)
        self._pause_btn.clicked.connect(self._toggle_pause)
        controls_layout.addWidget(self._pause_btn)

        stop_btn = QPushButton("Stop", controls)
        stop_btn.setProperty("class", "danger")
        stop_btn.clicked.connect(self._stop)
        controls_layout.addWidget(stop_btn)

        controls_layout.addStretch(1)
        root.addWidget(controls)

        jump = QFrame(self)
        jump.setFrameShape(QFrame.Shape.StyledPanel)
        jump_layout = QVBoxLayout(jump)
        jump_layout.setContentsMargins(12, 12, 12, 12)
        jump_layout.setSpacing(10)

        jump_row = QHBoxLayout()
        jump_row.addWidget(QLabel("Run from step:", jump))
        self._step_spin = QSpinBox(jump)
        self._step_spin.setRange(1, 999999)
        self._step_spin.setValue(1)
        jump_row.addWidget(self._step_spin)
        self._run_step_btn = QPushButton("Run", jump)
        self._run_step_btn.clicked.connect(self._run_from_step)
        jump_row.addWidget(self._run_step_btn)
        jump_row.addStretch(1)
        jump_layout.addLayout(jump_row)

        steps_title = QLabel("Steps (auto reload):", jump)
        steps_title.setProperty("class", "cardTitle")
        jump_layout.addWidget(steps_title)

        self._steps_list = QListWidget(jump)
        self._steps_list.setMinimumHeight(220)
        self._steps_list.currentRowChanged.connect(self._sync_spin_from_list)
        self._steps_list.itemDoubleClicked.connect(lambda _: self._run_selected_step())
        jump_layout.addWidget(self._steps_list, 1)

        run_sel_row = QHBoxLayout()
        run_sel_row.addStretch(1)
        run_selected_btn = QPushButton("Run selected", jump)
        run_selected_btn.clicked.connect(self._run_selected_step)
        run_sel_row.addWidget(run_selected_btn)
        jump_layout.addLayout(run_sel_row)

        root.addWidget(jump)

        self._refresh_pause_button()
        self._setup_step_watcher()

    def apply_update(self, update: ScenarioDebugUpdate) -> None:
        self._last_update = update
        if update.scenario_name and update.scenario_name != self._scenario_name:
            self._scenario_name = update.scenario_name
            try:
                from app.storage.db import db_get_scenario_path

                self._set_scenario_path(db_get_scenario_path(update.scenario_name))
            except Exception:
                pass
        self._scenario_label.setText(f"Scenario: {update.scenario_name or '-'}")
        self._account_label.setText(f"Account: {update.account_name or '-'}")
        step_no = int(update.step_index) + 1
        total = int(update.total_steps)
        tag = (update.tag or "").strip() or "-"
        action = (update.action or "").strip() or "-"
        order_row = self._row_for_step_index(int(update.step_index))
        order_total = self._steps_list.count()
        if order_row is not None:
            self._step_label.setText(
                f"Order: {order_row + 1}/{max(1, order_total)} (step #{step_no}/{total}, tag: {tag}, action: {action})"
            )
        else:
            self._step_label.setText(f"Step #: {step_no}/{total} (tag: {tag}, action: {action})")
        self._desc_label.setText(f"Description: {update.description or update.tag or update.action or '-'}")
        self._reload_label.setText(f"Hot reload: last reload {_fmt_ts(update.reloaded_at)}")
        self._step_spin.setMaximum(max(1, max(1, self._steps_list.count())))
        try:
            self._step_spin.blockSignals(True)
            if order_row is not None:
                self._step_spin.setValue(max(1, min(order_row + 1, self._step_spin.maximum())))
            else:
                self._step_spin.setValue(max(1, min(step_no, self._step_spin.maximum())))
        finally:
            self._step_spin.blockSignals(False)
        try:
            self._steps_list.blockSignals(True)
            if order_row is not None:
                self._steps_list.setCurrentRow(order_row)
        finally:
            self._steps_list.blockSignals(False)
        self._refresh_steps_status(total)
        self._refresh_pause_button()

    def mark_finished(self, *, stopped: bool = False) -> None:
        update = self._last_update
        if update is not None:
            step_no = int(update.step_index) + 1
            total = int(update.total_steps)
            tag = (update.tag or "").strip() or "-"
            action = (update.action or "").strip() or "-"
            status = "stopped" if stopped else "finished"
            self._step_label.setText(
                f"Status: {status} (last: {step_no}/{total}, tag: {tag}, action: {action}) — choose a step and press Run"
            )
        else:
            self._step_label.setText(
                ("Status: stopped" if stopped else "Status: finished") + " — choose a step and press Run"
            )
        self._reload_label.setText("Hot reload: stopped" if stopped else "Hot reload: finished")
        # Keep controls enabled so the user can restart from any step while the browser is still open.
        self._pause_btn.setEnabled(True)
        self._run_step_btn.setEnabled(True)
        self._refresh_pause_button()

    def _refresh_pause_button(self) -> None:
        self._pause_btn.setText("Resume" if self._session.paused else "Pause")

    def _toggle_pause(self) -> None:
        if self._session.paused:
            self._session.resume()
        else:
            self._session.pause()
        self._refresh_pause_button()

    def _stop(self) -> None:
        self._session.request_stop()
        self._refresh_pause_button()

    def _run_from_step(self) -> None:
        row = int(self._step_spin.value()) - 1
        actual = self._step_index_for_row(row)
        if actual is None:
            return
        self._session.request_jump_to_step(actual + 1)
        self._session.resume()
        self._refresh_pause_button()

    def _sync_spin_from_list(self, row: int) -> None:
        if row < 0:
            return
        try:
            self._step_spin.setValue(int(row) + 1)
        except Exception:
            pass

    def _run_selected_step(self) -> None:
        row = self._steps_list.currentRow()
        if row < 0:
            return
        actual = self._step_index_for_row(row)
        if actual is None:
            return
        self._session.request_jump_to_step(actual + 1)
        self._session.resume()
        self._refresh_pause_button()

    def _setup_step_watcher(self) -> None:
        if not self._scenario_path:
            self._steps_label.setText("Steps: -")
            return
        try:
            scenario_path = Path(self._scenario_path)
        except Exception:
            self._steps_label.setText("Steps: -")
            return
        self._scenario_path = scenario_path

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(lambda _: self._schedule_steps_reload())
        self._watcher.directoryChanged.connect(lambda _: self._schedule_steps_reload())
        try:
            self._watcher.addPath(str(self._scenario_path.parent))
        except Exception:
            pass
        self._ensure_watched_file()

        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._reload_steps_from_disk)
        self._reload_steps_from_disk()

    def _set_scenario_path(self, path: Path) -> None:
        try:
            scenario_path = Path(path)
        except Exception:
            return
        self._scenario_path = scenario_path
        if self._watcher:
            try:
                self._watcher.removePaths(self._watcher.files())
            except Exception:
                pass
            try:
                self._watcher.removePaths(self._watcher.directories())
            except Exception:
                pass
            try:
                self._watcher.addPath(str(self._scenario_path.parent))
            except Exception:
                pass
            self._ensure_watched_file()
        self._reload_steps_from_disk()

    def _ensure_watched_file(self) -> None:
        if not self._watcher or not self._scenario_path:
            return
        file_path = str(self._scenario_path)
        if file_path in set(self._watcher.files()):
            return
        if self._scenario_path.exists():
            try:
                self._watcher.addPath(file_path)
            except Exception:
                pass

    def _schedule_steps_reload(self) -> None:
        self._ensure_watched_file()
        if self._reload_timer:
            self._reload_timer.start(200)

    def _reload_steps_from_disk(self) -> None:
        self._ensure_watched_file()
        if not self._scenario_path:
            return
        if not self._scenario_path.exists():
            self._steps_list.clear()
            self._steps_loaded_at = None
            self._refresh_steps_status(0)
            return
        try:
            payload = json.loads(self._scenario_path.read_text(encoding="utf-8"))
        except Exception:
            return
        steps = payload.get("steps") or []
        if not isinstance(steps, list):
            return

        ordered = self._order_steps_for_display(steps)
        prev_row = self._steps_list.currentRow()
        self._steps_list.blockSignals(True)
        self._steps_list.clear()
        for order_idx, original_idx in enumerate(ordered):
            step = steps[original_idx] if 0 <= original_idx < len(steps) else {}
            step_dict = step if isinstance(step, dict) else {}
            action = str(step_dict.get("action") or "")
            tag = str(step_dict.get("tag") or step_dict.get("label") or "")
            desc = str(step_dict.get("description") or tag or action or "")
            suffix = f" ({tag})" if tag and tag != desc else ""
            text = f"{order_idx + 1:03d}: {action or '-'} - {desc}{suffix}"
            item = QListWidgetItem(text, self._steps_list)
            item.setData(Qt.ItemDataRole.UserRole, int(original_idx))
        self._steps_list.blockSignals(False)
        # Restore selection to the same underlying step index when possible.
        restored = None
        if self._last_update is not None:
            restored = self._row_for_step_index(int(self._last_update.step_index))
        if restored is not None:
            self._steps_list.setCurrentRow(restored)
        elif prev_row >= 0 and prev_row < self._steps_list.count():
            self._steps_list.setCurrentRow(prev_row)
        elif self._steps_list.count() > 0:
            self._steps_list.setCurrentRow(0)

        self._steps_loaded_at = time.time()
        self._refresh_steps_status(self._steps_list.count())

    def _refresh_steps_status(self, total_steps: int) -> None:
        if self._scenario_path:
            name = self._scenario_path.name
        else:
            name = "-"
        loaded = _fmt_ts(self._steps_loaded_at)
        self._steps_label.setText(f"Steps: {int(total_steps)} (file: {name}, loaded {loaded})")

    def _step_index_for_row(self, row: int) -> Optional[int]:
        if row < 0 or row >= self._steps_list.count():
            return None
        item = self._steps_list.item(row)
        if item is None:
            return None
        try:
            value = item.data(Qt.ItemDataRole.UserRole)
            return int(value)
        except Exception:
            return None

    def _row_for_step_index(self, step_index: int) -> Optional[int]:
        try:
            idx = int(step_index)
        except Exception:
            return None
        for row in range(self._steps_list.count()):
            if self._step_index_for_row(row) == idx:
                return row
        return None

    @staticmethod
    def _order_steps_for_display(steps: list) -> list[int]:
        """
        Order steps by their execution flow (happy path), not by creation/index.

        The "happy path" is computed by starting at the start step (action=start) and
        following `next_success_step` tags; falling back to sequential order when absent.
        Remaining unvisited steps are appended by index.
        """
        if not steps:
            return []
        tag_index: dict[str, int] = {}
        for i, step in enumerate(steps):
            if isinstance(step, dict) and step.get("tag"):
                tag_index[str(step.get("tag"))] = i

        start = 0
        for i, step in enumerate(steps):
            if isinstance(step, dict) and str(step.get("action") or "").lower() == "start":
                start = i
                break

        order: list[int] = []
        visited: set[int] = set()
        idx = start
        while 0 <= idx < len(steps) and idx not in visited:
            visited.add(idx)
            order.append(idx)
            step = steps[idx] if isinstance(steps[idx], dict) else {}
            next_tag = step.get("next_success_step")
            if next_tag and str(next_tag) in tag_index:
                nxt = int(tag_index[str(next_tag)])
                if nxt not in visited:
                    idx = nxt
                    continue
            if step.get("_no_default_links"):
                break
            idx = idx + 1

        for i in range(len(steps)):
            if i not in visited:
                order.append(i)
        return order

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._session.disable()
        except Exception:
            pass
        super().closeEvent(event)
