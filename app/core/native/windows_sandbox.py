"""AppContainer read/execute access for an owned, verified installation stage only."""

import ctypes
import stat
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

# The two installation capabilities used by Chromium's ConfigureAppContainerSandbox.
INSTALL_CAPABILITY_SIDS = (
    "S-1-15-3-1024-3424233489-972189580-2057154623-747635277-1604371224-316187997-3786583170-1043257646",
    "S-1-15-3-1024-2302894289-466761758-1166120688-1039016420-2430351297-4240214049-4028510897-3317428798",
)
MAX_STAGE_PATHS = 50001


def _stage_snapshot(payload: Path) -> dict[Path, tuple[int, int, int, int]]:
    pending = [payload]
    checked = {}
    while pending:
        path = pending.pop()
        info = path.lstat()
        if (path.resolve(strict=True) != path or info.st_file_attributes & 0x400
                or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
                or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
            raise ValueError("Sandbox installation stage contains a link or non-regular object")
        checked[path] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        if len(checked) + len(pending) > MAX_STAGE_PATHS:
            raise ValueError("Sandbox installation stage exceeds its object limit")
        if stat.S_ISDIR(info.st_mode):
            children = list(path.iterdir())
            if len(checked) + len(pending) + len(children) > MAX_STAGE_PATHS:
                raise ValueError("Sandbox installation stage exceeds its object limit")
            pending.extend(children)
    return checked


def _system_icacls() -> Path:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel.GetSystemDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    count = kernel.GetSystemDirectoryW(buffer, len(buffer))
    if not 0 < count < len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    executable = Path(buffer.value) / "icacls.exe"
    if executable.resolve(strict=True) != executable or not executable.is_file():
        raise ValueError("Windows system ACL utility is missing or linked")
    return executable


def configure_staged_sandbox_access(payload: Path, stage: Path) -> None:
    """Call only after archive/manifest verification and before publishing the release."""
    if sys.platform != "win32":
        raise OSError("Installation capability configuration requires Windows")
    if (not isinstance(stage, Path) or not isinstance(payload, Path)
            or not stage.is_absolute() or stage.resolve(strict=True) != stage
            or not stage.is_dir() or not stage.name.startswith("native-install-")
            or payload.parent != stage or payload.name != "payload"
            or payload.resolve(strict=True) != payload or not payload.is_dir()):
        raise ValueError("Sandbox access may only be configured on the owned installation payload")
    before = _stage_snapshot(payload)
    command = [str(_system_icacls()), str(payload), "/grant",
               *("*" + sid + ":(OI)(CI)(RX)" for sid in INSTALL_CAPABILITY_SIDS), "/Q"]
    try:
        subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                       check=True, timeout=30,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.SubprocessError as error:
        raise OSError("Could not configure Native installation sandbox read/execute access") from error
    if _stage_snapshot(payload) != before:
        raise ValueError("Installation payload identity or content metadata changed during ACL configuration")
