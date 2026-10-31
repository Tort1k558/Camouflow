import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-execution-inputs'


def preparation():
    return json.loads((ENV / 'webgpu-execution-inputs-preparation.json').read_bytes())


def test_execution_inputs_bind_full_chain_and_extracted_public_fixture():
    record = preparation()
    assert record['passed'] and record['exact_sixteen_packet_replay_and_reverse_verified']
    assert len(record['prerequisites']) == 15
    assert len(record['sources']) == 4 and len(record['composed_sources']) == 81
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for name, key in [('check.py', 'checker_sha256'), ('predicates-template.cc', 'template_sha256')]:
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == record[key]
    assert hashlib.sha256((MODULE.parent / 'webgpu-private-backing/check.py').read_bytes()).hexdigest() == record['shared_checker_sha256']
    assert set(record['extracted_predicates_sha256']) == {'inputs', 'native_use', 'indirect', 'attachments'}


def test_execution_inputs_preserve_logical_controls_before_scratch_rewrites():
    record = preparation()
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('struct GlintIndirectInputs', 'Ref<BufferBase> countBuffer',
                 'dispatch->glintInputs = std::move(glintInputs)', '&dispatch->glintInputs',
                 'AppendGlintOriginalIndirectUses', 'Missing or invalid original Glint dispatch inputs',
                 'Missing or invalid original Glint draw inputs', 'Missing or invalid original Glint multi-draw inputs'):
        assert text in packet
    added = '\n'.join(line[1:] for line in packet.splitlines() if line.startswith('+') and not line.startswith('+++'))
    assert added.count('cmd->glintInputs = ') == 4
    assert added.count('glintInputs = {indirectBuffer, indirectOffset') == 5
    for key in ('logical_indirect_inputs_retained_source_prepared',
                'compute_draw_indexed_multi_draw_frontend_capture_source_prepared',
                'logical_and_executed_controls_both_considered_source_prepared'):
        assert record[key] is True
    syntax = record['proofs']['native_syntax']['runs']
    assert len(syntax) == 13 and all(row['returncode'] == 0 for row in syntax)
    assert all(any(row['source'].endswith(name + '.cpp') for row in syntax)
               for name in ('Commands', 'ComputePassEncoder', 'RenderEncoderBase'))


def test_execution_inputs_do_not_promote_unprojected_attachment_dependencies():
    record = preparation()
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    for text in ('HasGlintUnprojectedAttachmentInputs', 'depthStencil.depthReadOnly',
                 'depthStencil.stencilReadOnly', 'pass.storageAttachments',
                 'mGlintRenderScope.textureInputs = mGlintRenderUnprojectedInputs',
                 'mGlintRenderProjectedReady && !mGlintRenderUnprojectedInputs'):
        assert text in packet
    assert record['implicit_attachment_readiness_source_prepared']
    assert record['cleared_depth_stencil_eligibility_cpu_verified']
    for key in ('loaded_depth_stencil_projection_implemented', 'pixel_local_storage_projection_implemented'):
        assert record[key] is False


def test_execution_inputs_cpu_evidence_keeps_backend_scope_explicit():
    record = preparation()
    runs = record['proofs']['cpu_contracts']['runs']
    assert {row['sanitizer'] for row in runs} == {'none', 'address'}
    for row in runs:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['passed'] and value['assertions'] == 2391
        assert value['attachment_cases'] == 720 and value['accepted_attachment_cases'] == 49
        assert value['denied_logical_control_cases'] == 2
        assert value['source_extracted_input_contracts_only'] and value['backend_mocked']
        assert not value['actual_frontend_encoding_executed'] and not value['actual_native_device_queue_executed']
    observed = record['public_checker_observation']
    assert observed['passed'] and observed['measurement_complete'] and observed['postguards_passed']
    assert observed['cpu_controller_executed'] and observed['source_extracted_control_flow_only']


def test_execution_inputs_do_not_admit_unfinished_native_browser_paths():
    record = preparation()
    for key in ('actual_frontend_encoding_executed', 'actual_native_depth_stencil_executed',
                'actual_native_device_queue_executed', 'actual_wire_server_roundtrip_executed',
                'full_raster_output_protection_implemented', 'gpu_buffer_input_projection_implemented',
                'all_native_buffer_write_paths_audited', 'gn_rechecked', 'component_link_verified',
                'gpu_execution_verified', 'runtime_verified', 'selected', 'default_feature_enabled',
                'canvas_gpu_shader_consistency_resolved', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    baseline = record['full_python_baseline']
    assert baseline['passed'] and baseline['postguards_passed'] and baseline['git_head'].startswith('1f322d9')
    assert baseline['counts'] == {'tests': 5175, 'passed': 5174, 'skipped': 1, 'failures': 0, 'errors': 0}


def test_execution_inputs_extractor_rejects_missing_source_contracts(tmp_path):
    spec = importlib.util.spec_from_file_location('execution_input_check', MODULE / 'check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    native = tmp_path / 'third_party/dawn/src/dawn/native'
    (native / 'd3d12').mkdir(parents=True)
    (native / 'Commands.h').write_text('', encoding='utf-8')
    (native / 'd3d12/CommandBufferD3D12.cpp').write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='substring not found'):
        checker.extract_contracts(tmp_path)


def test_execution_inputs_changed_inputs_are_refused_before_compilation():
    observation = preparation()['changed_input_refusal']
    assert observation['passed']
    assert {row['case'] for row in observation['cases']} == {
        'packet', 'template', 'shared-checker', 'extraction-hash', 'generated-fixture-hash',
    }
    for row in observation['cases']:
        assert row['passed'] and row['returncode'] in (1, 2)
        assert row['expected_error_observed'] and row['refused_before_compilation']
