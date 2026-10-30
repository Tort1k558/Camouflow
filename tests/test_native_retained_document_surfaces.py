import asyncio
import copy
import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from test_native_gpu import profile_identity_readback_observation
from test_native_protected_surface_history import observed


ROOT = Path(__file__).resolve().parents[1]
PROBE = runpy.run_path(str(ROOT / 'native/drafts/environment/first-script/retained_document_surfaces.py'))
ROLES = {'main', 'same', 'cross', 'nested-return', 'srcdoc', 'about-blank'}


@pytest.fixture
def retained(observed):
    observed['gpu'] = profile_identity_readback_observation()['document']
    before = {role: dict(nonce=role + '-document-nonce', origin='http://127.0.0.1:1234',
        location='http://127.0.0.1:1234/screen?role=' + role, timeOrigin=123456,
        persisted=False, observed=copy.deepcopy(observed)) for role in ROLES}
    after = copy.deepcopy(before)
    for value in after.values():
        value['persisted'] = True
    return before, after


def test_six_real_roles_keep_identity_and_do_not_claim_retained_objects_or_workers(retained):
    before, after = retained
    unchanged = copy.deepcopy(retained)
    result = PROBE['validate_pair'](before, after)
    assert retained == unchanged and result['passed'] and result['document_contexts'] == 6
    assert result['webgl_apis'] == 2 and result['audio_phases'] == 3
    assert all(result[key] is False for key in ('retained_gpu_objects_verified', 'workers_verified',
        'webgpu_readback_verified', 'privacy_admitted', 'production_admitted'))


@pytest.mark.parametrize('role', sorted(ROLES))
@pytest.mark.parametrize('field,value', [('nonce', 'new-document'), ('origin', 'http://localhost:1234'),
    ('location', 'about:blank'), ('timeOrigin', 987654), ('persisted', False)])
def test_replaced_or_nonrestored_document_cannot_pass_by_matching_surface_hashes(retained, role, field, value):
    before, after = retained
    after[role][field] = value
    with pytest.raises(ValueError, match='replaced|restored'):
        PROBE['validate_pair'](before, after)


@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('fault', ['missing', 'extra'])
def test_incomplete_or_extra_context_coverage_is_rejected(retained, side, fault):
    if fault == 'missing':
        retained[side].pop('cross')
    else:
        retained[side]['fake-worker'] = copy.deepcopy(retained[side]['main'])
    with pytest.raises(ValueError, match='Six actual'):
        PROBE['validate_pair'](*retained)


@pytest.mark.parametrize('fault', ['audio-copy', 'audio-unavailable', 'pack-state', 'png', 'limits'])
def test_matching_but_invalid_api_evidence_does_not_count_as_coverage(retained, fault):
    for side in retained:
        observed = side['cross']['observed']
        if fault == 'audio-copy':
            observed['audio']['signal']['copyToSeesMutation'] = False
        elif fault == 'audio-unavailable':
            observed['audio'] = dict(available=False, reason='API unavailable')
        elif fault == 'pack-state':
            observed['gpu']['webgl']['webgl2']['scene']['packState']['skipRows'] = 999
        elif fault == 'png':
            observed['gpu']['webgl']['webgl']['scene']['png'][0] ^= 1
        else:
            observed['gpu']['webgl']['webgl2']['limits'] = {}
    with pytest.raises((ValueError, TypeError, KeyError)):
        PROBE['validate_pair'](*retained)


def test_render_duration_and_shader_cache_length_are_not_retained_identity(retained):
    for value in retained[1].values():
        for phase in ('signal', 'repeat', 'silence'):
            value['observed']['audio'][phase]['renderMilliseconds'] = 100
        for api in ('webgl', 'webgl2'):
            value['observed']['gpu']['webgl'][api]['translatedShaderLength'] += 1
    assert PROBE['validate_pair'](*retained)['passed']


def test_restored_collection_uses_cdp_and_exact_registration_without_frame_objects(retained):
    registry = {role: {key: value[key] for key in ('nonce', 'origin', 'location')}
                for role, value in retained[1].items()}
    session = SimpleNamespace(send=AsyncMock(return_value={'result': {'value': retained[1]}}))
    result = asyncio.run(PROBE['collect'](session, dict(token='owned-token', registry=registry), persisted=True))
    assert result == retained[1]
    command, params = session.send.await_args.args
    assert command == 'Runtime.evaluate' and params['awaitPromise'] and params['returnByValue']
    assert 'owned-token' in params['expression'] and 'probe.collect' in params['expression']


@pytest.mark.parametrize('response', [{'exceptionDetails': {}}, {'result': {}}, {'result': {'value': {}}}])
def test_cdp_failure_or_partial_collection_has_no_recreation_fallback(response):
    session = SimpleNamespace(send=AsyncMock(return_value=response))
    with pytest.raises(ValueError):
        asyncio.run(PROBE['collect'](session, dict(token='owned-token', registry={'main': {}}), persisted=True))


def test_integrated_package_binds_every_selected_source_and_reversible_archive(worker_sources_before_integration):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'retained-document-surfaces-preparation.json').read_bytes())
    assert record['selected'] and record['runtime_verified'] is False
    assert hashlib.sha256((directory / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    for row in record['sources']:
        actual = (worker_sources_before_integration['sha256'][row['source']]
                  if row['source'] in worker_sources_before_integration['sha256']
                  else hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest())
        assert actual == row['staged_sha256']


def test_measured_runtime_keeps_all_six_actual_documents_and_pending_boundaries(worker_sources_before_integration):
    directory = ROOT / 'native/drafts/environment'
    record = json.loads((directory / 'retained-document-surfaces75-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert {row['mode'] for row in record['runs']} == {'manager-desktop', 'manager-mobile-web'}
    for row in record['runs']:
        assert row['passed'] and set(row['document_roles']) == ROLES
        assert row['validation']['document_contexts'] == 6
        assert row['bfcache_navigation_type'] == 'BackForwardCacheRestore'
        assert row['post_surfaces_screen_verified'] and row['browser_connection_closed']
        assert row['runtime_resources_released'] and row['remaining_observed_processes'] == 0
    for key in ('retained_gpu_objects_verified', 'workers_verified', 'webgpu_readback_verified',
                'cross_session_screenshot_fixed', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    for name, expected in record['measured_inputs_sha256'].items():
        actual = (worker_sources_before_integration['sha256'][name]
                  if name in worker_sources_before_integration['sha256']
                  else hashlib.sha256((ROOT / name).read_bytes()).hexdigest())
        assert actual == expected, name


def test_real_browser_message_faults_are_routing_tests_not_extra_surface_coverage():
    path = ROOT / 'native/drafts/environment/retained-document-surfaces75-observations.json'
    record = json.loads(path.read_bytes())
    controls = record['routing_fault_controls']
    assert controls['passed'] and controls['measurement_complete'] and controls['postguards_passed']
    assert len(controls['runs']) == 2
    assert sum(len(row['cases']) for row in controls['runs']) == 20
    for run in controls['runs']:
        rows = {row['fault']: row for row in run['cases']}
        assert rows['valid-main']['accepted']
        assert all(rows[name]['rejected'] for name in ('source', 'nonce', 'origin', 'url', 'persisted', 'duplicate', 'unknown-role'))
        assert all(rows[name]['ignored'] for name in ('stale-request', 'wrong-token'))
