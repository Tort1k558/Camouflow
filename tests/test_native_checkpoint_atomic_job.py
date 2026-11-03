import json
import os
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows process/ACL integration')

from scripts import native_checkpoint_crash as control

FIXTURES = Path(__file__).resolve().parent / 'fixtures/glint_checkpoint_host'
PYTHON = Path(sys._base_executable).resolve()
STUB = FIXTURES / 'ack_child.py'


def invoke(root, stub=STUB, **overrides):
    kwargs = dict(owner_root=root, output=root / 'atomic-owned', cwd=FIXTURES,
        env=dict(os.environ), expected_binary_sha256=control.checksum(PYTHON), timeout_seconds=5)
    kwargs.update(overrides)
    return control.run_acknowledged_crash([str(PYTHON), '-B', str(stub)], **kwargs)


def test_atomic_create_does_not_use_the_racy_assign_after_start_path(tmp_path, monkeypatch):
    def forbidden_late_assignment(*args):
        raise AssertionError('Late job assignment must not be used')

    monkeypatch.setattr(control._OwnedJob, 'assign', forbidden_late_assignment)
    result = invoke(tmp_path)
    assert result['passed'], result
    assert result['job_assigned_at_creation'] and result['owned_process_cleanup_complete']


def test_owned_job_membership_does_not_follow_reused_global_parent_pid_links(tmp_path, monkeypatch):
    def forbidden_global_parent_snapshot(*args):
        raise AssertionError('Job ownership must not come from global reusable parent PID links')

    monkeypatch.setattr(control.WindowsProcessTreeReader, 'read_tree', forbidden_global_parent_snapshot)
    result = invoke(tmp_path)
    assert result['passed'], result
    assert result['job_assigned_at_creation'] and result['owned_process_cleanup_complete']


def test_failed_initial_membership_check_still_cleans_the_already_owned_child(tmp_path, monkeypatch):
    def reject(*args):
        raise ValueError('Injected initial membership rejection')

    monkeypatch.setattr(control._OwnedJob, 'require_member', reject)
    result = invoke(tmp_path)
    assert not result['passed'] and 'membership rejection' in result['error']
    assert result['job_assigned_at_creation'] and result['owned_process_cleanup_complete']
    with pytest.raises(OSError) as missing:
        control.WindowsProcessTreeReader().read(result['owned_pid'])
    assert isinstance(missing.value, ProcessLookupError) or missing.value.winerror == 87


def test_early_breakaway_is_rejected_by_the_job_before_acknowledgment(tmp_path):
    result = invoke(tmp_path, FIXTURES / 'atomic_child.py')
    assert result['passed'], result
    assert result['job_assigned_at_creation'] and result['owned_process_cleanup_complete']
    receipt = Path(result['profile']) / 'early-breakaway.json'
    assert json.loads(receipt.read_bytes()) == {'winerror': 5}


def test_ambiguous_windows_environment_rejects_without_launching_a_child(tmp_path):
    environment = dict(os.environ)
    environment['GLINT_HOST_DUPLICATE'] = 'one'
    environment['glint_host_duplicate'] = 'two'
    result = invoke(tmp_path, env=environment)
    assert not result['passed'] and 'unambiguous environment' in result['error']
    assert 'owned_pid' not in result and result['owned_process_cleanup_complete']
