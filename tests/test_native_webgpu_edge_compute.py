import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-edge-compute'


def observations():
    return json.loads((ENV / 'webgpu-edge-compute-observations.json').read_bytes())


def test_edge_compute_measured_sources_and_shared_cpu_packet_are_bound():
    record = observations()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert set(record['sources_sha256']) == {'compute_test.cc', 'edge_compute.hlsl', 'check.py'}
    for name, expected in record['sources_sha256'].items():
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == expected
    packet = record['shared_cpu_packet']
    assert hashlib.sha256((ENV / packet['patch']).read_bytes()).hexdigest() == packet['sha256']


def test_edge_compute_domain_matches_the_existing_cpu_algorithm():
    record = observations()
    patch = (ENV / record['shared_cpu_packet']['patch']).read_text(encoding='utf-8-sig')
    domains = set(re.findall(r'kEdgeDomain\[\] = "([^"]+)"', patch))
    assert len(domains) == 1
    shader = (MODULE / 'edge_compute.hlsl').read_text(encoding='utf-8-sig')
    match = re.search(r'Domain\[30\] = \{([^}]+)\}', shader, re.DOTALL)
    assert match is not None
    assert bytes(int(value) for value in re.findall(r'\d+', match.group(1))) == domains.pop().encode()


def test_edge_compute_hardware_results_are_scoped_to_raw_buffers():
    record = observations()
    for key in ('raw_buffer_projection_verified', 'rgba8_bgra8_cpu_equivalence_verified',
                'repeated_projection_verified', 'projection_idempotence_verified',
                'alpha_and_padding_preserved', 'uniform_and_nonopaque_fixtures_preserved',
                'shader_compile_warnings_as_errors'):
        assert record[key] is True
    assert record['same_input_different_keys_cases'] == 2
    assert record['hmac_key_bytes'] == 32 and record['max_hmac_test_message_bytes'] == 55
    assert {row['sanitizer'] for row in record['hardware_runs']} == {'none', 'address'}
    for row in record['hardware_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'hardware_adapter': True, 'hmac_cases': 6, 'image_cases': 32,
            'assertions': 173282, 'changed_channels': 4548, 'browser_integrated': False,
            'shader_input_routing_implemented': False,
        }


def test_edge_compute_public_hardware_check_was_executed():
    record = observations()['public_checker_observation']
    assert record['passed'] and record['postguards_passed'] and record['hardware_execution_verified']
    assert not record['compile_only']
    assert len(record['runs']) == 2
    for row in record['runs']:
        assert row['result']['hardware_adapter'] and row['result']['assertions'] == 173282


def test_edge_compute_failure_history_and_browser_limits_are_explicit():
    record = observations()
    assert record['earlier_failed_prototype']['passed'] is False
    assert record['earlier_failed_prototype']['root_cause_proven'] is False
    for key in ('software_adapter_fallback', 'typed_texture_views_tested', 'browser_integrated',
                'native_shader_input_routing_installed', 'canvas_gpu_shader_consistency_resolved',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_edge_compute_compile_only_does_not_claim_hardware_execution():
    record = observations()['compile_only_observation']
    assert record['passed'] and record['postguards_passed'] and record['compile_only']
    assert record['hardware_execution_verified'] is False
    assert len(record['runs']) == 2
    for row in record['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {'passed': True, 'hardware_adapter': False, 'compile_only': True}


def test_edge_compute_python_baseline_does_not_grant_native_admission():
    record = observations()['full_python_baseline']
    assert record['passed'] and record['postguards_passed'] and record['git_head'].startswith('dfe2648')
    assert record['counts'] == {
        'tests': 5125, 'passed': 5124, 'skipped': 1, 'failures': 0, 'errors': 0,
    }
