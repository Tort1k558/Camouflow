import asyncio
import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

from test_native_retained_gpu_objects import pair, runs as document_runs


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment/first-script'


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.syspath_prepend(str(DIRECTORY))
    return runpy.run_path(str(DIRECTORY / 'retained_gpu_worker_objects.py'))


def worker_pair(probe, mode='desktop'):
    documents, _ = pair(mode)
    token = hashlib.sha256(mode.encode()).hexdigest()[:48]
    before = dict(rootTimeOrigin=documents['main']['timeOrigin'], persisted=False, workers={})
    for index, kind in enumerate(sorted(probe['lifecycle'].WORKER_KINDS)):
        worker_class, script_type = kind.split('-')
        observed = copy.deepcopy(documents[sorted(documents)[index]]['observed'])
        observed.update(id=mode + '/gpu/' + kind, timeOrigin=2000000 + index)
        before['workers'][kind] = dict(request='before/' + kind, token=token, kind=kind,
            location=f'http://localhost:54321/owned-retained-{worker_class}.js?token={token}&type={script_type}',
            instanceId=mode + '/worker/' + kind, timeOrigin=2000000 + index, sequence=1, observed=observed)
    after = copy.deepcopy(before)
    after['persisted'] = True
    for kind, value in after['workers'].items():
        value.update(request='after/' + kind, sequence=2)
        value['observed']['read'] = 2
    return before, after


def forced_cases(probe, start):
    cases = []
    before = start
    for index, kind in enumerate(('service-classic', 'service-module')):
        after = copy.deepcopy(before)
        for name, value in after['workers'].items():
            value['request'] = f'forced/{index}/{name}'
            value['sequence'] += 1
            value['observed']['read'] += 1
        target = after['workers'][kind]
        target.update(instanceId=target['instanceId'] + '/restart', timeOrigin=target['timeOrigin'] + 1000, sequence=1)
        target['observed'].update(id=target['observed']['id'] + '/restart', timeOrigin=target['timeOrigin'], read=1)
        comparison = probe['validate_restart_pair'](before, after, kind=kind)
        events = [dict(versionId=str(index), registrationId=str(index), status='activated',
            scriptURL=before['workers'][kind]['location'], runningStatus=status)
            for status in ('running', 'stopped', 'running')]
        cases.append(dict(kind=kind, passed=True, before=before, after=after, comparison=comparison,
            version_events=events, request_event_offset=0, stopped_event_index=1, restarted_event_index=2))
        before = after
    return cases


def worker_runs(probe, *, forced=False):
    values = document_runs()
    for row in values:
        before, after = worker_pair(probe, row['mode'])
        row.update(retained_gpu_workers_before=before, retained_gpu_workers_after=after,
            retained_gpu_worker_validation=probe['validate_pair'](before, after),
            retained_gpu_worker_cleanup={'closed': True})
        if forced:
            cases = forced_cases(probe, after)
            documents = copy.deepcopy(row['retained_documents_after'])
            for document in documents.values():
                document['observed']['read'] += 1
            row.update(retained_gpu_service_restart_cases=cases, retained_gpu_documents_after_restart=documents,
                retained_gpu_service_restart_validation=probe['validate_forced_cases'](cases,
                    row['retained_documents_before'], documents, before['rootTimeOrigin']))
    return values


def test_retention_and_explicit_service_restart_have_different_meanings(probe):
    before, after = worker_pair(probe)
    result = probe['validate_pair'](before, after)
    assert all(row['retained_gpu_objects'] and not row['service_restarted'] for row in result['workers'])
    assert result['service_retention_guaranteed'] is False
    normal = probe['validate_runs'](worker_runs(probe))
    forced = probe['validate_runs'](worker_runs(probe, forced=True))
    assert normal['forced_service_restart_verified'] is False and normal['forced_service_restarts'] == 0
    assert forced['forced_service_restart_verified'] and forced['forced_service_restarts'] == 4


@pytest.mark.parametrize('fault', ['missing-kind', 'not-restored', 'owner-epoch', 'request-replay',
    'recreated-gpu', 'worker-sequence', 'gpu-sequence', 'lost', 'buffer', 'png', 'gpu-epoch'])
def test_worker_gpu_corruption_cannot_be_admitted(probe, fault):
    before, after = worker_pair(probe)
    target = after['workers']['dedicated-classic']
    if fault == 'missing-kind':
        after['workers'].pop('dedicated-classic')
    elif fault == 'not-restored':
        after['persisted'] = False
    elif fault == 'owner-epoch':
        after['rootTimeOrigin'] += 1
    elif fault == 'request-replay':
        target['request'] = before['workers']['dedicated-classic']['request']
    elif fault == 'recreated-gpu':
        target['observed']['id'] += '/new'
    elif fault == 'worker-sequence':
        target['sequence'] = 1
    elif fault == 'gpu-sequence':
        target['observed']['read'] = 1
    elif fault == 'lost':
        target['observed']['apis'][0]['contextLostEvents'] = 1
    elif fault == 'buffer':
        target['observed']['apis'][0]['resources']['buffer'] = False
    elif fault == 'png':
        target['observed']['apis'][0]['pngHash'] = 'c' * 64
    else:
        target['observed']['timeOrigin'] += 1
    with pytest.raises(ValueError):
        probe['validate_pair'](before, after)


@pytest.mark.parametrize('fault', ['version', 'registration', 'status', 'url', 'offset', 'index',
    'worker-reuse', 'gpu-reuse', 'png', 'comparison', 'case-type', 'document', 'document-owner'])
