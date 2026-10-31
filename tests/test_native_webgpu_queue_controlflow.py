import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-render-ranges'


def observations():
    return json.loads((ENV / 'webgpu-queue-controlflow-observations.json').read_bytes())


def test_queue_controlflow_observation_binds_native_packet_and_public_sources():
    record = observations()
    parent = json.loads((ENV / 'webgpu-render-ranges-preparation.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['parent_patch_sha256'] == parent['patch_sha256']
    native_queue = next(row for row in parent['composed_sources']
                        if row['source'].endswith('/d3d12/QueueD3D12.cpp'))
    assert native_queue['after_sha256'] == record['native_queue_source_sha256']
    assert hashlib.sha256((MODULE / 'check.py').read_bytes()).hexdigest() == record['checker_sha256']
    assert hashlib.sha256((MODULE / 'queue_controlflow_test.cc').read_bytes()).hexdigest() == record['test_sha256']
    assert len(record['extracted_functions_sha256']) == 3
    assert len(record['error_header_sha256']) == len(record['macro_sha256']) == 64


def test_queue_controlflow_all_failure_paths_pass_with_real_cpu_controller_and_mock_backend():
    record = observations()
    assert record['backend_mocked']
    assert {row['sanitizer'] for row in record['cpu_runs']} == {'none', 'address'}
    for row in record['cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'assertions': 372, 'scenarios': 26,
            'source_extracted_queue_control_flow_only': True,
            'backend_mocked': True, 'native_gpu_queue_executed': False,
        }


def test_queue_controlflow_tampered_validation_inputs_fail_before_compilation():
    cases = observations()['validator_negative_cases']
    assert {row['name'] for row in cases} == {
        'test-hash', 'function', 'macro', 'native-source', 'function-count', 'parent',
    }
    for row in cases:
        assert row['passed'] and row['returncode'] == 2 and row['generated_binary'] is False


def test_queue_controlflow_public_cli_preserves_default_controller_suite():
    record = observations()
    for key, suite, assertions in (
            ('public_checker_observation', 'queue-controlflow', 372),
            ('controller_checker_observation', 'controller', 4969123)):
        value = record[key]
        assert value['passed'] and value['postguards_passed'] and value['suite'] == suite
        assert len(value['runs']) == 2
        assert {row['sanitizer'] for row in value['runs']} == {'none', 'address'}
        for row in value['runs']:
            assert row['compile_returncode'] == row['test_returncode'] == 0
            assert row['result']['assertions'] == assertions
        assert value['native_gpu_queue_executed'] is value['runtime_verified'] is False


def test_queue_controlflow_mock_faults_do_not_grant_native_or_privacy_admission():
    record = observations()
    for key in ('actual_native_submission_failure_injected', 'native_gpu_queue_executed',
                'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_queue_controlflow_full_python_baseline_is_not_native_queue_evidence():
    record = observations()['full_python_baseline']
    assert record['passed'] and record['postguards_passed']
    assert record['git_head'].startswith('34045dc')
    assert record['counts'] == {
        'tests': 5119, 'passed': 5118, 'skipped': 1, 'failures': 0, 'errors': 0,
    }
