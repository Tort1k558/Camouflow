"""Original WebGPU resource continuity, not native fingerprint protection."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
from uuid import NAMESPACE_URL, uuid5

import pytest


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment/first-script'
ROLES = {'main', 'same', 'cross', 'nested-return', 'srcdoc', 'about-blank'}


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.syspath_prepend(str(DIRECTORY))
    return runpy.run_path(str(DIRECTORY / 'retained_webgpu_worker_objects.py'))


def observed(seed, epoch):
    return dict(id=str(uuid5(NAMESPACE_URL, seed)), timeOrigin=epoch, read=1,
        sameReferences=[True] * 9, computeMatched=True, textureMatched=True,
        paddingZero=True, detached=True, deviceLost=False, unexpected=[])


def documents(mode):
    before = {}
    for index, role in enumerate(sorted(ROLES)):
        epoch = 1000000 + index
        before[role] = dict(nonce=hashlib.sha256((mode + role).encode()).hexdigest()[:48],
            origin='http://localhost:54321', location='http://localhost:54321/' + role,
            timeOrigin=epoch, persisted=False, observed=observed(mode + role, epoch))
    after = copy.deepcopy(before)
    for row in after.values():
        row['persisted'] = True
        row['observed']['read'] = 2
    return before, after


def workers(probe, mode, owner_epoch):
    token = hashlib.sha256(mode.encode()).hexdigest()[:48]
    before = dict(rootTimeOrigin=owner_epoch, persisted=False, workers={})
    for index, kind in enumerate(sorted(probe['lifecycle'].WORKER_KINDS)):
        worker_class, script_type = kind.split('-')
        epoch = 2000000 + index
        before['workers'][kind] = dict(request='before/' + kind, token=token, kind=kind,
            location=f'http://localhost:54321/owned-retained-{worker_class}.js?token={token}&type={script_type}',
            instanceId=str(uuid5(NAMESPACE_URL, mode + '/worker/' + kind)), timeOrigin=epoch,
            sequence=1, observed=observed(mode + '/gpu/' + kind, epoch))
    after = copy.deepcopy(before)
    after['persisted'] = True
    for kind, value in after['workers'].items():
        value.update(request='after/' + kind, sequence=2)
        value['observed']['read'] = 2
    return before, after


def forced_cases(probe, before):
    cases = []
    for index, kind in enumerate(('service-classic', 'service-module')):
        after = copy.deepcopy(before)
        for name, value in after['workers'].items():
            value['request'] = f'forced/{index}/{name}'
            value['sequence'] += 1
            value['observed']['read'] += 1
        target = after['workers'][kind]
        target.update(instanceId=str(uuid5(NAMESPACE_URL, target['instanceId'] + '/restart')),
            timeOrigin=target['timeOrigin'] + 1000, sequence=1)
        target['observed'].update(id=str(uuid5(NAMESPACE_URL, target['observed']['id'] + '/restart')),
            timeOrigin=target['timeOrigin'], read=1)
        comparison = probe['validate_restart_pair'](before, after, kind=kind)
        events = [dict(versionId=str(index), registrationId=str(index), status='activated',
            scriptURL=before['workers'][kind]['location'], runningStatus=status)
            for status in ('running', 'stopped', 'running')]
        cases.append(dict(kind=kind, passed=True, before=before, after=after, comparison=comparison,
            version_events=events, request_event_offset=0, stopped_event_index=1, restarted_event_index=2))
        before = after
    return cases


def runs(probe):
    values = []
    for mode in ('manager-desktop', 'manager-mobile-web'):
        before, after = documents(mode)
        first, second = workers(probe, mode, before['main']['timeOrigin'])
        row = dict(mode=mode, passed=True, bfcache_restored=True, protected_arguments_verified=True,
            post_surfaces_screen_verified=True, runtime_resources_released=True, browser_connection_closed=True,
            observed_processes=5, remaining_observed_processes=0,
            history_navigation={'type': 'BackForwardCacheRestore'},
            retained_documents_before=before, retained_documents_after=after,
            retained_gpu_object_validation=probe['backend'].validate_pair(before, after),
            retained_gpu_workers_before=first, retained_gpu_workers_after=second,
            retained_gpu_worker_validation=probe['validate_pair'](first, second), retained_gpu_worker_cleanup={'closed': True})
        cases = forced_cases(probe, second)
        final_documents = copy.deepcopy(after)
        for document in final_documents.values():
            document['observed']['read'] += 1
        row.update(retained_gpu_service_restart_cases=cases,
            retained_gpu_documents_after_restart=final_documents,
            retained_gpu_service_restart_validation=probe['validate_forced_cases'](
                cases, before, final_documents, first['rootTimeOrigin']))
        values.append(row)
    return values


def test_documents_workers_and_forced_restarts_have_no_native_protection_admission(probe):
    result = probe['validate_runs'](runs(probe))
    assert result['passed'] and result['webgpu_readback_verified']
    assert result['forced_service_restart_verified'] and result['forced_service_restarts'] == 4
    assert result['privacy_admitted'] is result['production_admitted'] is False
    assert probe['backend'].validate_runs(runs(probe))['native_webgpu_readback_protection'] is False
    assert probe['worker_read']() == probe['backend'].READ


@pytest.mark.parametrize('fault', ['missing-role', 'not-restored', 'replacement', 'stale-read',
    'lost-device', 'unexpected-error', 'false-reference', 'truthy-reference', 'compute', 'texture',
    'padding', 'mapping', 'epoch', 'nonce', 'origin', 'duplicate-instance'])
def test_corrupt_retained_webgpu_documents_are_rejected(probe, fault):
    before, after = documents('test')
    row = after['same']
    value = row['observed']
    if fault == 'missing-role': after.pop('main')
    elif fault == 'not-restored': row['persisted'] = False
    elif fault == 'replacement': value['id'] = str(uuid5(NAMESPACE_URL, 'replacement'))
    elif fault == 'stale-read': value['read'] = 1
    elif fault == 'lost-device': value['deviceLost'] = True
    elif fault == 'unexpected-error': value['unexpected'] = ['device lost']
    elif fault == 'false-reference': value['sameReferences'][0] = False
    elif fault == 'truthy-reference': value['sameReferences'][0] = 1
    elif fault == 'compute': value['computeMatched'] = False
    elif fault == 'texture': value['textureMatched'] = False
    elif fault == 'padding': value['paddingZero'] = False
    elif fault == 'mapping': value['detached'] = False
    elif fault == 'epoch': value['timeOrigin'] += 1
    elif fault == 'nonce': row['nonce'] = 'wrong'
    elif fault == 'origin': row['origin'] = 'http://example.com'
    elif fault == 'duplicate-instance': value['id'] = before['main']['observed']['id']
    with pytest.raises(ValueError):
        probe['backend'].validate_pair(before, after)


@pytest.mark.parametrize('fault', ['missing-worker', 'replaced-worker', 'replaced-gpu', 'stale-request',
    'stale-read', 'lost-device', 'mixed-token', 'owner-epoch', 'not-restored', 'false-reference'])
def test_webgpu_worker_lifecycle_rejects_inconsistent_globals_and_readbacks(probe, fault):
    before, after = workers(probe, 'test', 1000000)
    row = after['workers']['dedicated-classic']
    if fault == 'missing-worker': after['workers'].pop('service-module')
    elif fault == 'replaced-worker': row['instanceId'] = 'replacement'
    elif fault == 'replaced-gpu': row['observed']['id'] = str(uuid5(NAMESPACE_URL, 'replacement'))
    elif fault == 'stale-request': row['request'] = before['workers']['dedicated-classic']['request']
    elif fault == 'stale-read': row['observed']['read'] = 1
    elif fault == 'lost-device': row['observed']['deviceLost'] = True
    elif fault == 'mixed-token': row['token'] = 'a' * 48
    elif fault == 'owner-epoch': after['rootTimeOrigin'] += 1
    elif fault == 'not-restored': after['persisted'] = False
    elif fault == 'false-reference': row['observed']['sameReferences'][0] = False
    with pytest.raises(ValueError):
        probe['validate_pair'](before, after)


def test_selected_webgpu_packet_binds_exact_sources_without_claiming_runtime_admission(sources_before_webgpu):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'retained-webgpu-integration-preparation.json').read_bytes())
    assert record['selected'] and record['runtime_verified'] is False
    assert hashlib.sha256((directory / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    for row in record['sources']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['staged_sha256']
        if row['before_sha256'] is not None:
            assert sources_before_webgpu['sha256'][row['source']] == row['before_sha256']


def test_public_webgpu_lifecycle_binds_actual_sources_cleanup_and_four_service_restarts():
    record = json.loads((ROOT / 'native/drafts/environment/retained-webgpu76-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['public_cli_integrated'] and record['probe'] == 'retained-webgpu-objects'
    assert record['forced_service_restarts'] == 4
    for relative, expected in record['measured_inputs_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    assert len(record['runs']) == 2
    assert {row['mode'] for row in record['runs']} == {'manager-desktop', 'manager-mobile-web'}
    for row in record['runs']:
        assert all(row[key] is True for key in ('passed', 'bfcache_restored',
            'post_restart_document_gpu_verified', 'all_six_retained_screens_verified',
            'owned_worker_cleanup_verified', 'runtime_resources_released', 'browser_connection_closed'))
        assert row['remaining_observed_processes'] == 0
        assert {value['role'] for value in row['document_contexts']} == ROLES
        assert all(value['original_resources_retained'] and value['reference_count'] == 9
                   and value['compute_and_texture_reference_matched'] and not value['device_lost']
                   for value in row['document_contexts'])
        assert {value['kind'] for value in row['workers']} == {
            kind + '-' + script for kind in ('dedicated', 'shared', 'service') for script in ('classic', 'module')}
        for value in row['workers']:
            assert value['compute_and_texture_reference_matched'] and not value['device_lost']
            if not value['kind'].startswith('service-'):
                assert value['same_worker_instance'] and value['original_resources_retained']
        assert len(row['forced_restarts']) == 2
        for value in row['forced_restarts']:
            assert value['new_worker_instance'] and value['new_gpu_instances']
            assert value['version_state_chain'] == ['running', 'stopped', 'running']
    assert {row['mode'] for row in record['compatibility_repeats']} == {
        'webgl-forced', 'webgpu-documents', 'webgpu-workers', 'default'}
    assert all(row['passed'] and row['postguards_passed'] for row in record['compatibility_repeats'])
    for key in ('native_webgpu_readback_protection', 'service_retention_guaranteed',
                'cross_profile_isolation_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_canvas_export_mismatch_is_retained_as_an_open_native_problem():
    record = json.loads((ROOT / 'native/drafts/environment/webgpu-canvas-export76-observations.json').read_bytes())
    assert record['measurement_complete'] and record['postguards_passed']
    assert record['canvas_gpu_export_consistent'] is False
    assert hashlib.sha256((ROOT / record['source']).read_bytes()).hexdigest() == record['source_sha256']
    rows = {row['mode']: row for row in record['rows']}
    assert rows['baseline']['changed_channels'] == rows['baseline']['maximum_delta'] == 0
    assert rows['ready']['changed_channels'] > 0 and rows['ready']['maximum_delta'] == 1
    assert all(row['direct_gpu_reference_matched'] and row['png_export_stable'] for row in rows.values())
    assert record['native_webgpu_readback_protection'] is record['privacy_admitted'] is record['production_admitted'] is False


def test_webgpu_cli_full_regression_predates_resource_lifecycle_integration():
    record = json.loads((ROOT / 'native/drafts/environment/canonical-python76-webgpu-cli-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('26082fe')
    assert record['counts'] == dict(tests=4926, passed=4925, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
