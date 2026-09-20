"""Application entry point."""

from __future__ import annotations

import logging
import os
import sys

from app.utils.gui_logging import LOG_FORMAT, PROFILE_FILTER, ProfileFormatter
from app.storage.db import init_db
from app.ui.qml_app import run_qml_app


def main() -> None:
    # In GUI builds (PyInstaller console=False), stdout/stderr can be None.
    # Python's logging StreamHandler expects a stream with .write().
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if len(sys.argv) == 3 and sys.argv[1] == "--show-trace":
        from playwright.__main__ import main as trace_main
        sys.argv = [sys.argv[0], "show-trace", sys.argv[2]]
        trace_main()
        return
    os.environ.setdefault("QT_LOGGING_RULES", "qt.text.font.db=false")

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    root_logger = logging.getLogger()
    if PROFILE_FILTER not in root_logger.filters:
        root_logger.addFilter(PROFILE_FILTER)
    for handler in root_logger.handlers:
        handler.setFormatter(ProfileFormatter(LOG_FORMAT))
        if PROFILE_FILTER not in handler.filters:
            handler.addFilter(PROFILE_FILTER)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    init_db()

    # Ensure Windows taskbar picks up the correct icon (best-effort).
    if sys.platform.startswith("win"):
        try:
            import ctypes  # type: ignore

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CamouFlow")
        except Exception:
            pass

    sys.exit(run_qml_app(sys.argv))


if __name__ == "__main__":
    main()
