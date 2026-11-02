import asyncio
import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


DIRECTORY = Path(__file__).resolve().parents[1] / 'native/drafts/upstream-156-image-r11'


def test_actual_renderer_success_does_not_hide_uncheckpointed_browser_data_loss():
    record = json.loads((DIRECTORY / 'crash-recovery-observations.json').read_bytes())
    native = json.loads((DIRECTORY / 'native-all-observations.json').read_bytes())
    for key in ('candidate_manifest_sha256', 'runtime_core_sha256_measured', 'receipt_sha256'):
        assert record[key] == native[key]
    assert record['collector_sha256'] == hashlib.sha256((DIRECTORY / 'measure_crash_recovery.py').read_bytes()).hexdigest()
    for name, digest in record['source_sha256'].items():
        assert hashlib.sha256((DIRECTORY.parents[2] / name).read_bytes()).hexdigest() == digest
    assert record['measurement_complete'] and record['postguards_passed']
    assert record['owned_resources_closed'] and record['fixture_thread_closed'] and record['all_crash_requests_settled']
    assert not any(record[key] for key in ('passed', 'privacy_admitted', 'production_admitted',
        'full_recovery_admitted', 'uncheckpointed_browser_durability_verified', 'power_loss_tested'))
    assert record['renderer_phases_passed'] == 3 and record['browser_phases_passed'] == 0
    assert record['gpu_phases_passed'] == len(record['phases']) == 6
    assert record['unretrieved_future_warnings_in_final_log'] == 0
    assert {(row['kind'], row['mode']) for row in record['phases']} == {
        (kind, mode) for kind in ('renderer', 'browser')
        for mode in ('baseline', 'native', 'gamma-1400-contrast-300')}
    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    contexts = protected_contexts = 0
    for row in record['phases']:
        assert row['resources_closed'] and row['crash_request']['settled']
        assert row['survivor_preserved'] and row['in_process_lock_retained_until_teardown']
        assert row['crash_signal_observed'] and row['gpu_recovery_verified']
        assert not row['graceful_checkpoint_before_crash']
        assert row['before_state_sha256'] == row['after_state_sha256']
        expected = collector['expected_storage']('-'.join((row['kind'], row['mode'], 'victim')))
        assert row['storage_components'] == collector['storage_components'](row['restored_storage'], expected)
        if row['kind'] == 'renderer':
            assert row['passed'] and all(row['storage_components'].values())
            assert row['same_browser_preserved'] and row['browser_connected_after_crash']
            assert row['browser_disconnect_notifications'] == 0 and row['page_crash_notifications'] >= 1
        else:
            assert not row['passed'] and row['browser_restarted'] and not row['browser_connected_after_crash']
            assert row['browser_disconnect_notifications'] == 1
            assert row['storage_components'] == dict(cookie=False, local=False, indexed=True, cached=True, workers=True)
        for observed in (row['before_validation'], row['after_validation']):
            assert observed['contexts'] == 8 and observed['textures'] == 48
            contexts += observed['contexts']
            if row['protected']:
                protected_contexts += observed['contexts']
    assert contexts == record['observed_context_executions'] == 96
    assert protected_contexts == record['protected_context_executions'] == 64
    assert len(record['earlier_attempts']) == 2
    assert all(row['original_failure_preserved'] for row in record['earlier_attempts'])
    upstream = record['upstream_commit_evidence']
    assert upstream['revision'] == '5a93aa59e3043e747eff68659dcf7d20193d160e'
    assert not upstream['actual_per_test_flush_timing_measured']


def test_storage_service_worker_scope_does_not_replace_the_gpu_probe_worker(monkeypatch):
    from scripts import verify_native_runtime as runtime

    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    script = collector['storage_script']()
    assert "register('/worker.js', {scope: '/owned-crash-storage/'})" in script
    assert "new URL(worker.scope).pathname === '/owned-crash-storage/'" in script
    assert 'navigator.serviceWorker.ready' in script
    assert all(name in script for name in ('indexedDB', 'localStorage', 'document.cookie', 'caches.open'))
    monkeypatch.setattr(runtime, 'STORAGE', runtime.STORAGE.replace("register('/worker.js')", "register('/changed.js')"))
    with pytest.raises(ValueError, match='exact existing storage fixture'):
        collector['storage_script']()


