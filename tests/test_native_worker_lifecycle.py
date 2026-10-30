import copy
import asyncio
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from test_native_gpu import profile_identity_readback_observation
from test_native_protected_history import runs as screen_runs


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'native/drafts/environment/first-script'


@pytest.fixture
def probes(monkeypatch):
    monkeypatch.syspath_prepend(str(FIXTURE))
    return {name: runpy.run_path(str(FIXTURE / (name + '.py'))) for name in
            ('retained_worker_lifecycle', 'controlled_service_workers', 'lifecycle')}


@pytest.fixture
def worker_runs(screen_runs):
    graphics = profile_identity_readback_observation()['document']
    token = 'a' * 48
    for run in screen_runs:
        worker_rows = {}
        for kind in ('dedicated', 'shared', 'service'):
            for script_type in ('classic', 'module'):
                name = kind + '-' + script_type
                canvas = dict(float16Available=True, rows=[copy.deepcopy(row)
                    for row in run['canvas_before']['rows'] if row['kind'] == 'offscreen'])
                worker_rows[name] = dict(request='initial-' + name, token=token, kind=name,
                    location=f'http://127.0.0.1:1234/owned-retained-{kind}.js?type={script_type}&token={token}',
                    instanceId='instance-' + name, timeOrigin=12345.5, sequence=1,
                    observed=dict(canvas=canvas, gpu=copy.deepcopy(graphics),
                                  audio=dict(available=False, reason='API unavailable')))
        before = dict(rootTimeOrigin=12345.5, persisted=False, workers=worker_rows)
        after = copy.deepcopy(before)
        after['persisted'] = True
        for name, row in after['workers'].items():
            row.update(request='restored-' + name, sequence=2)
        run.update(worker_lifecycle_before=before, worker_lifecycle_after=after,
                   worker_lifecycle_cleanup={'closed': True}, post_surfaces_screen_verified=True,
                   surfaces_before={'gpu': copy.deepcopy(graphics)})
    return screen_runs


def bind_worker_summaries(probes, runs):
    worker = probes['retained_worker_lifecycle']
    for run in runs:
        run['worker_lifecycle_validation'] = worker['validate_pair'](
            run['worker_lifecycle_before'], run['worker_lifecycle_after'],
            canvas_document=run['canvas_before'], document_gpu=run['surfaces_before']['gpu'])


def test_all_six_workers_are_required_without_counting_unavailable_audio(probes, worker_runs):
    bind_worker_summaries(probes, worker_runs)
    result = probes['retained_worker_lifecycle']['validate_runs'](worker_runs)
    assert result['passed'] and len(result['runs']) == 2
    assert all(row['worker_classes'] == 6 and all(worker['canvas_cases'] == 16
        and worker['audio_api_available'] is False and worker['audio_readback_verified'] is False
        for worker in row['workers']) for row in result['runs'])


@pytest.mark.parametrize('fault', ['missing', 'bool-sequence', 'wrong-class', 'external-url', 'duplicate-instance',
    'owner-clock', 'pack-state', 'canvas', 'cleanup', 'resources', 'fake-summary'])
def test_worker_lifecycle_rejects_partial_forged_or_invalid_records(probes, worker_runs, fault):
    bind_worker_summaries(probes, worker_runs)
    row = worker_runs[0]
    first = row['worker_lifecycle_before']
    worker = first['workers']['shared-classic']
    if fault == 'missing':
        first['workers'].pop('service-module')
    elif fault == 'bool-sequence':
        worker['sequence'] = True
    elif fault == 'wrong-class':
        worker['kind'] = 'service-classic'
    elif fault == 'external-url':
        worker['location'] = 'https://not-owned.invalid/worker.js'
    elif fault == 'duplicate-instance':
        worker['instanceId'] = first['workers']['dedicated-classic']['instanceId']
    elif fault == 'owner-clock':
        first['rootTimeOrigin'] = False
    elif fault == 'pack-state':
        worker['observed']['gpu']['webgl']['webgl2']['scene']['packState']['skipRows'] = 999
    elif fault == 'canvas':
        worker['observed']['canvas']['rows'][0]['observed']['hash'] = 'b' * 64
    elif fault == 'cleanup':
        row['worker_lifecycle_cleanup']['closed'] = False
    elif fault == 'resources':
        row['runtime_resources_released'] = False
    else:
        row['worker_lifecycle_validation']['worker_classes'] = 0
    with pytest.raises(ValueError):
        probes['retained_worker_lifecycle']['validate_runs'](worker_runs)


