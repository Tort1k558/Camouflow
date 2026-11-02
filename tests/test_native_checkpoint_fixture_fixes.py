import hashlib
import json
from pathlib import Path
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/checkpoint-native-fixture-fixes'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    added = '\n'.join(line[1:] for line in patch.read_text(encoding='utf-8-sig').splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_checkpoint_fixture_corrections_are_not_retested_native_claims():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-checkpoint-r12')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['isolated_apply_reverse_passed'] and record['test_case_declarations_unchanged']
    assert record['original_failures_retained']
    for key in ('selected', 'registered', 'compiled', 'native_executed',
                'production_sources_changed', 'canonical_sources_modified',
                'production_admitted', 'runtime_verified', 'full_candidate_composition_verified'):
        assert record[key] is False


def test_checkpoint_fixture_patch_keeps_failures_and_strengthens_persistence_check():
    _, _, added = packet()
    assert 'CookieSameSite::LAX_MODE' in added
    assert 'CHECK (name != ' in added
    assert 'ALTER TABLE cookies DROP COLUMN checkpoint_guard' in added
    assert "SELECT value FROM cookies WHERE name='later'" in added
    assert 'EXPECT_EQ("value", query.ColumnString(0))' in added
    assert 'CompleteCheckpointMutationAt(0, true)' in added
    assert 'EXPECT_FALSE(result.Get())' in added
    assert 'DISABLED_' not in added and 'GTEST_SKIP' not in added
    assert 'CREATE TRIGGER' not in added


def test_checkpoint_fixture_host_sqlite_probe_is_explicitly_not_chromium():
    record, _, _ = packet()
    probe = record['host_sqlite_probe']
    assert probe['triggers_explicitly_disabled'] and probe['legacy_trigger_bypassed']
    assert probe['check_constraint_rejected_write'] and probe['valid_write_after_constraint_removal']
    assert probe['chromium_execution'] is False


def test_checkpoint_fixture_patch_changes_only_existing_test_files():
    record, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    paths = {line.split('\t', 2)[2] for line in result.stdout.splitlines()}
    assert paths == {row['source'] for row in record['sources']}
    assert len(paths) == 4
    assert all(p.endswith(('_unittest.cc', '_test.cc')) or '/testing/' in p for p in paths)
