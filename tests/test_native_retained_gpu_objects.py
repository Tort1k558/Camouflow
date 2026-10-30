import copy
import hashlib
import json
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment/first-script'
GPU = runpy.run_path(str(DIRECTORY / 'retained_gpu_objects.py'))


def pair(mode='desktop'):
    before = {}
    for index, role in enumerate(sorted(GPU['ROLES'])):
        apis = [dict(api=api, resources={key: True for key in GPU['RESOURCES']},
                     contextLostEvents=0, contextRestoredEvents=0,
                     reads=[dict(target=target, hash='a' * 64, repeat='a' * 64, bytes=1024, maximumDelta=1)
                            for target in ('framebuffer', 'default')], pngHash='b' * 64)
                for api in ('webgl', 'webgl2')]
        before[role] = dict(nonce=f'{index + 1:048x}', origin='http://localhost:54321',
            location='about:blank' if role == 'about-blank' else f'http://localhost:54321/screen?role={role}',
            timeOrigin=1000000 + index, persisted=False,
            observed=dict(id=f'{mode}/{role}', timeOrigin=1000000 + index, read=1, apis=apis))
    after = copy.deepcopy(before)
    for row in after.values():
        row['persisted'] = True
        row['observed']['read'] = 2
    return before, after


def runs():
    result = []
    for mode in ('manager-desktop', 'manager-mobile-web'):
        before, after = pair(mode)
        result.append(dict(mode=mode, passed=True, bfcache_restored=True,
            protected_arguments_verified=True, post_surfaces_screen_verified=True,
            runtime_resources_released=True, browser_connection_closed=True,
            observed_processes=5, remaining_observed_processes=0,
            history_navigation={'type': 'BackForwardCacheRestore'},
            retained_documents_before=before, retained_documents_after=after,
            retained_gpu_object_validation=GPU['validate_pair'](before, after)))
    return result


