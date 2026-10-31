import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-buffer-bindings'
SCATTER = MODULE.parent / 'webgpu-buffer-scatter'


def preparation():
    return json.loads((ENV / 'webgpu-buffer-bindings-preparation.json').read_bytes())


def test_buffer_bindings_bind_twenty_two_packets_and_native_extension():
    record = preparation()
    assert record['passed'] and record['exact_twenty_two_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 21 and len(record['sources']) == 2
    assert len(record['composed_sources']) == 84
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    assert record['source_extension'] == {
        'patch': record['patch'], 'patch_sha256': record['patch_sha256'], 'sources': record['sources'],
    }


def test_buffer_bindings_bind_fixture_sources_and_shared_runner():
    record = preparation()
    for directory, mapping in ((MODULE, record['sources_sha256']),
                               (SCATTER, record['dependency_sources_sha256'])):
        for name, value in mapping.items():
            assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == value
    for path, key in ((MODULE / 'check.py', 'checker_sha256'), (SCATTER / 'check.py', 'shared_checker_sha256'),
                      (MODULE.parent / 'webgpu-input-plan/check.py', 'source_gate_checker_sha256'),
                      (ENV / 'webgpu-input-plan-preparation.json', 'source_gate_record_sha256'),
                      (MODULE.parent / 'webgpu-edge-compute/edge_compute.hlsl', 'edge_shader_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert set(record['generated_sources_sha256']) == {'native_method.inc'}
    assert record['composed_fixture_sha256'] == record['sources_sha256']['compute_test.cc']


def test_buffer_bindings_preserve_ordinary_va_contract_and_fail_closed_for_missing_root():
    record = preparation()
    assert record['shared_descriptor_writer_source_prepared'] and record['dynamic_uniform_address_source_prepared']
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('ToBackend(binding.buffer)->GetVA(), binding', 'baseAddress + binding.offset',
                 'ResolveGlintRootBufferAddress', 'dynamicOffset % 256',
                 'Missing or out-of-range Glint dynamic uniform override.',
                 'D3D12_REQ_CONSTANT_BUFFER_ELEMENT_COUNT', 'HasPrivateGlintReadbackBacking()',
                 'return PopulateGlintViews(allocator, overrides, {}, allocation)'):
        assert text in packet


def test_buffer_bindings_hardware_executes_methods_not_native_dawn_dispatch():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['postguards_passed'] and proof['measurement_complete']
    assert proof['hardware_execution_verified'] and proof['native_source_extension_verified']
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['cases'] == 20 and value['assertions'] == 21728
        assert value['rejected_overrides'] == 244 and value['root_uniform_cases'] == 2
        for key in ('passed', 'hardware_adapter', 'native_descriptor_methods_executed',
                    'cached_descriptors_unchanged', 'original_buffer_unchanged'):
            assert value[key] is True
        assert value['browser_integrated'] is False and value['native_binding_routing_installed'] is False
    for row in proof['source_gate']['runs']:
        assert row['result']['assertions'] == 12802 and row['result']['legacy_assertions'] == 10154
        assert row['result']['actual_native_device_queue_executed'] is False


def test_buffer_bindings_keep_unconnected_native_paths_unadmitted():
    record = preparation()
    syntax = record['native_syntax']
    assert syntax['passed'] and syntax['postguards_passed'] and len(syntax['runs']) == 14
    assert all(row['returncode'] == 0 for row in syntax['runs'])
    for key in ('native_shadow_producer_connected', 'native_binding_routing_installed',
                'writable_copyback_implemented', 'actual_native_device_queue_executed',
                'actual_wire_server_roundtrip_executed', 'gn_rechecked', 'component_link_verified',
                'dxc_execution_verified', 'runtime_verified', 'canvas_gpu_shader_consistency_resolved',
                'selected', 'default_feature_enabled', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_buffer_bindings_changed_inputs_distinguish_cpu_gate_from_hardware_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'fixture', 'model', 'shader', 'checker', 'shared-checker', 'packet',
        'source-gate', 'source-record', 'parameters', 'generated-method-hash',
    }
    for row in proof['cases']:
        assert row['passed'] and row['returncode'] in (1, 2) and row['expected_error_observed']
        assert row['refused_before_hardware_compilation']
        late = row['case'] == 'generated-method-hash'
        assert row['refused_before_any_compilation'] is not late
        assert row['child_cpu_compilation_started'] is late


def test_buffer_bindings_extractor_rejects_missing_native_writer(tmp_path):
    spec = importlib.util.spec_from_file_location('buffer_bindings_check', MODULE / 'check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    source = tmp_path / 'third_party/dawn/src/dawn/native/d3d12/BindGroupD3D12.cpp'
    source.parent.mkdir(parents=True)
    source.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='substring not found'):
        checker.extract_methods(tmp_path)
