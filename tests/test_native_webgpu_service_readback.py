"""Verify source/proof binding without claiming execution of the new Wire tests."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((ENV / 'webgpu-service-readback-preparation.json').read_bytes())


def test_service_readback_packet_binds_17_paths_and_five_prerequisites():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert len(record['sources']) == 17 and len(record['composed_sources']) == 69
    assert record['exact_patch_roundtrip_verified'] and record['six_packet_composition_verified']
    assert hashlib.sha256((ENV / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['prerequisites']) == 5
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']


def test_service_bridge_added_sources_extract_and_reverse(tmp_path):
    record = preparation()
    rows = [row for row in record['sources'] if row['before_sha256'] is None]
    assert len(rows) == 2
    command = ['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
               '--include=gpu/command_buffer/service/glint_webgpu_wire_filter.*']
    subprocess.run(command + [str(ENV / record['patch'])], cwd=tmp_path,
                   check=True, capture_output=True, timeout=15)
    for row in rows:
        assert hashlib.sha256((tmp_path / row['source']).read_bytes()).hexdigest() == row['staged_sha256']
    subprocess.run(command + ['--reverse', str(ENV / record['patch'])], cwd=tmp_path,
                   check=True, capture_output=True, timeout=15)
    assert all(not (tmp_path / row['source']).exists() for row in rows)


def test_service_measurements_distinguish_mock_bridge_from_real_wire_execution():
    record = preparation()
    assert len(record['syntax_checks']) == 7 and len(record['wire_test_syntax_checks']) == 2
    assert record['syntax_diagnostic_bytes'] == 0
    assert all(row['returncode'] == 0 for row in record['syntax_checks'] + record['wire_test_syntax_checks'])
    assert {row['sanitizer'] for row in record['cpu_runs']} == {'none', 'address'}
    for row in record['cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {'passed': True, 'assertions': 36, 'concurrent_maps': 800,
                                 'native_lookup_mocked': True}
    assert record['native_device_lookup_mocked_in_cpu_tests']
    assert record['wire_roundtrip_tests_prepared'] == 8
    assert record['wire_roundtrip_tests_executed'] is False
    path = ROOT / 'native/drafts/webgpu-service-readback/bridge_test.cc'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['bridge_test_sha256']
    checker = path.with_name('check.py')
    assert hashlib.sha256(checker.read_bytes()).hexdigest() == record['public_checker_sha256']
    assert record['public_cli_runs'] == record['cpu_runs']


def test_service_preparation_has_no_privacy_or_runtime_admission():
    record = preparation()
    for key in ('native_observer_registration_prepared', 'ordinary_map_serialization_filter_prepared',
                'direct_backing_disabled_for_protected_buffers_in_source',
                'disabled_feature_policy_command_rejected', 'immutable_policy_retry_prepared',
                'epoch_saturates_in_source'):
        assert record[key]
    for key in ('selected', 'default_feature_enabled', 'chromium_component_link_verified',
                'gpu_service_observer_runtime_registered', 'native_map_shadow_runtime_installed',
                'shared_memory_privacy_verified', 'shader_taint_propagation_installed',
                'runtime_verified', 'privacy_admitted', 'production_admitted',
                'canvas_gpu_export_mismatch_resolved'):
        assert record[key] is False


def test_service_wire_cases_are_prepared_not_reported_as_executed():
    record = preparation()
    patch = (ENV / record['patch']).read_text(encoding='utf-8-sig')
    added = '\n'.join(line[1:] for line in patch.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    names = re.findall(r'TEST_F\(WireFiltered(?:Readback|Backing)Tests,\s*(\w+)\)', added)
    assert set(names) == {
        'ProtectedBytesAreSerializedWithoutModifyingNativeInput',
        'ProtectedPartialMapPreservesAbsoluteOffset', 'DenialDoesNotReadOrSerializeNativeBytes',
        'WrongShadowSizeFailsClosed', 'UnprotectedDeviceRetainsExistingReadBehavior',
        'NativeMapFailureDoesNotInvokeFilter', 'ProtectedDeviceNeverAttemptsDirectSharedBacking',
        'UnprotectedDeviceRetainsDirectBackingOptimization'}
    assert len(names) == record['wire_roundtrip_tests_prepared'] == 8
    assert record['wire_roundtrip_tests_executed'] is False


def test_service_gn_checks_cover_native_wire_service_and_test_headers_without_linking():
    prepared = preparation()
    assert prepared['gn_graph_verified']
    record = json.loads((ENV / prepared['gn_observations']).read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['service_patch_sha256'] == prepared['patch_sha256']
    assert record['sources'] == prepared['composed_sources'] and len(record['sources']) == 69
    assert len(record['prerequisites']) == 6
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    assert record['source_rollback_verified'] and record['original_git_indexes_unchanged']
    assert record['dawn_git_index_unchanged'] and record['original_build_outputs_unchanged']
    assert {row['mode'] for row in record['graphs']} == {'static', 'component'}
    for row in record['graphs']:
        assert row['targets'] > 30000 and row['build_files'] == 5063
        assert len(row['checks']) == 12
        for check in row['checks']:
            assert check['returncode'] == 0
            assert hashlib.sha256(check['stdout'].encode('utf-8')).hexdigest() == check['log_sha256']
    for key in ('selected', 'native_compilation_started', 'chromium_component_link_verified',
                'wire_roundtrip_tests_executed', 'gpu_service_observer_runtime_registered',
                'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
