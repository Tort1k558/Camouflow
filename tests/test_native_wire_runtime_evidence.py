import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / 'native/drafts/webgpu-capture-retention'


def observation():
    return json.loads((PACKET / 'wire-runtime-observations-20261101.json').read_bytes())


def test_wire_runtime_keeps_failed_matrix_and_standalone_scope():
    record = observation()
    assert record['original_matrix_passed'] is False
    for key in ('browser_integrated', 'quota_recovery_verified', 'privacy_admitted', 'production_admitted'):
        assert record[key] is False
    variants = {row['name']: row for row in record['variants']}
    assert set(variants) == {'uniform-routing', 'wire-device-lifetime', 'wire-byte-budget'}
    for name, count in (('uniform-routing', 51), ('wire-device-lifetime', 21), ('wire-byte-budget', 24)):
        variant = variants[name]
        assert len(variant['cases']) == count
        assert variant['persisted_report_passed'] is False
        assert variant['passed'] == (name != 'wire-byte-budget')
        failed = [row for row in variant['cases'] if not row['passed']]
        assert len(failed) == (3 if name == 'wire-byte-budget' else 0)
        assert all(row['mode'] == '--byte-budget' and row['returncode'] == 1 for row in failed)


def test_byte_budget_diagnostic_replays_and_reverses_exact_source(tmp_path):
    record = observation()['byte_budget_diagnostic']
    target = tmp_path / 'wire_probe.cc'
    target.write_bytes((PACKET / 'wire_probe.cc').read_bytes())
    original_patch = PACKET / 'wire-byte-budget.patch'
    diagnostic_patch = PACKET / record['patch']
    assert hashlib.sha256(diagnostic_patch.read_bytes()).hexdigest() == record['patch_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(original_patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['base_source_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(diagnostic_patch)], cwd=tmp_path, check=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['source_sha256']
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--reverse', str(diagnostic_patch)],
                   cwd=tmp_path, check=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == record['base_source_sha256']


def test_byte_budget_diagnostic_observes_loss_not_successful_recovery():
    diagnostic = observation()['byte_budget_diagnostic']
    assert diagnostic['passed'] and diagnostic['inputs_postguard_passed']
    assert diagnostic['compatibility_fixed'] is False
    assert diagnostic['quota_recovery_verified'] is False
    assert len(diagnostic['runs']) == 3
    for row in diagnostic['runs']:
        assert row['passed'] and row['returncode'] == 0
        value = row['observation']
        assert value['actual_wire_client_server_executed'] and value['hardware_adapter_selected']
        assert value['capture_budget_limit_bytes'] == 64 * 1024 * 1024
        assert value['capture_bytes_before_fault'] == 3 * value['per_capture_charge_bytes']
        assert value['capture_bytes_before_fault'] <= value['capture_budget_limit_bytes']
        assert value['capture_budget_limit_bytes'] - value['capture_bytes_before_fault'] < value['per_capture_charge_bytes']
        assert value['device_lost_under_capture_budget_pressure'] and value['owned_capture_out_of_memory_observed']
        assert value['map_status'] == 'aborted' and value['map_state'] == 'unmapped'
        assert value['map_callback_count'] == value['device_lost_callback_count'] == 1
        assert value['capture_bytes_after_destroy'] == 0
        assert value['browser_integrated'] is False
        assert value['physical_memory_exhaustion_attempted'] is False
        assert value['hardware_tdr_tested'] is False
