"""Source-bound isolated native components, not browser/API protection admission."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'
SOURCES = ROOT / 'native/drafts/webgpu-readback-layout'


def record():
    return json.loads((DIRECTORY / 'webgpu-readback-provenance-preparation.json').read_bytes())


def test_complete_native_component_archive_has_exact_current_sources_and_round_trips(tmp_path, native_components_before_capture_lifecycle):
    evidence = record()
    patch = DIRECTORY / evidence['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == evidence['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert len(evidence['sources']) == 6
    for row in evidence['sources']:
        source, applied = ROOT / row['staged_source'], tmp_path / row['source']
        historical = native_components_before_capture_lifecycle['sources'].get(row['staged_source'], source.read_bytes())
        assert row['before_sha256'] is None and historical == applied.read_bytes()
        assert hashlib.sha256(applied.read_bytes()).hexdigest() == row['staged_sha256']
        assert not source.read_bytes().startswith(bytes.fromhex('efbbbf')) and b'\r' not in source.read_bytes()
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert all(not (tmp_path / row['source']).exists() for row in evidence['sources'])


def test_exact_public_native_checks_cover_layout_provenance_and_snapshot_with_asan(native_components_before_capture_lifecycle):
    evidence = record()
    for relative, expected in evidence['measured_inputs_sha256'].items():
        actual = native_components_before_capture_lifecycle['sha256'].get(relative,
            hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        assert actual == expected, relative
    rows = evidence['isolated_component_checks']
    assert len(rows) == 6 and {(row['name'], row['sanitizer']) for row in rows} == {
        (name, sanitizer) for name in ('layout', 'provenance', 'snapshot') for sanitizer in ('none', 'address')}
    expected = {
        'layout': dict(passed=True, property_iterations=1024, assertions=525936, browser_integrated=False),
        'provenance': dict(passed=True, named_cases=18, property_iterations=256, assertions=1232777, browser_integrated=False),
        'snapshot': dict(passed=True, named_cases=26, formats=2, property_iterations=64, assertions=748, browser_integrated=False),
    }
    for row in rows:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == expected[row['name']]
    assert evidence['isolated_provenance_verified'] and evidence['isolated_snapshot_transform_verified']
    assert evidence['isolated_address_sanitizer_verified']
    for key in ('selected', 'browser_integrated', 'native_queue_hooks_installed',
                'full_surface_capture_producer_verified', 'mapped_js_lifetime_verified',
                'runtime_verified', 'native_webgpu_readback_protection',
                'canvas_gpu_export_mismatch_resolved', 'privacy_admitted', 'production_admitted'):
        assert evidence[key] is False
    checkpoint = (ROOT / 'native/drafts/upstream-156/checkpoints/001-076.json').read_text(encoding='utf-8-sig')
    assert 'webgpu_readback_snapshot' not in checkpoint and 'webgpu_readback_provenance' not in checkpoint


def test_public_native_checker_rejects_invalid_paths_before_creating_output(tmp_path):
    output = tmp_path / 'must-not-exist'
    result = subprocess.run([sys.executable, str(SOURCES / 'check.py'),
        '--chromium-root', str(tmp_path / 'chromium'), '--sdk-root', str(tmp_path / 'sdk'),
        '--work-dir', str(output)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2 and 'canonical' in result.stderr
    assert not output.exists()
