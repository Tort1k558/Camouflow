import hashlib
import json
from pathlib import Path
import re
import subprocess

from scripts.native_build import load_candidate


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'native/drafts/storage-aggregate-fence'


def packet():
    record = json.loads((DIRECTORY / 'source-observations.json').read_bytes())
    patch = DIRECTORY / record['patch']
    added = '\n'.join(line[1:] for line in patch.read_text(encoding='utf-8-sig').splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    return record, patch, added


def test_aggregate_packet_does_not_select_or_modify_the_r11_runtime():
    record, patch, _ = packet()
    candidate = load_candidate('upstream-156-image-r11')
    assert record['base_manifest_sha256'] == candidate['manifest_sha256']
    assert record['target_revision'] == candidate['manifest']['target_revision']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == record['patch_sha256']
    assert record['changed_files'] == len(record['sources']) == 7
    names = {row['source'] for row in record['sources']}
    assert len(names) == 7 and not names & {row['path'] for row in candidate['manifest']['source_files']}
    assert len(candidate['manifest']['patches']) == 136
    assert record['namespace_aggregation_source_implemented']
    assert not any(record[key] for key in ('selected', 'canonical_sources_modified',
        'compiled_browser', 'runtime_verified', 'profile_checkpoint_implemented',
        'privacy_admitted', 'production_admitted', 'native_cases_executed',
        'full_candidate_composition_verified', 'browser_coordinator_implemented',
        'network_producer_fence_implemented'))


def test_aggregate_replay_binds_both_shared_area_sources():
    record, _, _ = packet()
    assert record['composed_files'] == len(record['composed_sources']) == 37
    assert record['forward_reverse_passed']
    assert len(record['composed_patch_chain']) == 5
    for row in record['composed_patch_chain']:
        assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['sha256']
    prerequisite = json.loads((ROOT / 'native/drafts/renderer-storage-fence/source-observations.json').read_bytes())
    for suffix in ('h', 'cc'):
        name = 'third_party/blink/renderer/modules/storage/cached_storage_area.' + suffix
        base = next(row for row in prerequisite['sources'] if row['source'] == name)
        changed = next(row for row in record['sources'] if row['source'] == name)
        composed = next(row for row in record['composed_sources'] if row['source'] == name)
        assert changed['before_sha256'] == base['after_sha256']
        assert composed['before_sha256'] == base['before_sha256']
        assert composed['after_sha256'] == changed['after_sha256']


def test_namespace_epoch_includes_mutations_topology_and_eviction_failure():
    record, _, added = packet()
    assert record['mutation_and_topology_epoch_checked_at_reply']
    assert record['pending_write_eviction_prevented'] and record['evicted_write_failure_retained']
    assert 'storage_namespace_->NotifyLocalStorageCheckpointChange();' in added
    assert 'owner->checkpoint_generation_ == generation' in added
    assert '!area.value->HasUnsettledCheckpointMutations()' in added
    assert 'checkpoint_failed_eviction_ |= area.value->HasCheckpointWriteFailure();' in added
    assert 'base::BarrierCallback<bool>' in added
    assert re.search(r'std::all_of\(\s*results.begin\(\),\s*results.end\(\),', added)
    assert 'WeakPersistent<StorageNamespace>' in added


def test_controller_checks_identity_deadline_and_empty_scope_without_new_api_surface():
    record, _, added = packet()
    assert record['explicit_empty_producer_scope']
    assert record['no_new_mojo_schema'] and record['no_javascript_surface']
    assert not any(row['source'].endswith(('.mojom', '.idl', '.js')) for row in record['sources'])
    assert record['namespace_and_controller_request_limits'] == 64
    assert added.count('checkpoint_requests_ < 64') == 2
    assert 'base::WeakPtr<StorageController>' in added
    assert 'owner->local_storage_namespace_.Get() == captured.Get()' in added
    assert 'captured->LocalStorageCheckpointGeneration() ==' in added
    assert 'deadline > base::TimeTicks::Now()' in added
    assert 'base::BindPostTaskToCurrentDefault' in added


def test_aggregate_native_bodies_are_prepared_not_reported_as_executed():
    record, _, added = packet()
    cases = re.findall(r'TEST_F\(LocalStorageCheckpointAggregationTest,\s*(Checkpoint\w+)\)', added)
    assert cases == record['native_case_bodies_prepared']
    assert len(cases) == len(set(cases)) == 17
    assert {'CheckpointEarlyAreaMutationRejectsAggregate', 'CheckpointNewAreaRejectsCapturedTopology',
            'CheckpointRemovalRejectsCapturedTopology', 'CheckpointEvictionPreservesUnacknowledgedWrites',
            'CheckpointFailedEvictionCannotEraseWriteFailure',
            'CheckpointControllerResetOverRealClientPipeFailsClosed',
            'CheckpointControllerOwnerLossRejectsLateReply'} <= set(cases)
    assert 'client_->ResetLocalStorageConnections();' in added
    assert not record['native_cases_executed']


def test_seven_type_checks_are_not_browser_or_profile_checkpoint_admission():
    record, _, _ = packet()
    assert record['type_checked_translation_units'] == len(record['syntax_targets']) == 7
    assert all(row['returncode'] == 0 for row in record['syntax_targets'])
    assert record['input_postguards_passed'] and record['active_core_unchanged']
    assert len(record['syntax_report_sha256']) == 64
    assert len(record['remaining']) == 5
    assert not record['compiled_browser'] and not record['profile_checkpoint_implemented']


def test_aggregate_patch_parses_as_seven_files_without_writing_sources(tmp_path):
    record, patch, _ = packet()
    result = subprocess.run(['git', 'apply', '--numstat', str(patch)], cwd=tmp_path,
                            capture_output=True, text=True, check=True, timeout=15)
    assert {line.split('\t', 2)[2] for line in result.stdout.splitlines()} == {
        row['source'] for row in record['sources']}
    assert not list(tmp_path.iterdir())
