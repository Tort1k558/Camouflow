"""Pending native capture model and separate real-browser API reference."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'


def test_capture_upgrade_reconstructs_old_sources_and_binds_current_ones(native_components_before_capture_lifecycle):
    record = json.loads((DIRECTORY / 'webgpu-capture-lifecycle-preparation.json').read_bytes())
    assert record['selected'] is record['browser_integrated'] is record['runtime_verified'] is False
    assert len(record['sources']) == 4
    for row in record['sources']:
        assert hashlib.sha256((ROOT / row['source']).read_bytes()).hexdigest() == row['staged_sha256']
        if row['before_sha256'] is not None:
            assert native_components_before_capture_lifecycle['sha256'][row['source']] == row['before_sha256']


def test_current_native_capture_archive_round_trips_exact_current_sources(tmp_path):
    record = json.loads((DIRECTORY / 'webgpu-capture-lifecycle-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert len(record['sources']) == 6
    for row in record['sources']:
        assert (tmp_path / row['source']).read_bytes() == (ROOT / row['staged_source']).read_bytes()
        assert hashlib.sha256((tmp_path / row['source']).read_bytes()).hexdigest() == row['staged_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert all(not (tmp_path / row['source']).exists() for row in record['sources'])


def test_public_isolated_capture_checks_bind_sources_and_arbitrary_completion_order():
    record = json.loads((DIRECTORY / 'webgpu-capture-lifecycle-observations.json').read_bytes())
    for relative, expected in record['measured_inputs_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    assert record['isolated_pending_capture_lifecycle_verified'] and record['isolated_address_sanitizer_verified']
    rows = record['isolated_component_checks']
    assert len(rows) == 8 and {(row['name'], row['sanitizer']) for row in rows} == {
        (name, sanitizer) for name in ('layout', 'provenance', 'snapshot', 'callback') for sanitizer in ('none', 'address')}
    assert all(row['compile_returncode'] == row['test_returncode'] == 0 and row['result']['passed'] for row in rows)
    for row in rows:
        if row['name'] == 'callback':
            assert row['result'] == dict(passed=True, named_cases=10, completion_orders=6,
                                        assertions=201, browser_integrated=False)
    for key in ('selected', 'browser_integrated', 'native_callback_integration_verified',
                'native_queue_hooks_installed', 'full_surface_capture_producer_verified',
                'mapped_js_lifetime_verified', 'runtime_verified', 'native_webgpu_readback_protection',
                'canvas_gpu_export_mismatch_resolved', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_real_076_api_reference_preserves_reverse_maps_abort_errors_and_detachment():
    record = json.loads((DIRECTORY / 'webgpu-map-lifecycle76-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert hashlib.sha256((ROOT / record['source']).read_bytes()).hexdigest() == record['source_sha256']
    assert len(record['rows']) == 2 and {row['mode'] for row in record['rows']} == {'baseline', 'ready'}
    for row in record['rows']:
        value = row['value']
        assert value['measured'] and value['compatibilityPassed']
        assert value['copyOrder'] == [1, 2] and value['readOrder'] == [2, 1]
        assert value['reads'] == [dict(source=source, referenceMatched=True, detached=True) for source in (2, 1)]
        assert value['cancellation'] == value['afterDestroy'] == 'AbortError'
        assert value['mapStateAfterDestroy'] == 'unmapped' and value['deviceLossReason'] == 'destroyed'
    assert 'OperationError' in record['prior_harness_negative']['reason']
    assert record['public_cli_integrated'] is record['native_callback_integration_verified'] is False
    assert record['privacy_admitted'] is record['production_admitted'] is False


def test_full_native_prototype_python_result_predates_pending_capture_upgrade():
    record = json.loads((DIRECTORY / 'canonical-python76-native-provenance-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('0731fc7')
    assert record['counts'] == dict(tests=4963, passed=4962, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
