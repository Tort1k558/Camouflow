import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'native/drafts/environment/gpu-process-recovery'


def observation():
    return json.loads((MODULE / 'observations.json').read_bytes())


def historical_probe_inputs():
    from scripts.verify_native_gpu_readback import probe_inputs

    sources = probe_inputs(candidate_name='upstream-156')
    # This CLI was added after the frozen 226-file GPU recovery measurements.
    del sources['scripts/verify_native_audio_lifecycle.py']
    # The checkpoint runner also postdates these frozen measurements.
    del sources['scripts/verify_native_checkpoint_units.py']
    return sources


def test_gpu_recovery_control_binds_public_sources_and_exact_runtime(host_sources_before_webgpu_r2, host_sources_before_profile_surface):
    record = observation()
    for name, expected in record['source_sha256'].items():
        source = host_sources_before_profile_surface['sources'].get(
            name, host_sources_before_webgpu_r2.get(name, (ROOT / name).read_bytes()))
        assert hashlib.sha256(source).hexdigest() == expected
    earlier = json.loads((ROOT / 'native/drafts/environment/webgpu-diagnostic-variant76-control-observations.json').read_bytes())
    for name in ('runtime_core_sha256_measured', 'candidate_manifest_sha256', 'receipt_sha256'):
        assert record[name] == earlier[name]
    assert record['passed'] and record['candidate'] == 'upstream-156'
    for name in ('protected_policies_enabled', 'protected_policy_recovery_verified',
                 'complete_candidate_verified', 'physical_gpu_reset_tested', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def test_gpu_recovery_complete_input_digest_preserves_measured_newlines(historical_source_newlines,
                                                                     native_build_before_index_mtime_fix,
                                                                     host_sources_before_webgpu_r2, host_sources_before_profile_surface,
                                                                     host_sources_before_monitor_gap_reset):
    sources = historical_probe_inputs()
    sources.update({name: hashlib.sha256(value).hexdigest()
                    for name, value in host_sources_before_monitor_gap_reset.items()})
    sources.update({name: hashlib.sha256(value).hexdigest() for name, value in host_sources_before_webgpu_r2.items()})
    sources.update({name: value for name, value in host_sources_before_profile_surface['sha256'].items()
                    if name in sources})
    for name in host_sources_before_profile_surface['absent']:
        assert name in sources
        del sources[name]
    sources[native_build_before_index_mtime_fix['source']] = native_build_before_index_mtime_fix['before_sha256']
    paths = [MODULE / 'collect.py', MODULE / 'watch.js',
             ROOT / 'native/drafts/environment/first-script/webgpu_shader_dataflow.js',
             ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json']
    for path in paths:
        sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name, row in historical_source_newlines.items():
        if name in sources:
            sources[name] = row['measured_sha256']
    record = observation()
    assert len(sources) == record['complete_probe_input_count'] == 226
    encoded = json.dumps(sources, sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(encoded).hexdigest() == record['complete_probe_input_snapshot_sha256']


def test_gpu_recovery_three_actual_runs_preserve_document_pixels_and_cleanup():
    rows = observation()['runs']
    assert len(rows) == 3 and {row['attempt'] for row in rows} == {1, 2, 3}
    reference = bytes(channel for y in range(16) for x in range(16)
                      for channel in ((x * 17) % 256, (y * 29 + 31) % 256,
                                      (x * 43 + y * 11) % 256, 255))
    digest = hashlib.sha256(reference).hexdigest()
    for row in rows:
        assert row['before'] == row['after'] == {'reference_matched': True,
            'rgba_sha256': digest, 'shader_sha256': digest, 'png_rgba_sha256': digest}
        assert row['loss'] == {'initialCopyMatched': True, 'deviceLostCallbacks': 1,
            'reason': 'unknown', 'oldMapRejectedWith': 'AbortError', 'oldMapState': 'unmapped'}
        assert row['runtime_asset_count'] == 269 and row['page_crashes'] == 0
        assert not row['remaining_owned_processes']
        assert all(row[name] is True for name in ('same_document_preserved', 'actual_gpu_crash_command_completed',
            'baseline_recovered', 'runtime_assets_unchanged', 'input_postguards_passed', 'driver_unchanged',
            'receipt_unchanged', 'server_closed', 'runtime_resource_free', 'owned_profiles_removed'))
        assert row['seconds'] > 0 and len(row['private_report_sha256']) == 64


def test_gpu_recovery_collector_import_has_no_cli_or_filesystem_side_effects():
    spec = importlib.util.spec_from_file_location('_glint_gpu_recovery', MODULE / 'collect.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)
    assert not hasattr(module, 'args') and not hasattr(module, 'runtime')


@pytest.mark.parametrize('options,expected', [(['--help'], 0),
    (['--candidate', 'unregistered'], 2),
    (['-O', '--executable', 'D:/absent/chrome.exe', '--driver-stage', 'D:/absent/driver',
      '--work-dir', 'D:/absent/output', '--candidate', 'upstream-156'], 2)])
def test_gpu_recovery_cli_rejects_unsafe_execution_before_launch(options, expected):
    optimize = options[:1] == ['-O']
    command = [sys.executable, *(['-O'] if optimize else []), str(MODULE / 'collect.py'),
               *(options[1:] if optimize else options)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == expected
    if optimize:
        assert 'Run without Python optimization' in result.stderr


def test_gpu_recovery_ready_extension_replays_without_modifying_measured_baseline(tmp_path):
    record = json.loads((MODULE / 'ready-mode-observations.json').read_bytes())
    source = MODULE / record['base_source']
    original = source.read_bytes()
    assert hashlib.sha256(original).hexdigest() == record['before_sha256']
    patch = MODULE / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    target = tmp_path / 'collect.py'
    target.write_bytes(original)
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--check', str(patch)],
                   cwd=tmp_path, capture_output=True, check=True, timeout=20)
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)],
                   cwd=tmp_path, capture_output=True, check=True, timeout=20)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['after_sha256']
    ast.parse(target.read_text(encoding='utf-8-sig'))
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(patch)],
                   cwd=tmp_path, capture_output=True, check=True, timeout=20)
    assert target.read_bytes() == source.read_bytes() == original


