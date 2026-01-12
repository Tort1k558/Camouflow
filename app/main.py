"""Application entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app.utils.gui_logging import LOG_FORMAT, PROFILE_FILTER
from app.storage.db import db_get_setting, init_db
from app.ui.main_window import MainWindow
from app.ui.style import DEFAULT_THEME, apply_modern_theme, normalize_theme


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    root_logger = logging.getLogger()
    if PROFILE_FILTER not in root_logger.filters:
        root_logger.addFilter(PROFILE_FILTER)

    init_db()

    # Ensure Windows taskbar picks up the correct icon (best-effort).
    if sys.platform.startswith("win"):
        try:
            import ctypes  # type: ignore

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CamouFlow")
        except Exception:
            pass

    app = QApplication(sys.argv)

    icon_path = Path(__file__).resolve().parents[1] / "logo.ico"
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)
    else:
        icon = QIcon()

    stored_theme = normalize_theme(db_get_setting("ui_theme") or DEFAULT_THEME)
    apply_modern_theme(app, stored_theme)
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    QTimer.singleShot(0, window.showMaximized)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
