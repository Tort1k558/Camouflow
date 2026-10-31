"""Bind the unselected CPU controller without claiming native map protection."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((ENV / 'webgpu-readback-controller-preparation.json').read_bytes())


def test_controller_packet_binds_seven_paths_and_prerequisites():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['exact_patch_roundtrip_verified'] and len(record['sources']) == 7
    assert hashlib.sha256((ENV / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert {row['patch'] for row in record['prerequisites']} == {
        'webgpu-native-copy-hook-next.patch', 'shared-gpu-readback-core-next.patch',
        'webgpu-renderer-policy-transport-next.patch'}
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']


def test_added_controller_sources_extract_and_reverse_exactly(tmp_path):
    record = preparation()
    rows = [row for row in record['sources'] if row['before_sha256'] is None]
    assert len(rows) == 2
    command = ['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
               '--include=gpu/command_buffer/service/glint_webgpu_readback_observer.*']
    subprocess.run(command + [str(ENV / record['patch'])], cwd=tmp_path,
                   check=True, capture_output=True, timeout=15)
    for row in rows:
        assert hashlib.sha256((tmp_path / row['source']).read_bytes()).hexdigest() == row['staged_sha256']
    subprocess.run(command + ['--reverse', str(ENV / record['patch'])], cwd=tmp_path,
                   check=True, capture_output=True, timeout=15)
    assert all(not (tmp_path / row['source']).exists() for row in rows)


def test_controller_measurements_are_cpu_and_syntax_only():
    record = preparation()
    assert len(record['syntax_checks']) == 4 and record['syntax_diagnostic_bytes'] == 0
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    assert {row['sanitizer'] for row in record['cpu_runs']} == {'none', 'address'}
    for row in record['cpu_runs']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == {'passed': True, 'assertions': 113, 'concurrent_maps': 400}
    for name in ('selected', 'chromium_component_link_verified',
                 'gpu_service_observer_registered', 'native_map_shadow_installed',
                 'shared_memory_map_protected', 'shader_taint_propagation_installed',
                 'runtime_verified', 'privacy_admitted', 'production_admitted',
                 'canvas_gpu_export_mismatch_resolved'):
        assert record[name] is False


def test_controller_readback_failures_do_not_authorize_raw_fallback():
    record = preparation()
    assert record['native_buffer_sizes_carried_without_reentry']
    assert record['borrowed_handles_not_dereferenced']
    assert record['failed_capture_denied_until_buffer_destruction']
    assert record['pending_capture_retry_supported']
    assert record['snapshot_budget_bytes'] == record['map_shadow_limit_bytes'] == 64 * 1024 * 1024
    assert record['buffer_limit'] == 256 and record['snapshot_slots'] == 16
    directory = ROOT / 'native/drafts/webgpu-readback-controller'
    assert hashlib.sha256((directory / 'controller_test.cc').read_bytes()).hexdigest() == record['test_sha256']


def test_public_cpu_sources_are_bound_without_redefining_native_integration():
    record = preparation()
    checker = ROOT / 'native/drafts/webgpu-readback-controller/check.py'
    assert hashlib.sha256(checker.read_bytes()).hexdigest() == record['public_checker_sha256']
    assert len(record['public_cli_report_sha256']) == 64
    assert record['public_cli_runs'] == record['cpu_runs']
    sources = record['cpu_sources_sha256']
    assert sources['controller_test.cc'] == record['test_sha256']
    for row in record['sources']:
        if row['source'] in sources:
            assert sources[row['source']] == row['staged_sha256']
    for relative, digest in sources.items():
        if relative.startswith('gpu/command_buffer/common/glint_webgpu_device_policy.'):
            path = ROOT / 'native/drafts/webgpu-private-policy' / Path(relative).name
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_combined_controller_gn_preserves_sources_indexes_and_runtime():
    prepared = preparation()
    assert prepared['gn_graph_verified']
    record = json.loads((ENV / prepared['gn_observations']).read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['controller_patch_sha256'] == prepared['patch_sha256']
    assert len(record['sources']) == 56 and len(record['prerequisites']) == 5
    for row in record['prerequisites']:
        assert hashlib.sha256((ENV / row['patch']).read_bytes()).hexdigest() == row['sha256']
    assert record['source_rollback_verified'] and record['original_git_indexes_unchanged']
    assert record['dawn_git_index_unchanged'] and record['original_build_outputs_unchanged']
    assert {row['mode'] for row in record['graphs']} == {'static', 'component'}
    for row in record['graphs']:
        assert row['targets'] > 30000 and row['build_files'] == 5063
        assert len(row['checks']) == 8
        for check in row['checks']:
            assert check['returncode'] == 0
            assert hashlib.sha256(check['stdout'].encode('utf-8')).hexdigest() == check['log_sha256']
    for name in ('selected', 'native_compilation_started', 'chromium_component_link_verified',
                 'gpu_service_observer_registered', 'native_map_shadow_installed',
                 'runtime_verified', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False