def test_gpu_recovery_ready_control_keeps_old_policy_inconsistency_failed():
    record = json.loads((MODULE / 'ready-mode-observations.json').read_bytes())
    assert record['control_passed']
    assert record['runtime_core_sha256_measured'] == observation()['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == observation()['receipt_sha256']
    assert [row['mode'] for row in record['modes']] == ['baseline', 'ready']
    for row in record['modes']:
        assert row['measurement_complete'] and row['document_recovered']
        assert row['transport_feature_enabled'] is False
        assert row['passed'] == row['policy_coherence_passed'] == (row['mode'] == 'baseline')
        assert row['collector_returncode'] == (0 if row['passed'] else 1)
        assert row['before'] == row['after']
        assert not row['remaining_owned_processes']
        assert all(row[key] is True for key in ('runtime_assets_unchanged', 'input_postguards_passed',
            'driver_unchanged', 'receipt_unchanged', 'server_closed', 'runtime_resource_free', 'owned_profiles_removed'))
    ready = record['modes'][1]['after']
    assert ready['surface_noise_observed'] and ready['readback_consistent'] is False
    assert ready['rgba_sha256'] == ready['shader_sha256'] != ready['png_rgba_sha256']
    assert ready['deviation_from_reference']['png'] == {'changed_channels': 384, 'maximum_delta': 1}
    assert all(record[name] is False for name in ('latest_001_116_candidate_verified',
        'protected_policy_recovery_admitted', 'privacy_admitted', 'production_admitted'))


def test_gpu_recovery_ready_control_binds_its_staged_source_layout(historical_source_newlines,
                                                                native_build_before_index_mtime_fix,
                                                                host_sources_before_webgpu_r2, host_sources_before_profile_surface,
                                                                host_sources_before_monitor_gap_reset):
    record = json.loads((MODULE / 'ready-mode-observations.json').read_bytes())
    sources = historical_probe_inputs()
    sources.update({name: hashlib.sha256(value).hexdigest()
                    for name, value in host_sources_before_monitor_gap_reset.items()})
    sources.update({name: hashlib.sha256(value).hexdigest() for name, value in host_sources_before_webgpu_r2.items()})
    sources.update({name: value for name, value in host_sources_before_profile_surface['sha256'].items()
                    if name in sources})
    for name in host_sources_before_profile_surface['absent']:
        assert name in sources
        del sources[name]
    for path in [MODULE / 'watch.js', ROOT / 'native/drafts/environment/first-script/webgpu_shader_dataflow.js',
                 ROOT / 'native/drafts/environment/playwright-driver-stage-binding-close.json']:
        sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    sources[(MODULE / 'collect.py').relative_to(ROOT).as_posix()] = record['after_sha256']
    assert record['native_build_at_measurement_sha256'] == native_build_before_index_mtime_fix['before_sha256']
    sources[native_build_before_index_mtime_fix['source']] = native_build_before_index_mtime_fix['before_sha256']
    for name, row in historical_source_newlines.items():
        if name in sources:
            sources[name] = row['canonical_lf_sha256']
    assert len(sources) == record['complete_probe_input_count'] == 226
    encoded = json.dumps(sources, sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(encoded).hexdigest() == record['complete_probe_input_snapshot_sha256']
    assert hashlib.sha256((MODULE / 'watch.js').read_bytes()).hexdigest() == record['watch_sha256']
