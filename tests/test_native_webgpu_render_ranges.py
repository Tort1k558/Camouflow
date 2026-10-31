import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((ENV / 'webgpu-render-ranges-preparation.json').read_bytes())


def test_render_range_source_packet_binds_complete_chain_and_roundtrip():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['exact_patch_roundtrip_verified'] and record['full_ten_packet_source_replay_verified']
    assert record['source_baseline_unchanged']
    assert len(record['sources']) == 5 and len(record['composed_sources']) == 70
    assert hashlib.sha256((ENV / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['prerequisites']) == 9
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    module = ROOT / 'native/drafts/webgpu-render-ranges'
    assert hashlib.sha256((module / 'check.py').read_bytes()).hexdigest() == record['checker_sha256']
    assert hashlib.sha256((module / 'render_ranges_test.cc').read_bytes()).hexdigest() == record['test_sha256']


def test_render_range_draw_paths_are_prepared_not_runtime_verified():
    record = preparation()
    assert set(record['native_draw_cases']) == {
        'draw', 'draw-indexed', 'draw-indirect', 'draw-indexed-indirect',
        'multi-draw-indirect', 'multi-draw-indexed-indirect',
    }
    assert record['shared_render_bundle_encoder_used']
    assert record['bound_vertex_index_slices_not_exact_fetched_elements']
    assert record['active_pipeline_texture_read_flags_source_prepared']
    assert len(record['syntax_checks']) == 3 and record['syntax_diagnostic_bytes'] == 0
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])


def test_render_range_extracted_stride_check_is_explicitly_cpu_only():
    record = preparation()
    source = ROOT / 'native/drafts/webgpu-render-ranges/stride_test.cc'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['stride_test_sha256']
    assert {row['sanitizer'] for row in record['stride_cpu_runs']} == {'none', 'address'}
    for row in record['stride_cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {'passed': True, 'assertions': 32, 'source_extracted_stride_only': True}


def test_render_range_evidence_does_not_grant_gpu_or_privacy_admission():
    record = preparation()
    for key in ('shader_instruction_reflection_implemented', 'actual_native_draw_callbacks_executed',
                'actual_render_bundles_executed', 'internal_indirect_validation_propagation_verified',
                'recording_failure_transaction_verified', 'default_disabled_overhead_measured',
                'actual_native_submission_failure_injected', 'failure_recovery_implemented',
                'default_feature_enabled', 'selected', 'gn_rechecked',
                'chromium_component_link_verified', 'shader_transformation_implemented',
                'canvas_gpu_shader_consistency_resolved', 'runtime_verified',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_render_range_execution_error_callback_is_cpu_checked_not_native_injected():
    record = preparation()
    assert record['native_execution_error_callbacks_source_prepared']
    assert record['cpu_execution_error_callback_verified']
    assert {row['sanitizer'] for row in record['cpu_runs']} == {'none', 'address'}
    for row in record['cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'assertions': 4969123, 'oracle_operations': 4000,
            'controller_scopes': 1000, 'shader_transformation_implemented': False,
        }
    observation = record['public_checker_observation']
    assert observation['passed'] and observation['postguards_passed']
    assert observation['native_handles_synthetic']
    assert all(row['result']['assertions'] == 4969123 for row in observation['runs'])
    assert observation['runtime_verified'] is observation['privacy_admitted'] is False


def test_render_range_full_python_baseline_does_not_prove_native_execution():
    record = preparation()['full_python_baseline']
    assert record['passed'] and record['postguards_passed']
    assert record['git_head'].startswith('4420e6f')
    assert record['counts'] == {
        'tests': 5113, 'passed': 5112, 'skipped': 1, 'failures': 0, 'errors': 0,
    }
