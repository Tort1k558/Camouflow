"""Qt-aware logging helpers."""

from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s [%(profile)s]: %(message)s"


class _GuiLogEmitter(QObject):
    message = pyqtSignal(str, int)


class GuiLogHandler(logging.Handler):
    """Logging handler that forwards records into the Qt GUI thread."""

    def __init__(self) -> None:
        super().__init__()
        self._emitter = _GuiLogEmitter()

    def connect(self, slot: Callable[[str, int], None]) -> None:
        self._emitter.message.connect(slot)

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - bridge to Qt
        try:
            message = self.format(record)
        except Exception:
            try:
                message = record.getMessage()
            except Exception:
                message = str(record.msg)
        self._emitter.message.emit(message, record.levelno)


class ProfileContextFilter(logging.Filter):
    """Ensure every log record has a profile attribute for formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "profile") or record.profile in (None, ""):
            record.profile = "-"
        return True


PROFILE_FILTER = ProfileContextFilter()