def test_changed_fixture_is_rejected_before_a_server_can_start(monkeypatch):
    from scripts import verify_native_runtime as runtime
    from scripts import verify_native_gpu_readback

    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    monkeypatch.setattr(runtime, 'STORAGE', 'unsupported fixture')
    def server(*args):
        pytest.fail('Invalid source fixture must not leak a running HTTP server')
    monkeypatch.setattr(runtime, 'FixtureServer', server)
    with pytest.raises(ValueError, match='exact existing storage fixture'):
        asyncio.run(collector['measure'](None, None))


@pytest.mark.parametrize('fail', [False, True])
def test_crash_request_result_is_consumed_after_teardown(fail):
    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    async def run():
        async def request():
            await asyncio.sleep(0)
            if fail:
                raise OSError('Injected closed crash transport')
        task = asyncio.create_task(request())
        result = await collector['settle_crash_request'](task)
        assert task.done() and not task.cancelled() and result['settled']
        assert result.get('error_type') == ('OSError' if fail else None)
    asyncio.run(run())


def test_crash_observation_timeout_does_not_cancel_the_owned_request():
    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    async def run():
        released = asyncio.Event()
        task = asyncio.create_task(released.wait())
        with pytest.raises(RuntimeError, match='remains pending'):
            await collector['settle_crash_request'](task, timeout=0.001)
        assert not task.done() and not task.cancelled()
        released.set()
        assert (await collector['settle_crash_request'](task))['settled']
    asyncio.run(run())


@pytest.mark.parametrize('lost', ['cookie', 'local', 'indexed', 'cached', 'workers'])
def test_uncheckpointed_storage_loss_is_reported_per_component(lost):
    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    expected = collector['expected_storage']('owned-value')
    observed = copy.deepcopy(expected)
    observed[lost] = 0 if lost == 'workers' else None
    result = collector['storage_components'](observed, expected)
    assert result[lost] is False and sum(result.values()) == 4
    assert observed[lost] != expected[lost]


@pytest.mark.parametrize('change', ['missing', 'extra', 'not-a-map', 'boolean-workers'])
def test_storage_evidence_cannot_silently_drop_a_store_or_coerce_its_type(change):
    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    expected = collector['expected_storage']('owned-value')
    observed = copy.deepcopy(expected)
    if change == 'boolean-workers':
        observed['workers'] = True
        assert collector['storage_components'](observed, expected)['workers'] is False
        return
    if change == 'missing':
        observed.pop('cookie')
    elif change == 'extra':
        observed['sessionStorage'] = 'unrequested'
    else:
        observed = None
    with pytest.raises(ValueError, match='five exact persistent store'):
        collector['storage_components'](observed, expected)


@pytest.mark.parametrize('current', [{}, {10: {'started': 'reused-pid'}}])
def test_cleanup_never_confuses_a_reused_pid_with_the_owned_process(monkeypatch, current):
    from scripts import verify_native_runtime as runtime

    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    calls = []
    def snapshot():
        calls.append(True)
        return current
    monkeypatch.setattr(runtime, 'process_snapshot', snapshot)
    asyncio.run(collector['wait_owned_exit']({10: {'started': 'owned-created'}}))
    assert calls == [True]


def test_cleanup_snapshot_failure_is_not_a_false_zero_remaining_processes(monkeypatch):
    from scripts import verify_native_runtime as runtime

    collector = runpy.run_path(str(DIRECTORY / 'measure_crash_recovery.py'))
    def snapshot():
        raise OSError('Injected process reader failure')
    monkeypatch.setattr(runtime, 'process_snapshot', snapshot)
    with pytest.raises(OSError, match='reader failure'):
        asyncio.run(collector['wait_owned_exit']({10: {'started': 'owned-created'}}))
