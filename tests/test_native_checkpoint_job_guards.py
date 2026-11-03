from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import native_checkpoint_process as process


def job_with_pids(pids):
    kernel = SimpleNamespace(GetProcessId=Mock(side_effect=pids), CloseHandle=Mock(return_value=True))
    return SimpleNamespace(kernel=kernel, terminate=Mock(), active=Mock(return_value=0))


@pytest.mark.parametrize('pids', [[], list(range(1, 514)), [1, 1], [0], [2]],
                         ids=['empty', 'over-limit', 'duplicate', 'invalid', 'missing-root'])
def test_invalid_job_membership_closes_every_held_handle_before_rejecting(monkeypatch, pids):
    handles = list(range(1000, 1000 + len(pids)))
    job = job_with_pids(pids)
    reader = SimpleNamespace(read=Mock())
    monkeypatch.setattr(process, '_owned_job_handles', lambda _: handles)
    with pytest.raises(ValueError, match='Owned'):
        process.sample_owned_job(job, reader, SimpleNamespace(pid=1, created_100ns=100))
    reader.read.assert_not_called()
    assert job.kernel.CloseHandle.call_count == len(handles)


def test_member_older_than_trusted_root_rejects_without_returning_totals(monkeypatch):
    job = job_with_pids([1, 2])
    root = SimpleNamespace(pid=1, created_100ns=100)
    older = SimpleNamespace(pid=2, created_100ns=99)
    reader = SimpleNamespace(read=Mock(side_effect=[root, older]))
    monkeypatch.setattr(process, '_owned_job_handles', lambda _: [1000, 1001])
    with pytest.raises(ValueError, match='predates'):
        process.sample_owned_job(job, reader, root)
    assert job.kernel.CloseHandle.call_count == 2


def test_membership_change_during_measurement_is_not_a_partial_success(monkeypatch):
    job = job_with_pids([1, 1, 2])
    root = SimpleNamespace(pid=1, created_100ns=100)
    reader = SimpleNamespace(read=Mock(return_value=root))
    snapshots = iter(([1000], [1001, 1002]))
    monkeypatch.setattr(process, '_owned_job_handles', lambda _: next(snapshots))
    with pytest.raises(ValueError, match='membership changed'):
        process.sample_owned_job(job, reader, root)
    assert reader.read.call_args_list[0].kwargs == {'expected_created_100ns': 100}
    assert reader.read.call_args_list[1].kwargs == {'expected_created_100ns': 100}
    assert job.kernel.CloseHandle.call_count == 3


@pytest.mark.parametrize('budget', [True, False, 0, -1, float('nan'), float('inf'), 6, '5'])
def test_invalid_cleanup_budget_never_touches_a_job(budget):
    job = Mock()
    with pytest.raises(ValueError, match='deadline'):
        process.terminate_owned_job(job, timeout=budget)
    assert job.mock_calls == []
