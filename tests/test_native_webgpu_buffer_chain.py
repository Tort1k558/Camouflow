import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-buffer-chain'


def observations():
    return json.loads((ENV / 'webgpu-buffer-chain-observations.json').read_bytes())


def test_buffer_chain_binds_fixtures_shaders_extractors_and_source_extension():
    record = observations()
    for name, expected in record['sources_sha256'].items():
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == expected
    for name, expected in record['dependency_files_sha256'].items():
        assert hashlib.sha256((MODULE.parent / name).read_bytes()).hexdigest() == expected
    for path, key in ((MODULE / 'check.py', 'checker_sha256'),
                      (MODULE.parent / 'webgpu-buffer-scatter/check.py', 'shared_checker_sha256'),
                      (MODULE.parent / 'webgpu-buffer-producer/check.py', 'source_gate_checker_sha256'),
                      (ENV / 'webgpu-buffer-producer-preparation.json', 'source_gate_record_sha256')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record[key]
    assert record['composed_fixture_sha256'] == record['sources_sha256']['compute_test.cc']
    extension = record['source_extension']
    assert len(extension['prerequisites']) == 1 and len(extension['sources']) == 4
    for row in [*extension['prerequisites'], {'patch': extension['patch'], 'sha256': extension['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    assert set(record['generated_sources_sha256']) == {
        'native_method.inc', 'descriptor_fixture.h', 'copyback_method.inc',
    }
    assert record['generated_sources_sha256']['descriptor_fixture.h'] == record['dependency_files_sha256'][
        'webgpu-buffer-bindings/descriptor_fixture.h']


def test_buffer_chain_consumes_native_gpu_projection_through_native_descriptor_methods():
    fixture = (MODULE / 'compute_test.cc').read_text(encoding='utf-8-sig')
    assert '#include "descriptor_fixture.h"' in fixture
    assert fixture.index('ProjectedTexture::Record(') < fixture.index('ProjectedBuffer::Record(')
    assert fixture.index('ProjectedBuffer::Record(') < fixture.index('group.PopulateGlintViews(')
    assert fixture.index('group.PopulateGlintViews(') < fixture.index('cmd->Dispatch(')
    for text in ('projected->canonical_pixel_buffer()', 'region.source_retirement = projected->retirement_handle()',
                 'f::GlintBufferViewOverride replacement{0, routed_hold, routed->buffer()}',
                 'Mutate the source AFTER native capture', 'buffer_readback.Get()',
                 'result[i] == expected[canonical]'):
        assert text in fixture
    checker = (MODULE / 'check.py').read_text(encoding='utf-8-sig')
    assert 'checker.extract_methods(native)' in checker
    assert "shutil.copyfile(path.parent / header.name, header)" in checker


def test_buffer_chain_normal_and_asan_hardware_results_keep_standalone_scope():
    proof = observations()['public_checker_observation']
    assert proof['passed'] and proof['measurement_complete'] and proof['postguards_passed']
    assert proof['hardware_execution_verified']
    assert {row['sanitizer'] for row in proof['runs']} == {'none', 'address'}
    for row in proof['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['passed'] and value['hardware_adapter'] and value['cases'] == 40
        assert value['assertions'] == 495537 and value['shared_quota_cases'] == 40
        assert value['typed_texture_consumer_verified'] and value['canonical_plane_verified']
        assert value['native_buffer_descriptor_chain_verified'] and value['source_mutation_isolated']
        assert value['writable_copyback_chain_verified']
        assert value['dependent_retirement_verified'] and value['browser_integrated'] is False


def test_buffer_chain_source_gate_is_separate_from_actual_dawn_submission():
    proof = observations()['public_checker_observation']
    assert proof['source_gate']['passed'] and proof['source_gate']['postguards_passed']
    assert proof['native_source_extension_verified']
    for row in proof['source_gate']['runs']:
        assert row['result']['native_producer_control_flow_executed']
        assert row['result']['backend_mocked']
        assert row['result']['actual_native_device_queue_executed'] is False
    assert proof['actual_native_device_queue_executed'] is False
    assert proof['actual_wire_server_roundtrip_executed'] is False
    assert proof['native_binding_routing_installed'] is False


def test_buffer_chain_does_not_admit_dynamic_receipts_or_browser_runtime():
    record = observations()
    assert all(record[key] for key in ('actual_native_projection_and_budgeted_shadow_helpers_executed',
               'extracted_native_descriptor_methods_executed', 'dawn_objects_and_descriptor_allocator_mocked',
               'writable_copyback_combined_chain_executed', 'extracted_native_copyback_method_executed',
               'readonly_and_writable_uav_modes_checked', 'resource_bytes_outside_logical_buffer_preserved'))
    assert record['combined_shader_compiler'] == 'FXC'
    for key in ('actual_glint_texture_projector_record_buffers_executed',
                'actual_native_binding_tracker_apply_executed', 'dynamic_uniform_root_combined_chain_executed',
                'native_receipt_issuer_executed',
                'actual_native_device_queue_executed', 'actual_wire_server_roundtrip_executed',
                'canvas_gpu_shader_consistency_resolved', 'runtime_verified', 'selected',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_buffer_chain_changed_inputs_are_refused_at_the_documented_compile_boundary():
    proof = observations()['changed_input_refusal']
    assert proof['passed']
    assert len(proof['cases']) == 13
    generated = {'generated-method-hash', 'generated-header-hash', 'generated-copyback-hash'}
    assert {row['case'] for row in proof['cases'] if row['source_gate_compilation_executed']} == generated
    assert all(row['passed'] and row['returncode'] in (1, 2) and row['expected_error_observed']
               and row['refused_before_hardware_compilation'] for row in proof['cases'])


def test_buffer_chain_extracts_copyback_and_checks_writable_data_without_clobbering_padding():
    fixture = (MODULE / 'compute_test.cc').read_text(encoding='utf-8-sig')
    checker = (MODULE / 'check.py').read_text(encoding='utf-8-sig')
    shader = (MODULE / 'buffer_consumer.hlsl').read_text(encoding='utf-8-sig')
    assert '#include "copyback_method.inc"' in fixture
    assert 'MaybeError CopyBackGlintComputeBuffers(' not in fixture
    assert 'source.index(\'    MaybeError CopyBackGlintComputeBuffers(\')' in checker
    for text in ('RunCase(fixture, storage_format, width, height, cancel_cpu_owner, false)',
                 'RunCase(fixture, storage_format, width, height, cancel_cpu_owner, true)',
                 'copyback.CopyBackGlintComputeBuffers(&copyback_context)',
                 'raw_observed[i] == wanted', 'if (writable_input && i < pixel_bytes)',
                 'uint8_t wanted = upload_bytes[i]', 'wanted ^= 0xa5'):
        assert text in fixture
    assert 'void readonly_main(' in shader and 'void writable_main(' in shader
    assert 'WritableInput.Store(id.x * 4, value ^ 0xa5a5a5a5u)' in shader
