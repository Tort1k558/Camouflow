"""Native quota ownership source preparation and isolated hardware evidence."""
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/environment'


def preparation():
    return json.loads((DIRECTORY / 'webgpu-d3d12-budget-preparation.json').read_bytes())


def test_budget_upgrade_round_trips_exact_sources_and_preserves_capture_history(
        native_d3d12_sources_before_budget, tmp_path):
    record = preparation()
    upgrade = record['source_upgrade']
    assert upgrade['exact_roundtrip_verified'] and len(upgrade['sources']) == 3
    patch = DIRECTORY / upgrade['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == upgrade['patch_sha256']
    for row in upgrade['sources']:
        path = tmp_path / row['source']
        path.parent.mkdir(parents=True, exist_ok=True)
        before = native_d3d12_sources_before_budget[row['source']]
        assert hashlib.sha256(before).hexdigest() == row['before_sha256']
        path.write_bytes(before)
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    for row in upgrade['sources']:
        data = (tmp_path / row['source']).read_bytes()
        assert data == (ROOT / row['source']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['after_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', '--whitespace=error', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    assert all((tmp_path / row['source']).read_bytes() == native_d3d12_sources_before_budget[row['source']]
               for row in upgrade['sources'])


def test_budget_hardware_measurements_bind_the_current_public_implementation():
    record = preparation()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    for relative, expected in record['public_source_sha256'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    assert len(record['hardware_checks']) == 2
    assert record['public_hardware_checks'] == record['hardware_checks']
    assert {row['sanitizer'] for row in record['hardware_checks']} == {'none', 'address'}
    for row in record['hardware_checks']:
        assert row['compile_returncode'] == row['test_returncode'] == 0
        assert row['result'] == dict(passed=True, hardware_adapter=True, cases=8, assertions=22720,
                                    budget_cases=8, contention_threads_tested=8, browser_integrated=False)
    assert record['hardware_contention_threads'] == 8
    assert record['budget_counts_actual_allocation_bytes']
    assert record['cpu_cancellation_releases_inflight_quota'] is False


def test_budget_native_packet_uses_one_device_owner_and_existing_com_retirement_queue(tmp_path):
    record = preparation()
    patch = DIRECTORY / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['native_patch_roundtrip_verified'] and len(record['sources']) == 9
    assert record['replacement_for'] == 'webgpu-d3d12-capture-next.patch'
    assert record['apply_both_native_packets'] is False
    assert record['per_device_quota_bytes'] == 64 * 1024 * 1024
    assert record['native_device_budget_owner_prepared'] and record['native_com_retirement_queue_reused']
    assert record['dependency'] == dict(repository='https://dawn.googlesource.com/dawn',
                                      revision='0a2c7df818e285d6db0f085135139cda04cee8bb')
    text = patch.read_text(encoding='utf-8-sig')
    assert 'device->GetGlintReadbackBudget()' in text
    assert 'device->ReferenceUntilUnused(capture->retirement_handle());' in text
    assert 'mGlintReadbackBudget(std::make_shared<' in text
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--whitespace=error',
                    '--include=third_party/dawn/src/dawn/native/d3d12/glint/*', str(patch)],
                   cwd=tmp_path, check=True, capture_output=True, timeout=15)
    rows = [row for row in record['sources'] if '/glint/' in row['source']]
    assert len(rows) == 2 and all(row['before_sha256'] is None for row in rows)
    for row in rows:
        data = (tmp_path / row['source']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['staged_sha256']
        assert data == (ROOT / 'native/drafts/webgpu-d3d12-capture' / Path(row['source']).name).read_bytes()


def test_native_budget_syntax_is_not_dawn_queue_or_browser_execution():
    record = preparation()
    assert len(record['syntax_checks']) == 4
    assert all(row['returncode'] == 0 for row in record['syntax_checks'])
    for key in ('selected', 'browser_integrated', 'runtime_verified', 'native_capture_hook_installed',
                'dawn_submission_runtime_verified', 'dawn_device_loss_runtime_verified',
                'gpu_process_global_budget_verified', 'native_webgpu_readback_protection',
                'snapshot_store_integration_verified', 'canvas_gpu_export_mismatch_resolved',
                'allocation_failure_injection_verified',
                'privacy_admitted', 'production_admitted'):
        assert record[key] is False


def test_complete_export_seed_python_regression_predates_gpu_budgeting():
    record = json.loads((DIRECTORY / 'canonical-python76-export-seed-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['git_head'].startswith('2ee3d99')
    assert record['counts'] == dict(tests=5043, passed=5042, skipped=1, failures=0, errors=0)
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
