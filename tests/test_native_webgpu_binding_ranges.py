import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-binding-ranges'


def preparation():
    return json.loads((ENV / 'webgpu-binding-ranges-preparation.json').read_bytes())


def test_binding_ranges_packet_and_reproducible_checker_are_bound():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['exact_patch_roundtrip_verified']
    assert record['full_nine_packet_source_replay_verified'] and record['source_baseline_unchanged']
    assert len(record['sources']) == 3 and len(record['composed_sources']) == 69
    assert hashlib.sha256((ENV / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['prerequisites']) == 8
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    assert hashlib.sha256((MODULE / 'binding_ranges_test.cc').read_bytes()).hexdigest() == record['test_sha256']
    assert hashlib.sha256((MODULE / 'check.py').read_bytes()).hexdigest() == record['checker_sha256']


def test_binding_ranges_cpu_oracles_cover_ranges_aliases_and_unique_buffer_limit():
    record = preparation()
    assert {row['sanitizer'] for row in record['cpu_runs']} == {'none', 'address'}
    for row in record['cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {
            'passed': True, 'assertions': 4969118, 'oracle_operations': 4000,
            'controller_scopes': 1000, 'shader_transformation_implemented': False,
        }
    assert record['compute_binding_ranges_source_prepared']
    assert record['render_scope_still_whole_buffer']


def test_binding_ranges_public_cpu_checker_was_executed_without_admission():
    record = preparation()['public_checker_observation']
    assert record['passed'] and record['postguards_passed'] and record['native_handles_synthetic']
    assert len(record['runs']) == 2
    assert {row['sanitizer'] for row in record['runs']} == {'none', 'address'}
    for row in record['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result']['assertions'] == 4969118
    for key in ('wire_roundtrip_tests_executed', 'runtime_verified',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_binding_ranges_native_source_syntax_is_not_native_execution():
    record = preparation()
    assert len(record['syntax_checks']) == 2
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    for key in ('actual_dynamic_offsets_executed', 'actual_indirect_execution_verified',
                'actual_texel_views_executed', 'native_shader_callbacks_executed',
                'gn_rechecked', 'chromium_component_link_verified', 'selected',
                'shader_transformation_implemented', 'canvas_gpu_shader_consistency_resolved',
                'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_binding_ranges_full_python_baseline_does_not_prove_native_behavior():
    record = preparation()['full_python_baseline']
    assert record['passed'] and record['postguards_passed']
    assert record['git_head'].startswith('439d8d6')
    assert record['counts'] == {
        'tests': 5108, 'passed': 5107, 'skipped': 1, 'failures': 0, 'errors': 0,
    }