@pytest.fixture
def controlled_runs(probes, worker_runs):
    bind_worker_summaries(probes, worker_runs)
    for run in worker_runs:
        observed = run['phases'][0]['observed']
        snapshots = {role: dict(snapshot=copy.deepcopy(row['snapshot']), persisted=True,
            parent=None if role == 'main' else 'cross' if role == 'nested-return' else 'main',
            children_sizes={}) for role, row in observed.items()}
        for role, row in snapshots.items():
            if row['parent'] is not None:
                snapshots[row['parent']]['children_sizes'][role] = copy.deepcopy(observed[role]['embedding_size'])
        history = dict(registered=True, events=[True], timedOut=False, protocolErrors=[], snapshots=snapshots)
        results = []
        for kind in ('service-classic', 'service-module'):
            reference = run['worker_lifecycle_after']['workers'][kind]
            url = reference['location']
            client_url = ('http://127.0.0.1:1234/owned-retained/' + reference['token']
                          + '/' + kind.split('-', 1)[1] + '/screen')
            controller = dict(scriptURL=url, state='activated')
            first = dict(controller=controller, worker=copy.deepcopy(reference),
                         document=dict(url=client_url, timeOrigin=98765, persisted=False))
            first['worker'].update(request='controlled-initial-' + kind, sequence=3)
            restored = copy.deepcopy(first)
            restored['document']['persisted'] = True
            restored['worker'].update(request='controlled-restored-' + kind, sequence=4)
            restarted = copy.deepcopy(restored)
            restarted['worker'].update(request='controlled-restarted-' + kind, sequence=1,
                                       instanceId='restarted-' + kind, timeOrigin=13345.5)
            version = dict(versionId='owned-' + kind, scriptURL=url, status='activated', runningStatus='running')
            results.append(dict(kind=kind, client_url=client_url, passed=True, forced_restart_verified=True,
                history_navigation={'type': 'BackForwardCacheRestore'}, initial=first, restored=restored,
                restarted=restarted, version_before_stop=version,
                stopped_event={**version, 'runningStatus': 'stopped'}, version_after_restart=copy.deepcopy(version),
                initial_screen=copy.deepcopy(observed), bfcache_state=copy.deepcopy(history),
                post_restart_history=copy.deepcopy(history)))
        run['controlled_service_validation'] = dict(passed=True, results=results)
    return worker_runs


def validate_controlled(probes, runs):
    screen = probes['lifecycle']
    return probes['controlled_service_workers']['validate_runs'](
        runs, screen['restored_observations'], screen['validate_page'])


def test_controlled_clients_require_actual_stop_restart_and_retained_document_evidence(probes, controlled_runs):
    result = validate_controlled(probes, controlled_runs)
    assert result['passed'] and result['controlled_clients'] == result['forced_restarts'] == 4
    assert all(row['forced_restart_verified'] and not row['worker_audio_readback_verified']
               for row in result['results'])
    assert result['retained_gpu_objects_verified'] is result['webgpu_readback_verified'] is False


@pytest.mark.parametrize('fault', ['reload', 'no-stop', 'wrong-version', 'wrong-script', 'no-running',
    'same-instance', 'old-clock', 'wrong-sequence', 'replaced-document', 'replayed-request', 'missing-class',
    'wrong-scope', 'bool-clock', 'invalid-version', 'screen'])
def test_controller_restart_cannot_pass_from_flags_alone(probes, controlled_runs, fault):
    group = controlled_runs[0]['controlled_service_validation']
    row = group['results'][0]
    if fault == 'reload':
        row['history_navigation']['type'] = 'Navigation'
    elif fault == 'no-stop':
        row['stopped_event']['runningStatus'] = 'running'
    elif fault == 'wrong-version':
        row['stopped_event']['versionId'] = 'not-owned'
    elif fault == 'wrong-script':
        row['stopped_event']['scriptURL'] = 'https://not-owned.invalid/worker.js'
    elif fault == 'no-running':
        row['version_after_restart']['runningStatus'] = 'starting'
    elif fault == 'same-instance':
        row['restarted']['worker']['instanceId'] = row['restored']['worker']['instanceId']
    elif fault == 'old-clock':
        row['restarted']['worker']['timeOrigin'] = row['restored']['worker']['timeOrigin']
    elif fault == 'wrong-sequence':
        row['restarted']['worker']['sequence'] = 2
    elif fault == 'replaced-document':
        row['restarted']['document']['timeOrigin'] += 1
    elif fault == 'replayed-request':
        row['restarted']['worker']['request'] = row['initial']['worker']['request']
    elif fault == 'missing-class':
        group['results'].pop()
    elif fault == 'wrong-scope':
        row['client_url'] = 'http://127.0.0.1:1234/not-controlled'
    elif fault == 'bool-clock':
        for phase in ('initial', 'restored', 'restarted'):
            row[phase]['document']['timeOrigin'] = False
    elif fault == 'invalid-version':
        for name in ('version_before_stop', 'stopped_event', 'version_after_restart'):
            row[name]['versionId'] = ''
    else:
        row['post_restart_history']['snapshots']['main']['snapshot']['screen']['width'] = 999
    with pytest.raises(ValueError):
        validate_controlled(probes, controlled_runs)


