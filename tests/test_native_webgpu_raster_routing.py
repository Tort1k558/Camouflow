import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-raster-routing'


def preparation():
    return json.loads((ENV / 'webgpu-raster-routing-preparation.json').read_bytes())


def test_raster_packet_binds_full_chain_and_exact_descriptor_method_fixture():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['exact_parent_roundtrip_verified'] and record['source_baseline_unchanged']
    assert record['full_twelve_packet_source_replay_verified']
    assert len(record['prerequisites']) == 11 and len(record['composed_sources']) == 77
    assert len(record['sources']) == 1
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for name, key in [('check.py','checker_sha256'), ('hardware-fixture.patch','fixture_patch_sha256'),
                      ('descriptor_fixture.h','descriptor_fixture_sha256'), ('raster_consumer.hlsl','raster_shader_sha256')]:
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == record[key]
    base = ROOT / 'native/drafts/webgpu-shadow-texture/shadow_test.cc'
    assert hashlib.sha256(base.read_bytes()).hexdigest() == record['base_hardware_test_sha256']


def test_raster_source_prepares_pass_before_render_begin_and_reuses_bundle_encoder():
    record = preparation()
    for key in ('render_projection_before_pass_begin', 'aggregate_pass_write_dependencies_rejected',
                'existing_shared_draw_bundle_encoder_used', 'per_bind_group_view_cache_prepared'):
        assert record[key] is True
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    assert 'PrepareGlintRenderProjection(' in packet
    assert 'usage & ~kReadOnlyTextureUsages' in packet
    assert 'mGlintGroupSources[groupIndex].Get() == group' in packet
    assert 'DAWN_TRY(PrepareGlintRenderBindings());' in packet
    assert 'mGlintRenderTextures.contains(texture)' in packet


def test_raster_hardware_observation_is_explicitly_not_actual_dawn():
    record = preparation()
    assert record['native_dawn_types_mocked'] is True
    assert {row['sanitizer'] for row in record['hardware_runs']} == {'none', 'address'}
    for row in record['hardware_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        result = row['result']
        assert result['passed'] and result['hardware_adapter']
        assert result['cases'] == result['raster_cases'] == result['shared_quota_cases'] == 8
        assert result['native_render_pass_cases'] == 4 and result['assertions'] == 36269
        assert result['native_dawn_types_mocked'] and result['source_extracted_descriptor_method']
        assert result['original_unchanged'] and result['browser_integrated'] is False
    assert len(record['syntax_checks']) == 7
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])


def test_raster_evidence_keeps_native_and_browser_admissions_closed():
    record = preparation()
    for key in ('native_dawn_dispatch_executed', 'actual_native_raster_routing_executed',
                'actual_native_state_tracker_executed', 'protected_shader_output_provenance_implemented',
                'selected', 'default_feature_enabled', 'gn_rechecked', 'component_link_verified',
                'actual_native_heap_rollover_verified', 'actual_native_state_restoration_verified',
                'canvas_gpu_shader_consistency_resolved', 'runtime_verified', 'privacy_admitted',
                'production_admitted'):
        assert record[key] is False


def test_raster_full_python_baseline_is_separate_from_native_hardware():
    baseline = preparation()['full_python_baseline']
    assert baseline['passed'] and baseline['postguards_passed']
    assert baseline['git_head'].startswith('155c3db')
    assert baseline['counts'] == {'tests': 5144, 'passed': 5143, 'skipped': 1, 'failures': 0, 'errors': 0}


def test_raster_checker_has_no_implicit_unsupported_hardware_or_raw_fallback():
    fixture = (MODULE / 'hardware-fixture.patch').read_text(encoding='utf-8-sig')
    driver = (MODULE / 'check.py').read_text(encoding='utf-8-sig')
    assert 'CHECK(options.RenderPassesValid)' in fixture
    assert 'CHECK(expected != packed)' in fixture
    assert 'group.PopulateGlintViews' in fixture
    assert 'descriptor_method_sha256' in driver
    assert 'D3D_DRIVER_TYPE_WARP' not in driver
    assert 'missing_baseline' in driver


def test_raster_public_checker_replays_sources_without_native_admission():
    observation = preparation()['public_checker_observation']
    assert observation['passed'] and observation['postguards_passed'] and observation['measurement_complete']
    assert observation['hardware_execution_verified'] and observation['native_dawn_types_mocked']
    assert observation['source_extracted_descriptor_method']
    assert {row['sanitizer'] for row in observation['runs']} == {'none', 'address'}
    for row in observation['runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result']['assertions'] == 36269
        assert row['result']['raster_cases'] == 8
        assert row['result']['native_render_pass_cases'] == 4
    for key in ('actual_native_dawn_dispatch_executed', 'actual_native_state_tracker_executed',
                'browser_integrated', 'privacy_admitted', 'production_admitted'):
        assert observation[key] is False


def test_raster_changed_input_checks_refuse_before_compilation():
    refusal = preparation()['changed_input_refusal']
    assert refusal['passed']
    assert {row['case'] for row in refusal['cases']} == {
        'native-packet', 'fixture-patch', 'descriptor-adapter', 'raster-shader', 'method-hash',
    }
    for row in refusal['cases']:
        assert row['passed'] and row['returncode'] == 2
        assert row['refused_before_compilation'] and row['expected_error_observed']
