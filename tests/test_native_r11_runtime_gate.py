import asyncio
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest


DIRECTORY = Path(__file__).resolve().parents[1] / 'native/drafts/upstream-156-image-r11'


def test_published_runtime_gates_keep_baseline_selected_and_unverified_scopes_separate():
    record = json.loads((DIRECTORY / 'runtime-gate-observations.json').read_bytes())
    native = json.loads((DIRECTORY / 'native-all-observations.json').read_bytes())
    for key in ('candidate_manifest_sha256', 'runtime_core_sha256_measured', 'receipt_sha256'):
        assert record[key] == native[key]
    assert record['passed'] and record['measurement_complete']
    assert not any(record[key] for key in ('privacy_admitted', 'production_admitted', 'full_objective_passed',
        'installed_package_verified', 'renderer_crash_tested', 'uncheckpointed_browser_crash_durability_tested',
        'selected_controller_crash_tested', 'selected_policy_permissions_and_proxy_verified'))
    baseline, selected = record['baseline'], record['selected']
    for phase, name in ((baseline, 'measure_runtime_gate.py'), (selected, 'measure_profile_restarts.py')):
        assert phase['passed'] and phase['postguards_passed']
        assert phase['collector_sha256'] == hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest()
    assert baseline['controller_driver_selection_verified'] and baseline['fixture_threads_closed']
    assert baseline['source_sha256'] == hashlib.sha256((DIRECTORY.parents[2] / 'scripts/verify_native_runtime.py').read_bytes()).hexdigest()
    assert baseline['checks_passed'] == len(baseline['checks']) == len(set(baseline['checks'])) == 18
    assert {'cross-process-owner-exclusion', 'browser-crash-restart-preserves-committed-storage',
            'authenticated-http-proxy-no-direct-dns-route', 'existing-recorder-capture-and-replay',
            'existing-browser-interface-and-scenario-executor', 'native-profile-backup-restore-storage-and-engine-isolation',
            'controller-kill-exits-observed-process-tree-and-restores-five-stores',
            'configured-permissions-isolation-revocation-and-restart'} <= set(baseline['checks'])
    assert [row['preset'] for row in selected['phases']] == ['native', 'gamma-1400-contrast-300']
    assert selected['fixture_thread_closed'] and selected['checkpoint_before_every_crash']
    assert selected['storage_scope'] == ['cookies', 'localStorage', 'IndexedDB', 'CacheStorage', 'service-worker registrations']
    rounds = [row for phase in selected['phases'] for row in phase['rounds']]
    assert len(rounds) == selected['browser_crashes'] == 6
    assert sum(row['concurrent_profiles'] for row in rounds) == selected['profile_round_executions'] == 18
    for phase in selected['phases']:
        assert phase['passed'] and [row['round'] for row in phase['rounds']] == [1, 2, 3]
        assert [row['crashed_profile'] for row in phase['rounds']] == [0, 1, 2]
    for row in rounds + baseline['multi_profile_restart_rounds']:
        assert row['concurrent_profiles'] == row['independent_drivers'] == 3
        assert row['remaining_owned_processes'] == 0 and row['checkpoint_before_crash']
        assert row['policy_capabilities'] == []
    earlier = record['earlier_attempt']
    assert earlier['original_result_preserved'] and not earlier['reviewed_controller_driver_selected']
    assert earlier['observed_bundle_sha256'] != earlier['pinned_bundle_sha256']
    assert earlier['observed_page_module_sha256'] != earlier['pinned_page_module_sha256']


@pytest.mark.parametrize('selected', [True, False])
def test_controller_driver_probe_checks_the_actual_child_search_order(monkeypatch, selected):
    import playwright

    collector = runpy.run_path(str(DIRECTORY / 'measure_runtime_gate.py'))
    expected = Path(playwright.__file__).resolve()
    captured = []
    def run(command, **kwargs):
        captured.append((command, kwargs))
        return SimpleNamespace(stdout=json.dumps(str(expected if selected else expected.with_name('unselected.py'))))
    monkeypatch.setattr(collector['subprocess'], 'run', run)
    if selected:
        assert asyncio.run(collector['verify_controller_driver']()) == dict(
            verified=True, same_package_path=True, browser_started=False)
    else:
        with pytest.raises(ValueError, match='shadows the explicitly selected Playwright'):
            asyncio.run(collector['verify_controller_driver']())
    command, options = captured[0]
    assert command[:3] == [collector['sys']._base_executable, '-B', '-c']
    assert options['timeout'] == 20 and options['check']
    assert options['env']['PYTHONPATH'] == (collector['sysconfig'].get_path('purelib')
        + os.pathsep + os.environ.get('PYTHONPATH', ''))