def test_service_lifecycle_flag_requires_explicit_worker_mode_before_output_creation(tmp_path):
    output = tmp_path / 'not-created'
    result = subprocess.run([sys.executable, str(FIXTURE / 'protected_history_runtime.py'),
        '--executable', str(tmp_path / 'chrome.exe'), '--work-dir', str(output),
        '--driver-stage', str(tmp_path / 'driver'), '--probe', 'canvas', '--verify-service-lifecycle'],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 2 and '--verify-service-lifecycle requires --probe retained-workers' in result.stderr
    assert not output.exists()


@pytest.mark.parametrize('cleanup_fails', [False, True])
def test_controlled_client_cleanup_preserves_the_primary_failure(probes, worker_runs, cleanup_fails):
    page = SimpleNamespace(goto=AsyncMock(side_effect=RuntimeError('owned navigation failed')))
    session = SimpleNamespace(send=AsyncMock(), detach=AsyncMock(
        side_effect=RuntimeError('owned detach failed') if cleanup_fails else None))
    context = SimpleNamespace(new_page=AsyncMock(return_value=page),
                              new_cdp_session=AsyncMock(return_value=session))
    with pytest.raises(RuntimeError, match='owned navigation failed') as error:
        asyncio.run(probes['controlled_service_workers']['capture'](
            context, None, {}, worker_runs[0], probes['lifecycle'], None, {}))
    session.detach.assert_awaited_once()
    if cleanup_fails:
        assert any('cleanup failed' in note for note in error.value.__notes__)


def test_published_worker_service_runtime_binds_actual_sources_and_all_four_restarts(sources_before_retained_gpu):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'worker-service75-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['selected_probe'] == 'retained-workers' and record['verify_service_lifecycle']
    assert record['worker_classes_per_mode'] == 6 and record['offscreen_cases_per_worker_phase'] == 16
    assert record['controlled_clients'] == record['forced_service_restarts'] == 4
    assert {row['mode'] for row in record['runs']} == {'manager-desktop', 'manager-mobile-web'}
    for run in record['runs']:
        assert run['passed'] and run['worker_cleanup_verified'] and run['runtime_resources_released']
        assert run['browser_connection_closed'] and run['remaining_observed_processes'] == 0
        assert len(run['controlled_service_cases']) == 2
        for case in run['controlled_service_cases']:
            assert case['version_state_chain'] == ['running', 'stopped', 'running']
            assert case['worker_instance_changed'] and case['worker_epoch_increased']
            assert case['restarted_sequence'] == 1 and case['owning_document_unchanged']
            assert case['all_six_retained_screens_verified']
            assert len(case['normalized_phase_sha256']) == 3 and len(set(case['normalized_phase_sha256'])) == 1
            assert case['worker_audio_api_available'] is case['worker_audio_readback_verified'] is False
    for relative, expected in record['measured_inputs_sha256'].items():
        actual = (sources_before_retained_gpu['sha256'][relative] if relative in sources_before_retained_gpu['sha256']
                  else hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        assert actual == expected, relative
    assert all(record[key] is False for key in ('stop_all_workers_used', 'worker_audio_readback_verified',
        'retained_gpu_objects_verified', 'webgpu_readback_verified', 'cross_session_screenshot_fixed',
        'privacy_admitted', 'production_admitted', 'full_current_source_regression_passed'))
    default = record['default_mode_repeat']
    assert default['passed'] and default['postguards_passed'] and default['measurement_complete']
    assert default['worker_diagnostics_enabled'] is default['service_restart_enabled'] is False


def test_published_worker_archive_is_selected_and_binds_current_integrated_sources(sources_before_retained_gpu):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'retained-worker-lifecycle-preparation.json').read_bytes())
    assert record['selected'] and record['runtime_verified'] is False
    assert hashlib.sha256((directory / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    for row in record['sources']:
        relative = row['source']
        actual = (sources_before_retained_gpu['sha256'][relative] if relative in sources_before_retained_gpu['sha256']
                  else hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        assert actual == row['staged_sha256']


def test_published_full_binding_repair_pass_does_not_claim_the_later_worker_extension():
    path = ROOT / 'native/drafts/environment/canonical-python75-historical-binding-repair-observations.json'
    record = json.loads(path.read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'] == '87ae4ed316bf1b68c4882e531e179b5f847a6152'
    assert record['counts'] == dict(tests=4768, failures=0, errors=0, skipped=1, passed=4767)
    assert 'before the worker/service' in record['scope']
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
