import sys
import os
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows process/ACL integration')

from scripts import native_checkpoint_recovery as recovery
from scripts.verify_native_checkpoint_units import run_tests
from test_native_checkpoint_recovery_job import PARENT, PYTHON, require_exited


@pytest.mark.parametrize('interruption', [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize('runner', [recovery._run_recovery_process, run_tests])
def test_cancellation_propagates_only_after_owned_tree_cleanup(tmp_path, monkeypatch, interruption, runner):
    marker = tmp_path / 'child-pid.txt'
    children = []
    actual_constructor = recovery.OwnedJobProcess

    def interrupted_process(*args, **kwargs):
        child = actual_constructor(*args, **kwargs)
        children.append(child)
        actual_wait = child.wait
        first_wait = True

        def wait(timeout):
            nonlocal first_wait
            if first_wait:
                first_wait = False
                deadline = time.monotonic() + 3
                while not marker.exists():
                    assert child.poll() is None
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
                raise interruption('intentional host-test interruption')
            return actual_wait(timeout)

        child.wait = wait
        return child

    sentinel = subprocess.Popen([PYTHON, '-c', 'import time; time.sleep(60)'],
        creationflags=subprocess.CREATE_NO_WINDOW)
    monkeypatch.setattr(recovery, 'OwnedJobProcess', interrupted_process)
    try:
        with pytest.raises(interruption, match='intentional host-test interruption'):
            runner(
                [PYTHON, '-c', PARENT, str(marker), 'timeout'], source=tmp_path,
                env=dict(os.environ), log=tmp_path / 'cancel.log', timeout=60)
        assert len(children) == 1 and children[0]._handle is None
        require_exited(children[0].pid)
        require_exited(int(marker.read_text(encoding='ascii')))
        assert sentinel.poll() is None
    finally:
        sentinel.terminate()
        sentinel.wait(timeout=5)
