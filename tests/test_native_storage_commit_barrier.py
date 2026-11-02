import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


DIRECTORY = Path(__file__).resolve().parents[1] / 'native/drafts/storage-commit-barrier'


def test_commit_packet_binds_pristine_inputs_without_modifying_the_r11_recipe():
    candidate = load_candidate('upstream-156-image-r11')
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert record['changed_files'] == len(record['sources']) == 3
    names = {row['source'] for row in record['sources']}
    assert not names & {row['path'] for row in candidate['manifest']['source_files']}
    assert record['disjoint_from_base_owned_source_inputs'] and record['forward_reverse_passed']
    assert names == {'components/services/storage/dom_storage/' + name for name in (
        'async_dom_storage_database.h', 'async_dom_storage_database.cc', 'async_dom_storage_database_unittest.cc')}
    assert all(row['before_sha256'] != row['after_sha256'] for row in record['sources'])
    assert len(candidate['manifest']['patches']) == 136
    assert not any(record[key] for key in ('selected', 'canonical_sources_modified', 'compiled_browser',
        'runtime_verified', 'profile_checkpoint_implemented', 'privacy_admitted', 'production_admitted',
        'native_cases_executed'))


def test_native_cases_are_exactly_prepared_not_reported_as_executed():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = (DIRECTORY / record['patch']).read_text(encoding='utf-8-sig')
    added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
    cases = re.findall(r'TEST_P\(AsyncDomStorageDatabaseTest,\s*(CommitPendingMaps\w+)\)', added)
    assert cases == record['native_cases_prepared'] and len(cases) == len(set(cases)) == 9
    assert {'CommitPendingMapsCompletesLoadedMapsBeforeAck', 'CommitPendingMapsOwnerLossNeverAcknowledgesSuccess',
            'CommitPendingMapsCommitterCanDestroyOwner', 'CommitPendingMapsPriorLegacyErrorRemainsSticky',
            'CommitPendingMapsNewCommitErrorIsReported', 'CommitPendingMapsDoesNotCommitNeighbourDatabase',
            'CommitPendingMapsRejectsMemoryOnlyDatabase', 'CommitPendingMapsRejectsUnopenedDatabase'} <= set(cases)
    assert 'checkpoint_commit_error_' in added
    assert 'base::SplitOnceCallback' in added and 'base::BindPostTaskToCurrentDefault' in added
    assert 'abandoned.Release().Reset()' in added and 'base::ScopedClosureRunner abandoned' in added
    assert 'InitiateCommitImpl(StatusCallback());' in added
    assert re.search(r'SetUpdateMapsStatus\(\s*DbStatus::OK\(\)\)', added)
    assert 'MakeAllCommitsFailForTesting' not in added


def test_type_checks_preserve_the_failed_attempt_and_do_not_admit_runtime():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 2
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    assert record['input_postguards_passed'] and record['active_core_unchanged']
    earlier = record['earlier_syntax_failure']
    assert earlier['original_failure_preserved'] and earlier['target_returncodes'] == [1, 0]
    assert len(record['remaining']) == 7 and not record['profile_checkpoint_implemented']


def test_patch_parses_as_three_text_sources_without_creating_files(tmp_path):
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    result = subprocess.run(['git', 'apply', '--numstat', str(DIRECTORY / record['patch'])], cwd=tmp_path,
                            capture_output=True, text=True, check=True, timeout=15)
    assert {line.split('\t', 2)[2] for line in result.stdout.splitlines()} == {row['source'] for row in record['sources']}
    assert not list(tmp_path.iterdir())
