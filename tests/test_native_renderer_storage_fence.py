import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/renderer-storage-fence'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    added = '\n'.join(line[1:] for line in patch.read_text(encoding='utf-8-sig').splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_renderer_fence_packet_is_bound_without_selecting_a_new_runtime():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-image-r11')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['changed_files'] == len(record['sources']) == 5
    names = {row['source'] for row in record['sources']}
    prefix = 'third_party/blink/renderer/modules/storage/'
    assert names == {prefix + name for name in ('cached_storage_area.h', 'cached_storage_area.cc',
        'cached_storage_area_test.cc', 'testing/mock_storage_area.h', 'testing/mock_storage_area.cc')}
    assert not names & {row['path'] for row in candidate['manifest']['source_files']}
    assert len(candidate['manifest']['patches']) == 136
    assert not any(record[key] for key in ('selected', 'canonical_sources_modified',
        'compiled_browser', 'runtime_verified', 'profile_checkpoint_implemented',
        'privacy_admitted', 'production_admitted', 'native_cases_executed',
        'full_candidate_composition_verified', 'database_commit_implemented',
        'namespace_aggregation_implemented', 'network_producer_fence_implemented'))


def test_renderer_fence_uses_existing_replies_not_new_mojo_or_javascript_surfaces():
    record, _, added = packet()
    assert record['no_new_mojo_schema'] and record['no_javascript_surface']
    assert not any(row['source'].endswith(('.mojom', '.idl', '.js')) for row in record['sources'])
    assert 'mojo::WrapCallbackWithDefaultInvokeIfNotRun' in added
    assert 'MakeCheckpointMutationCallback(source)' in added
    assert added.count('base::BindOnce(MakeCheckpointMutationCallback(source), true)') == 2
    assert 'checkpoint_pending_.Contains(checkpoint_acknowledged_ + 1)' in added
    assert 'std::numeric_limits<uint64_t>::max() - 1' in added
    assert 'FlushAsyncForTesting' not in added and 'FlushForTesting' not in added


def test_renderer_fence_guards_serial_generation_owner_and_deadline_at_reply():
    record, _, added = packet()
    assert record['required_monotonic_deadline']
    assert record['mutations_during_fence_invalidate_reply']
    assert record['pending_fence_limit'] == 256
    assert 'base::TimeTicks deadline' in added
    assert 'checkpoint_waiters_.size() >= 256' in added
    assert 'deadline.is_max()' in added
    assert 'owner->checkpoint_generation_ == generation' in added
    assert 'owner->checkpoint_issued_ == serial' in added
    assert 'base::TimeTicks::Now() < deadline' in added
    assert 'base::OneShotTimer checkpoint_timeout_' in added
    assert 'checkpoint_timeout_.Stop();' in added and 'checkpoint_timeout_.Start(' in added
    assert 'checkpoint_write_failed_ |= !checkpoint_pending_.empty();' in added
    assert 'checkpoint_write_failed_ |= !success;' in added


def test_renderer_fence_cases_are_prepared_not_executed():
    record, _, added = packet()
    cases = re.findall(r'TEST_([FP])\((CachedStorageAreaTest(?:WithParam)?),\s*(Checkpoint\w+)\)', added)
    assert [{'kind': kind, 'fixture': fixture, 'name': name} for kind, fixture, name in cases] == record['native_case_bodies_prepared']
    assert len(cases) == len(set(cases)) == 15
    assert sum(kind == 'P' for kind, _, _ in cases) == 1
    names = {name for _, _, name in cases}
    assert {'CheckpointWaitsForAllOutOfOrderMutationReplies',
            'CheckpointNewMutationInvalidatesCapturedFence',
            'CheckpointUnansweredMutationExpires', 'CheckpointPendingFenceQueueIsBounded',
            'CheckpointDoesNotWaitForNeighbourArea', 'CheckpointRejectsUnboundAreaWithoutRebinding'} <= names
    correction = record['source_review_correction']
    assert len(correction['previous_preparation_sha256']) == 64
    assert len(correction['previous_syntax_report_sha256']) == 64
    assert not correction['runtime_failure_measured']
    assert not record['native_cases_executed']


def test_five_packet_replay_and_type_checks_do_not_claim_complete_candidate_admission():
    record, _, _ = packet()
    assert record['composed_files'] == 32 and record['forward_reverse_passed']
    assert len(record['composed_patch_chain']) == 4
    for row in record['composed_patch_chain']:
        assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['sha256']
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 3
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    assert record['input_postguards_passed'] and record['active_core_unchanged']
    assert not record['full_candidate_composition_verified']
    assert len(record['remaining']) == 6


def test_renderer_fence_patch_parses_without_writing_sources(tmp_path):
    record, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)], cwd=tmp_path,
                            capture_output=True, text=True, check=True, timeout=15)
    assert {line.split('\t', 2)[2] for line in result.stdout.splitlines()} == {
        row['source'] for row in record['sources']}
    assert not list(tmp_path.iterdir())
