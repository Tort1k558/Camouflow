"""Logs bridge for QML."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.storage.db import DATA_ROOT
from app.ui.bridge.models import DictListModel

_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+([A-Z]+)\s+(.*)$")


def _split_line(line: str) -> Tuple[str, str, str]:
    """Split 'timestamp LEVEL message' into parts; falls back to the raw line."""
    match = _LINE_RE.match(line)
    if match:
        return match.group(1).replace("T", " "), match.group(2), match.group(3)
    return "", "", line


class _QmlLogHandler(logging.Handler):
    def __init__(self, bridge: "LogsBridge") -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._bridge.append(self.format(record), record.levelname)
        except Exception:
            pass


class LogsBridge(QObject):
    modelChanged = pyqtSignal()
    textChanged = pyqtSignal()
    countsChanged = pyqtSignal()

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._model = DictListModel(["level", "text", "time", "message"], parent=self)
        self._rows: List[dict] = []
        self._text = ""
        self._level_filter = "all"
        self._counts = {"all": 0, "errors": 0, "warnings": 0}
        self._app_state = app_state
        self._install_handler()
        self.refresh()
        if app_state is not None:
            app_state.refreshRequested.connect(self.refresh)

    @pyqtProperty(QObject, constant=True)
    def model(self) -> QObject:
        return self._model

    @pyqtProperty(str, notify=textChanged)
    def text(self) -> str:
        return self._text

    @pyqtProperty(str, notify=countsChanged)
    def levelFilter(self) -> str:  # noqa: N802
        return self._level_filter

    @pyqtProperty(int, notify=countsChanged)
    def errorCount(self) -> int:  # noqa: N802
        return self._counts["errors"]

    @pyqtProperty(int, notify=countsChanged)
    def warningCount(self) -> int:  # noqa: N802
        return self._counts["warnings"]

    @pyqtProperty(int, notify=countsChanged)
    def totalCount(self) -> int:  # noqa: N802
        return self._counts["all"]

    @pyqtSlot(str)
    def setLevelFilter(self, level: str) -> None:  # noqa: N802
        value = str(level or "all").lower()
        if value not in {"all", "errors", "warnings"}:
            value = "all"
        if value == self._level_filter:
            return
        self._level_filter = value
        self._apply()
        self.countsChanged.emit()

    def _apply(self) -> None:
        if self._level_filter == "errors":
            shown = [row for row in self._rows if row["level"] == "ERROR"]
        elif self._level_filter == "warnings":
            shown = [row for row in self._rows if row["level"] in {"WARNING", "ERROR"}]
        else:
            shown = list(self._rows)
        self._counts = {
            "all": len(self._rows),
            "errors": sum(1 for row in self._rows if row["level"] == "ERROR"),
            "warnings": sum(1 for row in self._rows if row["level"] in {"WARNING", "ERROR"}),
        }
        self._model.set_rows(list(reversed(shown[-200:])))

    def _install_handler(self) -> None:
        root = logging.getLogger()
        for handler in root.handlers:
            if isinstance(handler, _QmlLogHandler):
                return
        handler = _QmlLogHandler(self)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root.addHandler(handler)

    def append(self, text: str, level: str = "INFO") -> None:
        timestamp, parsed_level, message = _split_line(str(text))
        row = {
            "level": parsed_level if parsed_level else str(level),
            "text": str(text),
            "time": timestamp or str(text)[:19],
            "message": message,
        }
        self._rows.append(row)
        self._rows = self._rows[-500:]
        self._apply()
        self._text = "\n".join(r["text"] for r in self._rows[-500:])
        self.modelChanged.emit()
        self.textChanged.emit()
        self.countsChanged.emit()

    @pyqtSlot()
    def refresh(self) -> None:
        rows: List[dict] = []
        logs_dir = DATA_ROOT / "logs"
        if logs_dir.exists():
            for path in sorted(logs_dir.glob("*.log")):
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
                except Exception:
                    lines = []
                for line in lines:
                    timestamp, parsed_level, message = _split_line(line)
                    if not parsed_level:
                        parsed_level = "ERROR" if "ERROR" in line else "WARNING" if "WARN" in line else "INFO"
                    rows.append({"level": parsed_level, "text": line, "time": timestamp or line[:19], "message": message})
        self._rows = rows[-500:]
        self._apply()
        self._text = "\n".join(r["text"] for r in self._rows[-500:])
        self.modelChanged.emit()
        self.textChanged.emit()
        self.countsChanged.emit()

    @pyqtSlot()
    def clear(self) -> None:
        self._rows = []
        self._text = ""
        self._apply()
        self.modelChanged.emit()
        self.textChanged.emit()
        self.countsChanged.emit()