@pytest.mark.parametrize('mode', ['success', 'runtime-failure', 'log-cleanup-failure'])
def test_full_gate_keeps_partial_failures_and_closes_both_fixtures(monkeypatch, tmp_path, mode):
    from scripts import verify_native_runtime as runtime

    collector = runpy.run_path(str(DIRECTORY / 'measure_runtime_gate.py'))
    root = tmp_path / 'native-owned-r11-runtime'
    monkeypatch.setenv('CAMOUFLOW_DATA_DIR', str(root / 'workspace'))
    owner = SimpleNamespace(profile_dir=root, executable=tmp_path / 'owned.exe')
    async def child_driver():
        return dict(verified=True, same_package_path=True)
    async def verify(profile_root, executable, origin, proxy, *, checks):
        assert profile_root == root and executable == owner.executable
        assert origin.startswith('http://127.0.0.1:') and proxy.proxy_mode is True
        checks.append('owned-runtime-check')
        if mode == 'runtime-failure':
            raise ValueError('Injected failed storage check')
        return dict(passed=True)
    def close_logs(path):
        assert path == root
        if mode == 'log-cleanup-failure':
            raise OSError('Injected retained log handle')
    collector['measure'].__globals__['verify_controller_driver'] = child_driver
    monkeypatch.setattr(runtime, 'verify', verify)
    monkeypatch.setattr(runtime, 'close_owned_log_handlers', close_logs)
    result = asyncio.run(collector['measure'](lambda *args: owner, object()))
    assert result['fixture_threads_closed']
    assert result['passed'] == (mode == 'success')
    assert result['completed_checks'] == ['owned-runtime-check']
    assert result['controller_driver']['verified']
    if mode == 'runtime-failure':
        assert not result['measurement_complete'] and result['error_type'] == 'ValueError'
    if mode == 'log-cleanup-failure':
        assert result['measurement_complete'] and result['cleanup_errors'][0]['stage'] == 'logs'


def test_driver_or_database_mismatch_does_not_start_a_fixture(monkeypatch, tmp_path):
    from scripts import verify_native_runtime as runtime

    collector = runpy.run_path(str(DIRECTORY / 'measure_runtime_gate.py'))
    owner = SimpleNamespace(profile_dir=tmp_path / 'owned', executable=tmp_path / 'owned.exe')
    def server(*args):
        pytest.fail('Fixture must not start after a database or child driver mismatch')
    monkeypatch.setattr(runtime, 'FixtureServer', server)
    monkeypatch.setenv('CAMOUFLOW_DATA_DIR', str(tmp_path / 'wrong'))
    with pytest.raises(ValueError, match='owned runtime gate database'):
        asyncio.run(collector['measure'](lambda *args: owner, object()))
    monkeypatch.setenv('CAMOUFLOW_DATA_DIR', str(owner.profile_dir / 'workspace'))
    async def child_driver():
        raise ValueError('Injected wrong child driver')
    collector['measure'].__globals__['verify_controller_driver'] = child_driver
    with pytest.raises(ValueError, match='wrong child driver'):
        asyncio.run(collector['measure'](lambda *args: owner, object()))


@pytest.mark.parametrize('failure', ['', 'gamma-1400-contrast-300', 'short-result'])
def test_selected_restart_gate_requires_all_rounds_and_retains_earlier_success(monkeypatch, tmp_path, failure):
    from scripts import verify_native_runtime as runtime

    collector = runpy.run_path(str(DIRECTORY / 'measure_profile_restarts.py'))
    calls = []
    @dataclass
    class Configuration:
        rendering_preset: str = 'native'
    def make(name, config):
        return SimpleNamespace(profile_dir=tmp_path / name, executable=tmp_path / 'owned.exe')
    async def restarts(profile, executable, origin, *, rounds, profiles, configuration):
        assert rounds == profiles == 3 and origin.startswith('http://127.0.0.1:')
        calls.append(configuration.rendering_preset)
        if configuration.rendering_preset == failure:
            raise ValueError('Injected failed profile recovery')
        return [{'round': number} for number in range(1, 3 if failure == 'short-result' else 4)]
    monkeypatch.setattr(runtime, 'verify_multi_profile_restarts', restarts)
    result = asyncio.run(collector['measure'](make, Configuration()))
    assert result['fixture_thread_closed']
    assert result['passed'] == result['measurement_complete'] == (not failure)
    assert calls == ['native', 'gamma-1400-contrast-300']
    if failure == 'gamma-1400-contrast-300':
        assert result['phases'][0]['passed']
        assert not result['phases'][1]['passed'] and result['phases'][1]['error_type'] == 'ValueError'
    if failure == 'short-result':
        assert all(not phase['passed'] for phase in result['phases'])
