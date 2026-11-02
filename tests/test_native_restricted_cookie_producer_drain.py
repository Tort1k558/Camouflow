import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/restricted-cookie-producer-drain'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    text = patch.read_text(encoding='utf-8-sig')
    added = '\n'.join(line[1:] for line in text.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_cookie_drain_is_internal_unselected_source_not_checkpoint_admission():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-checkpoint-r12')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert record['patch_sha256'] == hashlib.sha256(patch.read_bytes()).hexdigest()
    for key in ('selected', 'registered', 'type_checked', 'compiled', 'native_executed',
                'mojo_exposed', 'renderer_integrated', 'whole_profile_checkpoint',
                'canonical_sources_modified', 'production_admitted', 'runtime_verified',
                'full_candidate_composition_verified'):
        assert record[key] is False


def test_cookie_drain_composition_matches_both_other_unselected_packets():
    record, _, _ = packet()
    assert record['isolated_three_packet_composition_passed']
    assert record['composed_final_files'] == 11
    assert record['composed_original_files_restored'] == 8
    assert record['composed_new_files_removed_on_reverse'] == 3
    assert len(record['composed_packets']) == 3
    for row, directory in zip(record['composed_packets'], (
            'profile-producer-cohort', 'local-storage-checkpoint-owner',
            'restricted-cookie-producer-drain')):
        artifact = ROOT / 'native/drafts' / directory / row['patch']
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == row['sha256']


def test_cookie_drain_declares_bounded_tracking_without_changing_ordinary_results():
    _, _, added = packet()
    assert 'pending_checkpoint_cookie_writes_.size() >= 4096' in added
    assert 'cookie_write_drains_.size() >= 64' in added
    assert 'base::Seconds(30)' in added
    assert 'std::numeric_limits<uint64_t>::max()' in added
    assert 'owner->checkpoint_cookie_write_serial_ == epoch' in added
    assert 'owner->pending_checkpoint_cookie_writes_.empty()' in added
    assert 'owner->CompleteCheckpointCookieWrite(serial)' in added
    assert 'std::move(callback).Run(accepted)' in added
    assert 'const uint64_t checkpoint_serial = BeginCheckpointCookieWrite();' in added
    assert 'checkpoint_cookie_tracking_broken_ = true' in added
    assert 'FlushStoreForCheckpoint' not in added


def test_cookie_drain_prepared_cases_are_not_native_results():
    record, patch, added = packet()
    cases = re.findall(r'TEST_P\(RestrictedCookieManagerCheckpointDrainTest,\s*(CheckpointDrain\w+)',
                       added)
    assert cases == record['fixture_case_bodies']
    assert len(cases) == len(set(cases)) == record['fixture_bodies_prepared'] == 12
    assert {'CheckpointDrainWaitsForAllOutOfOrderWrites',
            'CheckpointDrainQueuedSuccessChecksEpoch',
            'CheckpointDrainQueuedSuccessChecksOwner',
            'CheckpointDrainTracksActualStringDispatch',
            'CheckpointDrainBrokenTrackerPreservesWrites'} <= set(cases)
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    paths = {line.split('\t', 2)[2] for line in result.stdout.splitlines()}
    assert paths == {row['source'] for row in record['sources']}
    assert len(paths) == 3
    assert all(p.startswith('services/network/restricted_cookie_manager') for p in paths)
