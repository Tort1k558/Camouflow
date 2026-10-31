import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-buffer-scatter'


def observations():
    return json.loads((ENV / 'webgpu-buffer-scatter-observations.json').read_bytes())


def test_buffer_scatter_binds_sources_and_reuses_the_existing_source_gate():
    record = observations()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    for name, value in record['sources_sha256'].items():
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == value
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE.parent / 'webgpu-execution-inputs/check.py', 'source_gate_checker_sha256'),
                      (ENV / 'webgpu-execution-inputs-preparation.json', 'source_gate_record_sha256'),
                      (MODULE.parent / 'webgpu-edge-compute/edge_compute.hlsl', 'edge_shader_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert set(record['sources_sha256']) == {'buffer_scatter.h', 'buffer_scatter.hlsl', 'compute_test.cc'}


def test_buffer_scatter_hardware_evidence_has_split_only_and_consumer_scope():
    record = observations()
    assert record['hardware_execution_verified']
    assert {row['sanitizer'] for row in record['runs']} == {'none', 'address'}
    for row in record['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['passed'] and value['hardware_adapter'] and value['cases'] == 58
        assert value['assertions'] == 176704 and value['changed_channels'] == 21501
        assert value['rejected_parameters'] == 696
        for key in ('gpu_projection_scatter_consumer_verified', 'split_only_scatter_verified',
                    'duplicate_scatter_verified', 'protected_source_unchanged'):
            assert value[key] is True
        assert not value['native_binding_routing_installed'] and not value['browser_integrated']


def test_buffer_scatter_does_not_confuse_atomic_masks_with_dispatch_ordering():
    shader = (MODULE / 'buffer_scatter.hlsl').read_text(encoding='utf-8-sig')
    fixture = (MODULE / 'compute_test.cc').read_text(encoding='utf-8-sig')
    for text in ('Shadow.InterlockedAnd', 'Shadow.InterlockedOr', 'InitialColumn',
                 'PrefixBytes', 'tid.y * 4096', 'SourcePitch - InitialColumn'):
        assert text in shader
    assert 'D3D12_RESOURCE_BARRIER_TYPE_UAV' in fixture
    assert 'mappings.insert(mappings.end(), repeated.begin(), repeated.end())' in fixture
    assert 'mappings.push_back(*complete)' not in fixture
    assert 'CHECK(!WebGpuCanonicalByte(part, part.buffer_offset + i))' in fixture


def test_buffer_scatter_source_gate_is_cpu_evidence_not_browser_admission():
    gate = observations()['source_gate']
    assert gate['passed'] and gate['measurement_complete'] and gate['postguards_passed']
    assert {row['sanitizer'] for row in gate['runs']} == {'none', 'address'}
    for row in gate['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        result = row['result']
        assert result['assertions'] == 2391 and result['source_extracted_input_contracts_only']
        assert result['actual_frontend_encoding_executed'] is False
        assert result['actual_native_device_queue_executed'] is False


def test_buffer_scatter_never_admits_uninstalled_native_paths():
    record = observations()
    for key in ('native_binding_routing_installed', 'native_immutable_gpu_snapshot_registry_implemented',
                'native_budgeted_shadow_buffer_allocator_implemented', 'actual_native_device_queue_executed',
                'actual_wire_server_roundtrip_executed', 'dxc_execution_verified', 'browser_integrated',
                'gpu_buffer_input_projection_integrated', 'selected', 'default_feature_enabled',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_buffer_scatter_public_runner_reproduces_the_measured_hardware_scope():
    record = observations()['public_checker_observation']
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['hardware_execution_verified']
    assert len(record['runs']) == 2 and all(row['result']['assertions'] == 176704 for row in record['runs'])


def test_buffer_scatter_modified_inputs_are_refused_before_child_compilation():
    refusal = observations()['changed_input_refusal']
    assert refusal['passed']
    assert {row['case'] for row in refusal['cases']} == {
        'shader', 'builder', 'fixture', 'checker', 'edge-shader', 'source-gate', 'source-record',
    }
    for row in refusal['cases']:
        assert row['passed'] and row['returncode'] == 2
        assert row['expected_error_observed'] and row['refused_before_compilation']
