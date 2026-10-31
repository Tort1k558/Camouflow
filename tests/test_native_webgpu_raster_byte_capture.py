import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-raster-byte-capture'


def preparation():
    return json.loads((ENV / 'webgpu-raster-byte-capture-preparation.json').read_bytes())


def test_raster_byte_capture_binds_full_source_chain_and_public_assets():
    record = preparation()
    assert record['passed'] and record['exact_fifteen_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 14
    assert len(record['sources']) == 1 and len(record['composed_sources']) == 78
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for name, key in [('check.py', 'checker_sha256'), ('predicates-template.cc', 'template_sha256'),
                      ('hardware.patch', 'hardware_patch_sha256'), ('raster_consumer.hlsl', 'raster_shader_sha256'),
                      ('raster-scope-template.h', 'raster_scope_template_sha256')]:
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == record[key]
    shared = MODULE.parent / 'webgpu-private-backing/check.py'
    assert hashlib.sha256(shared.read_bytes()).hexdigest() == record['shared_checker_sha256']


def test_raster_byte_capture_retains_controls_and_reuses_the_compute_capture_path():
    record = preparation()
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('struct GlintNativeBufferUse', 'Ref<BufferBase> owner', 'MergeGlintBoundScope',
                 'AccumulateGlintRenderScope', 'CaptureGlintBoundScope', 'CaptureGlintRenderScope(commandContext)',
                 'Buffer copies/transitions are forbidden inside a native render pass.'):
        assert text in packet
    added = '\n'.join(line[1:] for line in packet.splitlines() if line.startswith('+') and not line.startswith('+++'))
    assert len(re.findall(r'DAWN_TRY\(\s*notifyDraw\(', added)) == 6
    for key in ('native_raster_byte_capture_source_prepared', 'pass_capture_after_end_source_prepared',
                'native_control_input_owners_retained_source_prepared', 'native_syntax_verified'):
        assert record[key] is True
    runs = record['proofs']['native_syntax']['runs']
    assert len(runs) == 10 and all(row['returncode'] == 0 for row in runs)


def test_raster_byte_capture_cpu_oracle_and_controller_scope_is_explicit():
    record = preparation()
    runs = record['proofs']['cpu_merge_controller']['runs']
    assert {row['sanitizer'] for row in runs} == {'none', 'address'}
    for row in runs:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['passed'] and value['assertions'] == 191422
        assert value['oracle_passes'] == 1000 and value['oracle_draws'] == 16000
        assert value['duplicate_draws'] == 8192 and value['controller_passes'] == 256
        assert value['source_extracted_merge_only'] and value['backend_mocked']
        assert value['actual_native_render_pass_executed'] is False
    observed = record['public_checker_observation']
    assert observed['passed'] and observed['measurement_complete'] and observed['postguards_passed']
    assert observed['cpu_controller_executed'] and observed['source_extracted_control_flow_only']


def test_raster_byte_capture_hardware_proof_is_not_dawn_or_wire_execution():
    runs = preparation()['proofs']['hardware']['runs']
    assert {row['sanitizer'] for row in runs} == {'none', 'address'}
    for row in runs:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['passed'] and value['hardware_adapter'] and value['assertions'] == 58791
        assert value['cases'] == value['raster_cases'] == 8
        assert value['raster_scope_draws'] == 16 and value['native_render_pass_cases'] == 4
        assert value['raster_shader_byte_capture_verified'] and value['native_dawn_types_mocked']
        for key in ('actual_native_render_pass_executed', 'actual_native_device_queue_executed',
                    'actual_wire_server_roundtrip_executed', 'browser_integrated'):
            assert value[key] is False


def test_raster_byte_capture_does_not_admit_unfinished_browser_paths():
    record = preparation()
    for key in ('gn_rechecked', 'component_link_verified', 'actual_dawn_render_pass_executed',
                'actual_native_device_queue_executed', 'actual_wire_server_roundtrip_executed',
                'full_raster_output_protection_implemented', 'gpu_buffer_input_projection_implemented',
                'all_native_buffer_write_paths_audited', 'runtime_verified', 'selected',
                'default_feature_enabled', 'canvas_gpu_shader_consistency_resolved',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    baseline = record['full_python_baseline']
    assert baseline['passed'] and baseline['postguards_passed'] and baseline['git_head'].startswith('657ad89')
    assert baseline['counts'] == {'tests': 5168, 'passed': 5167, 'skipped': 1, 'failures': 0, 'errors': 0}


def test_raster_byte_capture_extractor_requires_the_actual_method(tmp_path):
    spec = importlib.util.spec_from_file_location('raster_capture_check', MODULE / 'check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    path = tmp_path / 'third_party/dawn/src/dawn/native/d3d12/CommandBufferD3D12.cpp'
    path.parent.mkdir(parents=True)
    path.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='substring not found'):
        checker.extract_merge(tmp_path)


def test_raster_byte_capture_changed_inputs_fail_before_compilation():
    observation = preparation()['changed_input_refusal']
    assert observation['passed']
    assert {row['case'] for row in observation['cases']} == {
        'packet', 'template', 'shared-checker', 'extraction-hash', 'generated-fixture-hash',
    }
    for row in observation['cases']:
        assert row['passed'] and row['returncode'] in (1, 2)
        assert row['expected_error_observed'] and row['refused_before_compilation']
