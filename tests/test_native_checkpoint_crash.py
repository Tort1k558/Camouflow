import copy
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows process/ACL integration')

from scripts import native_checkpoint_crash as control

FIXTURES = Path(__file__).resolve().parent / 'fixtures/glint_checkpoint_host'
PYTHON = Path(sys._base_executable).resolve()
STUB = FIXTURES / 'ack_child.py'


def invoke(root, mode='valid', *, extra=None, timeout=5):
    return control.run_acknowledged_crash(
        [str(PYTHON), '-B', str(STUB), '--mode=' + mode, *(extra or [])],
        owner_root=root, output=root / 'owned-crash', cwd=FIXTURES, env=dict(os.environ),
        expected_binary_sha256=control.checksum(PYTHON), timeout_seconds=timeout)


@pytest.mark.parametrize('mode,minimum_processes', [('valid', 1), ('descendant', 2)])
def test_qualified_ack_kills_only_its_owned_job_and_children(tmp_path, mode, minimum_processes):
    measured = invoke(tmp_path, mode)
    assert measured['passed'], measured
    assert measured['qualified_termination']
    assert measured['exit_code'] == control.FORCED_EXIT_CODE
    assert measured['remaining_job_processes'] == 0
    assert measured['owned_process_cleanup_complete']
    assert len(measured['observed_processes']) >= minimum_processes
    assert measured['ack_to_exit_seconds'] <= 2
    assert not measured['gtest_completed'] and not measured['recovery_measured']


@pytest.mark.parametrize('mode', ['wrong-challenge', 'wrong-profile', 'exit', 'missing'])
def test_unqualified_ack_or_early_exit_is_never_success(tmp_path, mode):
    measured = invoke(tmp_path, mode, timeout=0.5 if mode == 'missing' else 5)
    assert not measured['passed'] and not measured['qualified_termination']
    assert measured['owned_process_cleanup_complete']
    assert 'error' in measured


def test_forged_foreign_pid_does_not_kill_the_foreign_sentinel(tmp_path):
    sentinel = subprocess.Popen([str(PYTHON), '-c', 'import time; time.sleep(60)'],
                                creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        measured = invoke(tmp_path, 'foreign', extra=['--foreign-pid=' + str(sentinel.pid)])
        assert not measured['passed'] and not measured['qualified_termination']
        assert 'PID' in measured['error']
        assert measured['owned_process_cleanup_complete']
        assert sentinel.poll() is None
    finally:
        sentinel.terminate()
        sentinel.wait(timeout=5)


@pytest.mark.parametrize('field,value', [
    ('schema', True), ('schema', 1.0), ('pid', True), ('pid', 2),
    ('challenge', 'wrong'), ('acknowledged', 1), ('acknowledged', False),
    ('workers', True), ('workers', 0), ('workers', 513), ('workers', 1.5),
    ('scope', 'document-only'), ('profile', 'relative/profile'), ('profile', None),
])
def test_receipt_fields_are_strict_not_truthy(tmp_path, field, value):
    profile = tmp_path / 'profile'
    profile.mkdir()
    valid = dict(schema=1, pid=1, challenge='a' * 64, profile=str(profile),
                 acknowledged=True, workers=1, scope='document-and-worker-cookie-prefix')
    invalid = copy.deepcopy(valid)
    invalid[field] = value
    with pytest.raises(ValueError):
        control.validate_ack(invalid, pid=1, challenge='a' * 64, profile=profile)


def test_existing_output_is_not_modified(tmp_path):
    output = tmp_path / 'owned-crash'
    output.mkdir()
    marker = output / 'preserve.txt'
    marker.write_text('protected', encoding='utf-8')
    with pytest.raises(ValueError, match='fresh'):
        invoke(tmp_path)
    assert marker.read_text(encoding='utf-8') == 'protected'


def test_wrong_executable_digest_rejects_before_output_creation(tmp_path):
    with pytest.raises(ValueError, match='binding'):
        control.run_acknowledged_crash([str(PYTHON)], owner_root=tmp_path,
            output=tmp_path / 'owned-crash', cwd=FIXTURES, env=dict(os.environ),
            expected_binary_sha256='0' * 64)
    assert not (tmp_path / 'owned-crash').exists()
