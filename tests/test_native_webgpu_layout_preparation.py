"""Unselected native byte-layout foundation, not browser protection admission."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'


def test_native_layout_patch_round_trips_exact_compiled_sources(tmp_path):
    record = json.loads((DIRECTORY / 'webgpu-readback-layout-preparation.json').read_bytes())
    patch = DIRECTORY / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    upgrade = json.loads((DIRECTORY / 'webgpu-readback-provenance-preparation.json').read_bytes())
    for row in record['sources']:
        source, applied = ROOT / row['staged_source'], tmp_path / row['source']
        assert row['before_sha256'] is None
        assert hashlib.sha256(applied.read_bytes()).hexdigest() == row['staged_sha256']
        current = next(value for value in upgrade['sources'] if value['source'] == row['source'])
        assert current['previous_staged_sha256'] == row['staged_sha256']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == current['staged_sha256']
        assert not source.read_bytes().startswith(bytes.fromhex('efbbbf')) and b'\r' not in source.read_bytes()
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert all(not (tmp_path / row['source']).exists() for row in record['sources'])


def test_isolated_native_and_asan_evidence_is_not_runtime_or_privacy_admission():
    record = json.loads((DIRECTORY / 'webgpu-readback-layout-preparation.json').read_bytes())
    assert record['isolated_native_compile_verified'] and record['isolated_address_sanitizer_verified']
    assert record['isolated_native_tests'] == record['address_sanitizer_result'] == dict(
        passed=True, property_iterations=1024, assertions=525936, browser_integrated=False)
    source = ROOT / record['standalone_harness']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == record['standalone_harness_sha256']
    for key in ('selected', 'browser_integrated', 'runtime_verified', 'native_webgpu_readback_protection',
                'canvas_gpu_export_mismatch_resolved', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    checkpoint = (ROOT / 'native/drafts/upstream-156/checkpoints/001-076.json').read_text(encoding='utf-8-sig')
    assert 'webgpu_readback_layout' not in checkpoint


def test_full_retained_webgpu_python_result_is_bound_to_its_measured_revision():
    record = json.loads((DIRECTORY / 'canonical-python76-webgpu-lifecycle-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('8e46cb2')
    assert record['counts'] == dict(tests=4957, passed=4956, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
