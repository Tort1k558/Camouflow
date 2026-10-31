import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'
MODULE = ROOT / 'native/drafts/webgpu-shader-capture'


def preparation():
    return json.loads((ENV / 'webgpu-shader-capture-preparation.json').read_bytes())


def test_shader_capture_batch_binds_full_chain_and_public_fixtures():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['full_thirteen_packet_source_replay_verified'] and record['exact_roundtrip_verified']
    assert record['full_thirteen_packet_reverse_verified']
    assert len(record['prerequisites']) == 12 and len(record['sources']) == 12
    assert len(record['composed_sources']) == 77
    for row in [*record['prerequisites'], {'patch': record['patch'], 'sha256': record['patch_sha256']}]:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    for name, key in [('check.py', 'checker_sha256'), ('controller_test.cc', 'controller_test_sha256'),
                      ('core_test.cc', 'core_test_sha256'), ('hardware.patch', 'hardware_patch_sha256'),
                      ('bridge-template.h', 'bridge_template_sha256')]:
        assert hashlib.sha256((MODULE / name).read_bytes()).hexdigest() == record[key]


def test_shader_capture_native_hooks_are_source_preparation_not_runtime():
    record = preparation()
    for key in ('native_compute_direct_indirect_capture_hook_source_prepared',
                'native_owner_and_writable_range_validation_source_prepared',
                'readiness_set_only_after_projection_success',
                'controller_failure_propagates_as_native_recording_error_source_prepared'):
        assert record[key] is True
    packet = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    assert 'CaptureGlintComputeScope(commandContext)' in packet
    assert 'mGlintComputeProjectedReady = false' in packet
    assert 'mGlintComputeProjectedReady = true' in packet
    assert 'Glint byte capture exceeds writable bindings' in packet
    assert 'RecordGlintNativeByteSnapshot' in packet
    assert 'Glint shader capture controller failed' in packet
    assert 'cmd->destinationOffset, ToQueryStorageSize(cmd->queryCount)' in packet
    assert record['query_resolve_write_invalidation_source_prepared'] is True
    syntax = record['proofs']['native_syntax']['runs']
    assert len(syntax) == 10 and all(row['returncode'] == 0 for row in syntax)


def test_shader_capture_controller_and_legacy_cpu_evidence_keep_gpu_scope_explicit():
    record = preparation()
    for label, count in [('cpu_controller', 10154), ('legacy_cpu', 4969123)]:
        rows = record['proofs'][label]['runs']
        assert {row['sanitizer'] for row in rows} == {'none', 'address'}
        for row in rows:
            assert row['compile_returncode'] == row['test_returncode'] == 0
            assert row['result']['passed'] and row['result']['assertions'] == count
            if label == 'cpu_controller':
                assert row['result']['scope_cycles'] == 2000
                assert row['result']['actual_native_gpu_hook_executed'] is False
                assert row['result']['native_handles_synthetic'] is True


def test_shader_capture_hardware_filter_evidence_is_not_wire_server_execution():
    record = preparation()
    rows = record['proofs']['gpu_controller_filter']['runs']
    assert {row['sanitizer'] for row in rows} == {'none', 'address'}
    for row in rows:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        value = row['result']
        assert value['passed'] and value['hardware_adapter']
        assert value['assertions'] == 47613 and value['cases'] == 8
        assert value['gpu_controller_filter_prepare_verified']
        assert value['exact_buffer_snapshot_verified']
        assert value['actual_wire_server_roundtrip_executed'] is False
        assert value['actual_native_device_queue_executed'] is False
        assert value['browser_integrated'] is False


def test_shader_capture_does_not_admit_unfinished_native_browser_paths():
    record = preparation()
    for key in ('actual_native_device_queue_executed', 'actual_native_capture_hook_executed',
                'actual_wire_server_roundtrip_executed', 'raster_output_capture_implemented',
                'gpu_buffer_input_projection_implemented', 'selected', 'default_feature_enabled',
                'component_link_verified', 'runtime_verified',
                'canvas_gpu_shader_consistency_resolved', 'privacy_admitted', 'production_admitted',
                'all_native_buffer_write_paths_audited'):
        assert record[key] is False


def test_shader_capture_gn_checks_are_not_component_link_or_runtime():
    record = preparation()
    assert record['gn_rechecked'] is True
    result = record['gn_only_observation']
    assert result['passed'] and result['sources_restored'] and result['postguards_passed']
    assert result['shader_capture_packet_sha256'] == record['patch_sha256']
    assert len(result['runs']) == 26 and all(row['returncode'] == 0 for row in result['runs'])
    for mode in ('static', 'component'):
        assert sum(row['name'].startswith(mode + '-') for row in result['runs']) == 12
    for key in ('native_compilation_started', 'component_link_verified', 'runtime_verified'):
        assert result[key] is False


def test_shader_capture_cli_reuses_sources_and_checks_requested_suite():
    driver = (MODULE / 'check.py').read_text(encoding='utf-8-sig')
    for name in ('hardware', 'controller', 'core', 'legacy', 'texture-compat'):
        assert name in driver
    assert 'Generated adapter/filter bridge differs' in driver
    assert 'Composed shader capture fixture differs' in driver
    assert 'Missing explicitly requested standalone suite scope' in driver
    assert 'missing_baseline' in driver
    assert 'D3D_DRIVER_TYPE_WARP' not in driver


def test_shader_capture_python_baseline_is_separate_from_native_admission():
    baseline = preparation()['full_python_baseline']
    assert baseline['passed'] and baseline['postguards_passed']
    assert baseline['git_head'].startswith('383803b')
    assert baseline['counts'] == {'tests': 5152, 'passed': 5151, 'skipped': 1, 'failures': 0, 'errors': 0}


def test_shader_capture_all_public_suites_reproduce_their_own_scopes():
    suites = preparation()['public_suites']
    expected = {'hardware': 47613, 'controller': 10154, 'core': 4886,
                'legacy': 4969123, 'texture-compat': 22720}
    assert set(suites) == set(expected)
    for name, observation in suites.items():
        assert observation['passed'] and observation['measurement_complete'] and observation['postguards_passed']
        assert observation['suite'] == name
        assert observation['hardware_execution_verified'] == (name in {'hardware', 'texture-compat'})
        assert {row['sanitizer'] for row in observation['runs']} == {'none', 'address'}
        for row in observation['runs']:
            assert row['compile_returncode'] == row['test_returncode'] == 0
            assert row['result']['passed'] and row['result']['assertions'] == expected[name]
        for key in ('actual_native_dawn_dispatch_executed', 'actual_native_state_tracker_executed',
                    'browser_integrated', 'privacy_admitted', 'production_admitted'):
            assert observation[key] is False


def test_shader_capture_changed_inputs_are_rejected_before_compilation():
    refusal = preparation()['changed_input_refusal']
    assert refusal['passed']
    assert {row['case'] for row in refusal['cases']} == {
        'native-packet', 'hardware-delta', 'bridge-template', 'controller-fixture',
        'core-fixture', 'adapter-hash', 'generated-bridge-hash',
    }
    for row in refusal['cases']:
        assert row['passed'] and row['returncode'] == 2
        assert row['refused_before_compilation'] and row['expected_error_observed']
