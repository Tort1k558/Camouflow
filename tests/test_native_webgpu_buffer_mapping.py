import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-buffer-mapping'
SCATTER = MODULE.parent / 'webgpu-buffer-scatter'


def preparation():
    return json.loads((ENV / 'webgpu-buffer-mapping-preparation.json').read_bytes())


def test_buffer_mapping_binds_twenty_three_packets_and_shared_header():
    record = preparation()
    assert record['passed'] and record['exact_twenty_three_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 22 and len(record['sources']) == 6
    assert len(record['composed_sources']) == 86
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    row = next(value for value in record['sources'] if value['source'].endswith('/buffer_scatter_mapping.h'))
    assert row['before_sha256'] is None
    assert hashlib.sha256((SCATTER / 'buffer_scatter_mapping.h').read_bytes()).hexdigest() == row['after_sha256']
    assert record['shared_mapping_header_sha256'] == row['after_sha256']
    for path, key in ((MODULE / 'check.py', 'checker_sha256'), (MODULE / 'predicates-template.cc', 'template_sha256'),
                      (MODULE.parent / 'webgpu-private-backing/check.py', 'shared_checker_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]


def test_buffer_mapping_uses_one_algorithm_and_explicit_native_channel_layout():
    record = preparation()
    for key in ('shared_normalizer_source_prepared', 'plan_scatter_words_source_prepared',
                'physical_initialization_api_source_prepared'):
        assert record[key]
    adapter = (SCATTER / 'buffer_scatter.h').read_text(encoding='utf-8-sig')
    assert 'std::bit_cast<BufferScatterParameters>(*words)' in adapter
    assert 'WebGpuCanonicalByte(' not in adapter
    header = (SCATTER / 'buffer_scatter_mapping.h').read_text(encoding='utf-8-sig')
    assert '(layout.format == WebGpuPixelFormat::kBgra8Unorm) != source_bgra' in header
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('std::array<uint32_t, 16> mapping', 'EnsureGlintAllocationInitialized',
                 'GetAllocatedSize() - GetSize()', 'Toggle::LazyClearResourceOnFirstUse',
                 'std::move(gpu), *mapping'):
        assert text in packet


def test_buffer_mapping_cpu_oracle_and_allocation_contract_are_not_gpu_execution():
    proof = preparation()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['cpu_controller_executed'] and proof['backend_mocked']
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['assertions'] == 110776 and value['prior_plan_assertions'] == 12802
        assert value['legacy_assertions'] == 10154
        assert value['native_mapping_matches_byte_oracle'] and value['physical_padding_contract_verified']
        assert value['backend_mocked'] and value['actual_native_device_queue_executed'] is False


def test_buffer_mapping_keeps_unconnected_producer_and_runtime_gates_closed():
    record = preparation()
    syntax = record['native_syntax']
    assert syntax['passed'] and syntax['postguards_passed'] and len(syntax['runs']) == 15
    assert all(row['returncode'] == 0 for row in syntax['runs'])
    assert any(row['source'].endswith('/BufferD3D12.cpp') for row in syntax['runs'])
    for key in ('native_shadow_producer_connected', 'native_binding_routing_installed',
                'writable_copyback_implemented', 'actual_physical_padding_gpu_clear_executed',
                'actual_native_device_queue_executed', 'actual_wire_server_roundtrip_executed',
                'gn_rechecked', 'component_link_verified', 'dxc_execution_verified', 'runtime_verified',
                'canvas_gpu_shader_consistency_resolved', 'selected', 'default_feature_enabled',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_buffer_mapping_altered_inputs_are_refused_before_compilation():
    proof = preparation()['changed_input_refusal']
    assert proof['passed']
    assert {row['case'] for row in proof['cases']} == {
        'packet', 'template', 'checker', 'shared-checker', 'allocation-hash',
        'generated-fixture-hash', 'legacy-fixture', 'shared-mapper',
    }
    assert all(row['passed'] and row['returncode'] in (1, 2)
               and row['expected_error_observed'] and row['refused_before_compilation']
               for row in proof['cases'])


def test_buffer_mapping_extractor_rejects_divergent_public_native_headers(tmp_path):
    spec = importlib.util.spec_from_file_location('buffer_mapping_check', MODULE / 'check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    path = tmp_path / 'gpu/command_buffer/common/glint/buffer_scatter_mapping.h'
    path.parent.mkdir(parents=True)
    path.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='Shared public/native mapping header differs'):
        checker.extract_contracts(tmp_path)
