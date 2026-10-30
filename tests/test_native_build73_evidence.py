import hashlib
import json
from pathlib import Path

from scripts import verify_native_privacy_units as units


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / 'native/drafts/upstream-156'


def test_completed_73_build_binds_checkpoint_and_retains_incremental_objects():
    record = json.loads((CANDIDATE / 'build73-observations.json').read_bytes())
    checkpoint = (CANDIDATE / record['required_manifest']).read_bytes()
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert hashlib.sha256(checkpoint).hexdigest() == record['candidate_manifest_sha256']
    assert len(json.loads(checkpoint)['patches']) == record['registered_patches'] == 73
    assert record['completed_stages'] == ['sync', 'hooks', 'patch', 'build']
    assert record['resumed_only_build'] and not record['sync_repeated_on_resume'] and not record['objects_cleaned']
    assert record['build_jobs'] == 4 and record['build_steps'] == 51
    assert record['resume_controller_duration_seconds'] >= record['ninja_build_duration_seconds'] > 0
    assert record['preserved_runtime_assets'] == 269 and record['unchanged_source_mtimes_restored'] == 287
    assert set(record['changed_source_files']) == {
        'third_party/blink/renderer/core/frame/web_frame_widget_impl.cc',
        'third_party/blink/renderer/modules/screen_orientation/screen_orientation_controller_test.cc'}
    assert record['browser_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False


def test_new_code_is_bound_to_the_dll_not_just_the_unchanged_launcher():
    before = json.loads((CANDIDATE / 'build72-observations.json').read_bytes())
    after = json.loads((CANDIDATE / 'build73-observations.json').read_bytes())
    assert before['runtime_core_sha256_measured']['chrome.exe'] == after['runtime_core_sha256_measured']['chrome.exe']
    assert before['runtime_core_sha256_measured']['chrome.dll'] != after['runtime_core_sha256_measured']['chrome.dll']
    assert after['runtime_core_sha256_measured']['chrome.dll'] == 'af79d5053ac9d54f37682af19b2d3e7c32d854dfb2511f5b0606fecdab596ded'


def test_all_21_native_groups_pass_including_the_four_retained_orientation_cases():
    record = json.loads((CANDIDATE / 'native-batch73-observations.json').read_bytes())
    build = json.loads((CANDIDATE / 'build73-observations.json').read_bytes())
    failed = json.loads((CANDIDATE / 'native-batch72-observations.json').read_bytes())
    assert record['passed'] and record['measurement_complete'] and record['postguards_passed']
    assert record['candidate_manifest_sha256'] == build['candidate_manifest_sha256']
    assert record['runtime_core_sha256_measured'] == build['runtime_core_sha256_measured']
    assert record['build_receipt_sha256'] == build['build_receipt_sha256']
    assert record['required_manifest'] == 'checkpoints/001-073.json' and record['compiled_patch_count'] == 73
    assert len(record['targets']) == len(units.SUPPORTED_TARGETS) == 21
    assert {row['target'] for row in record['targets']} == set(units.SUPPORTED_TARGETS)
    assert all(row['native_cases_passed'] and row['returncode'] == 0 for row in record['targets'])
    assert sum(row['tests'] for row in record['targets']) == record['tests_passed'] == 488
    assert next(row for row in record['targets'] if row['target'] == 'screen-orientation')['tests'] == 4
    assert failed['passed'] is False and failed['tests_failed'] == 3
    assert record['browser_runtime_verified'] is record['privacy_admitted'] is record['production_admitted'] is False
