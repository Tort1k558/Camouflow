"""Bounded evidence for the hardware capture core, not browser admission."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'


def load_record():
    return json.loads((DIRECTORY / 'webgpu-d3d12-capture-preparation.json').read_bytes())


def test_capture_patch_and_public_sources_match_measured_bytes():
    record = load_record()
    assert hashlib.sha256((DIRECTORY / record['patch']).read_bytes()).hexdigest() == record['patch_sha256']
    assert len(record['sources']) == 7
    assert record['exact_patch_roundtrip_verified'] and record['postguards_passed']
    for relative, expected in record['public_source_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    rows = {row['source']: row for row in record['sources']}
    for filename in ('texture_capture.h', 'texture_capture.cc'):
        source = ROOT / 'native/drafts/webgpu-d3d12-capture' / filename
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest == record['measured_hardware_source_sha256'][filename]
        assert digest == rows['third_party/dawn/src/dawn/native/d3d12/glint/' + filename]['staged_sha256']


def test_hardware_checks_are_complete_and_do_not_admit_native_glue():
    record = load_record()
    assert record['hardware_adapter'] and record['software_adapter_fallback'] is False
    assert len(record['hardware_checks']) == 2
    assert {row['sanitizer'] for row in record['hardware_checks']} == {'none', 'address'}
    for row in record['hardware_checks']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == dict(passed=True, hardware_adapter=True, cases=8,
                                    assertions=22525, browser_integrated=False)
    assert record['public_hardware_checks'] == record['hardware_checks']
    for filename, expected in record['public_hardware_source_sha256'].items():
        assert hashlib.sha256((ROOT / 'native/drafts/webgpu-d3d12-capture' / filename).read_bytes()).hexdigest() == expected
    assert len(record['syntax_checks']) == 3
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    for key in ('selected', 'browser_integrated', 'native_capture_hook_installed',
                'runtime_verified', 'privacy_admitted', 'production_admitted',
                'device_gpu_budget_retirement_verified', 'dawn_submission_runtime_verified',
                'snapshot_store_integration_verified', 'canvas_gpu_export_mismatch_resolved',
                'native_webgpu_readback_protection'):
        assert record[key] is False


def test_renderer_python_baseline_predates_native_capture():
    record = json.loads((DIRECTORY / 'canonical-python76-renderer-policy-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('1300fa2')
    assert record['counts'] == dict(tests=4974, passed=4973, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
