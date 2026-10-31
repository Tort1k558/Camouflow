import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-buffer-shadow'
SCATTER = MODULE.parent / 'webgpu-buffer-scatter'


def preparation():
    return json.loads((ENV / 'webgpu-buffer-shadow-preparation.json').read_bytes())


def test_buffer_shadow_binds_seventeen_packet_source_chain():
    record = preparation()
    assert record['passed'] and record['exact_seventeen_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 16
    assert len(record['sources']) == 5 and len(record['composed_sources']) == 84
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    extension = record['source_extension']
    assert extension['patch'] == record['patch'] and extension['patch_sha256'] == record['patch_sha256']
    assert extension['sources'] == record['sources']


def test_buffer_shadow_binds_shared_runner_fixture_and_parameter_abi():
    record = preparation()
    for directory, mapping in ((MODULE, record['sources_sha256']),
                               (SCATTER, record['dependency_sources_sha256'])):
        for name, value in mapping.items():
            assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == value
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (SCATTER / 'check.py', 'shared_checker_sha256'),
                      (MODULE.parent / 'webgpu-execution-inputs/check.py', 'source_gate_checker_sha256'),
                      (ENV / 'webgpu-execution-inputs-preparation.json', 'source_gate_record_sha256'),
                      (MODULE.parent / 'webgpu-edge-compute/edge_compute.hlsl', 'edge_shader_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert record['shared_parameter_abi_source_verified']


def test_buffer_shadow_hardware_checks_budget_and_dependent_retirement():
    record = preparation()
    proof = record['public_checker_observation']
    assert proof['passed'] and proof['postguards_passed'] and proof['measurement_complete']
    assert proof['native_source_extension_verified'] and proof['hardware_execution_verified']
    assert proof['runs'] == record['runs']
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        result = row['result']
        assert result['passed'] and result['hardware_adapter']
        assert result['cases'] == 58 and result['assertions'] == 178960
        assert result['budget_rejections'] == 812 and result['rejected_parameters'] == 696
        assert result['cpu_cancel_cases'] == 26 and result['changed_channels'] == 21501
        for key in ('budgeted_shadow_helper_executed', 'dependent_quota_lifetime_verified',
                    'original_buffer_unchanged', 'gpu_projection_scatter_consumer_verified'):
            assert result[key] is True
        assert not result['native_binding_routing_installed'] and not result['browser_integrated']


def test_buffer_shadow_native_syntax_is_not_link_or_runtime_evidence():
    record = preparation()
    syntax = record['native_syntax']
    assert syntax['passed'] and syntax['postguards_passed'] and len(syntax['runs']) == 14
    assert all(row['returncode'] == 0 for row in syntax['runs'])
    assert any(row['source'].endswith('/projected_buffer.cc') for row in syntax['runs'])
    for key in ('gn_rechecked', 'component_link_verified', 'actual_native_device_queue_executed',
                'actual_wire_server_roundtrip_executed', 'live_native_budgeted_shadow_allocator_installed',
                'native_binding_routing_installed', 'native_immutable_gpu_snapshot_registry_implemented',
                'gpu_buffer_input_projection_integrated', 'dxc_execution_verified', 'runtime_verified',
                'canvas_gpu_shader_consistency_resolved', 'selected', 'default_feature_enabled',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_buffer_shadow_changed_dependencies_are_refused_before_compilation():
    refusal = preparation()['changed_input_refusal']
    assert refusal['passed']
    assert {row['case'] for row in refusal['cases']} == {
        'fixture', 'checker', 'shared-checker', 'parameters', 'packet', 'source-gate',
        'source-record', 'edge-shader', 'missing-extension',
    }
    for row in refusal['cases']:
        assert row['passed'] and row['returncode'] == 2
        assert row['expected_error_observed'] and row['refused_before_compilation']
