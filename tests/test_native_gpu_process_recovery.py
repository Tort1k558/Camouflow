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


def test_gpu_recovery_control_binds_public_sources_and_exact_runtime():
    record = observation()
    for name, expected in record['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    earlier = json.loads((ROOT / 'native/drafts/environment/webgpu-diagnostic-variant76-control-observations.json').read_bytes())
    for name in ('runtime_core_sha256_measured', 'candidate_manifest_sha256', 'receipt_sha256'):
        assert record[name] == earlier[name]
    assert record['passed'] and record['candidate'] == 'upstream-156'
    for name in ('protected_policies_enabled', 'protected_policy_recovery_verified',
                 'complete_candidate_verified', 'physical_gpu_reset_tested', 'privacy_admitted', 'production_admitted'):
        assert record[name] is False


def test_gpu_recovery_complete_input_digest_preserves_measured_newlines(historical_source_newlines):
    from scripts.verify_native_gpu_readback import probe_inputs

    sources = probe_inputs(candidate_name='upstream-156')
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
