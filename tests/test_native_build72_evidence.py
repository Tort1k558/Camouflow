import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native/drafts/upstream-156'


def test_built_72_binds_exact_checkpoint_and_preserved_runtime_without_admission():
    record = json.loads((NATIVE / 'build72-observations.json').read_bytes())
    raw = (NATIVE / record['required_manifest']).read_bytes()
    assert record['passed'] and record['completed_stages'] == ['sync', 'hooks', 'patch', 'build']
    assert hashlib.sha256(raw).hexdigest() == record['candidate_manifest_sha256']
    assert len(json.loads(raw)['patches']) == record['registered_patches'] == 72
    assert record['build_jobs'] == 4 and record['build_steps'] == 64 and record['build_duration_seconds'] == 913.62
    assert record['preserved_runtime_assets'] == 269 and len(set(record['changed_source_files'])) == 9
    assert record['runtime_core_sha256_measured']['chrome.dll'] == '3fa8284bf94254bf7775e9c5a8e42400d268919d3f635aa378ba4e4904e96915'
    assert all(record[name] is False for name in ('native_units_verified', 'protected_formats_verified',
                                                'privacy_admitted', 'production_admitted'))


def test_runtime_72_baseline_is_eighteen_real_checks_not_protected_policy_admission():
    record = json.loads((NATIVE / 'runtime-baseline72-observations.json').read_bytes())
    build = json.loads((NATIVE / 'build72-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['returncode'] == 0 and record['check_count'] == len(set(record['checks'])) == 18
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['receipt_sha256'] == build['build_receipt_sha256']
    assert {'authenticated-http-proxy-no-direct-dns-route', 'existing-recorder-capture-and-replay',
            'native-profile-backup-restore-storage-and-engine-isolation'}.issubset(record['checks'])
    assert all(record[name] is False for name in ('protected_policies_enabled', 'installed_package_verified',
        'cloud_server_team_isolation_verified', 'uncommitted_transactions_recovery_verified', 'privacy_admitted', 'production_admitted'))


def test_python_repeat_after_historical_binding_followup_has_no_failures():
    record = json.loads((ROOT / 'native/drafts/environment/canonical-python72-export-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['counts'] == {'tests': 4465, 'failures': 0, 'errors': 0, 'skipped': 1, 'passed': 4464}
    assert record['changed_tracked_files'] == []
    assert record['native_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False


def test_native_72_batch_retains_three_orientation_failures_and_twenty_passing_groups():
    record = json.loads((NATIVE / 'native-batch72-observations.json').read_bytes())
    build = json.loads((NATIVE / 'build72-observations.json').read_bytes())
    assert record['passed'] is False and record['postguards_passed']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['build_receipt_sha256'] == build['build_receipt_sha256']
    assert len(record['targets']) == 21
    assert sum(row.get('tests', 0) for row in record['targets'] if row['native_cases_passed']) == 484
    assert [row['target'] for row in record['targets'] if not row['native_cases_passed']] == ['screen-orientation']
    assert (record['tests'], record['tests_passed'], record['tests_failed']) == (488, 485, 3)
    assert len(record['orientation_cases']) == 4 and sum(row['passed'] for row in record['orientation_cases']) == 1
    assert record['correction_applied'] is record['correction_compiled'] is record['production_admitted'] is False


def test_full_python_ui_failure_is_not_rewritten_as_success_after_targeted_followup():
    record = json.loads((ROOT / 'native/drafts/environment/canonical-python72-ui-failures.json').read_bytes())
    assert record['passed'] is False and record['measurement_complete'] and record['postguards_passed']
    assert record['counts'] == {'tests': 4475, 'failures': 2, 'errors': 0, 'skipped': 1, 'passed': 4472}
    assert len(record['failed_tests']) == 2 and all('test_native_qml_configuration_and_profile_creation' in name for name in record['failed_tests'])
    assert record['targeted_followup']['tests_passed'] == 2 and record['targeted_followup']['source_and_deadlines_unchanged']
    assert record['fixed'] is record['production_admitted'] is False
