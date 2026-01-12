"""Logging helpers for the main window."""

from __future__ import annotations

import logging
import os
import threading
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QWidget
from app.utils.gui_logging import GuiLogHandler, LOG_FORMAT, PROFILE_FILTER


class LoggingMixin:
    def _ui_log_path(self) -> str:
        base_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "ui.log")

    def _append_ui_log_to_file(self, text: str) -> None:
        if getattr(self, "_suppress_ui_log_persist", False):
            return
        lock = getattr(self, "_ui_log_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._ui_log_lock = lock
        try:
            normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
            if not normalized.endswith("\n"):
                normalized += "\n"
            with lock:
                with open(self._ui_log_path(), "a", encoding="utf-8") as f:
                    f.write(normalized)
        except Exception:
            return

    def _load_ui_log_from_file(self, max_lines: int = 5000) -> None:
        if not hasattr(self, "log_edit"):
            return
        path = self._ui_log_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception:
            return
        if max_lines and len(lines) > max_lines:
            lines = lines[-max_lines:]
        try:
            self._suppress_ui_log_persist = True
            self.log_edit.setPlainText("\n".join(lines))
            cursor = self.log_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_edit.setTextCursor(cursor)
            self.log_edit.ensureCursorVisible()
        finally:
            self._suppress_ui_log_persist = False

    def log(self, text: str, level: int = logging.INFO) -> None:
        self._append_log_message(text, level)

    def _append_log_message(self, text: str, level: int) -> None:
        if not hasattr(self, "log_edit"):
            return
        edit = self.log_edit
        if self._log_default_color is None:
            palette = edit.palette()
            self._log_default_color = palette.color(QPalette.ColorRole.Text)
        cursor = edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        fmt = cursor.charFormat()
        color = self._log_error_color if level >= logging.ERROR else self._log_default_color
        if color is not None:
            fmt.setForeground(color)
        cursor.insertText(text + "\n", fmt)
        edit.setTextCursor(cursor)
        edit.ensureCursorVisible()
        self._append_ui_log_to_file(text)

    def _install_log_handler(self) -> None:
        if getattr(self, "_gui_log_handler", None):
            return
        if hasattr(self, "log_edit") and self._log_default_color is None:
            palette = self.log_edit.palette()
            self._log_default_color = palette.color(QPalette.ColorRole.Text)
        handler = GuiLogHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        handler.addFilter(PROFILE_FILTER)
        handler.connect(self._append_log_message)
        root_logger = logging.getLogger()
        if PROFILE_FILTER not in root_logger.filters:
            root_logger.addFilter(PROFILE_FILTER)
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
        self._gui_log_handler = handler

    def _refresh_log_colors(self) -> None:
        if hasattr(self, "log_edit"):
            palette = self.log_edit.palette()
            self._log_default_color = palette.color(QPalette.ColorRole.Text)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.MouseButtonPress and isinstance(source, QWidget):
            item = self._account_row_widgets.get(source)
            if item and hasattr(self, "accounts_list"):
                modifiers = QApplication.keyboardModifiers()
                if modifiers & Qt.KeyboardModifier.ControlModifier:
                    item.setSelected(not item.isSelected())
                else:
                    if not (modifiers & Qt.KeyboardModifier.ShiftModifier):
                        self.accounts_list.clearSelection()
                    if modifiers & Qt.KeyboardModifier.ShiftModifier:
                        current_row = self.accounts_list.currentRow()
                        target_row = self.accounts_list.row(item)
                        if current_row < 0:
                            current_row = target_row
                        start, end = sorted((current_row, target_row))
                        for row in range(start, end + 1):
                            self.accounts_list.item(row).setSelected(True)
                    item.setSelected(True)
                    self.accounts_list.setCurrentItem(item)
                return True
        return super().eventFilter(source, event)