def test_integrated_archive_binds_exact_current_sources(sources_before_gpu_workers):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'retained-gpu-objects-integration-preparation.json').read_bytes())
    assert record['selected'] and record['runtime_verified'] is False
    assert hashlib.sha256((directory / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    for row in record['sources']:
        relative = row['source']
        actual = (sources_before_gpu_workers['sha256'][relative] if relative in sources_before_gpu_workers['sha256']
                  else hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        assert actual == row['staged_sha256']


def test_retained_objects_require_actual_document_and_resource_continuity():
    before, after = pair()
    value = GPU['validate_pair'](before, after)
    assert value['passed'] and value['document_contexts'] == 6 and value['webgl_apis'] == 2
    assert value['retained_gpu_objects_verified']
    assert value['workers_verified'] is value['webgpu_readback_verified'] is False
    assert GPU['validate_runs'](runs())['passed']


@pytest.mark.parametrize('fault', ['missing-role', 'not-restored', 'replacement', 'same-read', 'lost',
    'invalid-buffer', 'truthy-buffer', 'repeat', 'reference', 'bytes', 'png', 'epoch', 'nonce',
    'missing-observed', 'malformed-api', 'malformed-read', 'duplicate-instance'])
def test_corrupt_document_or_gpu_observation_is_rejected(fault):
    before, after = pair()
    observed = after['same']['observed']
    if fault == 'missing-role':
        after.pop('same')
    elif fault == 'not-restored':
        after['same']['persisted'] = False
    elif fault == 'replacement':
        observed['id'] = 'replacement'
    elif fault == 'same-read':
        observed['read'] = 1
    elif fault == 'lost':
        observed['apis'][0]['contextLostEvents'] = 1
    elif fault in {'invalid-buffer', 'truthy-buffer'}:
        observed['apis'][0]['resources']['buffer'] = False if fault == 'invalid-buffer' else 1
    elif fault in {'repeat', 'reference', 'bytes'}:
        key, value = {'repeat': ('repeat', 'c' * 64), 'reference': ('maximumDelta', 3), 'bytes': ('bytes', 1000)}[fault]
        observed['apis'][0]['reads'][0][key] = value
    elif fault == 'png':
        observed['apis'][0]['pngHash'] = 'c' * 64
    elif fault == 'epoch':
        observed['timeOrigin'] += 1
    elif fault == 'nonce':
        before['same'].pop('nonce')
        after['same'].pop('nonce')
    elif fault == 'missing-observed':
        after['same'].pop('observed')
    elif fault == 'malformed-api':
        observed['apis'][0] = None
    elif fault == 'malformed-read':
        observed['apis'][0]['reads'][0] = None
    else:
        observed['id'] = after['main']['observed']['id']
    with pytest.raises(ValueError):
        GPU['validate_pair'](before, after)


@pytest.mark.parametrize('field', ['passed', 'bfcache_restored', 'protected_arguments_verified',
    'post_surfaces_screen_verified', 'runtime_resources_released', 'browser_connection_closed'])
def test_aggregate_cannot_admit_failed_lifecycle_or_cleanup(field):
    values = runs()
    values[0][field] = False
    with pytest.raises(ValueError):
        GPU['validate_runs'](values)


@pytest.mark.parametrize('value', [None, {}, [], [None, None], [{'mode': {}}, {'mode': 'manager-desktop'}]])
def test_malformed_aggregate_is_a_typed_validation_failure(value):
    with pytest.raises(ValueError):
        GPU['validate_runs'](value)


def test_aggregate_revalidates_raw_observations_and_rejects_reused_instances():
    values = runs()
    values[1]['retained_documents_before'] = copy.deepcopy(values[0]['retained_documents_before'])
    values[1]['retained_documents_after'] = copy.deepcopy(values[0]['retained_documents_after'])
    with pytest.raises(ValueError, match='same document/resource'):
        GPU['validate_runs'](values)
    values = runs()
    values[0]['history_navigation'] = None
    with pytest.raises(ValueError):
        GPU['validate_runs'](values)


def test_exact_public_gpu_runtime_binds_sources_and_keeps_default_and_workers(sources_before_gpu_workers):
    record = json.loads((ROOT / 'native/drafts/environment/retained-gpu-objects76-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['public_cli_integrated'] and record['runtime_verified']
    assert record['selected_probe'] == 'retained-gpu-objects'
    for relative, expected in record['measured_inputs_sha256'].items():
        actual = (sources_before_gpu_workers['sha256'][relative] if relative in sources_before_gpu_workers['sha256']
                  else hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        assert actual == expected, relative
    assert {row['mode'] for row in record['runs']} == {'manager-desktop', 'manager-mobile-web'}
    for row in record['runs']:
        assert row['passed'] and row['history_navigation_type'] == 'BackForwardCacheRestore'
        assert row['runtime_resources_released'] and row['browser_connection_closed']
        assert row['remaining_observed_processes'] == 0 and row['post_surfaces_screen_verified']
        assert len(row['documents']) == 6
        for document in row['documents']:
            assert document['same_gpu_instances'] and document['same_document_epoch']
            assert document['genuine_bfcache_restoration']
            assert document['webgl_apis'] == ['webgl', 'webgl2']
            assert document['read_sequence'][1] > document['read_sequence'][0]
            assert 0 <= document['maximum_reference_delta'] <= 2
            assert len(set(document['normalized_before_after_sha256'])) == 1
    default = record['default_repeat']
    assert default['passed'] and default['postguards_passed'] and default['selected_probe'] == 'canvas'
    assert default['retained_gpu_probe_enabled'] is default['worker_probe_enabled'] is False
    worker = record['worker_service_repeat']
    assert worker['passed'] and worker['postguards_passed']
    assert all(row['worker_classes'] == 6 for row in worker['worker_validation']['runs'])
    assert worker['controlled_service_validation']['forced_restarts'] == 4
    assert worker['controlled_service_validation']['controlled_clients'] == 4
    for key in ('workers_verified', 'webgpu_readback_verified', 'cross_profile_isolation_verified',
                'privacy_admitted', 'production_admitted'):
        assert record['validation'][key] is False


def test_full_integration_regression_is_bound_to_its_measured_head_and_scope():
    record = json.loads((ROOT / 'native/drafts/environment/canonical-python76-retained-gpu-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('10230bd')
    assert record['counts'] == dict(tests=4855, passed=4854, skipped=1, failures=0, errors=0)
    assert 'before this evidence-only publication' in record['scope']
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