def test_forced_restart_requires_new_globals_exact_owned_events_and_stable_documents(probe, fault):
    before, after = worker_pair(probe)
    cases = forced_cases(probe, after)
    documents_before, documents_after = pair()
    case = cases[0]
    if fault in {'version', 'registration', 'status', 'url'}:
        key, value = {'version': ('versionId', 'other'), 'registration': ('registrationId', 'other'),
            'status': ('runningStatus', 'stopped'), 'url': ('scriptURL', 'https://example.com/foreign.js')}[fault]
        case['version_events'][2][key] = value
    elif fault == 'offset':
        case['request_event_offset'] = 2
    elif fault == 'index':
        case['stopped_event_index'] = True
    elif fault == 'worker-reuse':
        case['after']['workers']['service-classic']['instanceId'] = case['before']['workers']['service-classic']['instanceId']
    elif fault == 'gpu-reuse':
        case['after']['workers']['service-classic']['observed']['id'] = case['before']['workers']['service-classic']['observed']['id']
    elif fault == 'png':
        case['after']['workers']['service-classic']['observed']['apis'][0]['pngHash'] = 'c' * 64
    elif fault == 'comparison':
        case['comparison'] = {'passed': True}
    elif fault == 'case-type':
        case['kind'] = {}
    elif fault == 'document':
        documents_after['main']['observed']['id'] = 'replaced'
    else:
        documents_before['main']['timeOrigin'] += 1000
        documents_after['main']['timeOrigin'] += 1000
        documents_before['main']['observed']['timeOrigin'] += 1000
        documents_after['main']['observed']['timeOrigin'] += 1000
    with pytest.raises(ValueError):
        probe['validate_forced_cases'](cases, documents_before, documents_after, before['rootTimeOrigin'])


def test_mixed_restart_coverage_and_wrong_stop_token_are_rejected(probe):
    values = worker_runs(probe, forced=True)
    values[0].pop('retained_gpu_service_restart_cases')
    with pytest.raises(ValueError, match='coverage differs'):
        probe['validate_runs'](values)
    _, after = worker_pair(probe)
    session = type('Session', (), {'send': AsyncMock()})()
    with pytest.raises(ValueError, match='token differs'):
        asyncio.run(probe['force_service_restarts'](session, {}, 'wrong-owner', after))
    session.send.assert_not_called()
    source = (DIRECTORY / 'retained_gpu_worker_objects.py').read_text(encoding='utf-8-sig')
    assert "'ServiceWorker.stopWorker'" in source and 'stopAllWorkers' not in source
    read = probe['worker_read']()
    assert 'new OffscreenCanvas(16, 16)' in read and 'convertToBlob' in read
    assert 'getUint32(16)' in read and 'window' not in read and 'document.' not in read


@pytest.mark.parametrize('flags', [
    ['--verify-retained-gpu-workers'],
    ['--probe', 'retained-gpu-objects', '--verify-retained-gpu-service-restart'],
    ['--probe', 'retained-workers', '--verify-retained-gpu-workers'],
])
def test_unsupported_gpu_worker_flag_combinations_fail_before_output(tmp_path, flags):
    output = tmp_path / 'must-not-exist'
    result = subprocess.run([sys.executable, str(DIRECTORY / 'protected_history_runtime.py'),
        '--executable', str(tmp_path / 'chrome.exe'), '--work-dir', str(output),
        '--driver-stage', str(tmp_path / 'driver'), *flags], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2 and 'requires' in result.stderr
    assert not output.exists()


def test_selected_worker_archive_is_exact_and_still_has_no_runtime_admission():
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'retained-gpu-workers-integration-preparation.json').read_bytes())
    assert record['selected'] and record['runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
    assert hashlib.sha256((directory / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    for row in record['sources']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['staged_sha256']


def test_public_gpu_worker_runtime_binds_sources_restarts_and_backward_modes():
    record = json.loads((ROOT / 'native/drafts/environment/retained-gpu-workers76-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['public_cli_integrated'] and record['verify_retained_gpu_workers']
    assert record['verify_retained_gpu_service_restart'] and record['forced_service_restarts'] == 4
    for relative, expected in record['measured_inputs_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    assert {row['mode'] for row in record['runs']} == {'manager-desktop', 'manager-mobile-web'}
    for row in record['runs']:
        assert row['passed'] and row['post_restart_document_gpu_verified']
        assert row['all_six_retained_screens_verified'] and row['owned_worker_cleanup_verified']
        assert row['runtime_resources_released'] and row['browser_connection_closed']
        assert row['remaining_observed_processes'] == 0
        assert {worker['kind'] for worker in row['workers']} == {
            kind + '-' + script for kind in ('dedicated', 'shared', 'service') for script in ('classic', 'module')}
        for worker in row['workers']:
            assert worker['webgl_apis'] == ['webgl', 'webgl2']
            assert len(set(worker['normalized_before_after_sha256'])) == 1
            if not worker['kind'].startswith('service-'):
                assert worker['same_worker_instance'] and worker['original_gpu_objects_retained']
        assert len(row['forced_restarts']) == 2
        for case in row['forced_restarts']:
            assert case['version_state_chain'] == ['running', 'stopped', 'running']
            assert case['new_worker_instance'] and case['new_gpu_instances']
            assert case['worker_sequence'] == case['gpu_read_sequence'] == 1
            assert case['policy_observations_stable'] and case['owning_document_unchanged']
    assert {row['mode'] for row in record['compatibility_repeats']} == {'workers', 'documents', 'default', 'legacy-service'}
    assert all(row['passed'] and row['postguards_passed'] for row in record['compatibility_repeats'])
    assert record['validation']['forced_service_restart_verified']
    for key in ('stop_all_workers_used', 'service_retention_guaranteed', 'worker_audio_verified',
                'webgpu_readback_verified', 'cross_profile_isolation_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
