"""Measured WebGPU compatibility is not native readback protection admission."""
import hashlib
import json
from pathlib import Path
import copy
import runpy
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'
CONTEXTS = {'document', *(kind + '-' + worker + '-worker'
    for kind in ('classic', 'module') for worker in ('dedicated', 'shared', 'service'))}


def observation():
    return json.loads((DIRECTORY / 'webgpu-readback76-observations.json').read_bytes())


def test_webgpu_probe_is_exact_measured_source_without_runtime_admission():
    record = observation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    source = ROOT / record['source']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['source_sha256']
    assert source.read_bytes().startswith(b'async function probeWebGPU()')
    assert record['public_probe_source'] and not record['public_cli_integrated']
    assert len(record['rows']) == 14
    assert {(row['mode'], row['context']) for row in record['rows']} == {
        (mode, context) for mode in ('baseline', 'ready') for context in CONTEXTS}
    for key in ('native_webgpu_readback_protection', 'retained_objects_verified',
                'cross_profile_isolation_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    original = record['driver_partitioning']['original'].split('=', 1)[1].split(',')
    replacement = record['driver_partitioning']['replacement'].split('=', 1)[1].split(',')
    assert 'ThirdPartyStoragePartitioning' in original
    assert replacement == [value for value in original if value != 'ThirdPartyStoragePartitioning']
    assert record['prior_negative']['passed'] is False


@pytest.mark.parametrize('mode', ['baseline', 'ready'])
@pytest.mark.parametrize('context', sorted(CONTEXTS))
def test_measured_webgpu_compute_texture_mapping_and_error_semantics(mode, context):
    row = next(row for row in observation()['rows'] if row['mode'] == mode and row['context'] == context)
    value = row['value']
    assert all(value[key] is True for key in ('secureContext', 'exposed', 'measured', 'compatibilityPassed'))
    assert value['privacyAdmitted'] is False and value['unexpected'] == []
    assert value['computeReads'] == [dict(words=64, referenceMatched=True, detached=True,
                                        rangeError='OperationError')] * 2
    assert value['textureReads'] == [dict(width=7, height=3, rowPitch=256,
                                         referenceMatched=True, paddingZero=True)] * 2
    assert value['validation'] == dict(alignmentError='OperationError', mapValidation=True, usageValidation=True)


def test_full_worker_gpu_python_regression_is_a_guarded_historical_measurement():
    record = json.loads((DIRECTORY / 'canonical-python76-gpu-workers-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'] == 'a05fbc696331d8264cf427931203c81f4d997f29'
    assert record['counts'] == dict(tests=4887, passed=4886, skipped=1, failures=0, errors=0)
    assert record['duration_seconds'] == 476.828
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False


@pytest.fixture
def probe():
    return runpy.run_path(str(DIRECTORY / 'first-script/webgpu_readback.py'))


def test_public_validator_accepts_all_measured_contexts_without_protection_admission(probe):
    result = probe['validate_rows'](observation()['rows'])
    assert result['passed'] and result['observations'] == 14 and result['contexts_per_mode'] == 7
    assert result['native_webgpu_readback_protection'] is result['retained_objects_verified'] is False


@pytest.mark.parametrize('field,value', [
    ('secureContext', False), ('exposed', False), ('measured', False),
    ('compatibilityPassed', 1), ('privacyAdmitted', True),
    ('computeReads', []), ('textureReads', []), ('validation', {}),
    ('unexpected', ['device lost']), ('unavailable', 'No default adapter'),
])
def test_webgpu_validator_rejects_missing_support_partial_results_and_false_claims(probe, field, value):
    row = copy.deepcopy(observation()['rows'][0]['value'])
    row[field] = value
    with pytest.raises(ValueError, match='compatibility'):
        probe['validate_observation'](row)


@pytest.mark.parametrize('field,value', [('words', True), ('referenceMatched', 1),
                                       ('detached', False), ('rangeError', 'TypeError')])
def test_webgpu_validator_rejects_compute_data_type_and_mapping_changes(probe, field, value):
    row = copy.deepcopy(observation()['rows'][0]['value'])
    row['computeReads'][0][field] = value
    with pytest.raises(ValueError, match='compatibility'):
        probe['validate_observation'](row)


@pytest.mark.parametrize('rows', [None, {}, [], [None] * 14])
def test_webgpu_validator_rejects_invalid_context_collections(probe, rows):
    with pytest.raises(ValueError):
        probe['validate_rows'](rows)


def test_webgpu_validator_rejects_duplicate_contexts_and_unknown_modes(probe):
    rows = copy.deepcopy(observation()['rows'])
    rows[-1] = rows[0]
    with pytest.raises(ValueError, match='Duplicate'):
        probe['validate_rows'](rows)
    rows = copy.deepcopy(observation()['rows'])
    rows[0]['mode'] = 'pretend-mobile'
    with pytest.raises(ValueError, match='unexpected'):
        probe['validate_rows'](rows)


def test_webgpu_worker_scripts_have_explicit_lifetime_and_no_api_replacement(probe):
    for kind in ('dedicated', 'shared', 'service'):
        script = probe['worker_source']('async function probeWebGPU() {}', kind)
        assert script.startswith('async function probeWebGPU() {}')
        assert 'postMessage' in script and 'await probeWebGPU()' in script
        assert 'prototype' not in script
    assert 'event.waitUntil' in probe['worker_source']('', 'service')
    assert 'self.close()' in probe['worker_source']('', 'shared')
    with pytest.raises(ValueError, match='Unsupported'):
        probe['worker_source']('', 'unknown')


def test_webgpu_cli_rejects_noncanonical_output_before_creating_it(tmp_path):
    output = tmp_path / 'must-not-exist'
    result = subprocess.run([sys.executable, str(DIRECTORY / 'first-script/webgpu_readback_runtime.py'),
        '--executable', str(tmp_path / 'chrome.exe'), '--work-dir', str(output),
        '--driver-stage', str(tmp_path / 'driver')], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2 and 'canonical' in result.stderr
    assert not output.exists()


def test_public_webgpu_cli_has_measured_source_binding_and_actual_runtime_cleanup(probe):
    record = json.loads((DIRECTORY / 'webgpu-readback76-public-cli-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['public_cli_integrated']
    assert record['validation'] == probe['validate_rows'](record['rows'])
    for name, expected in record['measured_inputs_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    assert {row['mode'] for row in record['runs']} == {'baseline', 'ready'}
    assert len(record['runs']) == 2
    for row in record['runs']:
        assert all(row[key] is True for key in ('passed', 'arguments_verified',
            'service_registrations_released', 'runtime_resources_released', 'browser_connection_closed'))
        assert row['observed_processes'] > 1 and row['remaining_observed_processes'] == 0
    assert record['privacy_admitted'] is record['production_admitted'] is False
