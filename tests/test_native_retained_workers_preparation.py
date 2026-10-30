import ast
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'native/drafts/environment'


def test_worker_prototype_is_scoped_and_does_not_admit_the_unselected_package():
    record = json.loads((ENV / 'retained-workers75-preparation-observations.json').read_bytes())
    assert record['selected'] is record['runtime_verified'] is record['public_package_runtime_verified'] is False
    assert record['prototype_browser_passed'] and record['prototype_postguards_passed']
    assert {row['mode'] for row in record['prototype_runs']} == {'manager-desktop', 'manager-mobile-web'}
    expected = {kind + '-' + script_type for kind in ('dedicated', 'shared', 'service')
                for script_type in ('classic', 'module')}
    for row in record['prototype_runs']:
        assert row['passed'] and row['history_navigation_type'] == 'BackForwardCacheRestore'
        assert row['owned_worker_cleanup_verified'] and row['runtime_resources_released']
        validation = row['validation']
        assert validation['passed'] and validation['worker_classes'] == 6
        assert {worker['kind'] for worker in validation['workers']} == expected
        assert all(worker['canvas_cases'] == 16 and worker['webgl_apis'] == 2
                   and worker['audio_api_available'] is False and worker['audio_readback_verified'] is False
                   for worker in validation['workers'])
    assert record['stricter_record_replay']['passed'] and record['stricter_record_replay']['cases'] == 16
    assert all(record[key] is False for key in ('service_worker_controlled_document_verified',
        'service_worker_forced_restart_verified', 'retained_gpu_objects_verified',
        'webgpu_readback_verified', 'privacy_admitted', 'production_admitted'))


def test_unselected_worker_package_applies_to_exact_base_and_binds_strict_helper(tmp_path, worker_sources_before_integration):
    record = json.loads((ENV / 'retained-workers75-preparation-observations.json').read_bytes())
    patch = ENV / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    for row in record['sources']:
        if row['before_sha256'] is not None:
            source = worker_sources_before_integration['sources'][row['source']]
            assert hashlib.sha256(source.encode('utf-8')).hexdigest() == row['before_sha256']
            target = tmp_path / row['source']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding='utf-8', newline='\n')
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=30)
    for row in record['sources']:
        target = tmp_path / row['source']
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row['staged_sha256']
        ast.parse(target.read_text(encoding='utf-8-sig'))
    helper = tmp_path / 'native/drafts/environment/first-script/retained_worker_lifecycle.py'
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == record['stricter_record_replay']['staged_helper_sha256']


def test_full_failure_is_retained_separately_from_targeted_historical_binding_repair():
    record = json.loads((ENV / 'canonical-python75-retained-binding-failure-observations.json').read_bytes())
    assert record['full_run_measurement_complete'] and record['full_run_postguards_passed']
    assert record['counts'] == dict(tests=4765, failures=28, errors=0, skipped=1, passed=4736)
    assert len(record['failed_tests']) == 28
    assert record['targeted_followup']['passed']
    assert record['targeted_followup']['counts'] == dict(tests=291, failures=0, errors=0, skipped=0)
    assert record['full_run_passed'] is record['full_followup_passed'] is False
    assert hashlib.sha256((ENV / record['reconstruction_patch']).read_bytes()).hexdigest() == record['reconstruction_patch_sha256']
