"""Prevent simultaneous desktop/CLI owners of a local workspace."""

from PyQt6.QtCore import QLockFile

from app.storage.db import SETTINGS_DIR


class WorkspaceInUseError(RuntimeError):
    """Another desktop or CLI process owns this workspace."""


def acquire_workspace_lock():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(SETTINGS_DIR / "application.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise WorkspaceInUseError(
            "This workspace is already open. Close CamouFlow before using the CLI."
        )
    return lock
