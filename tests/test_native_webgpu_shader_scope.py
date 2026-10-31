import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT/'native/drafts/environment'


def preparation():
    return json.loads((ENV/'webgpu-shader-scope-preparation.json').read_bytes())


def test_shader_scope_packet_binds_dependency_extension_and_measured_sources():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['exact_patch_roundtrip_verified'] and len(record['sources']) == 4
    assert hashlib.sha256((ENV/record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['prerequisites']) == 6
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV/row['patch']).read_bytes()).hexdigest() == row['sha256']
    source = ROOT/'native/drafts/webgpu-shader-scope/shader_scope_test.cc'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['test_sha256']


def test_shader_scope_cpu_checks_are_interim_refusal_not_compatible_pixel_protection():
    record = preparation()
    assert {row['sanitizer'] for row in record['cpu_runs']} == {'none','address'}
    for row in record['cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {'passed': True, 'assertions': 29, 'interim_denial_only': True,
                                 'compatible_shader_protection': False, 'concurrent_scopes': 400}
    assert len(record['syntax_checks']) == 2 and record['syntax_diagnostic_bytes'] == 0
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])


def test_shader_scope_bounds_and_transaction_semantics_remain_explicit():
    record = preparation()
    assert record['metadata_buffer_limit'] == 256
    for name in ('missing_scope_metadata_denies_device', 'input_inspection_precedes_output_mutation',
                 'borrowed_scope_not_retained', 'native_scope_bound_checked_before_vector_allocation',
                 'entire_buffer_ranges_conservative', 'derived_storage_read_denial_prepared'):
        assert record[name]
    assert set(record['native_notification_paths']) == {'dispatch','dispatch-indirect','render-pass'}
    for name in ('default_feature_enabled', 'selected', 'native_shader_scope_callbacks_executed',
                 'compatible_shader_protection', 'exact_binding_ranges_implemented',
                 'chromium_component_link_verified', 'runtime_verified', 'privacy_admitted',
                 'production_admitted', 'canvas_gpu_shader_consistency_resolved'):
        assert record[name] is False


def test_shader_scope_gn_covers_full_tree_and_restores_existing_runtime():
    prepared = preparation()
    assert prepared['gn_graph_verified']
    record = json.loads((ENV/prepared['gn_observations']).read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['patch_sha256'] == prepared['patch_sha256']
    assert len(record['sources']) == 69 and len(record['prerequisites']) == 7
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV/row['patch']).read_bytes()).hexdigest() == row['sha256']
    assert record['source_rollback_verified'] and record['original_git_indexes_unchanged']
    assert record['dawn_git_index_unchanged'] and record['original_build_outputs_unchanged']
    assert {row['mode'] for row in record['graphs']} == {'static','component'}
    for row in record['graphs']:
        assert row['targets'] > 30000 and row['build_files'] == 5063 and len(row['checks']) == 12
        for check in row['checks']:
            assert check['returncode'] == 0
            assert hashlib.sha256(check['stdout'].encode('utf-8')).hexdigest() == check['log_sha256']
    for key in ('selected', 'native_compilation_started', 'native_shader_scope_callbacks_executed',
                'compatible_shader_protection', 'chromium_component_link_verified',
                'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_shader_scope_python_baseline_is_not_native_shader_evidence():
    record = preparation()['full_python_baseline']
    assert record['passed'] and record['postguards_passed'] and record['git_head'].startswith('94739fe')
    assert record['counts'] == {'tests': 5098, 'passed': 5097, 'skipped': 1, 'failures': 0, 'errors': 0}
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
