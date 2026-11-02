import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/cookie-checkpoint'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    added = '\n'.join(line[1:] for line in patch.read_text(encoding='utf-8-sig').splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_cookie_packet_is_bound_to_pristine_inputs_not_selected_runtime():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-image-r11')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    names = {row['source'] for row in record['sources']}
    assert names == {'net/extras/sqlite/sqlite_persistent_cookie_store' + suffix
                     for suffix in ('.h', '.cc', '_unittest.cc')}
    assert record['changed_files'] == len(names) == 3
    assert record['disjoint_from_base_owned_source_inputs']
    assert not names & {row['path'] for row in candidate['manifest']['source_files']}
    assert all(row['before_sha256'] != row['after_sha256'] for row in record['sources'])
    assert len(candidate['manifest']['patches']) == 136
    assert not any(record[key] for key in ('selected', 'canonical_sources_modified',
        'compiled_browser', 'runtime_verified', 'profile_checkpoint_implemented',
        'privacy_admitted', 'production_admitted', 'native_cases_executed'))


def test_cookie_completion_does_not_infer_success_from_legacy_flush():
    _, patch, added = packet()
    assert 'base::SplitOnceCallback' in added
    assert 'base::ScopedClosureRunner abandoned' in added
    assert 'abandoned.Release().Reset()' in added
    assert 'base::BindPostTaskToCurrentDefault' in added
    assert 'checkpoint_write_failed_' in added
    assert 'checkpoint_closed_' in added
    assert 'std::memory_order_acquire' in added and 'std::memory_order_release' in added
    assert 'WeakPtrFactory' not in added
    assert 'base::MakeRefCounted<base::RefCountedData<std::atomic<bool>>>()' in added
    assert 'FlushForCheckpoint(base::OnceCallback<void(bool)> callback);' in added
    assert 'backend_->Flush(std::move(callback));' not in added
    assert 'checkpoint_write_failed_ = false;' in added
    assert added.count('checkpoint_write_failed_ = false;') == 1
    assert not re.search(r'\+\s*checkpoint_write_failed_ = true;\n\+\s*checkpoint_write_failed_ = true;',
                         patch.read_text(encoding='utf-8-sig'))


def test_native_cases_are_prepared_and_faults_explicitly_expected():
    record, _, added = packet()
    cases = re.findall(r'TEST_F\(SQLitePersistentCookieStoreTest,\s*(Checkpoint\w+)\)', added)
    assert cases == record['native_cases_prepared']
    assert len(cases) == len(set(cases)) == 9
    assert {'CheckpointLegacyWriteErrorRemainsSticky', 'CheckpointReportsNewWriteError',
            'CheckpointReportsEncryptionFailure', 'CheckpointReportsAbandonedBackgroundTask',
            'CheckpointOwnerLossNeverRepliesSuccess'} <= set(cases)
    assert added.count('errors.ExpectError(SQLITE_CONSTRAINT);') == 2
    assert added.count('errors.SawExpectedErrors()') == 2
    assert 'background->ClearPendingTasks();' in added
    assert 'base::test::TestFuture<bool>' in added
    assert not record['native_cases_executed']


def test_composition_binds_both_storage_prerequisites_without_claiming_full_replay():
    record, _, _ = packet()
    assert record['forward_reverse_passed'] and record['three_packet_forward_reverse_passed']
    assert record['three_packet_composed_files'] == 13
    assert len(record['prerequisite_patches']) == 2
    for row in record['prerequisite_patches']:
        path = ROOT / row['path']
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    assert len(record['remaining']) == 6


def test_type_checks_are_not_reported_as_native_execution():
    record, _, _ = packet()
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 2
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    assert record['input_postguards_passed'] and record['active_core_unchanged']
    failure = record['earlier_syntax_failure']
    assert failure['original_failure_preserved']
    assert failure['target_returncodes'] == [1, 0]
    assert len(failure['report_sha256']) == 64
    assert not record['compiled_browser'] and not record['runtime_verified']


def test_cookie_patch_parses_without_writing_sources(tmp_path):
    record, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)], cwd=tmp_path,
                            capture_output=True, text=True, check=True, timeout=15)
    assert {line.split('\t', 2)[2] for line in result.stdout.splitlines()} == {
        row['source'] for row in record['sources']}
    assert not list(tmp_path.iterdir())
