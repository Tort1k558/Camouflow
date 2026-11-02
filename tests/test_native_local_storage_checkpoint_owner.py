import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/local-storage-checkpoint-owner'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    text = patch.read_text(encoding='utf-8-sig')
    return record, patch, text


def added(text):
    return '\n'.join(line[1:] for line in text.splitlines()
                     if line.startswith('+') and not line.startswith('+++'))


def test_checkpoint_owner_artifact_is_not_native_execution_or_admission():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-checkpoint-r12')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['observed_patch_sha256'] == record['patch_sha256']
    for key in ('selected', 'registered', 'type_checked', 'compiled',
                'native_executed', 'fixtures_executed', 'whole_profile_checkpoint',
                'runtime_verified', 'production_admitted', 'canonical_sources_modified',
                'full_candidate_composition_verified'):
        assert record[key] is False
    assert record['isolated_apply_reverse_passed']
    assert record['formatted_with_pinned_clang_format']


def test_checkpoint_owner_scope_and_lifecycle_are_explicit_in_source():
    _, _, text = packet()
    production = '\n'.join(block for block in text.split('diff --git ')[1:]
                           if not block.split('\n', 1)[0].endswith('_unittest.cc'))
    source = added(production)
    assert 'FlushLocalStorageForCheckpoint(' in source
    assert 'local_storage_control_.QueryVersion(' in source
    assert 'local_storage_control_->FlushForCheckpoint(' in source
    assert 'version < 1' in source
    assert 'local_storage_checkpoints_.size() >= 64' in source
    assert 'base::Seconds(30)' in source
    assert 'checkpoint_weak_factory_.InvalidateWeakPtrsAndDoom()' in source
    assert 'checkpoint_weak_factory_.InvalidateWeakPtrs()' in source
    assert 'owner && !owner->checkpoint_shutdown_' in source
    assert 'std::numeric_limits<uint64_t>::max()' in source
    assert 'GetStorageService(' not in source
    assert 'GetDefaultStoragePartition(' not in source
    assert 'local_storage_control_->Flush();' not in source


def test_checkpoint_owner_prepared_fixtures_are_not_executed_results():
    record, _, text = packet()
    cases = re.findall(r'TEST_F\(DOMStorageContextWrapperTest,\s*(Checkpoint\w+)',
                       added(text))
    assert len(cases) == len(set(cases)) == record['native_fixture_bodies_prepared'] == 7
    assert {'CheckpointMissingConnectionRejectsPosted',
            'CheckpointVersionedBackendSuccess', 'CheckpointBackendFailurePropagates',
            'CheckpointTimeoutIgnoresLateSuccess',
            'CheckpointDisconnectRejectsHungRequest',
            'CheckpointShutdownRejectsAndIsIdempotent',
            'CheckpointTimedOutWireSlotsRemainBounded'} == set(cases)
    assert record['fixtures_executed'] is False


def test_checkpoint_owner_patch_has_exact_three_file_scope():
    record, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    sources = {line.split('\t', 2)[2] for line in result.stdout.splitlines()}
    assert sources == {row['source'] for row in record['sources']}
    assert record['files'] == len(sources) == 3
    assert all(path.startswith('content/browser/dom_storage/') for path in sources)
