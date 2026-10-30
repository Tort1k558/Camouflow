"""Measured WebGPU compatibility is not native readback protection admission."""
import hashlib
import json
from pathlib import Path

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
