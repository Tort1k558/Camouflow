import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-compute-projection'


def preparation():
    return json.loads((ENV / 'webgpu-compute-projection-preparation.json').read_bytes())


def test_compute_projection_packet_binds_full_chain_and_public_cpu_checker():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['exact_patch_roundtrip_verified']
    assert record['full_eleven_packet_source_replay_verified']
    assert record['source_baseline_unchanged']
    assert len(record['prerequisites']) == 10
    assert len(record['sources']) == 15 and len(record['composed_sources']) == 77
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for filename, key in [('check.py', 'checker_sha256'), ('seed_test.cc', 'test_sha256')]:
        assert hashlib.sha256((MODULE / filename).read_bytes()).hexdigest() == record[key]


def test_compute_projection_source_prepares_dispatch_local_state_without_admission_bypass():
    record = preparation()
    for key in ('native_compute_direct_indirect_routing_source_prepared',
                'immutable_bind_group_descriptor_copy_source_prepared',
                'pipeline_root_descriptor_immediate_restoration_source_prepared',
                'shared_quota_retirement_owner_kept_with_texture_reference'):
        assert record[key] is True
    patch = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    assert patch.count('+                DAWN_TRY(bindingTracker->PrepareGlintComputeProjection(commandContext));') == 2
    assert '+    ComPtr<IUnknown> retirement;\n+    ComPtr<ID3D12Resource> resource;' in patch
    assert 'GetGlintTextureProjector()' in patch
    assert 'Glint projected texture physical owner' in patch
    assert 'InvalidateAfterGlintProjection' in patch
    assert 'Opaque shader-derived output remains denied' in record['shader_output_map_policy']
    assert 'no raw fallback' in record['unsupported_input_handling']


def test_compute_projection_seed_observation_is_cpu_only_and_clears_failed_output():
    record = preparation()
    assert {row['sanitizer'] for row in record['cpu_seed_runs']} == {'none', 'address'}
    for row in record['cpu_seed_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {'passed': True, 'assertions': 29, 'concurrent_samples': 8000,
                                 'native_gpu_queue_executed': False}
    assert record['cpu_only_checker_scope'] is True


def test_compute_projection_syntax_and_standalone_dxc_are_not_native_execution():
    record = preparation()
    assert len(record['syntax_checks']) == 7
    assert record['syntax_diagnostic_bytes'] == 0
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    assert len(record['standalone_dxc_compiler_sha256']) == 64
    assert {row['sanitizer'] for row in record['standalone_dxc_hardware_runs']} == {'none', 'address'}
    for row in record['standalone_dxc_hardware_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {'passed': True, 'hardware_adapter': True, 'cases': 8,
                                 'assertions': 19220, 'shared_quota_cases': 8,
                                 'typed_texture_consumer_verified': True,
                                 'original_unchanged': True, 'browser_integrated': False}
    for key in ('selected', 'default_feature_enabled', 'gn_rechecked',
                'chromium_component_link_verified', 'actual_native_compute_dispatch_executed',
                'actual_native_descriptor_heap_rollover_verified', 'actual_native_state_restoration_verified',
                'raster_shader_input_routing_implemented', 'full_gpu_format_support',
                'canvas_gpu_shader_consistency_resolved', 'runtime_verified', 'privacy_admitted',
                'production_admitted'):
        assert record[key] is False


def test_compute_projection_python_baseline_is_separate_from_browser_admission():
    baseline = preparation()['full_python_baseline']
    assert baseline['passed'] and baseline['postguards_passed']
    assert baseline['git_head'].startswith('d1b089b')
    assert baseline['counts'] == {'tests': 5138, 'failures': 0, 'errors': 0, 'skipped': 1, 'passed': 5137}


def test_compute_projection_public_replay_checker_matches_the_cpu_seed_scope():
    observation = preparation()['public_cpu_checker_observation']
    assert observation['passed'] and observation['postguards_passed']
    assert {row['sanitizer'] for row in observation['runs']} == {'none', 'address'}
    for row in observation['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result']['assertions'] == 29
        assert row['result']['concurrent_samples'] == 8000
    for key in ('native_gpu_queue_executed', 'wire_roundtrip_tests_executed',
                'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert observation[key] is False
