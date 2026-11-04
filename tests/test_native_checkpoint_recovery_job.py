import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows process/ACL integration')

from scripts.native_checkpoint_recovery import _run_recovery_process
from scripts.verify_native_checkpoint_units import run_tests

PYTHON = str(Path(sys._base_executable).resolve())
PARENT = (
    'import subprocess,sys,time; from pathlib import Path; '
    'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
    'marker=Path(sys.argv[1]); pending=marker.with_suffix(".tmp"); '
    'pending.write_text(str(child.pid),encoding="ascii"); pending.replace(marker); '
    'time.sleep(60 if sys.argv[2]=="timeout" else 0); '
    'sys.exit(7 if sys.argv[2]=="fail" else 0)'
)


def require_exited(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        assert ctypes.get_last_error() == 87
        return
    try:
        assert kernel.WaitForSingleObject(handle, 0) == 0
    finally:
        kernel.CloseHandle(handle)


@pytest.mark.parametrize('runner', [_run_recovery_process, run_tests])
@pytest.mark.parametrize('mode', ['exit', 'timeout', 'fail'])
def test_recovery_cleans_descendants_even_after_parent_exit(tmp_path, mode, runner):
    marker = tmp_path / 'child-pid.txt'
    sentinel = subprocess.Popen([PYTHON, '-c', 'import time; time.sleep(60)'],
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        args = ([PYTHON, '-c', PARENT, str(marker), mode],)
        kwargs = dict(source=tmp_path, env=dict(os.environ),
            log=tmp_path / 'recovery.log', timeout=2)
        if mode == 'timeout':
            with pytest.raises(subprocess.TimeoutExpired):
                runner(*args, **kwargs)
        elif mode == 'fail':
            with pytest.raises(subprocess.CalledProcessError) as observed:
                runner(*args, **kwargs)
            assert observed.value.returncode == 7
        else:
            runner(*args, **kwargs)
        require_exited(int(marker.read_text(encoding='ascii')))
        assert sentinel.poll() is None
    finally:
        sentinel.terminate()
        sentinel.wait(timeout=5)
